import json
import os

import httpx
import pytest
from pydantic import SecretStr
from test_workflow import draft, new_requirement

from app.jira.client import JiraClient, JiraError, preview_tickets
from app.stories import StoryDraft, validate_stories


def stories() -> list:
    return validate_stories([StoryDraft.model_validate(draft())], [new_requirement()])


def test_public_mode_forces_preview_without_network() -> None:
    tickets = preview_tickets(stories())
    assert tickets[0]["dry_run"]
    assert tickets[0]["fields"]["labels"][0].startswith("idem-")
    assert tickets[0]["fields"]["description"]["type"] == "doc"


def test_existing_issue_is_reused() -> None:
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"issues": [{"key": "HD-7"}]})

    with httpx.Client(
        base_url="https://jira.example", transport=httpx.MockTransport(respond)
    ) as http:
        result = JiraClient(client=http).create_tickets(stories())
    assert result == [
        {
            "key": "HD-7",
            "url": "https://jira.example/browse/HD-7",
            "reused": True,
            "dry_run": False,
        }
    ]
    assert len(requests) == 1
    assert requests[0].url.path == "/rest/api/3/search/jql"


def test_rate_limit_retries_then_creates_once() -> None:
    attempts = []
    sleeps = []

    def respond(request: httpx.Request) -> httpx.Response:
        attempts.append(request.method)
        if request.method == "GET":
            return httpx.Response(200, json={"issues": []})
        if attempts.count("POST") < 4:
            return httpx.Response(429)
        return httpx.Response(201, json={"key": "HD-8"})

    with httpx.Client(
        base_url="https://jira.example", transport=httpx.MockTransport(respond)
    ) as http:
        result = JiraClient(client=http, sleep=sleeps.append).create_tickets(stories())
    assert result[0]["key"] == "HD-8"
    assert sleeps == [1, 2, 4]
    assert attempts.count("POST") == 4


@pytest.mark.parametrize("found", [False, True])
def test_ambiguous_create_checks_label_without_blind_retry(found: bool) -> None:
    attempts = []

    def respond(request: httpx.Request) -> httpx.Response:
        attempts.append(request.method)
        if request.method == "GET":
            issues = [{"key": "HD-9"}] if found and "POST" in attempts else []
            return httpx.Response(200, json={"issues": issues})
        raise httpx.ReadTimeout("private-key", request=request)

    with httpx.Client(
        base_url="https://jira.example", transport=httpx.MockTransport(respond)
    ) as http:
        jira = JiraClient(client=http)
        if found:
            assert jira.create_tickets(stories())[0]["reused"]
        else:
            with pytest.raises(JiraError, match="unconfirmed") as error:
                jira.create_tickets(stories())
            assert "private-key" not in str(error.value)
    assert attempts == ["GET", "POST", "GET"]


def test_ticket_description_carries_story_criteria_and_evidence() -> None:
    requirement = new_requirement().model_copy(update={"spec_refs": ["HD-EXPORT"]})
    rule = requirement.model_copy(
        update={"id": "R2", "status": "duplicate", "text": "Keep CSV format."}
    )
    [ticket] = preview_tickets(stories(), [requirement, rule])
    text = json.dumps(ticket["fields"]["description"])
    headings = [
        node["content"][0]["text"]
        for node in ticket["fields"]["description"]["content"]
        if node["type"] == "heading"
    ]
    assert headings == [
        "User story",
        "Acceptance criteria",
        "Source evidence",
        "Related rules from the same call",
    ]
    assert "Keep CSV format." in text
    assert len(ticket["fields"]["labels"][0]) == len("idem-") + 16
    assert "Show monthly counts." in text and "Nora" in text and "HD-EXPORT" in text
    assert ticket["fields"]["labels"][1] == "discovery-agent"


def test_run_response_keeps_live_ticket_link() -> None:
    from app.run_contracts import TicketResult

    url = "https://demo.atlassian.net/browse/KAN-1"
    ticket = {"key": "KAN-1", "url": url, "dry_run": False, "reused": False}
    assert TicketResult.model_validate(ticket).url == url


def test_public_demo_forces_preview_and_live_needs_atlassian(settings) -> None:
    from app.jira.client import jira_session

    settings.jira_dry_run = False
    assert settings.jira_live is False
    settings.public_demo = False
    assert settings.jira_live is True
    settings.jira_base_url = "https://jira.example.com"
    with pytest.raises(JiraError, match="Jira Cloud"):
        with jira_session(settings):
            pass


@pytest.mark.parametrize(
    ("get_status", "post_status", "definite"),
    [(401, None, True), (200, 400, True), (200, 503, False)],
)
def test_definite_jira_failures_are_rejections(
    get_status: int, post_status: int | None, definite: bool
) -> None:
    from app.jira.client import JiraRejected

    def respond(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(get_status, json={"issues": []})
        return httpx.Response(post_status or 201, json={})

    with httpx.Client(
        base_url="https://jira.example", transport=httpx.MockTransport(respond)
    ) as http:
        with pytest.raises(JiraError) as error:
            JiraClient(client=http, sleep=lambda _: None).create_tickets(stories())
    assert isinstance(error.value, JiraRejected) is definite


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL")
def test_live_rejected_jira_write_releases_ledger(settings) -> None:
    from app.jira.client import JiraRejected
    from app.jira.ledger import create_once
    from app.rag.ingest import connect
    from app.run_store import RunStore

    settings.database_url = SecretStr(os.environ["TEST_DATABASE_URL"])
    RunStore(settings).setup()

    class Rejecting:
        project_key = "HD"

        def create_tickets(self, stories, requirements=()):
            raise JiraRejected("Jira request failed (HTTP 400)")

    with connect(settings) as conn:
        for _ in range(2):  # the second attempt must not be blocked as unconfirmed
            with pytest.raises(JiraRejected):
                create_once(conn, Rejecting(), "https://x.atlassian.net", stories())
        assert conn.execute("SELECT count(*) FROM agent_jira_ledger").fetchone()[0] == 0
