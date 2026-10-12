"""Frozen pretrained code representations and repository-clustered evaluation."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import platform
import time

import numpy as np

from .analysis import analyze_report, compare_reports, validate_report
from .data import audit, load_dataset
from .experiment import export_workbench, projection, run_experiment, split_summaries
from .external import attach_predictions
from .features import tokenize
from .io import fingerprint, load_json, write_json, write_jsonl
from .metrics import binary_metrics, choose_threshold
from .models import Model
from .public_data import sha256

MODEL_FILES = ["config.json", "merges.txt", "vocab.json", "tokenizer_config.json", "special_tokens_map.json", "pytorch_model.bin"]


def head_tail(tokens, max_length=512):
    if type(max_length) is not int or not 4 <= max_length <= 512:
        raise ValueError("CodeBERT input length must be an integer from 4 through 512")
    budget = max_length - 2
    return list(tokens) if len(tokens) <= budget else list(tokens[:(budget + 1) // 2]) + list(tokens[-(budget // 2):])


def extract_embeddings(samples, model_path, config, destination, expected_hashes):
    """Encode each original once; identical views reuse the same exact input.

    A frozen encoder sees all inputs but performs no corpus fitting. Its numeric
    probe, vocabulary of the lexical baseline and all thresholds use train/val.
    """
    if (config.get("pooling") != "mean_non_special_tokens" or config.get("truncation") != "head_tail_equal"
            or config.get("normalization") != "row_l2" or config.get("fine_tuning") is not False):
        raise ValueError("Unsupported encoder pooling, truncation, normalization or fine-tuning protocol")
    if type(config.get("batch_size")) is not int or config["batch_size"] < 1 or type(config.get("threads")) is not int or config["threads"] < 1:
        raise ValueError("Batch size and CPU threads must be positive integers")
    import torch
    import transformers
    from transformers import AutoModel, AutoTokenizer

    start = time.perf_counter()
    model_path, destination = Path(model_path), Path(destination)
    for filename in MODEL_FILES:
        if sha256(model_path / filename) != expected_hashes[filename]:
            raise ValueError("Pinned pretrained model file hash mismatch: " + filename)
    if any(s.view_code != s.code for s in samples):
        raise ValueError("The public benchmark expects identity views, not invented augmentation scores")
    torch.set_num_threads(config["threads"])
    torch.manual_seed(17)
    tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
    encoder = AutoModel.from_pretrained(str(model_path), local_files_only=True, weights_only=True).eval()
    for parameter in encoder.parameters():
        parameter.requires_grad_(False)
    raw = [tokenizer.encode(s.code, add_special_tokens=False) for s in samples]
    sequences = [tokenizer.build_inputs_with_special_tokens(head_tail(t, config["max_length"])) for t in raw]
    records = [{"id": s.id, "tokens_before_truncation": len(t), "input_tokens": len(u),
                "truncated": len(t) > config["max_length"] - 2, "input_sha256": fingerprint(u)}
               for s, t, u in zip(samples, raw, sequences)]
    vectors = []
    with torch.inference_mode():
        for first in range(0, len(samples), config["batch_size"]):
            group = sequences[first:first + config["batch_size"]]
            batch = tokenizer.pad({"input_ids": group}, padding=True, return_tensors="pt")
            hidden = encoder(**batch).last_hidden_state
            mask = batch["attention_mask"].bool()
            for special in tokenizer.all_special_ids:
                mask &= batch["input_ids"] != special
            if (mask.sum(dim=1) == 0).any():
                raise ValueError("No non-special tokens to pool")
            pooled = (hidden * mask.unsqueeze(-1)).sum(dim=1) / mask.sum(dim=1, keepdim=True)
            vectors.append(pooled.cpu().numpy())
            print(f"CodeBERT encoded {min(first + len(group), len(samples))}/{len(samples)} originals", flush=True)
    features = np.concatenate(vectors).astype(np.float64)
    features /= np.maximum(np.linalg.norm(features, axis=1, keepdims=True), 1e-12)
    if not np.isfinite(features).all():
        raise ValueError("Non-finite pretrained embeddings")
    destination.mkdir(parents=True, exist_ok=True)
    temporary = destination / "embeddings.npz.part"
    with temporary.open("wb") as stream:
        np.savez_compressed(stream, embeddings=features, ids=np.asarray([s.id for s in samples]))
    temporary.replace(destination / "embeddings.npz")
    by_pair = {}
    for s, u in zip(samples, sequences):
        by_pair.setdefault(s.pair_id, []).append(u)
    provenance = {"schema_version": "1.0", "dataset_sha256": audit(samples)["fingerprint"],
                  "model_id": config["model_id"], "revision": config["revision"], "files_sha256": expected_hashes,
                  "model_parameters": sum(p.numel() for p in encoder.parameters()), "encoder_training": "frozen_pretrained",
                  "config": config, "torch": torch.__version__, "transformers": transformers.__version__,
                  "device": "cpu", "embedding_sha256": sha256(destination / "embeddings.npz"),
                  "created_at": datetime.now(timezone.utc).isoformat(), "duration_seconds": time.perf_counter() - start,
                  "truncated_examples": sum(r["truncated"] for r in records),
                  "pairs_with_identical_visible_tokens": [p for p, v in by_pair.items() if v[0] == v[1]],
                  "inputs": records, "view_kind": "identity", "pretraining_overlap": "not_auditable_from_available_training_metadata"}
    write_json(destination / "embedding-provenance.json", provenance)
    return features, provenance


def load_embeddings(samples, directory):
    directory = Path(directory)
    provenance = load_json(directory / "embedding-provenance.json")
    if provenance["dataset_sha256"] != audit(samples)["fingerprint"]:
        raise ValueError("Embedding dataset fingerprint mismatch")
    if sha256(directory / "embeddings.npz") != provenance["embedding_sha256"]:
        raise ValueError("Embedding byte fingerprint mismatch")
    with np.load(directory / "embeddings.npz", allow_pickle=False) as saved:
        if saved["ids"].tolist() != [s.id for s in samples]:
            raise ValueError("Embedding IDs/order mismatch")
        features = saved["embeddings"].astype(np.float64)
    if features.shape != (len(samples), 768) or not np.isfinite(features).all():
        raise ValueError("Expected finite 768-dimensional CodeBERT features")
    return features, provenance


def repository_metrics(report, run_id, split="test"):
    selected = [s for s in report["samples"] if s["split"] == split]
    run = next(r for r in report["runs"] if r["id"] == run_id)
    predictions = {p["id"]: p["score"] for p in run["predictions"]}
    groups = sorted({s["group_id"] for s in selected})
    values = []
    for group in groups:
        rows = [s for s in selected if s["group_id"] == group]
        m = binary_metrics([s["label"] for s in rows], [predictions[s["id"]] for s in rows], run["threshold"])
        m["balanced_accuracy"] = .5 * (m["recall"] + 1 - m["fpr"])
        pairs = {}
        for s in rows:
            pairs.setdefault(s["pair_id"], {})[s["label"]] = predictions[s["id"]]
        m["pair_ordering"] = sum(p[1] > p[0] for p in pairs.values()) / len(pairs)
        m["pair_both_correct"] = sum(p[1] >= run["threshold"] > p[0] for p in pairs.values()) / len(pairs)
        values.append({"group_id": group, "pairs": len(pairs), "metrics": m})
    return {"groups": values, "macro_balanced_accuracy": float(np.mean([v["metrics"]["balanced_accuracy"] for v in values])),
            "macro_pair_ordering": float(np.mean([v["metrics"]["pair_ordering"] for v in values])),
            "macro_pair_both_correct": float(np.mean([v["metrics"]["pair_both_correct"] for v in values]))}


def macro_uncertainty(repository_summary, draws=2000, seed=17):
    groups = repository_summary["groups"]
    if not groups or not 200 <= draws <= 2000:
        raise ValueError("Expected repository groups and 200–2000 bootstrap draws")
    matrix = np.asarray([[g["metrics"][k] for k in ["balanced_accuracy", "pair_ordering", "pair_both_correct"]] for g in groups])
    rng = np.random.default_rng(seed)
    samples = matrix[rng.integers(0, len(groups), size=(draws, len(groups)))].mean(axis=1)
    limits = np.quantile(samples, [.025, .975], axis=0)
    return {"unit": "repository_component", "groups": len(groups), "draws": draws, "seed": seed,
            "percentile_95": {k: limits[:, i].tolist() for i, k in enumerate(["macro_balanced_accuracy", "macro_pair_ordering", "macro_pair_both_correct"])},
            "interpretation": "Exploratory intervals resample whole repository components; few components and one fixed cohort limit generalization"}


def add_probe(report, samples, features, provenance, output, config):
    if config.get("kind") != "linear" or config.get("optimizer") != "full_batch_Adam" or config.get("l2") != 1e-4 or config.get("positive_weight") != 1:
        raise ValueError("The numeric probe supports a linear Adam head with fixed l2=0.0001 and positive_weight=1")
    train = np.asarray([i for i, s in enumerate(samples) if s.split == "train"])
    y = np.asarray([s.label for s in samples])
    probe = Model.create(features.shape[1], "linear", 17)
    history = probe.fit(features[train], y[train], epochs=config["epochs"], learning_rate=config["learning_rate"])
    scores = probe.predict(features)
    predictions = [{"id": s.id, "score": float(v), "view_score": float(v)} for s, v in zip(samples, scores)]
    attached = attach_predictions(report, predictions, run_id="codebert", name="CodeBERT · frozen linear probe",
                                  provenance={**provenance, "probe": config, "config": {"contrastive_weight": 0, "positive_weight": 1}},
                                  embeddings=features, history=history, max_fpr=report["config"]["max_validation_fpr"])
    write_json(Path(output) / "model-codebert-probe.json", {"schema_version": "1.0", "model": probe.to_dict(),
               "threshold": attached["runs"][-1]["threshold"], "dataset_sha256": report["dataset"]["fingerprint"],
               "embedding_sha256": provenance["embedding_sha256"], "encoder": {k: provenance[k] for k in ["model_id", "revision", "config", "files_sha256"]},
               "probe": config})
    write_jsonl(Path(output) / "predictions-codebert.jsonl", predictions)
    return attached


def run_benchmark(dataset, cohort_path, config_path, output, *, model_path=None, embedding_cache=None, model_lock_path=None):
    samples, cohort, config = load_dataset(dataset), load_json(cohort_path), load_json(config_path)
    if audit(samples)["fingerprint"] != cohort["dataset"]["fingerprint"]:
        raise ValueError("Cohort manifest does not match actual dataset")
    output = Path(output)
    if output.exists() and any(output.iterdir()) and not (output / "benchmark-summary.json").exists():
        raise ValueError("Choose an empty benchmark output directory")
    output.mkdir(parents=True, exist_ok=True)
    if embedding_cache is not None:
        features, provenance = load_embeddings(samples, embedding_cache)
    else:
        if model_path is None or model_lock_path is None:
            raise ValueError("Pass a local pinned CodeBERT directory and model lock, or verified saved embeddings")
        model_lock = load_json(model_lock_path)
        if model_lock["revision"] != config["encoder"]["revision"] or model_lock["model_id"] != config["encoder"]["model_id"]:
            raise ValueError("Pretrained model revision disagrees with the protocol")
        features, provenance = extract_embeddings(samples, model_path, config["encoder"], output / "encoder", model_lock["files_sha256"])
    # Cached embeddings must obey the identical preprocessing/model protocol.
    if provenance["config"] != config["encoder"]:
        raise ValueError("Embedding preprocessing disagrees with benchmark protocol")
    seeds, results, reports = config["training_seeds"], [], []
    for seed in seeds:
        target = output / f"seed-{seed}"
        report = run_experiment(samples, target, seed=seed, epochs=config["epochs"], max_fpr=config["max_validation_fpr"], publish_report=False)
        report["dataset"].update(name=cohort["name"], kind="public_patch_context", scope=cohort["labels"],
                                 view_kind="identity", source_revision=cohort["source_revision"],
                                 repositories=cohort["repositories"], components=cohort["components"], pairs_provenance=cohort["pairs"])
        report["config"]["benchmark_protocol"] = config
        report["experiment_id"] = fingerprint({"dataset": report["dataset"]["fingerprint"], "protocol": config, "seed": seed, "encoder_files": provenance["files_sha256"], "version": report["version"]})[:16]
        report["limitations"] = cohort["limits"] + ["The lexical/MLP contrastive positives are identity copies, not an augmentation experiment", "Frozen CodeBERT with a trained linear head is not a fine-tuned vulnerability specialist", "Small test repository counts make uncertainty intervals exploratory"]
        report = add_probe(report, samples, features, provenance, target, config["probe"])
        # Train-label prevalence is .5 because each selected CVE contributes a pair.
        control = [{"id": s.id, "score": .5, "view_score": .5} for s in samples]
        report = attach_predictions(report, control, run_id="constant", name="Constant 0.5 control", provenance={"dataset_sha256": report["dataset"]["fingerprint"], "training": "none", "config": {"contrastive_weight": 0, "positive_weight": 1}}, max_fpr=config["max_validation_fpr"])
        summaries = {}
        for run in report["runs"]:
            run["repository_metrics"] = {split: repository_metrics(report, run["id"], split) for split in ["train", "validation", "test"]}
            run["repository_metrics"]["test"]["bootstrap"] = macro_uncertainty(run["repository_metrics"]["test"], **{k: config["bootstrap"][k] for k in ["draws", "seed"]})
            diag = analyze_report(report, run["id"])
            summaries[run["id"]] = {"name": run["name"], "metrics": run["splits"]["test"]["metrics"],
                                    "repository_metrics": run["repository_metrics"]["test"],
                                    "pair_ordering": sum(p["ordering"] == "expected" for p in diag["pair_margins"]) / len(diag["pair_margins"]),
                                    "threshold": run["threshold"]}
        comparison = compare_reports(report, report, "linear", "codebert", "test", config["bootstrap"]["draws"], config["bootstrap"]["seed"])
        write_json(target / "comparison-linear-codebert.json", comparison)
        write_json(target / "report.json", report)
        export_workbench(report, target / "workbench")
        results.append({"seed": seed, "models": summaries, "comparison": comparison})
        reports.append(report)
        print(f"Completed public benchmark seed {seed}", flush=True)
    tokens = {s.id: tokenize(s.code) for s in samples}
    pairs = {}
    for s in samples:
        pairs.setdefault(s.pair_id, []).append(s)
    summary = {"schema_version": "1.0", "project": "PatchLens", "version": "2.0.0", "dataset_sha256": audit(samples)["fingerprint"],
               "protocol": config, "protocol_sha256": fingerprint(config), "cohort": {k: cohort[k] for k in ["candidate_entries", "retained_pairs", "repositories", "exclusion_counts", "components"]},
               "environment": {"python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform()},
               "encoder": provenance, "results": results,
               "lexically_indistinguishable_pairs": [p for p, s in pairs.items() if tokens[s[0].id] == tokens[s[1].id]],
               "repeat_interpretation": "Seeds vary the MLP initialization on one fixed test cohort. The zero-initialized linear models and frozen CodeBERT probe are deterministic and repeat the same predictions.",
               "limits": reports[0]["limitations"]}
    write_json(output / "benchmark-summary.json", summary)
    write_json(output / "report.json", reports[0])
    export_workbench(reports[0], output / "workbench")
    return summary
