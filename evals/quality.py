"""Deterministic scoring; model calls belong to the shared application helper."""

import math
from collections.abc import Sequence


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("Embedding dimensions must match and be nonempty")
    if not all(math.isfinite(value) for value in (*left, *right)):
        raise ValueError("Embeddings must contain finite numbers")
    norm = math.hypot(*left) * math.hypot(*right)
    return sum(a * b for a, b in zip(left, right, strict=True)) / norm if norm else 0.0


# Calibrated for embeddinggemma:300m on hand-checked pairs; recalibrate per model.
MATCH_THRESHOLD = 0.58


def match_requirements(
    predicted: Sequence[Sequence[float]],
    gold: Sequence[Sequence[float]],
    threshold: float = MATCH_THRESHOLD,
) -> list[tuple[int, int]]:
    """Greedy one-to-one matching: most similar pairs above the threshold first."""
    scores = sorted(
        (
            (cosine_similarity(vector, reference), i, j)
            for i, vector in enumerate(predicted)
            for j, reference in enumerate(gold)
        ),
        reverse=True,
    )
    pairs: list[tuple[int, int]] = []
    for score, i, j in scores:
        if score < threshold:
            break
        if all(i != p and j != g for p, g in pairs):
            pairs.append((i, j))
    return sorted(pairs)


def percentile95(values: list[float]) -> float | None:
    return sorted(values)[math.ceil(0.95 * len(values)) - 1] if values else None


def baseline_failures(baseline: dict, *, full: bool = False) -> list[str]:
    expected_mode = "full" if full else "rag"
    failures = []
    if baseline.get("mode", expected_mode) != expected_mode:
        failures.append("Baseline scope does not match evaluation mode")
    names = ["conflict_f1"]
    if full:
        names += ["requirement_precision", "requirement_recall"]
    for name in names:
        value = baseline["metrics"].get(name)
        if value is None or not math.isfinite(value) or not 0 <= value <= 1:
            failures.append(f"{name}: fixed baseline must be measured and within 0-1")
    tolerance = baseline.get("tolerance")
    if tolerance is None or not math.isfinite(tolerance) or not 0 <= tolerance <= 1:
        failures.append("Baseline tolerance must be finite and within 0-1")
    return failures


def check_thresholds(metrics: dict, baseline: dict, *, full: bool = False) -> list[str]:
    """Never replace missing measurements with passing defaults."""
    names = ["conflict_f1"]
    if full:
        names += ["requirement_precision", "requirement_recall"]
    setup_failures = baseline_failures(baseline, full=full)
    failures = setup_failures.copy()
    if metrics.get("error_cases"):
        failures.append("One or more evaluation cases failed")
    if metrics.get("incomplete_reason"):
        failures.append("Evaluation is incomplete")
    if (
        metrics.get("requested_cases_n") is not None
        and metrics.get("cases_n") != metrics["requested_cases_n"]
    ):
        failures.append("Evaluation did not measure every requested case")
    if baseline.get("case_ids") is not None and set(metrics.get("case_ids", [])) != set(
        baseline["case_ids"]
    ):
        failures.append("Baseline and evaluation case cohorts differ")
    for name in names:
        observed = metrics.get(name)
        reference = baseline["metrics"].get(name)
        if observed is None or reference is None:
            failures.append(f"{name}: measurement or fixed baseline missing")
        elif not math.isfinite(observed) or not 0 <= observed <= 1:
            failures.append(f"{name}: metric must be finite and within 0-1")
        elif not setup_failures and observed < reference - baseline["tolerance"]:
            failures.append(
                f"{name}: {observed:.3f} below {reference - baseline['tolerance']:.3f}"
            )
    if full:
        if metrics.get("grounding_rate") != 1.0:
            failures.append("grounding_rate must be 1.0 on nonempty output")
        quality = metrics.get("story_quality")
        if quality is None or not math.isfinite(quality) or not 3.5 <= quality <= 5:
            failures.append("story_quality must be measured and at least 3.5")
        if not metrics.get("judge_calibrated"):
            failures.append("judge requires calibration against ten manual scores")
    return failures
