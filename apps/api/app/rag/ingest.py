import argparse
import json
import sys
from pathlib import Path

import psycopg
from pydantic import ValidationError

from app.config import Settings
from app.llm import LLMError, LLMHelper
from app.rag.chunking import SpecChunk, chunk_spec

# shortcut: untyped vector and exact scan, add vector(N) + HNSW index past ~10k chunks.
SCHEMA = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS spec_chunks (
    project_id text NOT NULL,
    chunk_id text NOT NULL,
    heading text NOT NULL,
    content text NOT NULL,
    embedding_model text NOT NULL,
    embedding vector NOT NULL,
    PRIMARY KEY (project_id, chunk_id)
)
"""


def connect(settings: Settings) -> psycopg.Connection:
    return psycopg.connect(
        settings.database_url.get_secret_value(), connect_timeout=10, autocommit=True
    )


def to_vector(values: list[float]) -> str:
    return "[" + ",".join(map(str, values)) + "]"


def ingest(
    conn: psycopg.Connection,
    project_id: str,
    chunks: list[SpecChunk],
    helper: LLMHelper,
) -> dict[str, object]:
    model = helper.settings.embedding_model
    wanted = {(chunk.id, chunk.heading, chunk.text, model) for chunk in chunks}
    with conn.transaction():
        conn.execute(SCHEMA)
        # Serialize concurrent ingests of one project.
        conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [project_id])
        stored = conn.execute(
            "SELECT chunk_id, heading, content, embedding_model"
            " FROM spec_chunks WHERE project_id = %s",
            [project_id],
        ).fetchall()
        if set(stored) == wanted:
            return {"project_id": project_id, "chunks": len(chunks), "changed": False}
        vectors = helper.embed([chunk.text for chunk in chunks])
        conn.execute("DELETE FROM spec_chunks WHERE project_id = %s", [project_id])
        with conn.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO spec_chunks VALUES (%s, %s, %s, %s, %s, %s::vector)",
                [
                    (project_id, c.id, c.heading, c.text, model, to_vector(v))
                    for c, v in zip(chunks, vectors)
                ],
            )
    return {"project_id": project_id, "chunks": len(chunks), "changed": True}


def main() -> int:
    parser = argparse.ArgumentParser(description="Chunk, embed and store a spec")
    parser.add_argument("spec", type=Path, help="data/demo/<project>/spec.md")
    args = parser.parse_args()
    helper: LLMHelper | None = None
    try:
        settings = Settings()
        chunks = chunk_spec(args.spec.read_text(encoding="utf-8"))
        helper = LLMHelper(settings)
        with connect(settings) as conn:
            result = ingest(conn, args.spec.resolve().parent.name, chunks, helper)
        print(json.dumps(result | helper.usage.model_dump(mode="json"), indent=2))
        return 0
    except ValidationError:
        error = "Invalid configuration; check keys, prices and DATABASE_URL"
    except OSError:
        error = "Cannot read the UTF-8 specification file"
    except psycopg.Error:
        # Driver messages can echo connection details; keep them out of output.
        error = "Database error; check DATABASE_URL and that pgvector is available"
    except (LLMError, ValueError) as exc:
        error = str(exc)
    usage = helper.usage.model_dump(mode="json") if helper else None
    print(json.dumps({"error": error, "usage": usage}), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
