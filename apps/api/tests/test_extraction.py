import json
from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest
from langchain_core.messages import HumanMessage
from langsmith import Client
from pydantic import ValidationError

from app.config import Settings
from app.extract import run_extraction
from app.graph.graph import build_graph
from app.llm import LLMError
from app.schemas import ExtractionOutput


def requirement(quote: str, id: str = "R1") -> dict[str, str]:
    return {
        "id": id,
        "text": "Allow report export.",
        "type": "functional",
        "priority": "must",
        "quote": quote,
        "speaker": "Nora",
    }


USAGE = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}


def test_langgraph_extraction_grounds_and_accounts(helper_factory: Callable) -> None:
    payload = {
        "requirements": [
            requirement("EXPORT reports."),
            requirement("Email reports.", "R2"),
        ]
    }
    helper, requests = helper_factory(json.dumps(payload), USAGE)

    result = run_extraction("Nora: Export\n reports.", helper)

    assert [item["id"] for item in result["requirements"]] == ["R1"]
    assert result["requirements"][0]["status"] is None
    assert result["requirements"][0]["spec_refs"] == []
    assert result["dropped_requirement_ids"] == ["R2"]
    assert result["input_tokens"] == 100
    assert result["output_tokens"] == 50
    assert Decimal(result["cost_usd"]) == Decimal("0.00012")
    assert result["trace_url"] is None
    assert result["latency_ms"] >= 0
    assert len(requests) == 1
    assert requests[0]["max_completion_tokens"] == 4096
    assert requests[0]["response_format"]["type"] == "json_schema"


def test_graph_has_real_extract_node(helper_factory: Callable) -> None:
    helper, _ = helper_factory('{"requirements": []}', USAGE)
    graph = build_graph(helper)

    assert set(graph.get_graph().nodes) == {"__start__", "extract", "__end__"}
    result = run_extraction("Nora: Good morning.", helper)
    assert result["requirements"] == []
    assert result["calls"] == 1


@pytest.mark.parametrize("text", ["", " \n", "x" * 20_001])
def test_invalid_transcript_never_calls_provider(
    helper_factory: Callable, text: str
) -> None:
    helper, requests = helper_factory('{"requirements": []}', USAGE)
    with pytest.raises(ValueError, match="Transcript"):
        run_extraction(text, helper)
    assert requests == []


@pytest.mark.parametrize(
    "content",
    [
        "not JSON",
        '{"requirements": [{"id": "R1"}]}',
        '{"requirements": [], "invented_field": true}',
    ],
)
def test_invalid_output_is_charged_before_rejection(
    helper_factory: Callable, content: str
) -> None:
    helper, requests = helper_factory(content, USAGE)
    with pytest.raises(LLMError, match="invalid structured"):
        run_extraction("Nora: Export reports.", helper)
    assert len(requests) == 1
    assert helper.usage.cost_usd == Decimal("0.00012")


def test_budget_blocks_before_network(helper_factory: Callable) -> None:
    helper, requests = helper_factory('{"requirements": []}', USAGE)
    helper.settings.max_cost_per_run_usd = Decimal("0.000001")
    with pytest.raises(LLMError, match="budget"):
        run_extraction("Nora: Export reports.", helper)
    assert requests == []
    assert helper.usage.calls == 0


def test_actual_overrun_is_recorded_and_blocks_more_calls(
    helper_factory: Callable,
) -> None:
    usage = {
        "prompt_tokens": 100,
        "completion_tokens": 100_000,
        "total_tokens": 100_100,
    }
    helper, requests = helper_factory('{"requirements": []}', usage)
    with pytest.raises(LLMError, match="budget exceeded"):
        run_extraction("Nora: Export reports.", helper)
    assert helper.usage.cost_usd == Decimal("0.16004")
    with pytest.raises(LLMError, match="budget"):
        helper.invoke([HumanMessage("Again")], ExtractionOutput)
    assert len(requests) == 1


@pytest.mark.parametrize("status_code", [200, 429, 503])
def test_unknown_usage_blocks_retries_and_sanitizes_errors(
    helper_factory: Callable, status_code: int
) -> None:
    helper, requests = helper_factory('{"requirements": []}', status_code=status_code)
    with pytest.raises(LLMError) as error:
        run_extraction("private-transcript", helper)
    assert "unknown" in str(error.value)
    assert "private-transcript" not in str(error.value)
    assert "SECRET-KEY" not in str(error.value)
    assert helper.usage.cost_usd is None
    with pytest.raises(LLMError, match="unknown"):
        helper.invoke([HumanMessage("Again")], ExtractionOutput)
    assert len(requests) == 1


