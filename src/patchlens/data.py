"""Dataset contracts and split-leakage checks."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
import re

from .io import fingerprint, load_jsonl

SPLITS = {"train", "validation", "test"}


@dataclass(frozen=True)
class Example:
    id: str
    pair_id: str
    group_id: str
    split: str
    label: int
    cwe: str
    title: str
    code: str
    view_code: str
    rationale: str
    assumptions: str
    source: str
    licence: str
    review_status: str

    @classmethod
    def from_dict(cls, row: dict) -> "Example":
        fields = set(cls.__dataclass_fields__)
        if set(row) != fields:
            raise ValueError(f"Example fields mismatch; missing={sorted(fields-set(row))}, extra={sorted(set(row)-fields)}")
        for name in fields - {"label"}:
            if not isinstance(row[name], str) or not row[name].strip():
                raise ValueError(f"{name} must be a non-empty string")
        if type(row["label"]) is not int or row["label"] not in (0, 1):
            raise ValueError("label must be integer 0 (non-vulnerable in context) or 1 (vulnerable)")
        if row["split"] not in SPLITS:
            raise ValueError("split must be train, validation or test")
        for name in ("id", "pair_id", "group_id"):
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", row[name]):
                raise ValueError(f"{name} must start with a letter/number and use 1-96 letters, numbers, dots, underscores or hyphens")
        if not re.fullmatch(r"CWE-\d+", row["cwe"]):
            raise ValueError("cwe must have the form CWE-79")
        if len(row["code"]) > 50000 or len(row["view_code"]) > 50000:
            raise ValueError("Code exceeds the per-example character limit")
        return cls(**row)

    def to_dict(self) -> dict:
        return asdict(self)


def audit(examples: list[Example], require_splits: bool = True) -> dict:
    if not examples:
        raise ValueError("The dataset is empty")
    if len(examples) > 10000:
        raise ValueError("The reference implementation accepts at most 10,000 examples")
    ids: set[str] = set()
    groups: dict[str, set] = defaultdict(set)
    pairs: dict[str, list[Example]] = defaultdict(list)
    seen_code: dict[str, Example] = {}
    for item in examples:
        if item.id in ids:
            raise ValueError(f"Duplicate example id: {item.id}")
        ids.add(item.id)
        groups[item.group_id].add(item.split)
        pairs[item.pair_id].append(item)
        # This catches exact text and whitespace duplicates, not semantic equivalence.
        for code in (item.code, item.view_code):
            key = re.sub(r"\s+", "", code)
            previous = seen_code.get(key)
            if previous and previous.label != item.label:
                raise ValueError(f"Contradictory labels on identical code: {previous.id}, {item.id}")
            if previous and previous.split != item.split:
                raise ValueError(f"Code leakage across splits: {previous.id}, {item.id}")
            seen_code[key] = item
    leaked = [group for group, splits in groups.items() if len(splits) != 1]
    if leaked:
        raise ValueError(f"Group leakage across splits: {', '.join(sorted(leaked))}")
    for pair, values in pairs.items():
        if len(values) != 2 or {v.label for v in values} != {0, 1}:
            raise ValueError(f"Pair {pair} must contain exactly one example of each class")
        if len({(v.group_id, v.split, v.cwe) for v in values}) != 1:
            raise ValueError(f"Pair metadata mismatch: {pair}")
    if require_splits:
        for split in sorted(SPLITS):
            if {v.label for v in examples if v.split == split} != {0, 1}:
                raise ValueError(f"Split {split} must contain both classes")
    counts = Counter(item.split for item in examples)
    return {"status": "passed", "examples": len(examples), "pairs": len(pairs),
            "groups": len(groups), "splits": dict(sorted(counts.items())),
            "categories": dict(sorted(Counter(v.cwe for v in examples).items())),
            "fingerprint": fingerprint([v.to_dict() for v in sorted(examples, key=lambda x: x.id)]),
            "checks": ["unique_ids", "binary_labels", "complete_pairs", "group_disjoint_splits", "whitespace_duplicate_leakage"],
            "limitations": ["No semantic or general near-duplicate detection", "Labels and source licences require human verification"]}


def load_dataset(path: str | Path) -> list[Example]:
    examples = [Example.from_dict(row) for row in load_jsonl(path)]
    audit(examples)
    return examples


def fixture_path() -> Path:
    return Path(__file__).parent / "data" / "fixtures.jsonl"
