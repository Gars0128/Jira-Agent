import hashlib
import json
from collections.abc import Sequence
from urllib.parse import urlparse

import psycopg
from psycopg.types.json import Jsonb

from app.jira.client import JiraClient, JiraError, JiraRejected
from app.schemas import Requirement
from app.stories import Story


def jira_ledger_key(base_url: str, project_key: str, story_key: str) -> str:
    destination = urlparse(base_url)
    material = [destination.hostname, destination.port or 443, project_key, story_key]
    return hashlib.sha256(json.dumps(material).encode()).hexdigest()


def create_once(
    conn: psycopg.Connection,
    jira: JiraClient,
    base_url: str,
    stories: list[Story],
    requirements: Sequence[Requirement] = (),
) -> list[dict]:
    results = []
    for story in stories:
        key = jira_ledger_key(base_url, jira.project_key, story.idempotency_key)
        with conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,1))", [key])
            existing = conn.execute(
                "SELECT result FROM agent_jira_ledger WHERE key=%s", [key]
            ).fetchone()
            if existing:
                if existing[0] is None:
                    raise JiraError(
                        "Previous Jira creation is unconfirmed; "
                        "reconcile it before retrying"
                    )
                results.append(existing[0] | {"reused": True})
                continue
            conn.execute("INSERT INTO agent_jira_ledger(key) VALUES(%s)", [key])
        # Commit intent before the side effect; uncertainty blocks replay.
        try:
            [result] = jira.create_tickets([story], requirements)
        except JiraRejected:
            # Nothing was created: release the intent so a fixed retry can proceed.
            conn.execute(
                "DELETE FROM agent_jira_ledger WHERE key=%s AND result IS NULL", [key]
            )
            raise
        conn.execute(
            "UPDATE agent_jira_ledger SET result=%s WHERE key=%s", [Jsonb(result), key]
        )
        results.append(result)
    return results
