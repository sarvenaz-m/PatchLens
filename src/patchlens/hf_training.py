"""Optional encoder fine-tuning and LoRA with explicit paired security views.

No remote model code is trusted. Dependencies load only when this track is used.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import math
from pathlib import Path
import random
import re

from .data import audit
from .io import write_json, write_jsonl


@dataclass
class TrainingConfig:
    mode: str = "lora"
    epochs: int = 3
    batch_pairs: int = 2
    learning_rate: float = 2e-4
    contrastive_weight: float = .3
    positive_weight: float = 3.
    temperature: float = .15
    max_length: int = 256
    seed: int = 17
    rank: int = 8
    target_modules: str = "query,value"
    max_fpr: float = .2
    device: str = "cpu"

    def validate(self):
        if self.mode not in {"frozen", "supervised", "lora"}:
            raise ValueError("mode must be frozen, supervised or lora")
        if not (1 <= self.epochs <= 100 and 1 <= self.batch_pairs <= 32 and 8 <= self.max_length <= 8192 and 1 <= self.rank <= 256 and self.seed >= 0):
            raise ValueError("Invalid training dimensions, seed or epoch count")
        numeric = (self.learning_rate, self.contrastive_weight, self.positive_weight, self.temperature, self.max_fpr)
        if not all(math.isfinite(x) for x in numeric):
            raise ValueError("Training hyperparameters must be finite")
        if not (0 < self.learning_rate <= .1 and self.contrastive_weight >= 0 and self.positive_weight > 0 and self.temperature > 0 and 0 <= self.max_fpr <= 1):
            raise ValueError("Invalid learning rate, loss weight, temperature or FPR ceiling")
        if self.mode == "frozen" and self.contrastive_weight:
            raise ValueError("Frozen encoders require contrastive_weight=0; their representations cannot learn")
        if self.device not in {"cpu", "cuda", "mps"}:
            raise ValueError("device must be cpu, cuda or mps")


def model_options(model_name, revision, allow_download):
    if not Path(model_name).is_dir() and not re.fullmatch(r"[0-9a-fA-F]{40}", revision or ""):
        raise ValueError("Remote/cached repository models require an exact 40-character commit revision")
    options = {"local_files_only": not allow_download, "trust_remote_code": False}
    if revision:
        options["revision"] = revision
    return options


def model_identity(model_name, revision):
    root = Path(model_name)
    if root.is_dir():
        files = {}
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix in {".json", ".txt", ".model", ".safetensors"}:
                sha = hashlib.sha256()
                with path.open("rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        sha.update(block)
                files[str(path.relative_to(root))] = sha.hexdigest()
        return {"model": "local:" + root.name, "files_sha256": files}
    return {"model": model_name, "revision": revision}


def paired_loss(embeddings, labels, temperature):
    """Symmetric InfoNCE: paired view is positive; same-label peers are masked.

    Batch order is [originals, corresponding views]. Each input batch contains
    complete vulnerable/corrected pairs, keeping opposite-label hard negatives.
    """
    import torch
    import torch.nn.functional as F
    n = len(labels)
    if n < 4 or n % 2 or not torch.equal(labels[:n // 2], labels[n // 2:]):
        raise ValueError("Contrastive rows must be originals followed by label-preserving views")
    if temperature <= 0 or not math.isfinite(temperature):
        raise ValueError("Contrastive temperature must be positive")
    z = F.normalize(embeddings, p=2, dim=1)
    logits = z @ z.T / temperature
    positives = (torch.arange(n, device=z.device) + n // 2) % n
    allowed = labels[:, None] != labels[None, :]
    allowed[torch.arange(n, device=z.device), positives] = True
    logits = logits.masked_fill(~allowed, torch.finfo(logits.dtype).min)
    return F.cross_entropy(logits, positives)


def train(samples, model_name, output, config, *, revision=None, allow_download=False):
    config.validate()
    dataset = audit(samples)
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Choose an empty HF training output directory")
    options = model_options(model_name, revision, allow_download)
    try:
        import torch
        import torch.nn.functional as F
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
    except ImportError as exc:
        raise ValueError('Install the optional training extra: pip install ".[train]"') from exc
    random.seed(config.seed)
    torch.manual_seed(config.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(config.seed)
    tokenizer = AutoTokenizer.from_pretrained(model_name, **options)
    if tokenizer.pad_token_id is None:
        raise ValueError("Encoder tokenizer must define a padding token")
    model, loading = AutoModelForSequenceClassification.from_pretrained(
        model_name, num_labels=2, output_loading_info=True, use_safetensors=True, **options)
    if model.config.is_encoder_decoder or getattr(model.config, "is_decoder", False):
        raise ValueError("This training track supports encoder-only sequence classifiers")
    if loading.get("mismatched_keys") or any(not any(part in k for part in ("classifier", "score")) for k in loading.get("missing_keys", [])):
        raise ValueError("Encoder weights are incomplete; only a new task classifier may be initialized")
    if config.max_length > getattr(model.config, "max_position_embeddings", config.max_length):
        raise ValueError("Token limit exceeds encoder position capacity")
    if config.mode == "frozen":
        model.base_model.requires_grad_(False)
    elif config.mode == "lora":
        try:
            from peft import LoraConfig, TaskType, get_peft_model
        except ImportError as exc:
            raise ValueError('LoRA requires the optional PEFT dependency: pip install ".[train]"') from exc
        modules = [value.strip() for value in config.target_modules.split(",") if value.strip()]
        if not modules:
            raise ValueError("Specify architecture-appropriate LoRA target modules")
        model = get_peft_model(model, LoraConfig(task_type=TaskType.SEQ_CLS, r=config.rank,
                              lora_alpha=2 * config.rank, lora_dropout=.05, target_modules=modules, bias="none"))
    device = torch.device(config.device)
    model.to(device)
    trainable = [p for p in model.parameters() if p.requires_grad]
    if not trainable:
        raise ValueError("No trainable parameters")
    optimizer = torch.optim.AdamW(trainable, lr=config.learning_rate)
    train_groups = {}
    for sample in samples:
        if sample.split == "train":
            train_groups.setdefault(sample.pair_id, []).append(sample)
    groups = list(train_groups.values())
    rng = random.Random(config.seed)
    truncated = {"original": [], "view": []}
    for sample in samples:
        for field, code in (("original", sample.code), ("view", sample.view_code)):
            if len(tokenizer(code, truncation=False)["input_ids"]) > config.max_length:
                truncated[field].append(sample.id)
    history = []
    for epoch in range(config.epochs):
        rng.shuffle(groups)
        model.train()
        if config.mode == "frozen":
            model.base_model.eval()
        totals = [0., 0., 0.]
        count = 0
        for start in range(0, len(groups), config.batch_pairs):
            batch = [s for pair in groups[start:start + config.batch_pairs] for s in pair]
            codes = [s.code for s in batch] + [s.view_code for s in batch]
            labels = torch.tensor([s.label for s in batch] * 2, dtype=torch.long, device=device)
            tokens = tokenizer(codes, return_tensors="pt", padding=True, truncation=True, max_length=config.max_length).to(device)
            outputs = model(**tokens, output_hidden_states=bool(config.contrastive_weight))
            losses = F.cross_entropy(outputs.logits, labels, reduction="none")
            weights = torch.where(labels == 1, config.positive_weight, 1.)
            classification = (losses * weights).mean()
            contrastive = paired_loss(outputs.hidden_states[-1][:, 0], labels, config.temperature) if config.contrastive_weight else classification.new_zeros(())
            loss = classification + config.contrastive_weight * contrastive
            if not torch.isfinite(loss):
                raise ValueError("Training produced a non-finite objective")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(trainable, 1.)
            optimizer.step()
            for i, item in enumerate((loss, classification, contrastive)):
                totals[i] += float(item.detach()) * len(batch)
            count += len(batch)
        history.append({"epoch": epoch + 1, "loss": totals[0] / count, "classification": totals[1] / count, "contrastive": totals[2] / count})
    model.eval()
    predictions, embeddings = [], []
    with torch.inference_mode():
        for sample in samples:
            tokens = tokenizer([sample.code, sample.view_code], return_tensors="pt", padding=True, truncation=True, max_length=config.max_length).to(device)
            result = model(**tokens, output_hidden_states=True)
            scores = torch.softmax(result.logits, dim=-1)[:, 1].cpu().tolist()
            predictions.append({"id": sample.id, "score": scores[0], "view_score": scores[1]})
            embeddings.append(result.hidden_states[-1][0, 0].cpu().tolist())
    output.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(output / "checkpoint", safe_serialization=True)
    tokenizer.save_pretrained(output / "checkpoint")
    metadata = {"schema_version": "1.0", "status": "completed", "created_at": datetime.now(timezone.utc).isoformat(),
                "base": model_identity(model_name, revision), "config": asdict(config), "vulnerable_class": 1,
                "dataset_sha256": dataset["fingerprint"], "training_ids": [s.id for s in samples if s.split == "train"],
                "selection": "Fixed epoch count; threshold selected on validation; test labels do not update weights",
                "trainable_parameters": sum(p.numel() for p in trainable), "total_parameters": sum(p.numel() for p in model.parameters()),
                "truncated_ids": truncated, "new_classifier_keys": loading.get("missing_keys", []),
                "environment": {package: importlib.metadata.version(package) for package in ("torch", "transformers", "safetensors")},
                "limits": ["Pretraining overlap may be unknown", "Fixture accuracy is not real-world efficacy", "Device-dependent floating-point differences may occur"]}
    if config.mode == "lora":
        metadata["environment"]["peft"] = importlib.metadata.version("peft")
    write_json(output / "training.json", metadata)
    write_jsonl(output / "predictions.jsonl", predictions)
    write_json(output / "embeddings.json", embeddings)
    write_json(output / "history.json", history)
    return metadata, predictions, embeddings, history


def predict_trained(samples, checkpoint, *, base_model=None, max_length=256, device="cpu"):
    """Reload either a full/frozen classifier or a PEFT adapter, without pickle."""
    from .adapters import predict_huggingface
    from .io import load_json
    checkpoint = Path(checkpoint)
    if not 8 <= max_length <= 8192:
        raise ValueError("Invalid prediction token limit")
    metadata_path = checkpoint.parent / "training.json"
    base_revision = None
    if metadata_path.is_file():
        metadata = load_json(metadata_path)
        if max_length != metadata["config"]["max_length"]:
            raise ValueError("Use the saved max_length from training.json for consistent inference")
        if base_model is not None:
            if "files_sha256" in metadata["base"]:
                if model_identity(base_model, None).get("files_sha256") != metadata["base"]["files_sha256"]:
                    raise ValueError("Base encoder fingerprint differs from the encoder used for training")
            else:
                if base_model != metadata["base"]["model"]:
                    raise ValueError("Pass the original cached repository identifier for this remote-trained adapter")
                base_revision = metadata["base"]["revision"]
    if not (checkpoint / "adapter_config.json").exists():
        return predict_huggingface(samples, str(checkpoint), vulnerable_class=1, max_length=max_length)
    if base_model is None:
        raise ValueError("LoRA inference requires --base-model with the original local encoder")
    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        from peft import PeftModel
    except ImportError as exc:
        raise ValueError('Install the optional training dependencies: pip install ".[train]"') from exc
    options = {"local_files_only": True, "trust_remote_code": False}
    base_options = {**options, **({"revision": base_revision} if base_revision else {})}
    model = AutoModelForSequenceClassification.from_pretrained(base_model, num_labels=2, use_safetensors=True, **base_options)
    model = PeftModel.from_pretrained(model, str(checkpoint), local_files_only=True, is_trainable=False).to(device).eval()
    tokenizer = AutoTokenizer.from_pretrained(str(checkpoint), **options)
    rows = []
    with torch.inference_mode():
        for sample in samples:
            batch = tokenizer([sample.code, sample.view_code], return_tensors="pt", padding=True, truncation=True, max_length=max_length).to(device)
            values = model(**batch).logits.softmax(-1)[:, 1].cpu().tolist()
            rows.append({"id": sample.id, "score": values[0], "view_score": values[1]})
    return rows
