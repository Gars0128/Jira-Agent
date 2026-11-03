import argparse
import json
import logging
import sys
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import psycopg
from pydantic import ValidationError

from app.config import Settings
from app.graph.graph import Search, build_graph
from app.llm import LLMError, LLMHelper, traced_root
from app.rag.ingest import connect
from app.rag.retrieve import retrieve


def run_extraction(
    transcript: str, helper: LLMHelper, search: Search | None = None
) -> dict[str, object]:
    if not transcript.strip() or len(transcript) > 20_000:
        raise ValueError("Transcript must contain 1 to 20000 characters of text")
    notes: dict = {}
    run_id = uuid4()
    started = perf_counter()
    with traced_root(
        helper.settings, "requirement_extraction", notes, run_id=run_id
    ) as span:
        result = build_graph(helper, search).invoke({"transcript": transcript})
        span.add_metadata(helper.usage.model_dump(mode="json"))
        span.end(outputs={"requirement_count": len(result["requirements"])})
    result_payload = {
        "run_id": str(run_id),
        "requirements": [item.model_dump() for item in result["requirements"]],
        "dropped_requirement_ids": result["dropped_requirement_ids"],
        "retrieved": {
            id: [chunk.model_dump() for chunk in chunks]
            for id, chunks in result.get("retrieved", {}).items()
        },
        **helper.usage.model_dump(mode="json"),
        "latency_ms": round((perf_counter() - started) * 1000),
        "trace_url": notes.get("trace_url"),
        "trace_warning": notes.get("trace_warning"),
    }
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
    parser.add_argument(
        "--project", help="also retrieve and classify against this ingested spec"
    )
    args = parser.parse_args()
    helper: LLMHelper | None = None
    try:
        settings = Settings()
        text = args.transcript.read_text(encoding="utf-8")
        helper = LLMHelper(settings)
        if args.project is None:
            print(json.dumps(run_extraction(text, helper), indent=2))
            return 0
        with connect(settings) as conn:

            def search(queries: list[str]) -> list:
                return retrieve(conn, helper, args.project, queries)

            print(json.dumps(run_extraction(text, helper, search), indent=2))
        return 0
    except ValidationError:
        error = "Invalid configuration; check keys, model, positive prices and budget"
    except OSError:
        error = "Cannot read the UTF-8 transcript file"
    except psycopg.Error:
        error = "Database error; check DATABASE_URL and run ingestion first"
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
