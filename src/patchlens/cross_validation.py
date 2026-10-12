"""Five repository folds with one honest held-out decision per original."""
from collections import Counter
import copy
from dataclasses import replace
from pathlib import Path
import shutil

import numpy as np

from .benchmark import load_embeddings, macro_uncertainty, run_benchmark
from .data import audit, load_dataset
from .io import fingerprint, load_json, write_json, write_jsonl


def fold_assignment(cohort, fold, folds=5):
    if folds != 5 or type(fold) is not int or not 0 <= fold < folds:
        raise ValueError("The public study has exactly five folds numbered 0 through 4")
    return {c["group_id"]: "test" if i % folds == fold else "validation" if i % folds == (fold + 1) % folds else "train"
            for i, c in enumerate(cohort["components"])}


def pool_oof(rows):
    """Pool binary decisions at their own fold thresholds; no pooled score AUC."""
    if not rows or len({r["id"] for r in rows}) != len(rows):
        raise ValueError("OOF predictions must cover unique originals exactly once")
    if any(r["decision"] != int(r["score"] >= r["threshold"]) for r in rows):
        raise ValueError("OOF decision disagrees with the stored fold threshold")
    groups = []
    for group in sorted({r["group_id"] for r in rows}):
        selected = [r for r in rows if r["group_id"] == group]
        if len({r["fold"] for r in selected}) != 1:
            raise ValueError("A repository component crosses test folds")
        counts = {"tp": 0, "tn": 0, "fp": 0, "fn": 0}
        pairs = {}
        for r in selected:
            key = "tp" if r["label"] and r["decision"] else "fn" if r["label"] else "fp" if r["decision"] else "tn"
            counts[key] += 1
            pair = pairs.setdefault(r["pair_id"], {})
            if r["label"] in pair:
                raise ValueError("Repeated label within OOF pair")
            pair[r["label"]] = r
        if any(set(p) != {0, 1} for p in pairs.values()):
            raise ValueError("Each OOF pair must include both code versions")
        tp, tn, fp, fn = (counts[k] for k in ["tp", "tn", "fp", "fn"])
        metrics = {**counts, "n": len(selected), "balanced_accuracy": .5 * (tp / (tp + fn) + tn / (tn + fp)),
                   "pair_ordering": sum(p[1]["score"] > p[0]["score"] for p in pairs.values()) / len(pairs),
                   "pair_both_correct": sum(p[1]["decision"] == 1 and p[0]["decision"] == 0 for p in pairs.values()) / len(pairs)}
        groups.append({"group_id": group, "pairs": len(pairs), "metrics": metrics})
    pooled = {k: sum(g["metrics"][k] for g in groups) for k in ["tp", "tn", "fp", "fn", "n"]}
    result = {"groups": groups, "pooled_counts": pooled,
              **{f"macro_{k}": float(np.mean([g["metrics"][k] for g in groups])) for k in ["balanced_accuracy", "pair_ordering", "pair_both_correct"]}}
    result["bootstrap"] = macro_uncertainty(result)
    return result


