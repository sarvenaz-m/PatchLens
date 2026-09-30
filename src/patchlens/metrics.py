"""Binary security metrics. Vulnerability is always the positive class."""
from __future__ import annotations

import math
from typing import Iterable

import numpy as np


def checked(labels: Iterable, scores: Iterable) -> tuple[np.ndarray, np.ndarray]:
    raw_labels, raw_scores = list(labels), list(scores)
    if len(raw_labels) != len(raw_scores) or not raw_labels:
        raise ValueError("Labels and scores must be non-empty and equally sized")
    if any(type(v) not in (int, np.int64, np.int32) or v not in (0, 1) for v in raw_labels):
        raise ValueError("Labels must be binary integers")
    if any(isinstance(v, (bool, str)) for v in raw_scores):
        raise ValueError("Scores must be finite numbers, not booleans or strings")
    y, p = np.asarray(raw_labels, dtype=int), np.asarray(raw_scores, dtype=float)
    if not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError("Scores must be finite and in [0, 1]")
    return y, p


def ratio(a: int | float, b: int | float) -> float | None:
    return float(a / b) if b else None


def wilson(successes: int, total: int) -> list[float] | None:
    if total == 0:
        return None
    z = 1.959963984540054
    p = successes / total
    centre = (p + z*z/(2*total)) / (1 + z*z/total)
    half = z * math.sqrt(p*(1-p)/total + z*z/(4*total*total)) / (1 + z*z/total)
    return [0. if successes == 0 else max(0., centre-half),
            1. if successes == total else min(1., centre+half)]


def curves(labels: Iterable, scores: Iterable) -> dict:
    y, p = checked(labels, scores)
    positive, negative = int(y.sum()), int((1-y).sum())
    order = np.argsort(-p, kind="stable")
    y, p = y[order], p[order]
    tp = fp = 0
    precision_recall = [{"threshold": None, "precision": 1., "recall": 0.}]
    roc = [{"threshold": None, "fpr": 0., "tpr": 0.}]
    ap, area = 0., 0.
    last_recall = last_tpr = last_fpr = 0.
    for stop in np.r_[np.flatnonzero(np.diff(p)) + 1, len(p)]:
        start = tp + fp
        new = y[start:int(stop)]
        tp += int(new.sum()); fp += int(len(new)-new.sum())
        precision = tp / (tp+fp)
        recall, fpr = ratio(tp, positive), ratio(fp, negative)
        precision_recall.append({"threshold": float(p[int(stop)-1]), "precision": precision, "recall": recall})
        roc.append({"threshold": float(p[int(stop)-1]), "fpr": fpr, "tpr": recall})
        if recall is not None:
            ap += (recall-last_recall)*precision; last_recall = recall
        if recall is not None and fpr is not None:
            area += (fpr-last_fpr)*(recall+last_tpr)/2
            last_tpr, last_fpr = recall, fpr
    return {"pr": precision_recall, "roc": roc,
            "average_precision": ap if positive else None,
            "roc_auc": area if positive and negative else None}


def binary_metrics(labels: Iterable, scores: Iterable, threshold: float = .5) -> dict:
    y, p = checked(labels, scores)
    if not isinstance(threshold, (float, int)) or isinstance(threshold, bool) or not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("Threshold must be a finite number in [0, 1]")
    pred = p >= threshold
    tp = int(((y == 1) & pred).sum()); fn = int(((y == 1) & ~pred).sum())
    fp = int(((y == 0) & pred).sum()); tn = int(((y == 0) & ~pred).sum())
    curve = curves(y, p)
    return {"n": len(y), "tp": tp, "tn": tn, "fp": fp, "fn": fn,
            "threshold": float(threshold), "accuracy": (tp+tn)/len(y),
            "precision": ratio(tp, tp+fp), "recall": ratio(tp, tp+fn),
            "f1": ratio(2*tp, 2*tp+fp+fn), "fnr": ratio(fn, tp+fn), "fpr": ratio(fp, fp+tn),
            "brier": float(np.mean((p-y)**2)),
            "average_precision": curve["average_precision"], "roc_auc": curve["roc_auc"],
            "fnr_wilson_95": wilson(fn, tp+fn), "fpr_wilson_95": wilson(fp, fp+tn)}


def choose_threshold(labels: Iterable, scores: Iterable, max_fpr: float = .2) -> dict:
    """Select on validation only: maximise recall subject to the FPR ceiling."""
    y, p = checked(labels, scores)
    if set(y.tolist()) != {0, 1}:
        raise ValueError("Threshold selection requires both validation classes")
    if not 0 <= max_fpr <= 1:
        raise ValueError("max_fpr must be in [0, 1]")
    candidates = sorted({0., .5, 1., *p.tolist(), *[float(np.nextafter(v, 1.)) for v in p if v < 1.]})
    valid = [binary_metrics(y, p, t) for t in candidates]
    valid = [m for m in valid if m["fpr"] <= max_fpr]
    if not valid:
        raise ValueError("No threshold in [0, 1] satisfies the validation FPR ceiling")
    best = min(valid, key=lambda m: (-m["recall"], m["fpr"], abs(m["threshold"]-.5), -m["threshold"]))
    return {"threshold": best["threshold"], "source_split": "validation", "max_fpr": max_fpr,
            "criterion": "max_recall_under_fpr_ceiling", "validation_metrics": best}


def stability(labels: Iterable, original: Iterable, views: Iterable, threshold: float) -> dict:
    y, p = checked(labels, original); _, v = checked(y, views)
    a, b = p >= threshold, v >= threshold
    return {"n": len(y), "agreement": float(np.mean(a == b)),
            "both_correct": float(np.mean((a == y) & (b == y))),
            "mean_score_shift": float(np.mean(np.abs(p-v))), "flips": int((a != b).sum())}
