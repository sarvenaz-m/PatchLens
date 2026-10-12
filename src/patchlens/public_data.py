"""Prepare a pinned, repository-disjoint Vul4J patch-context cohort.

Only source text is read. Build commands, tests and patches are never executed.
The labels describe a documented security correction in its original context.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
import hashlib
from pathlib import Path
import re
import shutil

from .data import Example, audit
from .features import TOKEN
from .io import fingerprint, load_json, write_json, write_jsonl

HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
TEST_PATH = re.compile(r"(^|/)(tests?|testcases|examples|src/it)(/|$)|(?:Test|Tests|TestCase)\.java$", re.I)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(code):
    """Exact lexical stream: remove comments/spacing, preserve literal values."""
    return tuple(m.group() for m in TOKEN.finditer(code) if m.lastgroup != "comment")


def grams(code):
    tokens = canonical(code)
    return {tokens[i:i + 5] for i in range(max(0, len(tokens) - 4))}


def parse_patch(text):
    """Read complete unified hunks, validating both line counts.

    Return one combined code context per commit. File names and hunk offsets
    remain in metadata, never become classifier input or before/after markers.
    """
    if len(re.findall(r"^From [a-f0-9]{40} ", text, re.M)) > 1:
        raise ValueError("multi_commit_patch")
    lines = text.splitlines()
    before, after, files, hunks = [], [], [], []
    path, old_path, new_path = None, None, None
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("diff --git "):
            path, old_path, new_path = None, None, None
        elif line.startswith("--- "):
            old_path = line[4:].removeprefix("a/")
        elif line.startswith("+++ "):
            new_path = line[4:].removeprefix("b/")
            path = old_path if new_path == "/dev/null" else new_path
        match = HUNK.match(line)
        if match:
            if old_path is None or new_path is None:
                raise ValueError("hunk_without_file")
            old_start, old_count, new_start, new_count = match.groups()
            old_count = int(old_count) if old_count is not None else 1
            new_count = int(new_count) if new_count is not None else 1
            old_lines, new_lines = [], []
            i += 1
            while len(old_lines) < old_count or len(new_lines) < new_count:
                if i >= len(lines):
                    raise ValueError("truncated_hunk")
                item = lines[i]
                if item.startswith("\\ No newline"):
                    i += 1
                    continue
                if not item or item[0] not in " +-":
                    raise ValueError("malformed_hunk")
                if item[0] in " -":
                    old_lines.append(item[1:])
                if item[0] in " +":
                    new_lines.append(item[1:])
                i += 1
            if len(old_lines) != old_count or len(new_lines) != new_count:
                raise ValueError("hunk_count_mismatch")
            if path and path.endswith(".java") and not TEST_PATH.search(path):
                before.append("\n".join(old_lines))
                after.append("\n".join(new_lines))
                if path not in files:
                    files.append(path)
                hunks.append({"file": path, "old_start": int(old_start), "old_count": old_count,
                              "new_start": int(new_start), "new_count": new_count})
            continue
        i += 1
    a, b = "\n\n".join(before).strip() + "\n", "\n\n".join(after).strip() + "\n"
    if not files or not a.strip() or not b.strip():
        raise ValueError("no_nonempty_production_java_pair")
    if canonical(a) == canonical(b):
        raise ValueError("no_lexical_code_change")
    if max(len(a), len(b)) > 50000:
        raise ValueError("context_exceeds_50000_characters")
    return a, b, files, hunks


def upstream_licence(text):
    """Conservative subset of explicit permissive licence documents."""
    if "Apache License" in text and re.search(r"Version\s+2\.0", text):
        return "Apache-2.0"
    if "Permission is hereby granted, free of charge" in text and "THE SOFTWARE IS PROVIDED" in text:
        return "MIT"
    if "Redistribution and use in source and binary forms" in text and "THIS SOFTWARE IS PROVIDED" in text:
        return "BSD (see upstream text)"
    return None


def split_components(candidates, seed=17, similarity=.9):
    """Join repositories sharing a CVE, exact code or >=90% token-5gram overlap.

    Components are ranked by a fixed salted hash; 70/15/15 applies to component
    counts, not examples. No score, label prevalence or model affects assignment.
    """
    repositories = sorted({r["repository"].lower() for r in candidates})
    parent = {r: r for r in repositories}

    def find(r):
        while parent[r] != r:
            parent[r] = parent[parent[r]]
            r = parent[r]
        return r

    def join(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[max(a, b)] = min(a, b)

    tokens = [(canonical(r["before"]), canonical(r["after"])) for r in candidates]
    shingles = [(grams(r["before"]), grams(r["after"])) for r in candidates]
    links = []
    for i, a in enumerate(candidates):
        for j in range(i):
            b = candidates[j]
            if a["repository"].lower() == b["repository"].lower():
                continue
            reason = "shared_cve" if a["cve"] == b["cve"] else None
            if not reason and any(x == y for x in tokens[i] for y in tokens[j]):
                reason = "identical_lexical_context"
            if not reason:
                for x in shingles[i]:
                    for y in shingles[j]:
                        if min(len(x), len(y)) >= 25 and len(x & y) / len(x | y) >= similarity:
                            reason = "near_duplicate_token_context"
            if reason:
                join(a["repository"].lower(), b["repository"].lower())
                links.append({"left": a["id"], "right": b["id"], "reason": reason})
    components = defaultdict(list)
    for r in repositories:
        components[find(r)].append(r)
    ordered = sorted(components.values(), key=lambda c: fingerprint({"seed": seed, "repositories": c}))
    if len(ordered) < 6:
        raise ValueError("At least six independent repository components are required")
    train_end = max(1, int(len(ordered) * .7))
    validation_end = min(len(ordered) - 1, train_end + max(1, int(len(ordered) * .15)))
    assignments = {}
    manifest = []
    for i, repos in enumerate(ordered):
        split = "train" if i < train_end else "validation" if i < validation_end else "test"
        group_id = "repo-" + fingerprint(repos)[:16]
        for repo in repos:
            assignments[repo] = (split, group_id)
        manifest.append({"group_id": group_id, "repositories": repos, "split": split})
    return assignments, manifest, links


def prepare_vul4j(cache, lock_path, output):
    cache, output = Path(cache), Path(output)
    lock = load_json(lock_path)
    csv_path = cache / "vul4j_dataset.csv"
    if sha256(csv_path) != lock["dataset_csv"]["sha256"]:
        raise ValueError("Pinned Vul4J CSV hash mismatch")
    if sha256(cache / "licences/Vul4J-DATA-LICENSE") != lock["dataset_licence"]["sha256"]:
        raise ValueError("Pinned Vul4J dataset licence hash mismatch")
    # Protect outputs that were not prepared by this importer.
    if output.exists() and any(output.iterdir()) and not (output / "cohort-manifest.json").exists():
        raise ValueError("Choose an empty dataset output directory")
    patch_lock = {p["id"]: p for p in lock["patches"]}
    licence_lock = {p["repository"]: p for p in lock["licences"]}
    candidates, exclusions = [], []
    rows = [r for r in csv.DictReader(csv_path.open(encoding="utf-8", newline="")) if int(r["no"]) <= 79]
    for row in rows:
        identity, repo = row["vul_id"], row["repo_slug"]
        try:
            source = patch_lock[identity]
            if source["status"] != "downloaded":
                raise ValueError("source_unavailable_in_pinned_release")
            patch = cache / "patches" / (identity + ".patch")
            if sha256(patch) != source["sha256"]:
                raise ValueError("Pinned patch hash mismatch: " + identity)
            documents = licence_lock[repo]["files"]
            if not documents:
                raise ValueError("upstream_licence_not_retrieved")
            for document in documents:
                if sha256(cache / "licences" / document["path"]) != document["sha256"]:
                    raise ValueError("Pinned licence hash mismatch: " + repo)
            licence = upstream_licence((cache / "licences" / documents[0]["path"]).read_text(encoding="utf-8", errors="strict"))
            if licence is None:
                raise ValueError("outside_verified_permissive_licence_subset")
            if not re.fullmatch(r"CVE-\d{4}-\d+", row["cve_id"]):
                raise ValueError("missing_cve_identifier")
            before, after, files, hunks = parse_patch(patch.read_text(encoding="utf-8"))
            candidates.append({"id": identity, "repository": repo, "cve": row["cve_id"],
                               "cwe": row["cwe_id"] if re.fullmatch(r"CWE-\d+", row["cwe_id"]) else "CWE-unknown",
                               "before": before, "after": after, "files": files, "hunks": hunks,
                               "commit_url": row["human_patch"], "licence": licence,
                               "patch_sha256": source["sha256"], "failing_tests": row["failing_tests"]})
        except ValueError as e:
            # Corrupt pinned inputs are errors, not sample-selection exclusions.
            if str(e).startswith("Pinned "):
                raise
            exclusions.append({"id": identity, "repository": repo, "reason": str(e)})
    # Conflicting labels on an identical context are not silently adjudicated.
    seen = defaultdict(list)
    for row in candidates:
        for label, code in [(1, row["before"]), (0, row["after"])]:
            seen[canonical(code)].append((row["id"], label))
    conflicts = {identity for values in seen.values() if len({label for _, label in values}) > 1 for identity, _ in values}
    accepted = []
    pair_seen = set()
    for row in candidates:
        key = (canonical(row["before"]), canonical(row["after"]))
        if row["id"] in conflicts or key in pair_seen:
            exclusions.append({"id": row["id"], "repository": row["repository"],
                               "reason": "conflicting_context_labels" if row["id"] in conflicts else "duplicate_pair"})
        else:
            pair_seen.add(key)
            accepted.append(row)
    assignments, components, links = split_components(accepted)
    examples = []
    for row in accepted:
        split, group = assignments[row["repository"].lower()]
        row.update(split=split, group_id=group)
        row["before_sha256"] = hashlib.sha256(row["before"].encode("utf-8")).hexdigest()
        row["after_sha256"] = hashlib.sha256(row["after"].encode("utf-8")).hexdigest()
        for label, code in [(1, row.pop("before")), (0, row.pop("after"))]:
            examples.append(Example(id=row["id"] + ("-before" if label else "-after"), pair_id=row["id"],
                                    group_id=group, split=split, label=label, cwe=row["cwe"],
                                    title=row["cve"] + " · " + row["repository"], code=code, view_code=code,
                                    rationale="Vul4J developer security correction; label inherited from the documented before/after patch context.",
                                    assumptions="Patch-centred Java context for " + row["cve"] + "; omitted surrounding code may affect interpretation. The fixed version is negative only for this documented correction. No PoV was re-executed in PatchLens.",
                                    source=row["commit_url"], licence=row["licence"] + "; Vul4J metadata CC-BY-4.0; see datasets/vul4j/licences",
                                    review_status="upstream_Vul4J_evidence_not_independently_adjudicated"))
    info = audit(examples)
    output.mkdir(parents=True, exist_ok=True)
    (output / "source").mkdir(exist_ok=True)
    (output / "licences").mkdir(exist_ok=True)
    shutil.copyfile(csv_path, output / "source/vul4j_dataset.csv")
    shutil.copyfile(lock_path, output / "source-lock.json")
    shutil.copyfile(cache / "licences/Vul4J-DATA-LICENSE", output / "licences/Vul4J-DATA-LICENSE")
    retained_repos = {r["repository"] for r in accepted}
    for repo in sorted(retained_repos):
        for doc in licence_lock[repo]["files"]:
            shutil.copyfile(cache / "licences" / doc["path"], output / "licences" / doc["path"])
    for row in accepted:
        shutil.copyfile(cache / "patches" / (row["id"] + ".patch"), output / "source" / (row["id"] + ".patch"))
    manifest = {"schema_version": "1.0", "name": "Vul4J public Java patch contexts", "dataset": info,
                "source_revision": lock["source_revision"], "source_url": lock["source_url"],
                "candidate_entries": len(rows), "retained_pairs": len(accepted), "repositories": len(retained_repos),
                "components": components, "connected_repository_links": links,
                "split_rule": "SHA256-ranked repository components, seed 17, floor(70%)/floor(15%)/remainder",
                "selection": "VUL4J-1 through VUL4J-79; retrievable single-commit patches, explicit permissive licences, nonempty changed production Java contexts; no performance-based filtering",
                "exclusion_counts": dict(Counter(r["reason"] for r in exclusions)), "exclusions": exclusions,
                "pairs": accepted, "view_kind": "identity", "view_meaning": "No source transformation or augmentation robustness experiment was performed",
                "labels": "1=before documented correction, 0=after correction for the listed CVE; patch context rather than complete-program ground truth",
                "near_duplicate_rule": "Join repositories for shared CVE, identical comment/whitespace-free lexical context, or >=0.90 Jaccard overlap of token 5-grams (minimum 25 unique grams)",
                "limits": ["Heuristic near-duplicate checks do not prove semantic independence", "Original upstream PoVs were not re-executed", "Balanced patch pairs do not represent vulnerability prevalence", "Repository separation does not establish separation from CodeBERT pretraining"]}
    write_jsonl(output / "dataset.jsonl", [e.to_dict() for e in examples])
    write_json(output / "cohort-manifest.json", manifest)
    return manifest
