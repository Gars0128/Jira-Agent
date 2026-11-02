from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb

from app.config import Settings
from app.rag.ingest import connect

SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_runs (
 id uuid PRIMARY KEY, project_id text NOT NULL, transcript text NOT NULL,
 status text NOT NULL, result jsonb NOT NULL, reserved numeric NOT NULL,
 budget_day date NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date,
 cache_key text, created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS agent_events (
 id bigserial PRIMARY KEY, run_id uuid NOT NULL REFERENCES agent_runs(id),
 body jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS agent_events_run ON agent_events(run_id,id);
CREATE TABLE IF NOT EXISTS agent_preset_cache (
 key text PRIMARY KEY, state jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_jira_ledger (
 key text PRIMARY KEY, result jsonb
);
"""


class RunLimitError(ValueError):
    pass


class RunBusyError(ValueError):
    pass


class RunStore:
    def __init__(self, settings: Settings):
        self.settings = settings

    def setup(self) -> None:
        with connect(self.settings) as conn:
            conn.execute(SCHEMA)

    def create(self, project_id: str, transcript: str, cache_key: str | None) -> str:
        run_id = str(uuid4())
        with connect(self.settings) as conn, conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(73190421)")
            pending = conn.execute(
                "SELECT count(*) FROM agent_runs WHERE status IN ('queued','running')"
            ).fetchone()[0]
            if pending >= self.settings.max_pending_runs:
                raise RunLimitError("Run queue is full; try again later")
            used = conn.execute(
                "SELECT coalesce(sum(reserved),0) FROM agent_runs WHERE budget_day ="
                " (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date"
            ).fetchone()[0]
            cached = (
                cache_key
                and conn.execute(
                    "SELECT 1 FROM agent_preset_cache WHERE key=%s", [cache_key]
                ).fetchone()
            )
            reserve = Decimal(0) if cached else self.settings.max_cost_per_run_usd
            if used + reserve > self.settings.daily_budget_usd:
                raise RunLimitError("Daily demo budget reached; try a cached preset")
            result = {
                "run_id": run_id,
                "status": "queued",
                "requirements": [],
                "stories": [],
                "questions": [],
                "retrieved": {},
                "tickets": [],
                "usage": {
                    "calls": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost_usd": "0",
                },
                "latency_ms": 0,
                "trace_url": None,
                "error": None,
                "cached": bool(cached),
            }
            conn.execute(
                "INSERT INTO agent_runs(id,project_id,transcript,status,result,"
                "reserved,cache_key) VALUES(%s,%s,%s,'queued',%s,%s,%s)",
                [run_id, project_id, transcript, Jsonb(result), reserve, cache_key],
            )
        return run_id

    def get(self, run_id: str) -> dict | None:
        with connect(self.settings) as conn:
            row = conn.execute(
                "SELECT result FROM agent_runs WHERE id=%s", [run_id]
            ).fetchone()
        return row[0] if row else None

    def event(self, run_id: str, kind: str, **data) -> None:
        with connect(self.settings) as conn:
            conn.execute(
                "INSERT INTO agent_events(run_id,body) VALUES(%s,%s)",
                [run_id, Jsonb({"type": kind, **data})],
            )

    def events(self, run_id: str, after: int) -> list[tuple[int, dict]]:
        with connect(self.settings) as conn:
            return conn.execute(
                "SELECT id,body FROM agent_events WHERE run_id=%s AND id>%s"
                " ORDER BY id LIMIT 100",
                [run_id, after],
            ).fetchall()

    def save(self, run_id: str, result: dict, *, settle: bool = False) -> None:
        with connect(self.settings) as conn:
            # Unknown usage retains the reservation instead of claiming zero cost.
            cost = result["usage"]["cost_usd"]
            conn.execute(
                "UPDATE agent_runs SET status=%s,result=%s,updated_at=now(),"
                " reserved=CASE WHEN %s AND %s::numeric IS NOT NULL"
                " THEN %s::numeric ELSE reserved END"
                " WHERE id=%s",
                [result["status"], Jsonb(result), settle, cost, cost, run_id],
            )

    @contextmanager
    def locked(self, run_id: str) -> Iterator[psycopg.Connection | None]:
        with connect(self.settings) as conn, conn.transaction():
            acquired = conn.execute(
                "SELECT pg_try_advisory_xact_lock(hashtextextended(%s,0))", [run_id]
            ).fetchone()[0]
            yield conn if acquired else None
