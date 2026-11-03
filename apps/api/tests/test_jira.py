import json

import httpx
import pytest
from test_workflow import draft, new_requirement

from app.jira.client import JiraClient, JiraError
from app.stories import StoryDraft, validate_stories


def stories() -> list:
    return validate_stories([StoryDraft.model_validate(draft())], [new_requirement()])


def test_public_mode_forces_preview_without_network() -> None:
    jira = JiraClient(dry_run=False, public_demo=True)
    tickets = jira.create_tickets(stories())
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
        result = JiraClient(
            client=http, public_demo=False, dry_run=False
        ).create_tickets(stories())
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
        result = JiraClient(
            client=http, public_demo=False, dry_run=False, sleep=sleeps.append
        ).create_tickets(stories())
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
        jira = JiraClient(client=http, public_demo=False, dry_run=False)
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
    [ticket] = JiraClient().create_tickets(stories(), [requirement, rule])
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
