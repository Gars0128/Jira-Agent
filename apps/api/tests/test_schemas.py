from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas import Requirement


@pytest.fixture
def requirement_data() -> dict[str, Any]:
    return {
        "id": "R1",
        "text": "Allow coordinators to export reports.",
        "type": "functional",
        "priority": "must",
        "quote": "  Coordinators must be allowed to export reservation reports too.  ",
        "speaker": "Nora",
    }


def test_extracted_requirement_preserves_quote_and_defaults(
    requirement_data: dict[str, Any],
) -> None:
    requirement = Requirement.model_validate(requirement_data)

    assert requirement.quote == requirement_data["quote"]
    assert requirement.status is None
    assert requirement.spec_refs == []
    assert requirement.note is None
    assert Requirement.model_validate_json(requirement.model_dump_json()) == requirement


@pytest.mark.parametrize("field", ["id", "text", "quote", "speaker"])
@pytest.mark.parametrize("value", ["", " \t\n"])
def test_rejects_blank_required_text(
    requirement_data: dict[str, Any], field: str, value: str
) -> None:
    requirement_data[field] = value

    with pytest.raises(ValidationError) as error:
        Requirement.model_validate(requirement_data)

    assert error.value.errors()[0]["loc"] == (field,)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("type", "feature"),
        ("priority", "urgent"),
        ("status", "approved"),
        ("quote", 123),
        ("spec_refs", "HD-EXPORT"),
        ("spec_refs", [" "]),
        ("unexpected", "silently ignored"),
    ],
)
def test_rejects_invalid_contract_values(
    requirement_data: dict[str, Any], field: str, value: Any
) -> None:
    requirement_data[field] = value

    with pytest.raises(ValidationError) as error:
        Requirement.model_validate(requirement_data)

    assert error.value.errors()[0]["loc"][0] == field


def test_requires_quote(requirement_data: dict[str, Any]) -> None:
    del requirement_data["quote"]

    with pytest.raises(ValidationError) as error:
        Requirement.model_validate(requirement_data)

    assert error.value.errors()[0]["loc"] == ("quote",)


def test_spec_refs_are_independent(requirement_data: dict[str, Any]) -> None:
    first = Requirement.model_validate(requirement_data)
    second = Requirement.model_validate(requirement_data)

    first.spec_refs.append("HD-EXPORT")

    assert second.spec_refs == []


@pytest.mark.parametrize(
    ("as_a", "i_want", "so_that"),
    [
        ("As a cooperative lead", "I want reports", "so that I can plan"),
        ("A cooperative lead", "I want reports", "So that I can plan"),
        ("cooperative lead", "reports", "I can plan"),
    ],
)
def test_story_drops_template_words_the_renderers_add(
    as_a: str, i_want: str, so_that: str
) -> None:
    from app.stories import StoryDraft

    story = StoryDraft(
        id="S1",
        title="Reports",
        as_a=as_a,
        i_want=i_want,
        so_that=so_that,
        acceptance_criteria=["Given x, when y, then z."],
        requirement_ids=["R1"],
    )
    # UI and Jira render "As a {as_a}, I want {i_want}, so that {so_that}".
    assert (story.as_a, story.i_want, story.so_that) == (
        "cooperative lead",
        "reports",
        "I can plan",
    )
