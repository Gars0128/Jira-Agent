import json
from collections.abc import Callable, Iterator
from typing import Any

import httpx
import pytest
from langchain_openai import ChatOpenAI

from app.config import Settings
from app.llm import LLMHelper


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        openai_api_key="test-not-a-real-key",
        llm_model="gpt-4.1-mini",
        llm_input_usd_per_million="0.4",
        llm_output_usd_per_million="1.6",
        langsmith_tracing=False,
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
