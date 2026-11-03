import re
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from urllib.parse import urlparse

import httpx

from app.config import Settings
from app.schemas import Requirement
from app.stories import Story


class JiraError(RuntimeError):
    pass


class JiraRejected(JiraError):
    """Jira definitely created nothing, so a retry after a fix is safe."""


def _text(text: str, bold: bool = False) -> dict:
    node: dict = {"type": "text", "text": text}
    if bold:
        node["marks"] = [{"type": "strong"}]
    return node


def _heading(text: str) -> dict:
    return {"type": "heading", "attrs": {"level": 3}, "content": [_text(text)]}


def _paragraph(*content: dict) -> dict:
    return {"type": "paragraph", "content": list(content)}


def _bullets(items: list[list[dict]]) -> dict:
    return {
        "type": "bulletList",
        "content": [
            {"type": "listItem", "content": [_paragraph(*item)]} for item in items
        ],
    }


def label(key: str) -> str:
    # 64 bits keeps collisions negligible and the board card readable.
    return f"idem-{key[:16]}"


def issue_fields(
    story: Story, project_key: str, requirements: Sequence[Requirement] = ()
) -> dict:
    by_id = {item.id: item for item in requirements}
    content = [
        _heading("User story"),
        _paragraph(
            _text("As a "),
            _text(story.as_a, bold=True),
            _text(", I want "),
            _text(story.i_want, bold=True),
            _text(", so that "),
            _text(story.so_that, bold=True),
            _text("."),
        ),
        _heading("Acceptance criteria"),
        _bullets([[_text(item)] for item in story.acceptance_criteria]),
        _heading("Source evidence"),
    ]
    for ref in story.requirement_ids:
        item = by_id.get(ref)
        if item is None:
            content.append(_paragraph(_text(ref, bold=True)))
            continue
        content.append(
            _paragraph(
                _text(f"{item.id} · {item.type} · {item.priority}: ", bold=True),
                _text(item.text),
            )
        )
        content.append(
            {
                "type": "blockquote",
                "content": [_paragraph(_text(f"“{item.quote}” — {item.speaker}"))],
            }
        )
        if item.spec_refs:
            content.append(
                _paragraph(_text("Specification: "), _text(", ".join(item.spec_refs)))
            )
        if item.note:
            content.append(_paragraph(_text("Analysis: "), _text(item.note)))
    # Rules the spec already covers yield no story; keep them for the developer.
    refs = {
        ref
        for id in story.requirement_ids
        if id in by_id
        for ref in by_id[id].spec_refs
    }
    related = [
        item
        for item in requirements
        if item.status == "duplicate" and refs & set(item.spec_refs)
    ]
    if related:
        content.append(_heading("Related rules from the same call"))
        content.append(
            _bullets(
                [
                    [_text(item.text), _text(f" “{item.quote}” — {item.speaker}")]
                    for item in related
                ]
            )
        )
    content.append(
        _paragraph(
            _text(
                "Drafted by Tiro from a client call transcript "
                "and approved by a human reviewer."
            )
        )
    )
    return {
        "project": {"key": project_key},
        "issuetype": {"name": "Story"},
        "summary": story.title,
        "labels": [label(story.idempotency_key), "discovery-agent"],
        "description": {"type": "doc", "version": 1, "content": content},
    }


def preview_tickets(
    stories: list[Story], requirements: Sequence[Requirement] = ()
) -> list[dict]:
    return [
        {
            "key": f"PREVIEW-{story.idempotency_key[:8]}",
            "dry_run": True,
            "reused": False,
            "fields": issue_fields(story, "DEMO", requirements),
        }
        for story in stories
    ]


class JiraClient:
    def __init__(
        self,
        *,
        client: httpx.Client,
        project_key: str = "DEMO",
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,49}", project_key):
            raise ValueError("Invalid Jira project key")
        self.project_key = project_key
        self.client = client
        self.sleep = sleep

    def _request(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        for attempt in range(4):
            try:
                response = self.client.request(method, path, **kwargs)
            except httpx.TransportError:
                raise JiraError(
                    "Jira response is unknown; creation may have succeeded"
                ) from None
            if response.status_code == 429 or (
                method == "GET" and response.status_code >= 500
            ):
                if attempt < 3:
                    self.sleep(2**attempt)
                    continue
            if response.status_code >= 400:
                # A 5xx POST may still have created the issue; a 4xx did not.
                error = JiraRejected if response.status_code < 500 else JiraError
                raise error(f"Jira request failed (HTTP {response.status_code})")
            return response

    def _browse(self, key: str) -> str:
        return str(self.client.base_url.join(f"/browse/{key}"))

    def _find(self, key: str) -> dict | None:
        response = self._request(
            "GET",
            "/rest/api/3/search/jql",
            params={
                "jql": f'project = "{self.project_key}" AND labels = "{label(key)}"',
                "fields": "key",
                "maxResults": 1,
            },
        )
        try:
            issues = response.json()["issues"]
            if issues:
                issue_key = issues[0]["key"]
                if not isinstance(issue_key, str) or not issue_key:
                    raise ValueError
                return {
                    "key": issue_key,
                    "url": self._browse(issue_key),
                    "reused": True,
                    "dry_run": False,
                }
        except (KeyError, TypeError, ValueError):
            raise JiraError("Jira returned an invalid search result") from None
        return None

    def create_tickets(
        self, stories: list[Story], requirements: Sequence[Requirement] = ()
    ) -> list[dict]:
        result = []
        for story in stories:
            fields = issue_fields(story, self.project_key, requirements)
            try:
                existing = self._find(story.idempotency_key)
            except JiraError as exc:
                raise JiraRejected(str(exc)) from None
            if existing:
                result.append(existing)
                continue
            try:
                response = self._request(
                    "POST", "/rest/api/3/issue", json={"fields": fields}
                )
            except JiraRejected:
                raise
            except JiraError:
                existing = self._find(story.idempotency_key)
                if existing:
                    result.append(existing)
                    continue
                # Search indexing can lag; retrying an ambiguous POST can duplicate.
                raise JiraError(
                    "Jira creation is unconfirmed; check Jira before retrying approval"
                ) from None
            try:
                key = response.json()["key"]
                if not isinstance(key, str) or not key:
                    raise ValueError
            except (KeyError, TypeError, ValueError):
                raise JiraError(
                    "Jira creation is unconfirmed; check Jira before retrying approval"
                ) from None
            result.append(
                {
                    "key": key,
                    "url": self._browse(key),
                    "dry_run": False,
                    "reused": False,
                }
            )
        return result


@contextmanager
def jira_session(settings: Settings) -> Iterator[JiraClient]:
    url = urlparse(settings.jira_base_url)
    token = settings.jira_api_token.get_secret_value()
    if (
        url.scheme != "https"
        or not (url.hostname or "").endswith(".atlassian.net")
        or not settings.jira_email
        or not token
    ):
        raise JiraError("Configure a Jira Cloud HTTPS URL, email and token")
    with httpx.Client(
        base_url=settings.jira_base_url.rstrip("/"),
        auth=(settings.jira_email, token),
        timeout=20,
        follow_redirects=False,
    ) as client:
        yield JiraClient(client=client, project_key=settings.jira_project_key)