def test_cumulative_cost_is_per_helper_run(helper_factory: Callable) -> None:
    helper, requests = helper_factory('{"requirements": []}', USAGE)
    helper.invoke([HumanMessage("First")], ExtractionOutput)
    helper.invoke([HumanMessage("Second")], ExtractionOutput)
    assert helper.usage.calls == len(requests) == 2
    assert helper.usage.cost_usd == Decimal("0.00024")
    assert helper.usage.input_tokens == 200


def test_duplicate_ids_are_rejected_after_accounting(helper_factory: Callable) -> None:
    payload = {"requirements": [requirement("Export reports.")] * 2}
    helper, _ = helper_factory(json.dumps(payload), USAGE)
    with pytest.raises(LLMError, match="duplicate requirement IDs"):
        run_extraction("Nora: Export reports.", helper)
    assert helper.usage.cost_usd == Decimal("0.00012")


def test_extraction_schema_has_no_classification_fields() -> None:
    fields = ExtractionOutput.model_json_schema()["$defs"]["ExtractedRequirement"]
    assert set(fields["properties"]) == {
        "id",
        "text",
        "type",
        "priority",
        "quote",
        "speaker",
    }
    assert set(fields["required"]) == set(fields["properties"])


def test_settings_reject_invalid_budget_and_missing_trace_key(
    settings: Settings,
) -> None:
    values = settings.model_dump()
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **(values | {"max_cost_per_run_usd": "NaN"}))
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **(values | {"langsmith_tracing": True}))


@pytest.mark.parametrize("failure", [None, "url", "flush", "close"])
@pytest.mark.parametrize("provider_failure", [False, True])
def test_tracing_failure_does_not_lose_paid_result(
    helper_factory: Callable,
    monkeypatch: pytest.MonkeyPatch,
    failure: str | None,
    provider_failure: bool,
) -> None:
    writes: list[dict[str, Any]] = []

    class OfflineTraceClient(Client):
        def create_run(self, *args: Any, **kwargs: Any) -> None:
            writes.append(kwargs)

        def update_run(self, *args: Any, **kwargs: Any) -> None:
            writes.append(kwargs)

        def get_run_url(self, **kwargs: Any) -> str:
            if failure == "url":
                raise RuntimeError("SECRET-KEY tracing failure")
            return "https://example.invalid/trace"

        def flush(self, timeout: float | None = None) -> None:
            assert timeout == 5
            if failure == "flush":
                raise RuntimeError("SECRET-KEY tracing failure")

        def close(self, timeout: float | None = None) -> None:
            assert timeout == 0
            if failure == "close":
                raise RuntimeError("SECRET-KEY tracing failure")

    def client_factory(**kwargs: Any) -> OfflineTraceClient:
        return OfflineTraceClient(**kwargs, info={"version": "offline"})

    monkeypatch.setattr("app.extract.Client", client_factory)
    helper, _ = helper_factory(
        '{"requirements": []}', USAGE, status_code=503 if provider_failure else 200
    )
    helper.settings.langsmith_tracing = True
    helper.settings.langsmith_api_key = helper.settings.openai_api_key

    if provider_failure:
        with pytest.raises(LLMError, match="Provider call failed") as error:
            run_extraction("Nora: Good morning.", helper)
        assert "SECRET-KEY" not in str(error.value)
        assert helper.usage.cost_usd is None
        assert writes
        return

    result = run_extraction("Nora: Good morning.", helper)

    assert result["requirements"] == []
    assert Decimal(result["cost_usd"]) == Decimal("0.00012")
    assert (result["trace_warning"] is not None) == (failure is not None)
    assert "SECRET-KEY" not in json.dumps(result)
    assert writes
    root_run_ids = [str(item["id"]) for item in writes if "id" in item]
    assert result["run_id"] in root_run_ids


def test_settings_do_not_depend_on_repository_path() -> None:
    assert Settings.model_config.get("env_file") is None


def test_settings_require_valid_agent_environment(settings: Settings) -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            **(settings.model_dump() | {"langsmith_agent_environment": "unknown"}),
        )


def test_environment_tracing_flag_does_not_trace_outside_explicit_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from langsmith import tracing_context
    from langsmith.utils import tracing_is_enabled

    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    assert tracing_is_enabled() is False
    with tracing_context(enabled=True):
        assert tracing_is_enabled() is True
