"""Attach actual external results without changing stored reference predictions."""
import copy
import re
import numpy as np
from .cli import match_predictions
from .data import Example, audit
from .experiment import projection, split_summaries
from .io import fingerprint
from .metrics import choose_threshold


def attach_predictions(report, predictions, *, run_id, name, provenance, max_fpr=.2, embeddings=None, history=None):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", run_id):
        raise ValueError("Invalid run ID")
    if not name or len(name) > 150 or not provenance:
        raise ValueError("A model name and provenance are required")
    if any(run["id"] == run_id for run in report["runs"]):
        raise ValueError("Run ID already exists")
    if len(report["runs"]) >= 20:
        raise ValueError("Workbench supports at most 20 models")
    samples = [Example.from_dict(s) for s in report["samples"]]
    info = audit(samples)
    if info["fingerprint"] != report["dataset"]["fingerprint"]:
        raise ValueError("Report dataset fingerprint mismatch")
    if provenance.get("dataset_sha256", info["fingerprint"]) != info["fingerprint"]:
        raise ValueError("Model provenance refers to a different dataset")
    matched = match_predictions(samples, predictions)
    if any("view_score" not in p for p in matched.values()):
        raise ValueError("Workbench import requires actual predictions on original and renamed views")
    predictions = [matched[s.id] for s in samples]
    val = [i for i, sample in enumerate(samples) if sample.split == "validation"]
    operating = choose_threshold([samples[i].label for i in val], [predictions[i]["score"] for i in val], max_fpr)
    if embeddings is None:
        # A missing embedding is not invented. Empty projection is an explicit
        # supported UI state, not a plot made from classification scores.
        projected = {"method": "not_available", "fit_split": None, "points": [], "explained_variance": []}
    else:
        array = np.asarray(embeddings, dtype=float)
        if array.ndim != 2 or len(array) != len(samples) or not np.isfinite(array).all():
            raise ValueError("Embedding rows must match the sample order and contain finite values")
        train = [i for i, s in enumerate(samples) if s.split == "train"]
        coords, explained = projection(array[train], array)
        projected = {"method": "PCA", "fit_split": "train", "explained_variance": explained,
                     "points": [{"id": s.id, "x": float(p[0]), "y": float(p[1])} for s, p in zip(samples, coords)]}
    result = copy.deepcopy(report)
    result["runs"].append({"id": run_id, "name": name, "kind": "external", "threshold": operating["threshold"],
                           "contrastive_weight": provenance.get("config", {}).get("contrastive_weight", "not supplied"),
                           "positive_weight": provenance.get("config", {}).get("positive_weight", "not supplied"),
                           "operating_point": operating, "predictions": predictions, "history": history or [],
                           "splits": split_summaries(samples, predictions, operating["threshold"]),
                           "projection": projected, "predictions_sha256": fingerprint(predictions), "provenance": provenance})
    return result


def attach_scan(report, scan):
    samples = [Example.from_dict(s) for s in report["samples"]]
    info = audit(samples)
    if scan.get("dataset_sha256") != info["fingerprint"]:
        raise ValueError("Scanner results refer to a different dataset")
    if scan.get("status") not in {"completed", "completed_with_errors", "failed", "not_run"}:
        raise ValueError("Unknown scanner status")
    known = {s.id for s in samples}
    if any(f.get("example_id") not in known for f in scan.get("findings", [])):
        raise ValueError("Unmapped findings must be kept in the unmapped list")
    result = copy.deepcopy(report)
    result["static_analysis"] = copy.deepcopy(scan)
    return result
