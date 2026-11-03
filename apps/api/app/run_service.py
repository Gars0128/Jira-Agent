import hashlib
import json
import logging
from collections.abc import Sequence
from contextlib import contextmanager
from pathlib import Path
from threading import Event, Thread
from time import perf_counter

from fastapi.encoders import jsonable_encoder
from langgraph.types import Command
from langsmith import Client, agent_address, trace, tracing_context
from psycopg.types.json import Jsonb

from app.checkpoints import postgres_saver
from app.config import Settings
from app.jira.client import JiraError, jira_session, preview_tickets
from app.jira.ledger import create_once
from app.llm import LLMError, LLMHelper, Usage
from app.projects import demo_root, projects
from app.rag.ingest import connect
from app.rag.retrieve import RetrievedChunk, retrieve
from app.run_store import RunBusyError, RunStore
from app.schemas import Requirement
from app.stories import Story, validate_stories
from app.workflow import Approval, build_workflow

logger = logging.getLogger(__name__)

RESULT_FIELDS = {
    "requirements": [],
    "stories": [],
    "questions": [],
    "retrieved": {},
    "tickets": [],
    "critic_feedback": [],
}


def hydrate_cache(cached: dict) -> dict:
    state = cached | {"revision_count": 1, "approved": False, "tickets": []}
    state["requirements"] = [
        Requirement.model_validate(item) for item in state["requirements"]
    ]
    state["stories"] = [Story.model_validate(item) for item in state["stories"]]
    state["retrieved"] = {
        key: [RetrievedChunk.model_validate(item) for item in chunks]
        for key, chunks in state.get("retrieved", {}).items()
    }
    return state


def checkpoint_result(values: dict) -> dict:
    state = jsonable_encoder(values)
    return {key: state.get(key, default) for key, default in RESULT_FIELDS.items()}


def preset_key(settings: Settings, project_id: str, transcript: str) -> str | None:
    presets = projects()[0]["transcripts"]
    if project_id != projects()[0]["id"] or not any(
        item["text"] == transcript for item in presets
    ):
        return None
    root = demo_root() / project_id
    code = Path(__file__).parent
    material = [
        project_id,
        transcript,
        settings.llm_model,
        settings.embedding_model,
        (root / "spec.md").read_text(encoding="utf-8"),
    ]
    for path in [code / "stories.py", code / "workflow.py", code / "graph/graph.py"]:
        material.append(path.read_text(encoding="utf-8"))
    return hashlib.sha256(json.dumps(material).encode()).hexdigest()


