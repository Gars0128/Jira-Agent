import re

from app.schemas import Requirement


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def is_quote_grounded(quote: str, transcript: str) -> bool:
    normalized_quote = _normalize(quote)
    # Evidence is whole words: at least two, not starting or ending inside a word.
    # A bare substring check accepted "a", which occurs in almost any transcript.
    if len(normalized_quote.split()) < 2:
        return False
    pattern = rf"(?<!\w){re.escape(normalized_quote)}(?!\w)"
    return re.search(pattern, _normalize(transcript)) is not None


def filter_grounded_requirements(
    requirements: list[Requirement], transcript: str
) -> list[Requirement]:
    return [
        requirement
        for requirement in requirements
        if is_quote_grounded(requirement.quote, transcript)
    ]
