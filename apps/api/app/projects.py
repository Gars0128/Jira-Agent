from pathlib import Path


def demo_root() -> Path:
    # The release image copies demo data beside app; source checkout keeps it at root.
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "data" / "demo"
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError("Demo corpus is not installed")


def transcripts(project_id: str) -> list[dict]:
    return [
        {
            "id": path.stem,
            "name": path.stem.replace("-", " ").title(),
            "text": path.read_text(encoding="utf-8"),
        }
        for path in sorted((demo_root() / project_id / "transcripts").glob("*.md"))
    ]


def projects() -> list[dict]:
    return [
        {
            "id": "harbor-desk",
            "name": "Harbor Desk (with specification)",
            "spec": True,
            "transcripts": transcripts("harbor-desk"),
        },
        {
            "id": "general",
            "name": "Any conversation",
            "spec": False,
            "transcripts": transcripts("general"),
        },
    ]


def find_project(project_id: str) -> dict | None:
    return next((item for item in projects() if item["id"] == project_id), None)
