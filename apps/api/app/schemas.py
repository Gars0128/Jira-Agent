from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonBlankString = Annotated[str, StringConstraints(pattern=r"\S")]


class Requirement(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: NonBlankString
    text: NonBlankString
    type: Literal["functional", "non_functional", "constraint"]
    priority: Literal["must", "should", "could"]
    quote: NonBlankString
    speaker: NonBlankString
    status: Literal["new", "duplicate", "conflict", "unclear"] | None = None
    spec_refs: list[NonBlankString] = Field(default_factory=list)
    note: str | None = None
