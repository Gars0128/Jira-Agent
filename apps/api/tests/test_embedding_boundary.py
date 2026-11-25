from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from app.llm import LLMError, LLMHelper


def helper_with_response(settings, data, tokens=3):
    response = SimpleNamespace(
        data=[SimpleNamespace(index=index, embedding=vector) for index, vector in data],
        usage=SimpleNamespace(prompt_tokens=tokens),
    )
    embedder = SimpleNamespace(embeddings=SimpleNamespace(create=lambda **_: response))
    return LLMHelper(settings, embedder=embedder)


def test_out_of_order_embeddings_keep_query_association(settings):
    helper = helper_with_response(settings, [(1, [0.0, 1.0]), (0, [1.0, 0.0])])
    assert helper.embed(["first", "second"]) == [[1.0, 0.0], [0.0, 1.0]]


@pytest.mark.parametrize(
    "data",
    [
        [(0, [1.0]), (0, [2.0])],
        [(0, [float("nan")]), (1, [1.0])],
        [(0, [0.0]), (1, [1.0])],
        [(0, [1.0]), (1, [1.0, 2.0])],
    ],
)
def test_invalid_vectors_still_account_for_provider_charge(settings, data):
    helper = helper_with_response(settings, data)
    with pytest.raises(LLMError, match="invalid"):
        helper.embed(["first", "second"])
    assert helper.usage.input_tokens == 3
    assert helper.usage.cost_usd > 0


def test_invalid_embedding_usage_blocks_future_calls(settings):
    helper = helper_with_response(settings, [(0, [1.0])], tokens=-1)
    with pytest.raises(LLMError, match="unknown"):
        helper.embed(["first"])
    assert helper.usage.cost_usd is None
    with pytest.raises(LLMError, match="unknown"):
        helper.embed(["second"])


def test_embeddings_can_use_their_own_endpoint(settings, monkeypatch):
    # Chat on a hosted provider, embeddings on local Ollama: stored vectors and
    # the calibrated match threshold belong to the embedding model.
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    shared = LLMHelper(settings).embedder
    assert shared.api_key == "test-not-a-real-key"

    settings.embedding_base_url = "http://localhost:11434/v1"
    settings.embedding_api_key = SecretStr("ollama")
    split = LLMHelper(settings).embedder
    assert str(split.base_url).rstrip("/") == "http://localhost:11434/v1"
    assert split.api_key == "ollama"
