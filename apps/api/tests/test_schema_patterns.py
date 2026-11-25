import re

import pytest

from app.schemas import ClassificationOutput, ExtractionOutput
from app.stories import CriticOutput, StoryOutput


def patterns(node: object) -> list[str]:
    if isinstance(node, dict):
        found = [node["pattern"]] if isinstance(node.get("pattern"), str) else []
        return found + [p for value in node.values() for p in patterns(value)]
    if isinstance(node, list):
        return [p for value in node for p in patterns(value)]
    return []


@pytest.mark.parametrize(
    "schema", [ExtractionOutput, ClassificationOutput, StoryOutput, CriticOutput]
)
def test_model_facing_patterns_survive_anchored_decoders(schema) -> None:
    # JSON Schema patterns are unanchored, but some providers' constrained
    # decoders (xAI) match them against the whole string: r"\S" then allows
    # exactly one character and the model returns "a" for every field.
    found = patterns(schema.model_json_schema())
    assert found
    for pattern in found:
        assert re.fullmatch(pattern, "Make the reservation form faster."), pattern
        assert not re.search(pattern, " \n\t"), pattern
