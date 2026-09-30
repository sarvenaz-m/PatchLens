"""Static analysis interchange. Findings are never converted to security labels."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import shutil
import subprocess
from urllib.parse import unquote, urlparse

from .data import audit
from .io import fingerprint, load_json, write_json


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def export_sources(samples, destination):
    destination = Path(destination)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Choose an empty source-export directory")
    info = audit(samples)
    (destination / "src").mkdir(parents=True, exist_ok=True)
    files = []
    for sample in samples:
        relative = "src/" + sample.id + ".js"
        path = destination / relative
        path.write_text(sample.code, encoding="utf-8")
        files.append({"path": relative, "example_id": sample.id, "sha256": digest(path)})
    manifest = {"schema_version": "1.0", "dataset_sha256": info["fingerprint"], "files": files}
    write_json(destination / "manifest.json", manifest)
    return manifest


def import_sarif(payload, manifest):
    """Resolve relative/absolute SARIF locations against a unique source manifest.

    A SARIF file does not prove that all input files were analysed. Coverage is
    deliberately marked unverified, even when a run has no reported errors.
    """
    if payload.get("version") != "2.1.0" or not payload.get("runs"):
        raise ValueError("Expected non-empty SARIF 2.1.0 runs")
    files = manifest.get("files", [])
    if not files or len({f["path"] for f in files}) != len(files):
        raise ValueError("A unique source manifest is required")
    if len({f["example_id"] for f in files}) != len(files):
        raise ValueError("Manifest example IDs must be unique")
    paths = {f["path"].replace("\\", "/"): f["example_id"] for f in files}
    findings, unmapped, errors, tools = [], [], [], []
    failed = False
    for run in payload["runs"]:
        driver = run.get("tool", {}).get("driver", {})
        tools.append({"name": driver.get("name", "unknown"), "version": driver.get("semanticVersion", driver.get("version", "unknown"))})
        for invocation in run.get("invocations", []):
            failed |= invocation.get("executionSuccessful") is False
            for notification in invocation.get("toolExecutionNotifications", []):
                if notification.get("level") in ("error", "warning"):
                    errors.append(notification.get("message", {}).get("text", "Scanner notification"))
        artifacts = run.get("artifacts", [])
        rules = driver.get("rules", [])
        for item in run.get("results", []):
            rule = item.get("ruleId")
            if rule is None and isinstance(item.get("ruleIndex"), int):
                index = item["ruleIndex"]
                if 0 <= index < len(rules):
                    rule = rules[index].get("id")
            # Multiple locations describe one result; retain one finding per
            # distinct input/line. Exact duplicates are removed below.
            for location in item.get("locations", [{}]):
                physical = location.get("physicalLocation", {})
                artifact = physical.get("artifactLocation", {})
                uri = artifact.get("uri")
                if uri is None and isinstance(artifact.get("index"), int):
                    index = artifact["index"]
                    if 0 <= index < len(artifacts):
                        uri = artifacts[index].get("location", {}).get("uri")
                raw = unquote(uri or "").replace("\\", "/")
                if raw.startswith("file:"):
                    raw = urlparse(raw).path
                raw = raw.removeprefix("./")
                matches = [value for path, value in paths.items() if raw == path or raw.endswith("/" + path)]
                line = physical.get("region", {}).get("startLine", 1)
                if type(line) is not int or line < 1:
                    raise ValueError("Invalid SARIF line number")
                finding = {"example_id": matches[0] if len(matches) == 1 else None,
                           "rule": str(rule or "unknown"), "line": line,
                           "message": str(item.get("message", {}).get("text", "")),
                           "severity": str(item.get("level", "warning")),
                           "scanner": str(driver.get("name", "unknown"))}
                if finding["example_id"] is None:
                    unmapped.append({**finding, "path": raw})
                else:
                    findings.append(finding)
    findings = list({fingerprint(f): f for f in findings}.values())
    return {"schema_version": "1.0", "status": "failed" if failed else "completed_with_errors" if errors or unmapped else "completed",
            "findings": findings, "unmapped": unmapped, "errors": errors, "tools": tools,
            "dataset_sha256": manifest["dataset_sha256"], "input_ids": [f["example_id"] for f in files],
            "coverage": "Input manifest only; per-file scanner coverage is not established by SARIF",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "meaning": "No finding is not evidence that code is secure"}


def run_codeql(source_dir, output, *, query_suite, executable="codeql", timeout=900):
    """Create a JavaScript database, analyse it and retain raw SARIF.

    Source export is text only. No project build or package install is run.
    The user installs CodeQL and its query packs under their permitted terms.
    """
    source_dir, output = Path(source_dir).resolve(), Path(output).resolve()
    manifest = load_json(source_dir / "manifest.json")
    for item in manifest["files"]:
        source = (source_dir / item["path"]).resolve()
        if not source.is_relative_to(source_dir) or digest(source) != item["sha256"]:
            raise ValueError("Source manifest does not match exported code")
    binary = shutil.which(executable)
    if not binary:
        raise ValueError("CodeQL CLI is not installed; use import-sarif for an existing scan")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Choose an empty CodeQL output directory")
    if not query_suite or timeout <= 0:
        raise ValueError("Pass a query suite and a positive timeout")
    output.mkdir(parents=True, exist_ok=True)
    commands = [
        [binary, "database", "create", str(output / "database"), "--language=javascript-typescript", "--source-root=" + str(source_dir / "src")],
        [binary, "database", "analyze", str(output / "database"), query_suite, "--format=sarifv2.1.0", "--output=" + str(output / "results.sarif")],
    ]
    # CodeQL paths are relative to its source root (src/), so retain that map.
    codeql_manifest = {**manifest, "files": [{**f, "path": Path(f["path"]).name} for f in manifest["files"]]}
    write_json(output / "manifest.json", codeql_manifest)
    for index, command in enumerate(commands):
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            write_json(output / "status.json", {"status": "failed", "stage": index, "reason": "timeout"})
            raise ValueError("CodeQL timed out; no completed scan is claimed") from exc
        (output / f"stage-{index}.log").write_text(result.stdout + result.stderr, encoding="utf-8")
        if result.returncode:
            write_json(output / "status.json", {"status": "failed", "stage": index, "returncode": result.returncode})
            raise ValueError("CodeQL failed; inspect the saved stage log")
    scan = import_sarif(load_json(output / "results.sarif"), codeql_manifest)
    scan["query_suite"] = query_suite
    write_json(output / "scan.json", scan)
    return scan
