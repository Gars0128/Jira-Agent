import json
import sys
from contextlib import nullcontext
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "evals"))

import run_evals  # noqa: E402
from quality import check_thresholds, match_requirements, percentile95  # noqa: E402
from sync_dataset import dataset_examples  # noqa: E402


def test_matching_is_one_to_one_and_finds_maximum_cardinality():
    assert match_requirements([[1, 0], [0.7, 0.7]], [[1, 0], [0.8, -0.6]], 0.7) == [
        (0, 1),
        (1, 0),
    ]
    assert len(match_requirements([[1, 0], [1, 0]], [[1, 0]])) == 1
    assert match_requirements([[0, 1]], [[1, 0]]) == []
    assert match_requirements([], []) == []


@pytest.mark.parametrize("vector", [[float("nan"), 0], [float("inf"), 0], [1]])
def test_matching_rejects_bad_embeddings(vector):
    with pytest.raises(ValueError):
        match_requirements([vector], [[1, 0]])


def test_gate_requires_measurements_and_does_not_accept_nan():
    baseline = {"metrics": {"conflict_f1": 0.8}, "tolerance": 0.05}
    assert check_thresholds({"conflict_f1": 0.76}, baseline) == []
    assert check_thresholds({"conflict_f1": 0.7}, baseline)
    assert check_thresholds({"conflict_f1": float("nan")}, baseline)
    assert check_thresholds({"conflict_f1": 0.9}, baseline, full=True)


def test_poor_model_result_fails_cli_without_rewriting_baseline(monkeypatch, tmp_path):
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps({"metrics": {"conflict_f1": 0.8}, "tolerance": 0.05})
    )
    before = baseline.read_bytes()
    monkeypatch.setattr(run_evals, "evaluate", lambda _: {"conflict_f1": 0.0})
    monkeypatch.setattr(
        sys, "argv", ["run_evals.py", "--check", "--baseline", str(baseline)]
    )
    assert run_evals.main() == 1
    assert baseline.read_bytes() == before


def test_empty_output_cannot_pass_full_gate():
    baseline = {
        "metrics": {
            "conflict_f1": 0.8,
            "requirement_precision": 0.8,
            "requirement_recall": 0.8,
        },
        "tolerance": 0.05,
    }
    assert check_thresholds(
        {"conflict_f1": 1.0, "grounding_rate": None}, baseline, full=True
    )


def test_calibration_requires_ten_distinct_real_scores(tmp_path):
    path = tmp_path / "calibration.json"
    path.write_text(json.dumps({"approved": True, "scores": []}))
    assert run_evals.calibration_status(path) == (False, None)
    rows = [{"example_id": str(i), "human": 4, "judge": 5} for i in range(10)]
    path.write_text(json.dumps({"approved": True, "scores": rows}))
    assert run_evals.calibration_status(path) == (True, 1.0)
    rows[0]["human"] = 7
    path.write_text(json.dumps({"approved": True, "scores": rows}))
    with pytest.raises(ValueError):
        run_evals.calibration_status(path)


def test_latency_uses_nearest_rank_and_reports_missing_sample():
    assert percentile95([]) is None
    assert percentile95(list(range(1, 101))) == 95


def test_dataset_upload_contains_only_repeatable_fictional_gold_examples():
    examples = dataset_examples("test")
    assert len(examples) == 12
    assert examples == dataset_examples("test")
    assert len({row["id"] for row in examples}) == 12
    assert all(row["metadata"]["fictional"] for row in examples)
    assert all(row["inputs"]["project_id"] == "harbor-desk" for row in examples)
    assert all(row["inputs"]["transcript"].strip() for row in examples)