class RunService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = RunStore(settings)
        self.stop = Event()
        self.thread: Thread | None = None

    def start(self) -> None:
        self.store.setup()
        with postgres_saver(self.settings) as saver:
            saver.setup()
        self.thread = Thread(target=self._worker, daemon=True, name="agent-worker")
        self.thread.start()

    def close(self) -> None:
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=5)

    def _worker(self) -> None:
        while not self.stop.is_set():
            try:
                with connect(self.settings) as conn:
                    rows = conn.execute(
                        "SELECT id FROM agent_runs WHERE status IN ('queued','running')"
                        " ORDER BY created_at LIMIT 8"
                    ).fetchall()
                for (run_id,) in rows:
                    if self.stop.is_set():
                        break
                    try:
                        self.execute(str(run_id))
                    except RunBusyError:
                        continue
            except Exception:
                # DB/SDK exceptions can contain credentials or transcript text.
                logger.warning("Run worker unavailable; will retry database polling")
            self.stop.wait(1)

    def _tickets(self, stories: list, requirements: Sequence = ()) -> list[dict]:
        settings = self.settings
        if not settings.jira_live:
            return preview_tickets(stories, requirements)
        with jira_session(settings) as jira, connect(settings) as conn:
            return create_once(
                conn, jira, settings.jira_base_url, stories, requirements
            )

    @contextmanager
    def graph(self, project_id: str, helper: LLMHelper):
        with (
            connect(self.settings) as conn,
            postgres_saver(self.settings) as saver,
        ):
            has_spec = any(
                item["id"] == project_id and item["spec"] for item in projects()
            )
            yield build_workflow(
                helper,
                (lambda queries: retrieve(conn, helper, project_id, queries))
                if has_spec
                # No specification: classify with no excerpts, so only new/unclear.
                else lambda queries: [[] for _ in queries],
                checkpointer=saver,
                create_tickets=self._tickets,
            )

    def execute(self, run_id: str, approval: Approval | None = None) -> dict | None:
        with self.store.locked(run_id) as lock:
            if lock is None:
                raise RunBusyError("Run is already being processed")
            row = lock.execute(
                "SELECT project_id,transcript,status,cache_key,result"
                " FROM agent_runs WHERE id=%s",
                [run_id],
            ).fetchone()
            if row is None:
                return None
            project_id, transcript, status, cache_key, result = row
            if approval is None and status not in {"queued", "running"}:
                return result
            if approval is not None and status not in {"awaiting_review", "done"}:
                raise ValueError("Run is not awaiting approval")
            if approval is not None:
                validated = validate_stories(
                    approval.stories,
                    [
                        Requirement.model_validate(item)
                        for item in result["requirements"]
                    ],
                )
                if status == "done":
                    if jsonable_encoder(validated) != result["stories"]:
                        raise ValueError(
                            "Run was already approved with different stories"
                        )
                    return result
            helper = LLMHelper(self.settings)
            helper.usage = Usage.model_validate(result["usage"])
            config = {"configurable": {"thread_id": run_id}}
            started = perf_counter()
            with self.graph(project_id, helper) as graph:
                if status == "running":
                    return self._recover(run_id, result, graph, config)
                if approval is not None:
                    graph_input = Command(resume=approval.model_dump())
                else:
                    cached = (
                        lock.execute(
                            "SELECT state FROM agent_preset_cache WHERE key=%s",
                            [cache_key],
                        ).fetchone()
                        if cache_key
                        else None
                    )
                    if cached:
                        graph.update_state(
                            config, hydrate_cache(cached[0]), as_node="critic"
                        )
                        graph_input = None
                    else:
                        graph_input = {"transcript": transcript}
                result.update(status="running", error=None)
                self.store.save(run_id, result)
                try:
                    self._stream(graph, graph_input, config, run_id, helper, result)
                    snapshot = graph.get_state(config)
                    state = jsonable_encoder(snapshot.values)
                    review = bool(snapshot.next)
                    result.update(checkpoint_result(state))
                    result["status"] = "awaiting_review" if review else "done"
                    if review and cache_key and not result["cached"]:
                        lock.execute(
                            "INSERT INTO agent_preset_cache VALUES(%s,%s)"
                            " ON CONFLICT(key) DO UPDATE SET state=excluded.state",
                            [cache_key, Jsonb(state)],
                        )
                except Exception as exc:
                    result["status"] = "error"
                    result["error"] = (
                        str(exc)
                        if isinstance(exc, (LLMError, JiraError))
                        else "Run failed; check configuration and service availability"
                    )
                result["usage"] = helper.usage.model_dump(mode="json")
                result["latency_ms"] += round((perf_counter() - started) * 1000)
                self.store.save(run_id, result, settle=True)
                kind = (
                    result["status"]
                    if result["status"] != "awaiting_review"
                    else "awaiting_review"
                )
                self.store.event(run_id, kind, error=result["error"])
                return result

    def _recover(self, run_id: str, result: dict, graph, config: dict) -> dict:
        snapshot = graph.get_state(config)
        if snapshot.next == ("human_review",):
            # This node only interrupts; no paid work or external writes can replay.
            graph.invoke(None, config)
            snapshot = graph.get_state(config)
            result.update(checkpoint_result(snapshot.values))
            result.update(status="awaiting_review", error=None)
        elif (
            not snapshot.next
            and snapshot.values.get("approved") is True
            and "tickets" in snapshot.values
        ):
            result.update(checkpoint_result(snapshot.values))
            result.update(status="done", error=None)
        else:
            # A provider call or Jira write may have completed without a checkpoint.
            result.update(
                status="error",
                error="Server stopped during processing; start a new run",
            )
        # Checkpoint and usage writes are separate; never understate a lost charge.
        result["usage"] = result["usage"] | {"cost_usd": None}
        result["trace_warning"] = "Recovered after restart; final cost is unknown"
        result.pop("transcript", None)
        self.store.save(run_id, result)
        self.store.event(run_id, result["status"], error=result["error"])
        return result

    def _stream(self, graph, graph_input, config, run_id, helper, result):
        client = None
        settings = self.settings
        if settings.langsmith_tracing and settings.langsmith_api_key:
            try:
                client = Client(
                    api_key=settings.langsmith_api_key.get_secret_value(),
                    api_url=settings.langsmith_endpoint,
                    hide_inputs=True,
                    hide_outputs=True,
                    timeout_ms=5000,
                    workspace_id=settings.langsmith_workspace_id,
                )
            except Exception:
                result["trace_warning"] = "LangSmith unavailable"
        try:
            with tracing_context(
                enabled=client is not None,
                client=client,
                address=agent_address(
                    settings.langsmith_agent_id, settings.langsmith_agent_environment
                )
                if client
                else None,
            ):
                with trace("discovery_to_jira", inputs={}) as span:
                    for namespace, mode, part in graph.stream(
                        graph_input,
                        config,
                        stream_mode=["updates", "tasks"],
                        subgraphs=True,
                    ):
                        if mode == "tasks":
                            if "input" in part:
                                self.store.event(
                                    run_id, "node_started", node=part["name"]
                                )
                            continue
                        for node, update in part.items():
                            if node == "__interrupt__":
                                continue
                            self.store.event(run_id, "node_finished", node=node)
                            # Keep transcript in its private column/checkpoint.
                            result.update(
                                {
                                    key: value
                                    for key, value in jsonable_encoder(update).items()
                                    if key != "transcript"
                                }
                            )
                            result["usage"] = helper.usage.model_dump(mode="json")
                            self.store.save(run_id, result)
                    span.add_metadata(helper.usage.model_dump(mode="json"))
                    span.end(outputs={"completed": True})
                    if client:
                        try:
                            result["trace_url"] = client.get_run_url(run=span)
                        except Exception:
                            result["trace_warning"] = "Trace link unavailable"
        finally:
            if client:
                try:
                    client.flush(timeout=5)
                except Exception:
                    result["trace_warning"] = "Trace delivery unverified"
                try:
                    client.close(timeout=0)
                except Exception:
                    result["trace_warning"] = "Trace delivery unverified"
