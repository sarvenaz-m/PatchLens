"""Repeated runs: variation across seeds is not additional independent data."""
from pathlib import Path
import numpy as np
from .experiment import run_experiment
from .io import write_json


def repeat(samples, output, seeds=(17, 29, 43), epochs=240, max_fpr=.2):
    if len(seeds) < 2 or len(seeds) > 20 or len(set(seeds)) != len(seeds):
        raise ValueError("Supply 2–20 distinct seeds")
    if any(type(seed) is not int or seed < 0 for seed in seeds):
        raise ValueError("Seeds must be nonnegative integers")
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Choose an empty repeated-study directory")
    reports = [run_experiment(samples, output / f"seed-{seed}", seed=seed, epochs=epochs, max_fpr=max_fpr) for seed in seeds]
    summary = {"seeds": list(seeds), "dataset_sha256": reports[0]["dataset"]["fingerprint"],
               "scope": "Same fixed test examples, repeated training seeds; not independent test replicates",
               "models": []}
    for model in reports[0]["runs"]:
        runs = [next(r for r in report["runs"] if r["id"] == model["id"]) for report in reports]
        metrics = {}
        for key in ("f1", "fnr", "fpr", "recall", "precision"):
            values = [r["splits"]["test"]["metrics"][key] for r in runs]
            valid = [value for value in values if value is not None]
            metrics[key] = {"values": values, "mean": float(np.mean(valid)) if valid else None,
                            "sample_sd": float(np.std(valid, ddof=1)) if len(valid) > 1 else None}
        summary["models"].append({"id": model["id"], "name": model["name"], "metrics": metrics,
                                  "thresholds": [r["threshold"] for r in runs]})
    write_json(output / "summary.json", summary)
    return summary