def test_evaluation_total_budget_blocks_next_case_before_model_call(
    monkeypatch, tmp_path
):
    directory = tmp_path / "evals" / "cases"
    directory.mkdir(parents=True)
    (tmp_path / "spec.md").write_text("## HD-TEST\nTest rule.")
    (directory / "case.json").write_text(
        json.dumps(
            {
                "id": "test",
                "project_id": "test",
                "spec_path": "spec.md",
                "transcript": "Test",
                "requirements": [],
            }
        )
    )
    calibration = tmp_path / "calibration.json"
    calibration.write_text(json.dumps({"approved": False, "scores": []}))
    settings = SimpleNamespace(
        max_cost_per_run_usd=Decimal("0.30"), daily_budget_usd=Decimal("0.20")
    )
    monkeypatch.setattr(run_evals, "ROOT", tmp_path)
    monkeypatch.setattr(run_evals, "Settings", lambda: settings)
    monkeypatch.setattr(run_evals, "connect", lambda _: nullcontext(None))
    monkeypatch.setattr(run_evals, "ingest", lambda *args: None)
    monkeypatch.setattr(
        run_evals,
        "LLMHelper",
        lambda _: SimpleNamespace(usage=SimpleNamespace(cost_usd=Decimal("0"))),
    )
    result = run_evals.evaluate(
        SimpleNamespace(
            limit=None,
            mode="rag",
            calibration=calibration,
            output=None,
            judge=False,
        )
    )
    assert result["cases_n"] == 0
    assert result["incomplete_reason"]
    monkeypatch.setattr(run_evals, "evaluate", lambda _: result)
    monkeypatch.setattr(sys, "argv", ["run_evals.py"])
    assert run_evals.main() == 2


def test_case_failure_keeps_accounted_usage_and_safe_reason(monkeypatch):
    from app import workflow
    from app.llm import LLMError

    def fail(*args):
        raise LLMError("Stories must cover all new requirements")

    monkeypatch.setattr(
        workflow, "build_workflow", lambda *a, **kw: SimpleNamespace(invoke=fail)
    )
    usage = {"cost_usd": "0.012", "calls": 4, "input_tokens": 30, "output_tokens": 20}
    helper = SimpleNamespace(usage=SimpleNamespace(model_dump=lambda **kw: usage))
    sample = run_evals.run_case(
        {"id": "test", "project_id": "test", "transcript": "Test", "requirements": []},
        SimpleNamespace(mode="full", judge=False),
        None,
        helper,
    )
    assert sample["error"] == "Stories must cover all new requirements"
    assert sample["stage"] == "workflow"
    assert sample["usage"] == usage


def test_resume_skips_paid_samples_and_retains_aggregate_cost(monkeypatch, tmp_path):
    directory = tmp_path / "evals" / "cases"
    directory.mkdir(parents=True)
    (tmp_path / "spec.md").write_text("## HD-TEST\nTest rule.")
    for identifier in ("first", "second"):
        (directory / f"{identifier}.json").write_text(
            json.dumps(
                {
                    "id": identifier,
                    "project_id": "test",
                    "spec_path": "spec.md",
                    "transcript": "Test",
                    "requirements": [],
                }
            )
        )
    calibration = tmp_path / "calibration.json"
    calibration.write_text(json.dumps({"approved": False, "scores": []}))
    sample = {
        "id": "first",
        "requirements": [],
        "stories": [],
        "matches": [],
        "judge_ratings": [],
        "usage": {"cost_usd": "0.02"},
    }
    previous = tmp_path / "previous.json"
    previous.write_text(
        json.dumps(
            {
                "mode": "rag",
                "cost_usd": "0.02",
                "samples": [sample],
                "legacy_resume": True,
                "unknown_cost_reservation_usd": "0.30",
            }
        )
    )
    settings = SimpleNamespace(
        max_cost_per_run_usd=Decimal("0.30"), daily_budget_usd=Decimal("1")
    )
    monkeypatch.setattr(run_evals, "ROOT", tmp_path)
    monkeypatch.setattr(run_evals, "Settings", lambda: settings)
    monkeypatch.setattr(run_evals, "connect", lambda _: nullcontext(None))
    monkeypatch.setattr(run_evals, "ingest", lambda *args: None)
    monkeypatch.setattr(
        run_evals,
        "LLMHelper",
        lambda _: SimpleNamespace(usage=SimpleNamespace(cost_usd=Decimal("0.01"))),
    )
    calls = []

    def one_case(case, *args):
        calls.append(case["id"])
        return {**sample, "id": case["id"]}

    monkeypatch.setattr(run_evals, "run_case", one_case)
    result = run_evals.evaluate(
        SimpleNamespace(
            limit=None,
            mode="rag",
            calibration=calibration,
            output=None,
            judge=False,
            resume_from=previous,
        )
    )
    assert calls == ["second"]
    assert result["cases_n"] == 2
    assert result["cost_usd"] == "0.04"
    assert result["legacy_resume"] is True
    assert result["unknown_cost_reservation_usd"] == "0.30"


