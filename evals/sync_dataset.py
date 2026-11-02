"""Explicitly upload the fictional gold corpus to a LangSmith dataset."""

import argparse
import json
import logging
import sys
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))

from langsmith import Client  # noqa: E402

from app.config import Settings  # noqa: E402


def dataset_examples(dataset_name: str) -> list[dict]:
    examples = []
    for path in sorted((ROOT / "evals/cases").glob("*.json")):
        case = json.loads(path.read_text("utf-8"))
        transcript = case.get("transcript") or (
            ROOT / case["transcript_path"]
        ).read_text("utf-8")
        examples.append(
            {
                "id": str(
                    uuid5(NAMESPACE_URL, f"discovery-jira/{dataset_name}/{case['id']}")
                ),
                "inputs": {"project_id": case["project_id"], "transcript": transcript},
                "outputs": {
                    key: case[key]
                    for key in ("requirements", "expected_stories", "questions")
                },
                "metadata": {"case_id": case["id"], "fictional": True},
            }
        )
    return examples


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="discovery-jira-gold-v1")
    args = parser.parse_args()
    logging.getLogger("langsmith").handlers = [logging.NullHandler()]
    logging.getLogger("langsmith").propagate = False
    client = None
    try:
        settings = Settings()
        if settings.langsmith_api_key is None:
            raise ValueError("LangSmith key missing")
        client = Client(
            api_key=settings.langsmith_api_key.get_secret_value(),
            api_url=settings.langsmith_endpoint,
            workspace_id=settings.langsmith_workspace_id,
            timeout_ms=5000,
        )
        dataset = (
            client.read_dataset(dataset_name=args.dataset)
            if client.has_dataset(dataset_name=args.dataset)
            else client.create_dataset(
                args.dataset,
                description="Fictional Harbor Desk cases; manually labeled corpus.",
            )
        )
        examples = dataset_examples(args.dataset)
        client.create_examples(dataset_id=dataset.id, examples=examples)
        print(json.dumps({"dataset": args.dataset, "examples_n": len(examples)}))
        return 0
    except Exception:
        print(
            json.dumps({"error": "Dataset sync failed; check LangSmith configuration"}),
            file=sys.stderr,
        )
        return 1
    finally:
        if client is not None:
            try:
                client.close(timeout=0)
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
