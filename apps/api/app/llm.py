import json
import math
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from typing import Any, TypeVar

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from langsmith import Client, agent_address, configure, trace, tracing_context
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

from app.config import Settings

# LANGSMITH_TRACING in the environment would auto-trace LangChain/LangGraph with a
# default client that uploads transcripts; trace only inside explicit contexts
# whose clients hide inputs and outputs.
configure(enabled=False)

Output = TypeVar("Output", bound=BaseModel)


@contextmanager
def traced_root(
    settings: Settings, name: str, notes: dict, **trace_kwargs: Any
) -> Iterator[Any]:
    """Root span with hidden I/O; tracing failures go to notes, never raise."""
    client = None
    if settings.langsmith_tracing and settings.langsmith_api_key is not None:
        try:
            client = Client(
                api_key=settings.langsmith_api_key.get_secret_value(),
                api_url=settings.langsmith_endpoint,
                hide_inputs=True,
                hide_outputs=True,
                workspace_id=settings.langsmith_workspace_id,
                timeout_ms=5000,
            )
        except Exception:
            notes["trace_warning"] = "LangSmith unavailable"
    address = (
        agent_address(settings.langsmith_agent_id, settings.langsmith_agent_environment)
        if client
        else None
    )
    try:
        with tracing_context(
            enabled=client is not None, client=client, address=address
        ):
            with trace(name, inputs={}, **trace_kwargs) as span:
                yield span
            if client:
                try:
                    # shortcut: sync URL API, migrate to async before 2027-01-31.
                    notes["trace_url"] = client.get_run_url(run=span)
                except Exception:
                    notes["trace_warning"] = "Trace link unavailable"
    finally:
        if client:
            for close in (
                lambda: client.flush(timeout=5),
                lambda: client.close(timeout=0),
            ):
                try:
                    close()
                except Exception:
                    notes["trace_warning"] = "Trace delivery unverified"


class Usage(BaseModel):
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: Decimal | None = Decimal("0")


class LLMError(RuntimeError):
    pass


class TokenCounts(BaseModel):
    input_tokens: int = Field(strict=True, ge=0)
    output_tokens: int = Field(strict=True, ge=0)


class LLMHelper:
    def __init__(
        self,
        settings: Settings,
        model: BaseChatModel | None = None,
        embedder: OpenAI | None = None,
    ) -> None:
        self.settings = settings
        self.usage = Usage()
        self.embedder = (
            embedder
            if embedder is not None
            else OpenAI(
                api_key=settings.openai_api_key.get_secret_value(),
                max_retries=0,
                timeout=60,
            )
        )
        self.model = (
            model
            if model is not None
            else ChatOpenAI(
                model=settings.llm_model,
                api_key=settings.openai_api_key,
                max_completion_tokens=settings.llm_max_output_tokens,
                max_retries=0,
                timeout=60,
            )
        )

    def invoke(self, messages: list[BaseMessage], schema: type[Output]) -> Output:
        if self.usage.cost_usd is None:
            raise LLMError("Previous call cost is unknown; further calls are blocked")
        # shortcut: byte-based admission estimate, use provider counting when available.
        input_estimate = (
            len(
                json.dumps(
                    [message.content for message in messages]
                    + [schema.model_json_schema()],
                    ensure_ascii=False,
                ).encode("utf-8")
            )
            + 1024
        )
        estimated_cost = (
            input_estimate * self.settings.llm_input_usd_per_million
            + self.settings.llm_max_output_tokens
            * self.settings.llm_output_usd_per_million
        ) / 1_000_000
        if self.usage.cost_usd + estimated_cost > self.settings.max_cost_per_run_usd:
            raise LLMError(
                "Run budget cannot cover the estimated request; call blocked"
            )

        structured = self.model.with_structured_output(
            schema.model_json_schema(),
            method="json_schema",
            strict=True,
            include_raw=True,
        )
        with trace("structured_llm", run_type="llm", inputs={}) as span:
            self.usage.calls += 1
            try:
                # Trace this sanitized wrapper, not SDK exceptions containing raw data.
                with tracing_context(enabled=False):
                    response = structured.invoke(messages)
            except Exception:
                self.usage.cost_usd = None
                raise LLMError("Provider call failed; cost is unknown") from None

            raw = response.get("raw")
            try:
                counts = TokenCounts.model_validate(
                    getattr(raw, "usage_metadata", None) or {}
                )
            except ValidationError:
                self.usage.cost_usd = None
                raise LLMError(
                    "Provider usage is missing or invalid; cost is unknown"
                ) from None
            self.usage.input_tokens += counts.input_tokens
            self.usage.output_tokens += counts.output_tokens
            self.usage.cost_usd += (
                counts.input_tokens * self.settings.llm_input_usd_per_million
                + counts.output_tokens * self.settings.llm_output_usd_per_million
            ) / 1_000_000
            span.add_metadata(self.usage.model_dump(mode="json"))
            if self.usage.cost_usd > self.settings.max_cost_per_run_usd:
                raise LLMError("Run budget exceeded after provider usage accounting")
            if response.get("parsing_error") is not None:
                raise LLMError("Model returned invalid structured output")
            try:
                result = schema.model_validate(response.get("parsed"))
            except ValidationError:
                raise LLMError("Model returned invalid structured output") from None
            span.end(outputs={"validated": True})
            return result

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self.usage.cost_usd is None:
            raise LLMError("Previous call cost is unknown; further calls are blocked")
        price = self.settings.embedding_usd_per_million
        # Bytes bound tokens from above for these English inputs.
        estimate = sum(len(text.encode("utf-8")) for text in texts) * price / 1_000_000
        if self.usage.cost_usd + estimate > self.settings.max_cost_per_run_usd:
            raise LLMError(
                "Run budget cannot cover the estimated request; call blocked"
            )
        with trace("embeddings", run_type="embedding", inputs={}) as span:
            self.usage.calls += 1
            try:
                with tracing_context(enabled=False):
                    response = self.embedder.embeddings.create(
                        model=self.settings.embedding_model, input=texts
                    )
                tokens = TokenCounts(
                    input_tokens=response.usage.prompt_tokens, output_tokens=0
                ).input_tokens
            except Exception:
                self.usage.cost_usd = None
                raise LLMError("Embedding call failed; cost is unknown") from None
            self.usage.input_tokens += tokens
            self.usage.cost_usd += tokens * price / 1_000_000
            span.add_metadata(self.usage.model_dump(mode="json"))
            if self.usage.cost_usd > self.settings.max_cost_per_run_usd:
                raise LLMError("Run budget exceeded after provider usage accounting")
            if len(response.data) != len(texts):
                raise LLMError("Provider returned a different number of embeddings")
            indexed = sorted(response.data, key=lambda item: item.index)
            if [item.index for item in indexed] != list(range(len(texts))):
                raise LLMError("Provider returned invalid embedding indices")
            vectors = [item.embedding for item in indexed]
            dimensions = len(vectors[0])
            if not dimensions or any(
                len(vector) != dimensions
                or not all(math.isfinite(value) for value in vector)
                or not any(vector)
                for vector in vectors
            ):
                raise LLMError("Provider returned invalid embedding vectors")
            span.end(outputs={"count": len(vectors)})
            return vectors
