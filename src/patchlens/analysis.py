"""Auditable diagnostics and paired, group-aware model comparisons."""
from __future__ import annotations

import math
import re

import numpy as np

from .data import Example, audit
from .metrics import binary_metrics, checked, wilson


def validate_report(report: dict) -> dict:
    """Verify source identity and exact score coverage before derived analysis."""
    if not isinstance(report, dict) or report.get("schema_version") != "1.0" or report.get("project") != "PatchLens":
        raise ValueError("Expected a PatchLens schema 1.0 report")
    try:
        samples = [Example.from_dict(row) for row in report["samples"]]
        dataset = audit(samples)
        if dataset["fingerprint"] != report["dataset"]["fingerprint"]:
            raise ValueError("Dataset fingerprint does not match the actual examples")
        ids = {s.id for s in samples}
        run_ids = set()
        if not isinstance(report["runs"], list) or not 1 <= len(report["runs"]) <= 20:
            raise ValueError("Expected 1–20 runs")
        for run in report["runs"]:
            if not isinstance(run["id"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", run["id"]) or run["id"] in run_ids:
                raise ValueError("Run identifiers must be valid and unique")
            run_ids.add(run["id"])
            threshold = run["threshold"]
            if type(threshold) not in (int, float) or not math.isfinite(threshold) or not 0 <= threshold <= 1:
                raise ValueError("Invalid operating threshold")
            if run["operating_point"]["source_split"] != "validation":
                raise ValueError("Operating thresholds must originate from validation")
            if run["operating_point"]["threshold"] != threshold:
                raise ValueError("Operating threshold and its provenance disagree")
            predictions = run["predictions"]
            if len(predictions) != len(ids) or {p["id"] for p in predictions} != ids:
                raise ValueError("Predictions must cover exact example IDs once")
            checked([0] * len(predictions), [p["score"] for p in predictions])
            checked([0] * len(predictions), [p["view_score"] for p in predictions])
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("Incomplete or malformed report") from error
    return report


def calibration(labels, scores, bins: int = 10) -> dict:
    """Equal-width probability bins; empty bins remain explicit."""
    y, p = checked(labels, scores)
    if type(bins) is not int or not 2 <= bins <= 20:
        raise ValueError("Calibration requires 2–20 bins")
    memberships = np.minimum((p * bins).astype(int), bins - 1)
    rows = []
    ece = 0.
    for i in range(bins):
        selected = memberships == i
        n = int(selected.sum())
        predicted = float(p[selected].mean()) if n else None
        observed = float(y[selected].mean()) if n else None
        if n:
            ece += n / len(y) * abs(predicted - observed)
        rows.append({"lower": i / bins, "upper": (i + 1) / bins, "n": n,
                     "mean_score": predicted, "observed_rate": observed,
                     "observed_wilson_95": wilson(int(y[selected].sum()), n)})
    clipped = np.clip(p, 1e-15, 1 - 1e-15)
    return {"n": len(y), "bin_count": bins, "ece": ece,
            "brier": float(np.mean((p - y) ** 2)),
            "log_loss": float(-np.mean(y * np.log(clipped) + (1 - y) * np.log(1 - clipped))),
            "bins": rows,
            "interpretation": "Descriptive only; bins on a small authored corpus do not establish calibrated probabilities"}


def _select(report, run_id, split):
    if split not in {"train", "validation", "test"}:
        raise ValueError("Unknown evaluation split")
    run = next((r for r in report["runs"] if r["id"] == run_id), None)
    if run is None:
        raise ValueError(f"Unknown run: {run_id}")
    rows = [s for s in report["samples"] if s["split"] == split]
    return run, rows, {p["id"]: p for p in run["predictions"]}


def _metrics(rows, predictions, threshold):
    result = binary_metrics([s["label"] for s in rows], [predictions[s["id"]]["score"] for s in rows], threshold)
    tp, tn, fp, fn = (result[k] for k in ("tp", "tn", "fp", "fn"))
    denominator = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    result["mcc"] = (tp * tn - fp * fn) / denominator if denominator else None
    result["balanced_accuracy"] = (tp / (tp + fn) + tn / (tn + fp)) / 2 if (tp + fn) and (tn + fp) else None
    return result


def analyze_report(report, run_id="weighted", split="test", bins=10) -> dict:
    validate_report(report)
    run, rows, predictions = _select(report, run_id, split)
    pairs, grouped_pairs = [], {}
    for row in rows:
        grouped_pairs.setdefault(row["pair_id"], []).append(row)
    for pair_id, pair in sorted(grouped_pairs.items()):
        vulnerable = next(s for s in pair if s["label"] == 1)
        corrected = next(s for s in pair if s["label"] == 0)
        margin = predictions[vulnerable["id"]]["score"] - predictions[corrected["id"]]["score"]
        pairs.append({"pair_id": pair_id, "title": vulnerable["title"], "cwe": vulnerable["cwe"],
                      "score_margin": margin, "ordering": "expected" if margin > 0 else "reversed" if margin < 0 else "tied"})
    return {"schema_version": "1.0", "kind": "diagnostics", "experiment_id": report["experiment_id"],
            "dataset_sha256": report["dataset"]["fingerprint"], "run_id": run_id, "split": split,
            "threshold_source": "validation", "metrics": _metrics(rows, predictions, run["threshold"]),
            "calibration": calibration([s["label"] for s in rows], [predictions[s["id"]]["score"] for s in rows], bins),
            "by_cwe": {c: _metrics([s for s in rows if s["cwe"] == c], predictions, run["threshold"])
                       for c in sorted({s["cwe"] for s in rows})},
            "pair_margins": sorted(pairs, key=lambda p: (p["score_margin"], p["pair_id"]))}


def compare_reports(baseline, candidate, baseline_run="linear", candidate_run="weighted", split="test", draws=1000, seed=17):
    validate_report(baseline)
    validate_report(candidate)
    left = sorted(baseline["samples"], key=lambda s: s["id"])
    right = sorted(candidate["samples"], key=lambda s: s["id"])
    if baseline["dataset"]["fingerprint"] != candidate["dataset"]["fingerprint"] or left != right:
        raise ValueError("Comparison requires identical source, labels, groups and split assignments")
    if type(draws) is not int or not 200 <= draws <= 2000 or type(seed) is not int or seed < 0:
        raise ValueError("Use 200–2000 bootstrap draws and a nonnegative integer seed")
    a, rows, pa = _select(baseline, baseline_run, split)
    b, _, pb = _select(candidate, candidate_run, split)
    changes = []
    for row in rows:
        score_a, score_b = pa[row["id"]]["score"], pb[row["id"]]["score"]
        correct_a, correct_b = int(score_a >= a["threshold"]) == row["label"], int(score_b >= b["threshold"]) == row["label"]
        changes.append({"id": row["id"], "pair_id": row["pair_id"], "group_id": row["group_id"],
                        "title": row["title"], "cwe": row["cwe"], "label": row["label"],
                        "baseline_score": score_a, "candidate_score": score_b,
                        "baseline_correct": correct_a, "candidate_correct": correct_b,
                        "outcome": "improved" if correct_b and not correct_a else "regressed" if correct_a and not correct_b else "both_correct" if correct_a else "both_wrong"})
    group_totals = {}
    for change in changes:
        total = group_totals.setdefault(change["group_id"], [0, 0])
        total[0] += int(change["candidate_correct"]) - int(change["baseline_correct"])
        total[1] += 1
    groups = sorted(group_totals)
    grouped = np.array([group_totals[group] for group in groups], dtype=float)
    rng = np.random.default_rng(seed)
    deltas = []
    # Bounded batches preserve the whole group and avoid quadratic memory growth.
    for start in range(0, draws, 100):
        selected = rng.integers(0, len(groups), size=(min(100, draws - start), len(groups)))
        totals = grouped[selected].sum(axis=1)
        deltas.extend((totals[:, 0] / totals[:, 1]).tolist())
    metrics_a, metrics_b = _metrics(rows, pa, a["threshold"]), _metrics(rows, pb, b["threshold"])
    return {"schema_version": "1.0", "kind": "paired_comparison", "dataset_sha256": baseline["dataset"]["fingerprint"],
            "split": split, "n": len(rows), "groups": len(groups),
            "baseline": {"experiment_id": baseline["experiment_id"], "run_id": baseline_run, "metrics": metrics_a},
            "candidate": {"experiment_id": candidate["experiment_id"], "run_id": candidate_run, "metrics": metrics_b},
            "outcomes": {key: sum(c["outcome"] == key for c in changes) for key in ("improved", "regressed", "both_correct", "both_wrong")},
            "accuracy_delta": metrics_b["accuracy"] - metrics_a["accuracy"],
            "bootstrap": {"unit": "group_id", "draws": draws, "seed": seed,
                          "accuracy_delta_percentile_95": np.quantile(deltas, [.025, .975]).tolist(),
                          "interpretation": "Exploratory paired group bootstrap on the same split; few groups and authored data limit generalization"},
            "changes": changes}
