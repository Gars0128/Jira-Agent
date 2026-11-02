import os
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from pydantic import SecretStr
from test_workflow import USAGE, responses, search

from app.api import service
from app.main import app
from app.projects import projects
from app.run_service import RunService, preset_key
from app.run_store import RunLimitError
from app.workflow import Approval, build_workflow


def test_progress_exposes_real_discovery_nodes(settings, helper_factory) -> None:
    helper, _ = helper_factory(responses(), USAGE)
    runtime = RunService(settings)
    seen = []

    class Store:
        def event(self, run_id, kind, **data):
            seen.append((kind, data.get("node")))

        def save(self, run_id, result):
            pass

    runtime.store = Store()
    graph = build_workflow(helper, search, checkpointer=InMemorySaver())
    runtime._stream(
        graph,
        {"transcript": "Nora: Show monthly counts."},
        {"configurable": {"thread_id": "progress"}},
        "progress",
        helper,
        {},
    )
    for node in ["extract", "retrieve_spec", "classify", "write_stories", "critic"]:
        assert ("node_started", node) in seen
        assert ("node_finished", node) in seen


def test_api_projects_and_invalid_payload_without_provider() -> None:
    with TestClient(app) as client:
        result = client.get("/projects")
        assert len(result.json()["projects"][0]["transcripts"]) == 6
        assert client.get("/runs/not-a-uuid").status_code in {422, 503}
    assert projects()[0]["id"] == "harbor-desk"
    general = projects()[1]
    assert general["id"] == "general" and general["spec"] is False
    assert general["transcripts"][0]["id"] == "01-grooming-salon"


def test_api_events_replay_errors_and_validation(settings) -> None:
    run_id = str(uuid4())

    class Store:
        def get(self, identifier):
            return {"status": "done"} if identifier == run_id else None

        def events(self, identifier, after):
            return [
                (i, {"type": kind})
                for i, kind in [(1, "node_started"), (2, "done")]
                if i > after
            ]

    runtime = RunService(settings)
    runtime.store = Store()
    app.dependency_overrides[service] = lambda: runtime
    try:
        with TestClient(app) as client:
            assert client.get(f"/runs/{uuid4()}").status_code == 404
            assert (
                client.post(
                    "/runs", json={"project_id": "harbor-desk", "transcript": " "}
                ).status_code
                == 422
            )
            response = client.get(
                f"/runs/{run_id}/events", headers={"Last-Event-ID": "1"}
            )
            assert response.status_code == 200
            assert "node_started" not in response.text
            assert '"type": "done"' in response.text
            assert (
                client.get(
                    f"/runs/{run_id}/events", headers={"Last-Event-ID": "x"}
                ).status_code
                == 400
            )
    finally:
        app.dependency_overrides.clear()


def test_cache_key_tracks_model_spec_and_real_preset(settings) -> None:
    text = projects()[0]["transcripts"][0]["text"]
    key = preset_key(settings, "harbor-desk", text)
    assert key and preset_key(settings, "harbor-desk", text + "x") is None
    assert preset_key(settings, "general", text) is None
    settings.llm_model = "other-model"
    assert preset_key(settings, "harbor-desk", text) != key


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL required"
)
def test_live_run_checkpoint_cache_budget_and_approval(
    settings, helper_factory, monkeypatch
) -> None:
    settings.database_url = SecretStr(os.environ["TEST_DATABASE_URL"])
    settings.daily_budget_usd = Decimal("100")
    settings.max_pending_runs = 100
    runtime = RunService(settings)
    runtime.store.setup()
    with PostgresSaver.from_conn_string(os.environ["TEST_DATABASE_URL"]) as saver:
        saver.setup()
    helper, requests = helper_factory(responses(), USAGE)
    monkeypatch.setattr("app.run_service.LLMHelper", lambda _: helper)
    monkeypatch.setattr("app.run_service.retrieve", lambda *args: search(args[3]))
    cache_key = "test-" + str(uuid4())
    run_id = runtime.store.create(
        "harbor-desk", "Nora: Show monthly counts.", cache_key
    )
    result = runtime.execute(run_id)
    assert result["status"] == "awaiting_review", result["error"]
    assert len(requests) == 4
    kinds = [body["type"] for _, body in runtime.store.events(run_id, 0)]
    assert "node_started" in kinds and "node_finished" in kinds
    approval = Approval.model_validate({"stories": result["stories"]})
    approval.stories[0].title = "Edited monthly counts"
    # A fresh service/graph/connection must resume a persisted interrupt.
    rebuilt = RunService(settings)
    approved = rebuilt.execute(run_id, approval)
    assert approved["status"] == "done", approved["error"]
    assert approved["stories"][0]["title"] == "Edited monthly counts"
    assert approved["tickets"][0]["dry_run"] is True
    assert rebuilt.execute(run_id, approval)["tickets"] == approved["tickets"]
    assert len(requests) == 4
    helper.usage.calls = 0
    helper.usage.input_tokens = 0
    helper.usage.output_tokens = 0
    helper.usage.cost_usd = Decimal(0)
    cached_id = runtime.store.create(
        "harbor-desk", "Nora: Show monthly counts.", cache_key
    )
    cached = runtime.execute(cached_id)
    assert cached["status"] == "awaiting_review", cached["error"]
    assert cached["cached"] is True and cached["usage"]["cost_usd"] == "0"
    assert len(requests) == 4
    settings.daily_budget_usd = Decimal("0.000001")
    with pytest.raises(RunLimitError, match="Daily"):
        runtime.store.create("harbor-desk", "uncached", None)
