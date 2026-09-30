"""Recorded local code generation. Generated text is never executed."""
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re

from .hf_training import model_identity, model_options
from .io import fingerprint, write_json, write_jsonl


def validate_prompts(prompts):
    if not 1 <= len(prompts) <= 100:
        raise ValueError("Supply 1–100 generation prompts")
    ids = set()
    for prompt in prompts:
        if set(prompt) != {"id", "prompt", "assumptions"}:
            raise ValueError("Each prompt needs exactly id, prompt and assumptions")
        if not isinstance(prompt["id"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", prompt["id"]) or prompt["id"] in ids:
            raise ValueError("Prompt IDs must be safe and unique")
        ids.add(prompt["id"])
        for key in ("prompt", "assumptions"):
            if not isinstance(prompt[key], str) or not 1 <= len(prompt[key]) <= 20000:
                raise ValueError("Prompt text and assumptions must be non-empty bounded strings")


def extract_code(text):
    stripped = text.strip()
    match = re.fullmatch(r"```(?:javascript|js)?\s*\n(.*?)\n```", stripped, flags=re.S)
    return match.group(1).strip() if match else stripped


def generate(prompts, model_name, output, *, revision=None, allow_download=False, seed=17,
             max_new_tokens=256, temperature=0., device="cpu"):
    validate_prompts(prompts)
    import math
    if seed < 0 or not 1 <= max_new_tokens <= 2048 or not math.isfinite(temperature) or not 0 <= temperature <= 2:
        raise ValueError("Invalid generation seed, length or temperature")
    options = model_options(model_name, revision, allow_download)
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Choose an empty generation output directory")
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise ValueError('Install optional generation dependencies: pip install ".[hf]"') from exc
    tokenizer = AutoTokenizer.from_pretrained(model_name, **options)
    model = AutoModelForCausalLM.from_pretrained(model_name, use_safetensors=True, **options).to(device).eval()
    if tokenizer.pad_token_id is None:
        if tokenizer.eos_token_id is None:
            raise ValueError("Tokenizer must define pad or EOS token")
        tokenizer.pad_token = tokenizer.eos_token
    records = []
    for index, prompt in enumerate(prompts):
        torch.manual_seed(seed + index)
        tokens = tokenizer(prompt["prompt"], return_tensors="pt").to(device)
        capacity = getattr(model.config, "max_position_embeddings", getattr(model.config, "n_positions", None))
        if capacity and tokens["input_ids"].shape[1] + max_new_tokens > capacity:
            raise ValueError("Prompt plus completion exceeds model context; no silent truncation is allowed")
        settings = {"max_new_tokens": max_new_tokens, "do_sample": temperature > 0, "pad_token_id": tokenizer.pad_token_id}
        if temperature > 0:
            settings.update(temperature=temperature, top_p=.95)
        with torch.inference_mode():
            sequence = model.generate(**tokens, **settings)
        generated = sequence[0, tokens["input_ids"].shape[1]:]
        raw = tokenizer.decode(generated, skip_special_tokens=True)
        code = extract_code(raw)
        records.append({**prompt, "seed": seed + index, "raw_completion": raw, "code": code,
                        "nonblank_physical_lines": sum(bool(line.strip()) for line in code.splitlines()),
                        "security_review": "not_reviewed", "syntax_status": "not_checked"})
    (output / "src").mkdir(parents=True, exist_ok=True)
    files = []
    for row in records:
        path = output / "src" / (row["id"] + ".js")
        path.write_text(row["code"], encoding="utf-8")
        files.append({"path": "src/" + path.name, "example_id": row["id"], "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    metadata = {"status": "completed", "created_at": datetime.now(timezone.utc).isoformat(),
                "base": model_identity(model_name, revision), "prompt_sha256": fingerprint(prompts),
                "config": {"seed": seed, "max_new_tokens": max_new_tokens, "temperature": temperature, "top_p": .95 if temperature else None, "device": device},
                "counting_rule": "Nonblank physical lines, including comment lines; not logical statements",
                "review": "Generated snippets were saved as text, not executed or certified secure"}
    write_jsonl(output / "generations.jsonl", records)
    write_json(output / "generation.json", metadata)
    write_json(output / "manifest.json", {"schema_version": "1.0", "dataset_sha256": fingerprint(records), "files": files})
    return metadata


def generation_summary(records, scan):
    if scan.get("dataset_sha256") != fingerprint(records):
        raise ValueError("Scanner report does not match this generation batch")
    ids = {row["id"] for row in records}
    if any(f.get("example_id") not in ids for f in scan.get("findings", [])):
        raise ValueError("Unknown generation ID in scanner results")
    findings = {fingerprint(f) for f in scan.get("findings", [])}
    count = sum(row["nonblank_physical_lines"] for row in records)
    completed = scan.get("status") == "completed"
    return {"scanner_status": scan.get("status"), "generated_examples": len(records), "deduplicated_findings": len(findings),
            "nonblank_physical_lines": count, "findings_per_100_nonblank_lines": 100 * len(findings) / count if completed and count else None,
            "adjudicated_vulnerabilities": None, "manual_review": "not_reviewed",
            "meaning": "Scanner-density proxy only; scanner silence is not a security verdict"}
