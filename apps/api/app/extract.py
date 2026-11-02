import argparse
import json
import logging
import sys
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from langsmith import Client, agent_address, trace, tracing_context
from pydantic import ValidationError

from app.config import Settings
from app.graph.graph import build_extraction_graph
from app.llm import LLMError, LLMHelper


def run_extraction(transcript: str, helper: LLMHelper) -> dict[str, object]:
    if not transcript.strip() or len(transcript) > 20_000:
        raise ValueError("Transcript must contain 1 to 20000 characters of text")
    settings = helper.settings
    warning = None
    client = None
    if settings.langsmith_tracing and settings.langsmith_api_key is not None:
        try:
            client = Client(
                api_key=settings.langsmith_api_key.get_secret_value(),
                api_url=settings.langsmith_endpoint,
                hide_inputs=True,
                hide_outputs=True,
                workspace_id=settings.langsmith_workspace_id,
                timeout_ms=5000,
            )
        except Exception:
            warning = "LangSmith unavailable; extraction continued without tracing"
    run_id = uuid4()
    started = perf_counter()
    try:
        with tracing_context(
            enabled=client is not None,
            client=client,
            address=agent_address(
                settings.langsmith_agent_id, settings.langsmith_agent_environment
            )
            if client is not None
            else None,
        ):
            with trace("requirement_extraction", run_id=run_id, inputs={}) as span:
                result = build_extraction_graph(helper).invoke(
                    {"transcript": transcript}
                )
                span.add_metadata(helper.usage.model_dump(mode="json"))
                span.end(outputs={"requirement_count": len(result["requirements"])})
                trace_url = None
                if client is not None:
                    try:
                        # shortcut: sync URL API, migrate to async before 2027-01-31.
                        trace_url = client.get_run_url(run=span)
                    except Exception:
                        warning = "LangSmith trace link unavailable"
        result_payload = {
            "run_id": str(run_id),
            "requirements": [item.model_dump() for item in result["requirements"]],
            "dropped_requirement_ids": result["dropped_requirement_ids"],
            **helper.usage.model_dump(mode="json"),
            "latency_ms": round((perf_counter() - started) * 1000),
            "trace_url": trace_url,
        }
    finally:
        if client is not None:
            try:
                client.flush(timeout=5)
            except Exception:
                warning = "LangSmith flush failed; trace delivery is unverified"
            try:
                client.close(timeout=0)
            except Exception:
                warning = "LangSmith close failed; trace delivery is unverified"
    result_payload["trace_warning"] = warning
    return result_payload


def main() -> int:
    # SDK logs can contain credential fragments; return generic warnings instead.
    sdk_logger = logging.getLogger("langsmith")
    sdk_logger.handlers = [logging.NullHandler()]
    sdk_logger.propagate = False
    parser = argparse.ArgumentParser(
        description="Extract requirements through LangGraph"
    )
    parser.add_argument("transcript", type=Path)
    args = parser.parse_args()
    helper: LLMHelper | None = None
    try:
        settings = Settings()
        text = args.transcript.read_text(encoding="utf-8")
        helper = LLMHelper(settings)
        print(json.dumps(run_extraction(text, helper), indent=2))
        return 0
    except ValidationError:
        error = "Invalid configuration; check keys, model, positive prices and budget"
    except OSError:
        error = "Cannot read the UTF-8 transcript file"
    except (LLMError, ValueError) as exc:
        error = str(exc)
    print(
        json.dumps(
            {
                "error": error,
                "usage": helper.usage.model_dump(mode="json") if helper else None,
            }
        ),
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
