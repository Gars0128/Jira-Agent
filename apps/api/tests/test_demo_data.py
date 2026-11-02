import json
import re
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]
CASES = sorted((ROOT / "evals/cases").glob("*.json"))


def normalized(text: str) -> str:
    return " ".join(text.casefold().split())


def validate_case(case: dict[str, Any]) -> None:
    assert case["id"] and case["project_id"] == "harbor-desk"
    spec_path = (ROOT / case["spec_path"]).resolve()
    assert spec_path.is_relative_to(ROOT)
    spec = spec_path.read_text(encoding="utf-8")
    section_ids = set(re.findall(r"^## (HD-[A-Z]+)\b", spec, re.MULTILINE))
    assert ("transcript_path" in case) != ("transcript" in case)
    if "transcript_path" in case:
        source = (ROOT / case["transcript_path"]).resolve()
        assert source.is_relative_to(ROOT)
        transcript = source.read_text(encoding="utf-8")
    else:
        transcript = case["transcript"]
    assert transcript.strip()

    requirements = case["requirements"]
    ids = {item["id"] for item in requirements}
    assert len(ids) == len(requirements)
    for item in requirements:
        assert item["id"] and item["text"].strip() and item["speaker"].strip()
        assert item["type"] in {"functional", "non_functional", "constraint"}
        assert item["priority"] in {"must", "should", "could"}
        assert item["status"] in {"new", "duplicate", "conflict", "unclear"}
        assert item["spec_refs"] and set(item["spec_refs"]) <= section_ids
        quote = normalized(item["quote"])
        assert quote and quote in normalized(transcript)
        speaker_lines = [
            line.split(":", 1)[1]
            for line in transcript.splitlines()
            if line.startswith((f"{item['speaker']}:", f"{item['speaker']} ("))
            and ":" in line
        ]
        assert any(quote in normalized(line) for line in speaker_lines)
        if item["status"] in {"conflict", "unclear"}:
            assert item["note"] and case["questions"]

    stories = case["expected_stories"]
    assert len({story["id"] for story in stories}) == len(stories)
    for story in stories:
        for field in ("id", "title", "as_a", "i_want", "so_that"):
            assert story[field].strip()
        assert story["requirement_ids"] and set(story["requirement_ids"]) <= ids
        assert story["acceptance_criteria"]
        assert all(criterion.strip() for criterion in story["acceptance_criteria"])
    assert isinstance(case["questions"], list)
    assert all(question.strip() for question in case["questions"])


def test_demo_corpus() -> None:
    assert len(CASES) == 12
    cases = [json.loads(path.read_text(encoding="utf-8")) for path in CASES]
    assert len({case["id"] for case in cases}) == len(cases)
    transcripts = list((ROOT / "data/demo/harbor-desk/transcripts").glob("*.md"))
    assert len(transcripts) == 6
    assert {case["transcript_path"] for case in cases if "transcript_path" in case} == {
        path.relative_to(ROOT).as_posix() for path in transcripts
    }
    assert sum("transcript" in case for case in cases) == 6
    for case in cases:
        validate_case(case)
    requirements = [item for case in cases for item in case["requirements"]]
    assert {item["status"] for item in requirements} == {
        "new",
        "duplicate",
        "conflict",
        "unclear",
    }
    assert {
        ref
        for item in requirements
        if item["status"] == "conflict"
        for ref in item["spec_refs"]
    } == {"HD-EXPORT", "HD-AUDIT", "HD-ACCESS", "HD-BOOKING"}
    assert any(not case["requirements"] for case in cases)


@pytest.mark.parametrize("corruption", ["quote", "speaker", "spec_ref", "story_ref"])
def test_rejects_corrupted_gold(corruption: str) -> None:
    case = json.loads(CASES[0].read_text(encoding="utf-8"))
    if corruption == "quote":
        case["requirements"][0]["quote"] = "This quotation was invented."
    elif corruption == "speaker":
        case["requirements"][0]["speaker"] = "Not the speaker"
    elif corruption == "spec_ref":
        case["requirements"][0]["spec_refs"] = ["HD-MISSING"]
    else:
        case["expected_stories"][0]["requirement_ids"] = ["R-MISSING"]
    with pytest.raises(AssertionError):
        validate_case(case)
