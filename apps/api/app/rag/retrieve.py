import argparse
import json
import sys

import psycopg
from pydantic import ValidationError

from app.config import Settings
from app.llm import LLMError, LLMHelper
from app.rag.chunking import SpecChunk
from app.rag.ingest import connect, to_vector


class RetrievedChunk(SpecChunk):
    distance: float


def retrieve(
    conn: psycopg.Connection,
    helper: LLMHelper,
    project_id: str,
    queries: list[str],
    k: int = 5,
) -> list[list[RetrievedChunk]]:
    if not queries:
        return []
    vectors = helper.embed(queries)
    results = []
    for vector in vectors:
        rows = conn.execute(
            "SELECT chunk_id, heading, content, embedding <=> %s::vector"
            " FROM spec_chunks WHERE project_id = %s AND embedding_model = %s"
            " ORDER BY 4 LIMIT %s",
            [to_vector(vector), project_id, helper.settings.embedding_model, k],
        ).fetchall()
        if not rows:
            raise ValueError(f"Specification for {project_id!r} is not ingested")
        results.append(
            [
                RetrievedChunk(id=id, heading=heading, text=text, distance=distance)
                for id, heading, text, distance in rows
            ]
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Show top-k spec chunks for a query")
    parser.add_argument("project_id")
    parser.add_argument("query")
    parser.add_argument("-k", type=int, default=5)
    args = parser.parse_args()
    helper: LLMHelper | None = None
    try:
        settings = Settings()
        helper = LLMHelper(settings)
        with connect(settings) as conn:
            [chunks] = retrieve(conn, helper, args.project_id, [args.query], args.k)
        print(
            json.dumps(
                {
                    "chunks": [chunk.model_dump() for chunk in chunks],
                    **helper.usage.model_dump(mode="json"),
                },
                indent=2,
            )
        )
        return 0
    except ValidationError:
        error = "Invalid configuration; check keys, prices and DATABASE_URL"
    except psycopg.Error:
        error = "Database error; check DATABASE_URL and run ingestion first"
    except (LLMError, ValueError) as exc:
        error = str(exc)
    usage = helper.usage.model_dump(mode="json") if helper else None
    print(json.dumps({"error": error, "usage": usage}), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
