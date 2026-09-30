"""Explicit opt-in integrations. Core experiments never download model weights."""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile

from .data import Example, audit


def scan_semgrep(samples: list[Example], rules: Path, timeout: int = 120) -> dict:
    executable = shutil.which("semgrep")
    if not executable:
        raise ValueError("Semgrep is not installed. Install it separately to use this optional adapter.")
    rules = Path(rules).resolve()
    if not rules.is_file():
        raise ValueError("Pass an existing local Semgrep rules file")
    with tempfile.TemporaryDirectory(prefix="patchlens-scan-") as directory:
        root = Path(directory)
        for item in samples:
            (root/(item.id+".js")).write_text(item.code, encoding="utf-8")
        command = [executable, "scan", "--json", "--metrics=off", "--disable-version-check", "--config", str(rules), str(root)]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            raise ValueError(f"Semgrep did not finish within {timeout} seconds; no findings were accepted") from exc
        if result.returncode not in (0, 1):
            raise ValueError("Semgrep failed: "+result.stderr[-1500:])
        import json
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise ValueError("Semgrep returned no valid JSON; scan is not completed. " + result.stderr[-1200:]) from exc
        findings = [{"example_id": Path(r["path"]).stem, "rule": r["check_id"],
                     "line": r["start"]["line"], "message": r.get("extra", {}).get("message", ""),
                     "severity": r.get("extra", {}).get("severity", "UNKNOWN")} for r in payload.get("results", [])]
        from .integrations import digest
        return {"status": "completed_with_errors" if payload.get("errors") else "completed", "findings": findings,
                "errors": payload.get("errors", []), "version": payload.get("version"),
                "tools": [{"name": "Semgrep", "version": payload.get("version", "unknown")}],
                "dataset_sha256": audit(samples)["fingerprint"], "input_ids": [s.id for s in samples],
                "rules_sha256": digest(rules), "coverage": payload.get("paths", {}),
                "meaning": "Static findings are review signals, not ground-truth vulnerability labels"}


def predict_huggingface(samples: list[Example], model_name: str, *, vulnerable_class: int,
                        revision: str | None = None, allow_download: bool = False, max_length: int = 512) -> list[dict]:
    """Import scores from an actual binary sequence-classification checkpoint.

    Refuses checkpoints with missing weights; a randomly initialised classifier
    must never be silently reported as a pretrained security model.
    """
    if vulnerable_class not in (0, 1) or not 8 <= max_length <= 8192:
        raise ValueError("Specify binary vulnerable_class and a supported token limit")
    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
    except ImportError as exc:
        raise ValueError('Install the optional extra with pip install ".[hf]"') from exc
    options = {"local_files_only": not allow_download, "trust_remote_code": False}
    if revision:
        options["revision"] = revision
    tokenizer = AutoTokenizer.from_pretrained(model_name, **options)
    model, info = AutoModelForSequenceClassification.from_pretrained(model_name, output_loading_info=True, use_safetensors=True, **options)
    if model.config.num_labels != 2 or info.get("missing_keys") or info.get("mismatched_keys"):
        raise ValueError("A complete binary classification checkpoint is required; random/missing classifier weights are rejected")
    model.eval()
    result = []
    with torch.inference_mode():
        for sample in samples:
            tokens = tokenizer([sample.code, sample.view_code], return_tensors="pt", padding=True, truncation=True, max_length=max_length)
            score = torch.softmax(model(**tokens).logits, dim=-1)[:, vulnerable_class].cpu().tolist()
            result.append({"id": sample.id, "score": score[0], "view_score": score[1]})
    return result
