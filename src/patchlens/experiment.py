"""Controlled experiments, provenance and portable workbench exports."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import platform
import shutil
import time

import numpy as np

from . import __version__
from .data import Example, audit
from .features import Vectorizer
from .io import fingerprint, write_json, write_jsonl
from .metrics import binary_metrics, choose_threshold, curves, stability
from .models import Model

VARIANTS = [
    {"id": "linear", "name": "Token baseline", "kind": "linear", "contrastive_weight": 0., "positive_weight": 1.},
    {"id": "supervised", "name": "Supervised encoder", "kind": "encoder", "contrastive_weight": 0., "positive_weight": 1.},
    {"id": "contrastive", "name": "Contrastive encoder", "kind": "encoder", "contrastive_weight": .3, "positive_weight": 1.},
    {"id": "weighted", "name": "Security-weighted encoder", "kind": "encoder", "contrastive_weight": .3, "positive_weight": 3.},
]


def projection(z_train: np.ndarray, z: np.ndarray) -> tuple[np.ndarray, list[float]]:
    """PCA basis fitted only on training representations."""
    mean = z_train.mean(axis=0)
    _, s, vh = np.linalg.svd(z_train-mean, full_matrices=False)
    components = vh[:2].copy()
    # Fix the arbitrary SVD sign for stable reports within an environment.
    for i in range(len(components)):
        j = np.argmax(np.abs(components[i]))
        if components[i, j] < 0:
            components[i] *= -1
    coords = (z-mean) @ components.T
    if coords.shape[1] < 2:
        coords = np.pad(coords, ((0, 0), (0, 2-coords.shape[1])))
    total = float((s*s).sum())
    explained = ((s[:2]**2)/total).tolist() if total else [0., 0.]
    return coords, explained


def split_summaries(samples: list[Example], predictions: list[dict], threshold: float) -> dict:
    result = {}
    for split in ("train", "validation", "test"):
        selected = [(s, p) for s, p in zip(samples, predictions) if s.split == split]
        labels = [s.label for s, _ in selected]
        scores = [p["score"] for _, p in selected]
        views = [p["view_score"] for _, p in selected]
        result[split] = {"metrics": binary_metrics(labels, scores, threshold), "curves": curves(labels, scores),
                         "stability": stability(labels, scores, views, threshold), "by_cwe": {}}
        for cwe in sorted({s.cwe for s, _ in selected}):
            rows = [(s, p) for s, p in selected if s.cwe == cwe]
            result[split]["by_cwe"][cwe] = binary_metrics([s.label for s, _ in rows], [p["score"] for _, p in rows], threshold)
    return result


def run_experiment(samples: list[Example], output: Path, *, seed: int = 17, epochs: int = 240, max_fpr: float = .2) -> dict:
    audit_result = audit(samples)
    if sum(s.split == "train" for s in samples) > 512:
        raise ValueError("The full-batch CPU reference supports at most 512 training originals; use a minibatch backend for larger research datasets")
    if not 1 <= epochs <= 10000 or not np.isfinite(max_fpr) or not 0 <= max_fpr <= 1 or seed < 0:
        raise ValueError("Invalid epochs, seed or validation FPR ceiling")
    output = Path(output)
    if output.exists() and any(output.iterdir()) and not (output/".patchlens-run").exists():
        raise ValueError("Output directory is non-empty and is not a PatchLens run; select a new directory")
    output.mkdir(parents=True, exist_ok=True)
    (output/".patchlens-run").write_text("patchlens-run-v1\n", encoding="utf-8")
    train = [s for s in samples if s.split == "train"]
    # Vocabulary/IDF are fitted strictly on training originals and training views.
    vectorizer = Vectorizer.fit([s.code for s in train]+[s.view_code for s in train])
    x = vectorizer.transform([s.code for s in samples]); xv = vectorizer.transform([s.view_code for s in samples])
    train_idx = np.array([i for i, s in enumerate(samples) if s.split == "train"])
    val_idx = np.array([i for i, s in enumerate(samples) if s.split == "validation"])
    y = np.array([s.label for s in samples])
    xt = np.concatenate([x[train_idx], xv[train_idx]])
    yt = np.concatenate([y[train_idx], y[train_idx]])
    config = {"seed": seed, "epochs": epochs, "max_validation_fpr": max_fpr,
              "vocabulary_features": len(vectorizer.vocabulary), "learning_rate": .012, "temperature": .15,
              "hidden_dimension": 48, "embedding_dimension": 16, "regularization": 1e-4,
              "variants": VARIANTS}
    identifier = fingerprint({"dataset": audit_result["fingerprint"], "config": config, "version": __version__})[:16]
    result = {"schema_version": "1.0", "project": "PatchLens", "version": __version__,
              "experiment_id": identifier, "created_at": datetime.now(timezone.utc).isoformat(),
              "dataset": {**audit_result, "name": "Authored JavaScript security fixtures" if all(s.source.startswith("authored:") for s in samples) else "User supplied code pairs",
                          "scope": "Teaching and pipeline validation; not a representative benchmark" if all(s.source.startswith("authored:") for s in samples) else "User supplied; assess representativeness and labels"},
              "environment": {"python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform()},
              "config": config, "samples": [s.to_dict() for s in samples], "runs": [],
              "static_analysis": {"status": "not_run", "findings": []},
              "limitations": ["Compact lexical/MLP models, not pretrained LLMs", "Authored fixture results do not demonstrate real-world security performance", "Uncertainty and repeated seeds require further evaluation", "Security labels are contextual and need independent review"]}
    for variant in VARIANTS:
        start = time.perf_counter()
        model = Model.create(x.shape[1], variant["kind"], seed)
        history = model.fit(xt, yt, epochs=epochs, contrastive_weight=variant["contrastive_weight"], positive_weight=variant["positive_weight"])
        scores, view_scores = model.predict(x), model.predict(xv)
        operating = choose_threshold(y[val_idx], scores[val_idx], max_fpr)
        predictions = [{"id": s.id, "score": float(p), "view_score": float(v)} for s, p, v in zip(samples, scores, view_scores)]
        z = model.encode(x)
        coords, explained = projection(z[train_idx], z)
        run = {**variant, "threshold": operating["threshold"], "operating_point": operating, "predictions": predictions,
               "splits": split_summaries(samples, predictions, operating["threshold"]), "history": history,
               "projection": {"method": "PCA", "fit_split": "train", "explained_variance": explained,
                              "points": [{"id": s.id, "x": float(c[0]), "y": float(c[1])} for s, c in zip(samples, coords)]},
               "duration_seconds": time.perf_counter()-start, "predictions_sha256": fingerprint(predictions)}
        result["runs"].append(run)
        write_json(output/f"model-{variant['id']}.json", {"schema_version": "1.0", "model": model.to_dict(), "vectorizer": vectorizer.to_dict(),
                                                       "threshold": run["threshold"], "dataset_sha256": audit_result["fingerprint"], "config": {**config, "variant": variant}})
        write_jsonl(output/f"predictions-{variant['id']}.jsonl", predictions)
    write_json(output/"report.json", result)
    write_json(output/"split-manifest.json", [{"id": s.id, "pair_id": s.pair_id, "group_id": s.group_id, "split": s.split} for s in samples])
    export_workbench(result, output/"workbench")
    return result


def export_workbench(report: dict, destination: Path) -> None:
    import json
    source = Path(__file__).parent / "web"
    shutil.copytree(source, destination, dirs_exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    (destination/"report-data.js").write_text("window.PATCHLENS_REPORT = "+payload+";\n", encoding="utf-8")
