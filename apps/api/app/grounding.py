from app.schemas import Requirement


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def is_quote_grounded(quote: str, transcript: str) -> bool:
    normalized_quote = _normalize(quote)
    return bool(normalized_quote) and normalized_quote in _normalize(transcript)


def filter_grounded_requirements(
    requirements: list[Requirement], transcript: str
) -> list[Requirement]:
    return [
        requirement
        for requirement in requirements
        if is_quote_grounded(requirement.quote, transcript)
    ]
