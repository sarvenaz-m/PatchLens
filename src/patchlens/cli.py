"""Command line interface for local, reproducible experiments."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from . import __version__
from .data import audit, fixture_path, load_dataset
from .io import load_json, load_jsonl, write_json, write_jsonl
from .metrics import binary_metrics, checked


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="patchlens", description="Inspect code-security model experiments locally.")
    p.add_argument("--version", action="version", version=__version__)
    commands = p.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Train four real CPU baselines and export a workbench")
    demo.add_argument("--dataset", type=Path, default=fixture_path())
    demo.add_argument("--output", type=Path, default=Path("runs/fixture-demo"))
    demo.add_argument("--epochs", type=int, default=240)
    demo.add_argument("--seed", type=int, default=17)
    demo.add_argument("--max-fpr", type=float, default=.2)
    check = commands.add_parser("audit", help="Validate pairs and group-disjoint splits")
    check.add_argument("dataset", nargs="?", type=Path, default=fixture_path())
    evaluate = commands.add_parser("evaluate", help="Evaluate saved scores, joined by exact example id")
    evaluate.add_argument("--dataset", type=Path, default=fixture_path())
    evaluate.add_argument("--predictions", type=Path, required=True)
    evaluate.add_argument("--threshold", type=float, default=.5)
    evaluate.add_argument("--split", choices=["train", "validation", "test"], default="test")
    evaluate.add_argument("--output", type=Path, required=True)
    predict = commands.add_parser("predict", help="Score code using a saved PatchLens model")
    predict.add_argument("--checkpoint", type=Path, required=True)
    predict.add_argument("--dataset", type=Path, default=fixture_path())
    predict.add_argument("--output", type=Path, required=True)
    scan = commands.add_parser("scan", help="Run an installed Semgrep with local rules")
    scan.add_argument("--dataset", type=Path, default=fixture_path())
    scan.add_argument("--rules", type=Path, required=True)
    scan.add_argument("--output", type=Path, required=True)
    hf = commands.add_parser("predict-hf", help="Score a binary Hugging Face checkpoint; optional dependency")
    hf.add_argument("--dataset", type=Path, default=fixture_path())
    hf.add_argument("--model", required=True)
    hf.add_argument("--revision")
    hf.add_argument("--vulnerable-class", type=int, choices=[0, 1], required=True)
    hf.add_argument("--allow-download", action="store_true")
    hf.add_argument("--output", type=Path, required=True)
    export = commands.add_parser("export", help="Rebuild a standalone workbench from a report JSON")
    export.add_argument("report", type=Path)
    export.add_argument("--output", type=Path, required=True)
    analyze = commands.add_parser("analyze", help="Audit a report and calculate calibration, CWE slices and pair margins")
    analyze.add_argument("report", type=Path)
    analyze.add_argument("--run", default="weighted")
    analyze.add_argument("--split", choices=["train", "validation", "test"], default="test")
    analyze.add_argument("--bins", type=int, default=10)
    analyze.add_argument("--output", type=Path, required=True)
    compare = commands.add_parser("compare", help="Compare matched reports with a paired group bootstrap")
    compare.add_argument("baseline", type=Path)
    compare.add_argument("candidate", type=Path)
    compare.add_argument("--baseline-run", default="linear")
    compare.add_argument("--candidate-run", default="weighted")
    compare.add_argument("--split", choices=["train", "validation", "test"], default="test")
    compare.add_argument("--draws", type=int, default=1000)
    compare.add_argument("--seed", type=int, default=17)
    compare.add_argument("--output", type=Path, required=True)
    repeat = commands.add_parser("repeat", help="Run a fixed-split study across independent training seeds")
    repeat.add_argument("--dataset", type=Path, default=fixture_path())
    repeat.add_argument("--seeds", type=int, nargs="+", default=[17, 29, 43])
    repeat.add_argument("--epochs", type=int, default=240)
    repeat.add_argument("--max-fpr", type=float, default=.2)
    repeat.add_argument("--output", type=Path, required=True)
    sources = commands.add_parser("export-sources", help="Export text-only JavaScript sources and a scanner manifest")
    sources.add_argument("--dataset", type=Path, default=fixture_path())
    sources.add_argument("--output", type=Path, required=True)
    sarif = commands.add_parser("import-sarif", help="Normalize a real SARIF file against a source manifest")
    sarif.add_argument("--sarif", type=Path, required=True)
    sarif.add_argument("--manifest", type=Path, required=True)
    sarif.add_argument("--output", type=Path, required=True)
    codeql = commands.add_parser("scan-codeql", help="Run an installed CodeQL CLI on exported JavaScript")
    codeql.add_argument("--source", type=Path, required=True)
    codeql.add_argument("--query-suite", required=True)
    codeql.add_argument("--timeout", type=int, default=900)
    codeql.add_argument("--output", type=Path, required=True)
    attach = commands.add_parser("attach-scan", help="Attach a dataset-matched scanner report")
    attach.add_argument("--report", type=Path, required=True)
    attach.add_argument("--scan", type=Path, required=True)
    attach.add_argument("--output", type=Path, required=True)
    ext = commands.add_parser("attach-predictions", help="Add real scores; select the operating point on validation")
    ext.add_argument("--report", type=Path, required=True)
    ext.add_argument("--predictions", type=Path, required=True)
    ext.add_argument("--provenance", type=Path, required=True)
    ext.add_argument("--embeddings", type=Path)
    ext.add_argument("--history", type=Path)
    ext.add_argument("--run-id", required=True)
    ext.add_argument("--name", required=True)
    ext.add_argument("--max-fpr", type=float, default=.2)
    ext.add_argument("--output", type=Path, required=True)
    train = commands.add_parser("train-hf", help="Train a frozen, full or LoRA encoder classifier")
    train.add_argument("--dataset", type=Path, default=fixture_path())
    train.add_argument("--model", required=True)
    train.add_argument("--revision")
    train.add_argument("--allow-download", action="store_true")
    train.add_argument("--mode", choices=["frozen", "supervised", "lora"], default="lora")
    train.add_argument("--epochs", type=int, default=3)
    train.add_argument("--batch-pairs", type=int, default=2)
    train.add_argument("--learning-rate", type=float, default=2e-4)
    train.add_argument("--contrastive-weight", type=float, default=.3)
    train.add_argument("--positive-weight", type=float, default=3.)
    train.add_argument("--temperature", type=float, default=.15)
    train.add_argument("--max-length", type=int, default=256)
    train.add_argument("--seed", type=int, default=17)
    train.add_argument("--rank", type=int, default=8)
    train.add_argument("--target-modules", default="query,value")
    train.add_argument("--max-fpr", type=float, default=.2)
    train.add_argument("--device", choices=["cpu", "cuda", "mps"], default="cpu")
    train.add_argument("--output", type=Path, required=True)
    trained = commands.add_parser("predict-trained", help="Reload a saved full or LoRA classifier")
    trained.add_argument("--dataset", type=Path, default=fixture_path())
    trained.add_argument("--checkpoint", type=Path, required=True)
    trained.add_argument("--base-model")
    trained.add_argument("--max-length", type=int, default=256)
    trained.add_argument("--output", type=Path, required=True)
    generate = commands.add_parser("generate", help="Generate code as text from recorded prompts using a local causal model")
    generate.add_argument("--prompts", type=Path, required=True)
    generate.add_argument("--model", required=True)
    generate.add_argument("--revision")
    generate.add_argument("--allow-download", action="store_true")
    generate.add_argument("--seed", type=int, default=17)
    generate.add_argument("--max-new-tokens", type=int, default=256)
    generate.add_argument("--temperature", type=float, default=0.)
    generate.add_argument("--device", choices=["cpu", "cuda", "mps"], default="cpu")
    generate.add_argument("--output", type=Path, required=True)
    density = commands.add_parser("generation-summary", help="Summarize a generation batch and its actual scanner results")
    density.add_argument("--generations", type=Path, required=True)
    density.add_argument("--scan", type=Path, required=True)
    density.add_argument("--output", type=Path, required=True)
    return p


def match_predictions(samples, predictions):
    by_id = {}
    for item in predictions:
        if set(item) - {"id", "score", "view_score"} or "id" not in item or "score" not in item:
            raise ValueError("Predictions require id and score; only view_score is optional")
        if item["id"] in by_id:
            raise ValueError("Duplicate prediction id: "+str(item["id"]))
        checked([0], [item["score"]])
        if "view_score" in item:
            checked([0], [item["view_score"]])
        by_id[item["id"]] = item
    expected = {s.id for s in samples}
    if set(by_id) != expected:
        raise ValueError(f"Prediction id coverage mismatch; missing={sorted(expected-set(by_id))}, extra={sorted(set(by_id)-expected)}")
    return by_id


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command in {"analyze", "compare"}:
            from .analysis import analyze_report, compare_reports
            if args.command == "analyze":
                result = analyze_report(load_json(args.report), args.run, args.split, args.bins)
            else:
                result = compare_reports(load_json(args.baseline), load_json(args.candidate),
                                         args.baseline_run, args.candidate_run, args.split, args.draws, args.seed)
            write_json(args.output, result)
            print(args.output.resolve())
            return 0
        if args.command in {"import-sarif", "scan-codeql", "attach-scan", "attach-predictions", "generate", "generation-summary"}:
            if args.command == "import-sarif":
                from .integrations import import_sarif
                result = import_sarif(load_json(args.sarif), load_json(args.manifest))
            elif args.command == "scan-codeql":
                from .integrations import run_codeql
                result = run_codeql(args.source, args.output, query_suite=args.query_suite, timeout=args.timeout)
                print(args.output.resolve() / "scan.json")
                return 0
            elif args.command == "attach-scan":
                from .external import attach_scan
                result = attach_scan(load_json(args.report), load_json(args.scan))
            elif args.command == "attach-predictions":
                from .external import attach_predictions
                result = attach_predictions(load_json(args.report), load_jsonl(args.predictions), run_id=args.run_id, name=args.name,
                                            provenance=load_json(args.provenance), max_fpr=args.max_fpr,
                                            embeddings=load_json(args.embeddings) if args.embeddings else None,
                                            history=load_json(args.history) if args.history else None)
            elif args.command == "generate":
                from .generation import generate
                generate(load_jsonl(args.prompts), args.model, args.output, revision=args.revision, allow_download=args.allow_download,
                         seed=args.seed, max_new_tokens=args.max_new_tokens, temperature=args.temperature, device=args.device)
                print(args.output.resolve() / "generation.json")
                return 0
            else:
                from .generation import generation_summary
                result = generation_summary(load_jsonl(args.generations), load_json(args.scan))
            write_json(args.output, result)
            print(args.output.resolve())
            return 0
        if args.command == "export":
            from .experiment import export_workbench
            report = load_json(args.report)
            if report.get("schema_version") != "1.0" or not report.get("runs"):
                raise ValueError("Not a supported PatchLens report")
            export_workbench(report, args.output)
            print(args.output.resolve()/"index.html")
            return 0
        samples = load_dataset(args.dataset)
        if args.command == "audit":
            print(json.dumps(audit(samples), indent=2))
        elif args.command == "demo":
            from .experiment import run_experiment
            report = run_experiment(samples, args.output, seed=args.seed, epochs=args.epochs, max_fpr=args.max_fpr)
            print(f"Experiment {report['experiment_id']} | {len(samples)} authored/user-supplied examples")
            for run in report["runs"]:
                m = run["splits"]["test"]["metrics"]
                print(f"{run['name']}: test F1={m['f1']:.3f}, FNR={m['fnr']:.3f}, FPR={m['fpr']:.3f}; n={m['n']}")
            print("Open "+str((args.output/"workbench/index.html").resolve()))
        elif args.command == "evaluate":
            predictions = match_predictions(samples, load_jsonl(args.predictions))
            selected = [s for s in samples if s.split == args.split]
            result = {"split": args.split, "metrics": binary_metrics([s.label for s in selected], [predictions[s.id]["score"] for s in selected], args.threshold),
                      "dataset_sha256": audit(samples)["fingerprint"], "threshold_origin": "user_supplied; not selected by this command"}
            write_json(args.output, result)
            print(json.dumps(result, indent=2))
        elif args.command == "predict":
            from .features import Vectorizer
            from .models import Model
            checkpoint = load_json(args.checkpoint)
            if checkpoint.get("schema_version") != "1.0":
                raise ValueError("Unsupported checkpoint schema")
            vectorizer = Vectorizer.from_dict(checkpoint["vectorizer"])
            model = Model.from_dict(checkpoint["model"], len(vectorizer.vocabulary))
            scores = model.predict(vectorizer.transform([s.code for s in samples]))
            views = model.predict(vectorizer.transform([s.view_code for s in samples]))
            write_jsonl(args.output, [{"id": s.id, "score": float(p), "view_score": float(v)} for s, p, v in zip(samples, scores, views)])
            print(args.output.resolve())
        elif args.command == "scan":
            from .adapters import scan_semgrep
            write_json(args.output, scan_semgrep(samples, args.rules))
            print(args.output.resolve())
        elif args.command == "predict-hf":
            from .adapters import predict_huggingface
            rows = predict_huggingface(samples, args.model, revision=args.revision, vulnerable_class=args.vulnerable_class, allow_download=args.allow_download)
            write_jsonl(args.output, rows)
            print(args.output.resolve())
        elif args.command == "repeat":
            from .studies import repeat
            repeat(samples, args.output, args.seeds, args.epochs, args.max_fpr)
            print(args.output.resolve() / "summary.json")
        elif args.command == "export-sources":
            from .integrations import export_sources
            export_sources(samples, args.output)
            print(args.output.resolve() / "manifest.json")
        elif args.command == "train-hf":
            from .hf_training import TrainingConfig, train
            config = TrainingConfig(**{key: getattr(args, key) for key in TrainingConfig.__dataclass_fields__})
            train(samples, args.model, args.output, config, revision=args.revision, allow_download=args.allow_download)
            print(args.output.resolve() / "training.json")
        elif args.command == "predict-trained":
            from .hf_training import predict_trained
            write_jsonl(args.output, predict_trained(samples, args.checkpoint, base_model=args.base_model, max_length=args.max_length))
            print(args.output.resolve())
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"patchlens: {exc}", file=sys.stderr)
        return 2
