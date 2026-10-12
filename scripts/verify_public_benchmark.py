"""Replay bundled source extraction, checkpoints and metrics without downloads."""
from collections import Counter
import json
from pathlib import Path

import numpy as np

from patchlens.analysis import validate_report
from patchlens.benchmark import load_embeddings, macro_uncertainty, repository_metrics
from patchlens.data import audit, load_dataset
from patchlens.features import Vectorizer
from patchlens.io import fingerprint, load_json, write_json
from patchlens.metrics import binary_metrics, choose_threshold
from patchlens.models import Model
from patchlens.public_data import parse_patch, sha256

ROOT = Path(__file__).resolve().parents[1]


def verify(root=ROOT):
    root = Path(root)
    data = root / "datasets/vul4j"
    study = root / "examples/public-benchmark"
    samples = load_dataset(data / "dataset.jsonl")
    by_id = {s.id: s for s in samples}
    cohort = load_json(data / "cohort-manifest.json")
    lock = load_json(data / "source-lock.json")
    assert audit(samples)["fingerprint"] == cohort["dataset"]["fingerprint"]
    assert sha256(data / "source/vul4j_dataset.csv") == lock["dataset_csv"]["sha256"]
    repository_splits = {}
    for pair in cohort["pairs"]:
        assert pair["repository"] not in repository_splits or repository_splits[pair["repository"]] == pair["split"]
        repository_splits[pair["repository"]] = pair["split"]
        path = data / "source" / (pair["id"] + ".patch")
        assert sha256(path) == pair["patch_sha256"]
        before, after, files, hunks = parse_patch(path.read_text(encoding="utf-8"))
        for suffix, code in [("before", before), ("after", after)]:
            s = by_id[pair["id"] + "-" + suffix]
            assert s.code == code == s.view_code
            assert s.source == pair["commit_url"]
            assert s.group_id == pair["group_id"] and s.split == pair["split"]
        assert files == pair["files"] and hunks == pair["hunks"]
    for item in lock["licences"]:
        if item["repository"] in repository_splits:
            for doc in item["files"]:
                assert sha256(data / "licences" / doc["path"]) == doc["sha256"]
    features, provenance = load_embeddings(samples, study / "encoder")
    prediction_checks = metric_checks = 0
    prior = {}
    cases = [(study / f"seed-{seed}", samples, features, provenance, load_json(root / "configs/public-benchmark.json"), True) for seed in [17, 29, 43]]
    from patchlens.cross_validation import fold_assignment, pool_oof
    from dataclasses import replace
    import copy
    cv_folder = root / "examples/repository-cross-validation"
    cv_protocol = load_json(root / "configs/repository-cross-validation.json")
    cv_summary = load_json(cv_folder / "cross-validation-summary.json")
    fold_reports = {}
    for fold in range(5):
        assignment = fold_assignment(cohort, fold)
        expected_samples = [replace(s, split=assignment[s.group_id]) for s in samples]
        folder = cv_folder / f"fold-{fold}"
        assert load_dataset(folder / "inputs/dataset.jsonl") == expected_samples
        fold_features, fold_provenance = load_embeddings(expected_samples, folder / "inputs/encoder")
        assert np.array_equal(features, fold_features)
        assert fold_provenance["original_dataset_sha256"] == cohort["dataset"]["fingerprint"]
        protocol = copy.deepcopy(load_json(root / "configs/public-benchmark.json"))
        protocol["training_seeds"] = [cv_protocol["training_seed"]]
        protocol["cross_validation"] = {"fold": fold, "protocol": cv_protocol, "protocol_sha256": fingerprint(cv_protocol)}
        assert load_json(folder / "inputs/protocol.json") == protocol
        cases.append((folder / "run/seed-17", expected_samples, fold_features, fold_provenance, protocol, False))
        fold_reports[fold] = load_json(folder / "run/report.json")
    for directory, selected_samples, features, provenance, protocol, repeat_check in cases:
        report = validate_report(load_json(directory / "report.json"))
        samples_for_run = selected_samples
        assert report["samples"] == [s.to_dict() for s in selected_samples]
        assert report["config"]["benchmark_protocol"] == protocol
        for run in report["runs"]:
            if run["id"] == "constant":
                scores = np.full(len(samples_for_run), .5)
            elif run["id"] == "codebert":
                checkpoint = load_json(directory / "model-codebert-probe.json")
                assert checkpoint["dataset_sha256"] == report["dataset"]["fingerprint"]
                assert checkpoint["embedding_sha256"] == provenance["embedding_sha256"]
                model = Model.from_dict(checkpoint["model"], features.shape[1])
                scores = model.predict(features)
            else:
                checkpoint = load_json(directory / f"model-{run['id']}.json")
                vectorizer = Vectorizer.from_dict(checkpoint["vectorizer"])
                model = Model.from_dict(checkpoint["model"], len(vectorizer.vocabulary))
                scores = model.predict(vectorizer.transform([s.code for s in samples_for_run]))
            assert fingerprint(run["predictions"]) == run["predictions_sha256"]
            assert [p["id"] for p in run["predictions"]] == [s.id for s in samples_for_run]
            np.testing.assert_allclose(scores, [p["score"] for p in run["predictions"]], rtol=0, atol=1e-12)
            np.testing.assert_allclose(scores, [p["view_score"] for p in run["predictions"]], rtol=0, atol=1e-12)
            prediction_checks += len(scores)
            labels = [s.label for s in samples_for_run if s.split == "validation"]
            val_scores = [p["score"] for s, p in zip(samples_for_run, run["predictions"]) if s.split == "validation"]
            operating = choose_threshold(labels, val_scores, report["config"]["max_validation_fpr"])
            assert operating == run["operating_point"]
            for split in ["train", "validation", "test"]:
                selected = [(s, p) for s, p in zip(samples_for_run, run["predictions"]) if s.split == split]
                expected = binary_metrics([s.label for s, _ in selected], [p["score"] for _, p in selected], run["threshold"])
                assert expected == run["splits"][split]["metrics"]
                macro = repository_metrics(report, run["id"], split)
                if split == "test":
                    macro["bootstrap"] = macro_uncertainty(macro)
                assert macro == run["repository_metrics"][split]
                metric_checks += 1
            if repeat_check and run["id"] in {"linear", "codebert", "constant"}:
                if run["id"] in prior:
                    assert run["predictions"] == prior[run["id"]]
                prior[run["id"]] = run["predictions"]
    for model in cv_summary["models"]:
        from patchlens.io import load_jsonl
        rows = load_jsonl(cv_folder / f"oof-predictions-{model}.jsonl")
        assert {r["id"] for r in rows} == set(by_id) and len(rows) == len(by_id)
        for row in rows:
            report = fold_reports[row["fold"]]
            source = next(s for s in report["samples"] if s["id"] == row["id"])
            run = next(r for r in report["runs"] if r["id"] == model)
            score = next(p["score"] for p in run["predictions"] if p["id"] == row["id"])
            assert source["split"] == "test" and row["label"] == source["label"]
            assert row["group_id"] == source["group_id"] and row["pair_id"] == source["pair_id"]
            assert row["threshold"] == run["threshold"] and row["score"] == score
            assert row["threshold_source"] == "validation"
        assert pool_oof(rows) == cv_summary["models"][model]
    assert sha256(data / "licences/Vul4J-DATA-LICENSE") == lock["dataset_licence"]["sha256"]
    return {"status": "passed", "pairs_reconstructed_from_raw_patches": cohort["retained_pairs"],
            "repository_disjoint_sources": len(repository_splits), "checkpoint_prediction_checks": prediction_checks,
            "split_metric_and_macro_checks": metric_checks, "training_seeds": [17, 29, 43], "repository_test_folds": 5, "oof_originals_verified_per_model": len(by_id),
            "embedding_fingerprint_verified": True, "thresholds_reselected_on_validation": True,
            "scope": "Bundled numeric replay and source reconstruction; no upstream PoV or encoder forward pass is repeated by this check"}


if __name__ == "__main__":
    result = verify()
    print(json.dumps(result, indent=2))
