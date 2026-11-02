import json
import os
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg
import pytest
from openai import OpenAI

from app.config import Settings
from app.extract import run_extraction
from app.graph.graph import build_graph, classify_requirements
from app.llm import LLMError, LLMHelper
from app.rag.chunking import chunk_spec
from app.rag.ingest import ingest
from app.rag.retrieve import RetrievedChunk, retrieve
from app.schemas import Requirement

ROOT = Path(__file__).resolve().parents[3]
SPEC = (ROOT / "data/demo/harbor-desk/spec.md").read_text(encoding="utf-8")
USAGE = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
TOPICS = ["export", "audit", "booking"]


def fake_vector(text: str) -> list[float]:
    return [float(topic in text.lower()) for topic in TOPICS] + [0.1]


def embedding_helper(
    settings: Settings, status_code: int = 200
) -> tuple[LLMHelper, list[dict]]:
    requests: list[dict] = []

    def respond(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        if status_code != 200:
            return httpx.Response(status_code, json={"error": {"message": "SECRET"}})
        data = [
            {"object": "embedding", "index": i, "embedding": fake_vector(text)}
            for i, text in enumerate(body["input"])
        ]
        usage = {"prompt_tokens": 10 * len(data), "total_tokens": 10 * len(data)}
        return httpx.Response(
            200,
            json={"object": "list", "data": data, "model": "m", "usage": usage},
        )

    client = OpenAI(
        api_key="test-not-a-real-key",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )
    return LLMHelper(settings, embedder=client), requests


def requirement(id: str, text: str) -> Requirement:
    return Requirement(
        id=id,
        text=text,
        type="functional",
        priority="must",
        quote=text,
        speaker="Nora",
    )


def chunk(id: str) -> RetrievedChunk:
    return RetrievedChunk(id=id, heading=id, text=f"{id} text", distance=0.1)


def test_spec_chunks_by_heading_and_covers_gold_refs() -> None:
    chunks = chunk_spec(SPEC)
    ids = [item.id for item in chunks]
    assert ids[0] == "intro"
    assert len(ids) == 13 and all(id.startswith("HD-") for id in ids[1:])
    assert chunks[7].heading == "HD-EXPORT — Report export permissions and format"
    assert chunks[7].text.startswith("## HD-EXPORT")
    gold_refs = {
        ref
        for case in (ROOT / "evals/cases").glob("*.json")
        for item in json.loads(case.read_text(encoding="utf-8"))["requirements"]
        for ref in item["spec_refs"]
    }
    assert gold_refs <= set(ids)


def test_long_sections_fall_back_to_fixed_size_parts() -> None:
    long_section = "## Long one\n\n" + "\n\n".join(["word " * 30] * 5) + "x" * 400
    chunks = chunk_spec(long_section, max_chars=200)
    assert [item.id for item in chunks][:2] == ["long-one#1", "long-one#2"]
    assert all(len(item.text) <= 200 for item in chunks)
    assert "".join(item.text for item in chunks).count("word") == 150
    assert [item.id for item in chunk_spec("No headings here.")] == ["intro"]


def test_duplicate_heading_ids_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        chunk_spec("## HD-A — One\n\nx\n\n## HD-A — Two\n\ny")


def test_embeddings_are_accounted_and_errors_block_reuse(settings: Settings) -> None:
    helper, requests = embedding_helper(settings)
    vectors = helper.embed(["export", "audit"])
    assert vectors == [fake_vector("export"), fake_vector("audit")]
    assert requests[0]["model"] == "text-embedding-3-small"
    assert helper.usage.input_tokens == 20
    assert helper.usage.cost_usd == Decimal("0.0000004")

    failing, _ = embedding_helper(settings, status_code=503)
    with pytest.raises(LLMError, match="unknown") as error:
        failing.embed(["x"])
    assert "SECRET" not in str(error.value)
    with pytest.raises(LLMError, match="unknown"):
        failing.embed(["x"])


def test_classification_applies_status_refs_and_note(
    helper_factory: Callable,
) -> None:
    output = {
        "classifications": [
            {
                "id": "R1",
                "status": "conflict",
                "spec_refs": ["HD-EXPORT"],
                "note": "Export is admin-only.",
            },
            {"id": "R2", "status": "new", "spec_refs": [], "note": " "},
        ]
    }
    helper, requests = helper_factory(json.dumps(output), USAGE)
    items = [requirement("R1", "Coordinators export"), requirement("R2", "Alerts")]
    retrieved = {"R1": [chunk("HD-EXPORT")], "R2": [chunk("HD-NOTIFY")]}

    result = classify_requirements(helper, items, retrieved)

    assert [(r.status, r.spec_refs, r.note) for r in result] == [
        ("conflict", ["HD-EXPORT"], "Export is admin-only."),
        ("new", [], None),
    ]
    sent = json.loads(requests[0]["messages"][1]["content"])
    assert sent["spec_excerpts"] == {
        "HD-EXPORT": "HD-EXPORT text",
        "HD-NOTIFY": "HD-NOTIFY text",
    }
    assert sent["requirements"][0]["excerpt_ids"] == ["HD-EXPORT"]


@pytest.mark.parametrize(
    ("classifications", "message"),
    [
        ([{"id": "R9", "status": "new", "spec_refs": [], "note": ""}], "set of"),
        (
            [{"id": "R1", "status": "new", "spec_refs": ["HD-AUDIT"], "note": ""}],
            "not given",
        ),
        (
            [{"id": "R1", "status": "duplicate", "spec_refs": [], "note": ""}],
            "lacks",
        ),
    ],
)
def test_classification_rejects_unsupported_output(
    helper_factory: Callable, classifications: list, message: str
) -> None:
    helper, _ = helper_factory(json.dumps({"classifications": classifications}), USAGE)
    with pytest.raises(LLMError, match=message):
        classify_requirements(
            helper, [requirement("R1", "Export")], {"R1": [chunk("HD-EXPORT")]}
        )


def test_full_graph_extracts_retrieves_and_classifies(
    helper_factory: Callable,
) -> None:
    extracted = {
        "requirements": [
            {
                "id": "R1",
                "text": "Export reports.",
                "type": "functional",
                "priority": "must",
                "quote": "Export reports.",
                "speaker": "Nora",
            }
        ]
    }
    classified = {
        "classifications": [
            {"id": "R1", "status": "duplicate", "spec_refs": ["HD-EXPORT"], "note": "x"}
        ]
    }
    helper, requests = helper_factory(
        [json.dumps(extracted), json.dumps(classified)], USAGE
    )
    queries: list[list[str]] = []

    def search(texts: list[str]) -> list[list[RetrievedChunk]]:
        queries.append(texts)
        return [[chunk("HD-EXPORT")] for _ in texts]

    assert set(build_graph(helper, search).get_graph().nodes) == {
        "__start__",
        "extract",
        "retrieve_spec",
        "classify",
        "__end__",
    }
    result = run_extraction("Nora: Export reports.", helper, search)

    assert queries == [["Export reports.\nExport reports."]]
    assert result["requirements"][0]["status"] == "duplicate"
    assert result["retrieved"]["R1"][0]["id"] == "HD-EXPORT"
    assert len(requests) == 2 and result["calls"] == 2


@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="set TEST_DATABASE_URL"
)
def test_ingest_is_idempotent_and_retrieves_nearest(settings: Settings) -> None:
    project = f"test-{uuid4().hex[:8]}"
    chunks = [item for item in chunk_spec(SPEC) if item.id != "intro"]
    with psycopg.connect(os.environ["TEST_DATABASE_URL"], autocommit=True) as conn:
        try:
            helper, requests = embedding_helper(settings)
            assert ingest(conn, project, chunks, helper)["changed"] is True
            assert ingest(conn, project, chunks, helper)["changed"] is False
            assert len(requests) == 1

            [top] = retrieve(conn, helper, project, ["audit retention"], k=3)
            assert len(top) == 3
            assert "audit" in top[0].text.lower()
            assert top[0].distance <= top[1].distance <= top[2].distance

            changed = chunks[:-1]
            assert ingest(conn, project, changed, helper)["changed"] is True
            count = conn.execute(
                "SELECT count(*) FROM spec_chunks WHERE project_id = %s", [project]
            ).fetchone()
            assert count == (len(changed),)
        finally:
            conn.execute("DELETE FROM spec_chunks WHERE project_id = %s", [project])
    with pytest.raises(ValueError, match="not ingested"):
        with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as conn:
            retrieve(conn, helper, project, ["x"])
