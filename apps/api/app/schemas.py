from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# Anchored on purpose: some constrained decoders (xAI) match patterns against the
# whole string, where an unanchored r"\S" would allow exactly one character.
NonBlankString = Annotated[str, StringConstraints(pattern=r"^\s*\S[\s\S]*$")]


class ExtractedRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: NonBlankString
    text: NonBlankString
    type: Literal["functional", "non_functional", "constraint"]
    priority: Literal["must", "should", "could"]
    quote: NonBlankString
    speaker: NonBlankString


class Requirement(ExtractedRequirement):
    status: Literal["new", "duplicate", "conflict", "unclear"] | None = None
    spec_refs: list[NonBlankString] = Field(default_factory=list)
    note: str | None = None


class ExtractionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    requirements: list[ExtractedRequirement]


class Classification(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: NonBlankString
    status: Literal["new", "duplicate", "conflict", "unclear"]
    spec_refs: list[NonBlankString]
    note: str


class ClassificationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    classifications: list[Classification]
