import pytest

from app.grounding import filter_grounded_requirements, is_quote_grounded
from app.schemas import Requirement


@pytest.mark.parametrize(
    ("quote", "transcript", "expected"),
    [
        ("Export reports", "Nora: Export reports, please.", True),
        ("EXPORT reports", "Nora: export REPORTS, please.", True),
        ("  Export\t reports\n", "Nora: Export\n   reports, please.", True),
        ("Export reports", "Nora: Export\u00a0reports, please.", True),
        ("", "Nora: Export reports.", False),
        (" \t\n", "Nora: Export reports.", False),
        ("Export reports", "", False),
        ("Email reports", "Nora: Export reports.", False),
        ("Export reports", "Export only monthly reports", False),
        ("Export reports!", "Export reports.", False),
    ],
)
def test_quote_grounding(quote: str, transcript: str, expected: bool) -> None:
    assert is_quote_grounded(quote, transcript) is expected


def test_filter_preserves_order_objects_and_source_text() -> None:
    transcript = "Nora: Export reports.\nJun: Keep CSV."
    requirements = [
        Requirement(
            id="R1",
            text="Allow report exports.",
            type="functional",
            priority="must",
            quote="  EXPORT\t reports.  ",
            speaker="Nora",
        ),
        Requirement(
            id="R2",
            text="Send reports by email.",
            type="functional",
            priority="should",
            quote="Send reports by email.",
            speaker="Nora",
        ),
        Requirement(
            id="R3",
            text="Keep CSV.",
            type="constraint",
            priority="must",
            quote="Keep CSV.",
            speaker="Jun",
        ),
    ]
    original = [requirement.model_dump() for requirement in requirements]

    result = filter_grounded_requirements(requirements, transcript)

    assert [requirement.id for requirement in result] == ["R1", "R3"]
    assert result[0] is requirements[0]
    assert result[1] is requirements[2]
    assert [requirement.model_dump() for requirement in requirements] == original


def test_empty_or_unsupported_input_returns_no_requirements() -> None:
    requirement = Requirement(
        id="R1",
        text="Keep CSV.",
        type="constraint",
        priority="must",
        quote="Keep CSV.",
        speaker="Jun",
    )

    assert filter_grounded_requirements([], "Jun: Keep CSV.") == []
    assert filter_grounded_requirements([requirement], " \n") == []
    assert filter_grounded_requirements([requirement], "Jun: Hello.") == []
