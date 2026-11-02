import json
import os
from collections.abc import Callable, Iterator
from typing import Any
from uuid import uuid4

import httpx
import psycopg
import pytest
from langchain_openai import ChatOpenAI
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from app.config import Settings
from app.llm import LLMHelper


@pytest.fixture(autouse=True)
def no_external_http(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject(self, request):
        raise AssertionError("External HTTP is disabled in tests; use MockTransport")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", reject)

    async def reject_async(self, request):
        raise AssertionError("External HTTP is disabled in tests; use MockTransport")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", reject_async)


@pytest.fixture(autouse=True)
def explicit_api_runtime():
    from fastapi import HTTPException

    from app.api import service
    from app.main import app

    def unavailable():
        raise HTTPException(503, "Tests must inject an explicit API runtime")

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[service] = unavailable
    try:
        yield
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


@pytest.fixture(autouse=True)
def isolated_live_database(request, monkeypatch: pytest.MonkeyPatch):
    original = os.getenv("TEST_DATABASE_URL")
    if not original or not request.node.name.startswith("test_live_"):
        yield
        return
    schema = "test_" + uuid4().hex
    with psycopg.connect(original, autocommit=True, connect_timeout=10) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        try:
            previous_options = conninfo_to_dict(original).get("options", "")
            isolated = make_conninfo(
                original,
                options=f"{previous_options} -c search_path={schema},public".strip(),
            )
            monkeypatch.setenv("TEST_DATABASE_URL", isolated)
            yield
        finally:
            # Only remove the disposable namespace created by this fixture.
            assert schema.startswith("test_") and len(schema) == 37
            conn.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
            )


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        openai_api_key="test-not-a-real-key",
        llm_model="gpt-4.1-mini",
        llm_input_usd_per_million="0.4",
        llm_output_usd_per_million="1.6",
        langsmith_tracing=False,
        public_demo=True,
        jira_dry_run=True,
        jira_base_url="",
        jira_email="",
        jira_api_token="",
        jira_project_key="",
    )


@pytest.fixture
def helper_factory(settings: Settings) -> Iterator[Callable]:
    clients = []

    def create(
        content: str | list[str],
        usage: dict[str, int] | None = None,
        status_code: int = 200,
    ) -> tuple[LLMHelper, list[dict[str, Any]]]:
        requests: list[dict[str, Any]] = []
        # A list gives one response per request, in order.
        contents = [content] if isinstance(content, str) else list(content)

        def respond(request: httpx.Request) -> httpx.Response:
            requests.append(json.loads(request.content))
            if status_code != 200:
                return httpx.Response(
                    status_code,
                    json={"error": {"message": "private-transcript SECRET-KEY"}},
                )
            body = {
                "id": "chatcmpl-offline",
                "object": "chat.completion",
                "created": 1,
                "model": "gpt-4.1-mini",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": contents[min(len(requests), len(contents)) - 1],
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": usage,
            }
            return httpx.Response(200, json=body)

        client = httpx.Client(transport=httpx.MockTransport(respond))
        clients.append(client)
        model = ChatOpenAI(
            model=settings.llm_model,
            api_key="test-not-a-real-key",
            http_client=client,
            max_retries=0,
            max_completion_tokens=settings.llm_max_output_tokens,
        )
        return LLMHelper(settings, model), requests

    yield create
    for client in clients:
        client.close()
