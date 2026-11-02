from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from app.llm import Usage
from app.rag.retrieve import RetrievedChunk
from app.schemas import Requirement
from app.stories import Story


class TicketResult(BaseModel):
    key: str
    dry_run: bool
    reused: bool
    fields: dict[str, JsonValue] | None = None


class RunResult(BaseModel):
    # Checkpoints contain internal state; the HTTP response is an explicit allowlist.
    model_config = ConfigDict(extra="ignore")

    run_id: str
    status: Literal["queued", "running", "awaiting_review", "done", "error"]
    requirements: list[Requirement]
    stories: list[Story]
    questions: list[str]
    retrieved: dict[str, list[RetrievedChunk]]
    usage: Usage
    latency_ms: int = Field(ge=0)
    trace_url: str | None
    tickets: list[TicketResult]
    error: str | None
    cached: bool
    trace_warning: str | None = None
    critic_feedback: list[str] = Field(default_factory=list)
    dropped_requirement_ids: list[str] = Field(default_factory=list)
