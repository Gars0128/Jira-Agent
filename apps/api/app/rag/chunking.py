import re

from pydantic import BaseModel

HEADING = re.compile(r"^## +(.+)$", re.MULTILINE)
SECTION_ID = re.compile(r"[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+")
MAX_CHARS = 2000


class SpecChunk(BaseModel):
    id: str
    heading: str
    text: str


def _section_id(heading: str) -> str:
    first = heading.split()[0]
    if SECTION_ID.fullmatch(first):
        return first
    return re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-") or "section"


def _split(text: str, max_chars: int) -> list[str]:
    parts: list[str] = []
    for paragraph in text.split("\n\n"):
        # A single oversized paragraph is cut at fixed character offsets.
        for start in range(0, len(paragraph), max_chars):
            piece = paragraph[start : start + max_chars]
            if parts and len(parts[-1]) + 2 + len(piece) <= max_chars:
                parts[-1] += "\n\n" + piece
            else:
                parts.append(piece)
    return parts


def chunk_spec(markdown: str, max_chars: int = MAX_CHARS) -> list[SpecChunk]:
    matches = list(HEADING.finditer(markdown))
    sections = []
    intro = markdown[: matches[0].start() if matches else len(markdown)].strip()
    if intro:
        sections.append(("intro", "Introduction", intro))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else None
        heading = match.group(1).strip()
        sections.append(
            (_section_id(heading), heading, markdown[match.start() : end].strip())
        )

    chunks = []
    for section_id, heading, text in sections:
        parts = _split(text, max_chars)
        for number, part in enumerate(parts, start=1):
            chunk_id = section_id if len(parts) == 1 else f"{section_id}#{number}"
            chunks.append(SpecChunk(id=chunk_id, heading=heading, text=part))
    ids = [chunk.id for chunk in chunks]
    if len(set(ids)) != len(ids):
        raise ValueError("Specification headings produce duplicate chunk IDs")
    return chunks
