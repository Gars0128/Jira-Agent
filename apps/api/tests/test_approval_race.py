import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Event

import pytest
from fastapi.encoders import jsonable_encoder
from pydantic import SecretStr
from test_recovery import cached_state

from app.checkpoints import postgres_saver
from app.jira.client import preview_tickets
from app.jira.ledger import jira_ledger_key
from app.llm import LLMHelper
from app.run_service import RunService, hydrate_cache
from app.workflow import Approval


def test_jira_ledger_is_scoped_to_destination_without_changing_story_key() -> None:
    story_key = "a" * 64
    first = jira_ledger_key("https://first.atlassian.net", "HD", story_key)
    assert first == jira_ledger_key("https://FIRST.atlassian.net:443/", "HD", story_key)
    assert first != jira_ledger_key("https://second.atlassian.net", "HD", story_key)
    assert first != jira_ledger_key("https://first.atlassian.net", "OTHER", story_key)
    assert first != jira_ledger_key("https://first.atlassian.net", "HD", "b" * 64)


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL required"
)
def test_live_concurrent_approvals_create_tickets_once(settings, monkeypatch) -> None:
    settings.database_url = SecretStr(os.environ["TEST_DATABASE_URL"])
    settings.daily_budget_usd = Decimal("100")
    settings.max_pending_runs = 100
    runtime = RunService(settings)
    runtime.store.setup()
    with postgres_saver(settings) as saver:
        saver.setup()
    run_id = runtime.store.create("harbor-desk", "Nora: Show monthly counts.", None)
    config = {"configurable": {"thread_id": run_id}}
    with runtime.graph("harbor-desk", LLMHelper(settings)) as graph:
        graph.update_state(config, hydrate_cache(cached_state()), as_node="critic")
        graph.invoke(None, config)
        state = jsonable_encoder(graph.get_state(config).values)
    result = runtime.store.get(run_id) | {
        "status": "awaiting_review",
        "requirements": state["requirements"],
        "stories": state["stories"],
    }
    runtime.store.save(run_id, result)
    approval = Approval.model_validate({"stories": result["stories"]})
    entered = Event()
    release = Event()
    writes = []

    def tickets(self, stories, requirements=()):
        writes.append(stories)
        entered.set()
        assert release.wait(timeout=10)
        return preview_tickets(stories)

    monkeypatch.setattr(RunService, "_tickets", tickets)
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(runtime.execute, run_id, approval)
        try:
            assert entered.wait(timeout=10)
            competing = RunService(settings)
            with pytest.raises(ValueError, match="already being processed"):
                competing.execute(run_id, approval)
        finally:
            release.set()
        completed = first.result(timeout=10)
    assert completed["status"] == "done", completed["error"]
    assert (
        RunService(settings).execute(run_id, approval)["tickets"]
        == completed["tickets"]
    )
    assert len(writes) == 1