@pytest.mark.parametrize(
    "extra",
    [
        {"error_cases": [{"id": "failed"}]},
        {"incomplete_reason": "budget"},
        {"cases_n": 1, "requested_cases_n": 2},
    ],
)
def test_successful_subset_cannot_hide_failed_or_missing_cases(extra):
    baseline = {"metrics": {"conflict_f1": 0.8}, "tolerance": 0.05}
    assert check_thresholds({"conflict_f1": 1.0, **extra}, baseline)


def test_gate_cannot_compare_a_different_case_cohort_or_pipeline_scope():
    baseline = {
        "mode": "rag",
        "case_ids": ["first", "second"],
        "metrics": {"conflict_f1": 0.8},
        "tolerance": 0.05,
    }
    assert check_thresholds({"conflict_f1": 1.0, "case_ids": ["first"]}, baseline)
    assert check_thresholds({"conflict_f1": 1.0}, baseline, full=True)


def test_missing_full_baseline_blocks_before_paid_evaluation(monkeypatch, tmp_path):
    path = tmp_path / "baseline.json"
    path.write_text(
        json.dumps(
            {
                "mode": "full",
                "metrics": {
                    "conflict_f1": 0.8,
                    "requirement_precision": None,
                    "requirement_recall": None,
                },
                "tolerance": 0.05,
            }
        )
    )

    def paid_call_must_not_happen(_):
        raise AssertionError("Paid evaluation must not run without a usable baseline")

    monkeypatch.setattr(run_evals, "evaluate", paid_call_must_not_happen)
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_evals.py", "--mode", "full", "--check", "--baseline", str(path)],
    )
    assert run_evals.main() == 1


def test_full_case_records_cosines_without_an_additional_embedding_call(monkeypatch):
    from app import workflow
    from app.schemas import Requirement

    item = {
        "id": "R1",
        "text": "Export reports",
        "quote": "Export reports",
        "speaker": "Nora",
        "type": "functional",
        "priority": "must",
        "status": "new",
        "spec_refs": [],
        "note": None,
    }
    monkeypatch.setattr(
        workflow,
        "build_workflow",
        lambda *a, **kw: SimpleNamespace(
            invoke=lambda *a: {
                "requirements": [Requirement.model_validate(item)],
                "stories": [],
                "retrieved": {},
            }
        ),
    )
    requests = []

    def embed(texts):
        requests.append(texts)
        return [[1.0, 0.0], [0.6, 0.8]]

    helper = SimpleNamespace(
        embed=embed, usage=SimpleNamespace(model_dump=lambda **kw: {"cost_usd": "0.01"})
    )
    result = run_evals.run_case(
        {
            "id": "test",
            "project_id": "test",
            "transcript": "Export reports",
            "requirements": [item],
        },
        SimpleNamespace(mode="full", judge=False),
        None,
        helper,
    )
    assert len(requests) == 1
    assert result["matching_threshold"] == 0.8
    assert result["cosine_matrix"] == [[0.6]]
    assert result["matches"] == []


def test_unapplied_thresholds_are_not_reported_as_a_pass(monkeypatch, capsys):
    monkeypatch.setattr(run_evals, "evaluate", lambda _: {"conflict_f1": 0.1})
    monkeypatch.setattr(sys, "argv", ["run_evals.py"])
    assert run_evals.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["thresholds_applied"] is False
    assert output["threshold_failures"] is None
