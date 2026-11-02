from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from psycopg.rows import dict_row

from app.config import Settings


@contextmanager
def postgres_saver(settings: Settings) -> Iterator[PostgresSaver]:
    serializer = JsonPlusSerializer(
        allowed_msgpack_modules=[
            ("app.schemas", "Requirement"),
            ("app.stories", "Story"),
            ("app.rag.retrieve", "RetrievedChunk"),
        ]
    )
    with psycopg.connect(
        settings.database_url.get_secret_value(),
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
        connect_timeout=10,
    ) as conn:
        yield PostgresSaver(conn, serde=serializer)
