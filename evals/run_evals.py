"""Phase 5 evals on gold requirements: retrieval recall@5 and classification.

Run from apps/api:
  python -m uv run --env-file ../../.env python ../../evals/run_evals.py
Thresholds come in phase 10; this script reports metrics with N only.
"""

import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))

from app.config import Settings  # noqa: E402
from app.graph.graph import classify_requirements, retrieve_spec_chunks  # noqa: E402
from app.llm import LLMHelper  # noqa: E402
from app.rag.chunking import chunk_spec  # noqa: E402
from app.rag.ingest import connect, ingest  # noqa: E402
from app.rag.retrieve import retrieve  # noqa: E402
from app.schemas import ExtractedRequirement, Requirement  # noqa: E402

FIELDS = set(ExtractedRequirement.model_fields)


def main() -> int:
    settings = Settings()
    cases = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((ROOT / "evals/cases").glob("*.json"))
    ]
    hits = total = correct = labelled = 0
    tp = fp = fn = 0
    cost = Decimal("0")
    misses = []
    with connect(settings) as conn:
        for spec_path, project in {(c["spec_path"], c["project_id"]) for c in cases}:
            spec = (ROOT / spec_path).read_text(encoding="utf-8")
            ingest_helper = LLMHelper(settings)
            ingest(conn, project, chunk_spec(spec), ingest_helper)
            cost += ingest_helper.usage.cost_usd
        for case in cases:
            if not case["requirements"]:
                continue
            helper = LLMHelper(settings)
            gold = {item["id"]: item for item in case["requirements"]}
            requirements = [
                Requirement.model_validate({k: item[k] for k in FIELDS})
                for item in case["requirements"]
            ]

            def search(queries: list[str]) -> list:
                return retrieve(conn, helper, case["project_id"], queries)

            retrieved = retrieve_spec_chunks(search, requirements)
            for item in requirements:
                top = {chunk.id.split("#")[0] for chunk in retrieved[item.id]}
                total += 1
                found = set(gold[item.id]["spec_refs"]) <= top
                hits += found
                if not found:
                    misses.append(f"{case['id']} {item.id}: retrieval top5={top}")
            for item in classify_requirements(helper, requirements, retrieved):
                expected = gold[item.id]["status"]
                labelled += 1
                correct += item.status == expected
                tp += item.status == expected == "conflict"
                fp += item.status == "conflict" != expected
                fn += expected == "conflict" != item.status
                if item.status != expected:
                    misses.append(
                        f"{case['id']} {item.id}: gold={expected} got={item.status}"
                        f" refs={item.spec_refs} note={item.note}"
                    )
            cost += helper.usage.cost_usd
    f1 = 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else 1.0
    print(
        json.dumps(
            {
                "retrieval_recall_at_5": f"{hits / total:.2f} on N={total}",
                "status_accuracy": f"{correct / labelled:.2f} on N={labelled}",
                "conflict_f1": f"{f1:.2f} (tp={tp} fp={fp} fn={fn})",
                "cost_usd": str(cost),
                "misses": misses,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