def run_cross_validation(dataset, cohort_path, base_protocol_path, cv_protocol_path, embedding_cache, output):
    original = load_dataset(dataset)
    cohort, base, cv = load_json(cohort_path), load_json(base_protocol_path), load_json(cv_protocol_path)
    _, original_provenance = load_embeddings(original, embedding_cache)
    if audit(original)["fingerprint"] != cohort["dataset"]["fingerprint"] or cv["folds"] != 5:
        raise ValueError("Cohort fingerprint or five-fold protocol mismatch")
    output = Path(output)
    if output.exists() and any(output.iterdir()) and not (output / "cross-validation-summary.json").exists():
        raise ValueError("Choose an empty cross-validation output directory")
    output.mkdir(parents=True, exist_ok=True)
    oof = {}
    fold_records = []
    for fold in range(5):
        assignment = fold_assignment(cohort, fold)
        samples = [replace(s, split=assignment[s.group_id]) for s in original]
        fold_cohort = copy.deepcopy(cohort)
        fold_cohort["dataset"] = audit(samples)
        for component in fold_cohort["components"]:
            component["split"] = assignment[component["group_id"]]
        for pair in fold_cohort["pairs"]:
            pair["split"] = assignment[pair["group_id"]]
        fold_cohort["split_rule"] = cv["assignment"] + f"; test bucket {fold}, validation bucket {(fold + 1) % 5}"
        folder = output / f"fold-{fold}"
        source = folder / "inputs"
        source.mkdir(parents=True, exist_ok=True)
        write_jsonl(source / "dataset.jsonl", [s.to_dict() for s in samples])
        write_json(source / "cohort-manifest.json", fold_cohort)
        protocol = copy.deepcopy(base)
        protocol["training_seeds"] = [cv["training_seed"]]
        protocol["cross_validation"] = {"fold": fold, "protocol": cv, "protocol_sha256": fingerprint(cv)}
        write_json(source / "protocol.json", protocol)
        # The encoder never fits any of the fold corpora. The input codes, order,
        # tokenization and vectors are identical; only split assignments change.
        shared = source / "encoder"
        shared.mkdir(exist_ok=True)
        shutil.copyfile(Path(embedding_cache) / "embeddings.npz", shared / "embeddings.npz")
        rebound = {**original_provenance, "dataset_sha256": fold_cohort["dataset"]["fingerprint"],
                   "original_dataset_sha256": cohort["dataset"]["fingerprint"],
                   "reuse_reason": "Identical original IDs, code, labels and input ordering; split metadata changes only. Frozen encoder performs no data fitting."}
        write_json(shared / "embedding-provenance.json", rebound)
        run_benchmark(source / "dataset.jsonl", source / "cohort-manifest.json", source / "protocol.json", folder / "run", embedding_cache=shared)
        report = load_json(folder / "run/report.json")
        fold_records.append({"fold": fold, "dataset_sha256": report["dataset"]["fingerprint"],
                             "examples": dict(Counter(s.split for s in samples)),
                             "components": dict(Counter(assignment.values()))})
        for run in report["runs"]:
            predictions = {p["id"]: p for p in run["predictions"]}
            for s in samples:
                if s.split == "test":
                    score = predictions[s.id]["score"]
                    oof.setdefault(run["id"], []).append({"id": s.id, "pair_id": s.pair_id, "group_id": s.group_id,
                                                         "label": s.label, "cwe": s.cwe, "fold": fold, "score": score,
                                                         "threshold": run["threshold"], "decision": int(score >= run["threshold"]),
                                                         "threshold_source": "validation", "source": s.source})
        print(f"Completed repository fold {fold + 1}/5", flush=True)
    expected = {s.id for s in original}
    summaries = {}
    for name, rows in oof.items():
        rows.sort(key=lambda r: r["id"])
        if {r["id"] for r in rows} != expected or len(rows) != len(original):
            raise ValueError("Missing or repeated out-of-fold test predictions")
        summaries[name] = pool_oof(rows)
        write_jsonl(output / f"oof-predictions-{name}.jsonl", rows)
    a, b = summaries["linear"], summaries["codebert"]
    if [g["group_id"] for g in a["groups"]] != [g["group_id"] for g in b["groups"]]:
        raise ValueError("Paired repository comparisons require identical groups")
    differences = np.asarray([gb["metrics"]["balanced_accuracy"] - ga["metrics"]["balanced_accuracy"] for ga, gb in zip(a["groups"], b["groups"])])
    rng = np.random.default_rng(cv["bootstrap_seed"])
    draws = differences[rng.integers(0, len(differences), size=(cv["bootstrap_draws"], len(differences)))].mean(axis=1)
    summary = {"schema_version": "1.0", "dataset_sha256": cohort["dataset"]["fingerprint"], "protocol": cv,
               "protocol_sha256": fingerprint(cv), "base_protocol_sha256": fingerprint(base), "folds": fold_records,
               "examples": len(original), "pairs": len(original) // 2, "repositories": cohort["repositories"],
               "models": summaries, "codebert_minus_linear": {"macro_balanced_accuracy_delta": float(differences.mean()),
                "paired_repository_percentile_95": np.quantile(draws, [.025, .975]).tolist(), "unit": "repository_component", "draws": cv["bootstrap_draws"]},
               "interpretation": "Each original is tested once. Fold-specific validation thresholds govern pooled decisions. Raw scores are not pooled into a common ROC/AUC. One training seed and overlapping fold training sets limit inference."}
    write_json(output / "cross-validation-summary.json", summary)
    return summary
