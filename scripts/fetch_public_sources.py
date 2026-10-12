"""Download only pinned public dataset/model files; never run upstream code.

python scripts/fetch_public_sources.py data --output .cache/vul4j
python scripts/fetch_public_sources.py model --output .cache/codebert-base
"""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def fetch_one(item):
    url, path, expected = item
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == expected:
        return path.name
    temporary = path.with_name(path.name + ".part")
    digest = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=90) as response, temporary.open("wb") as stream:
        while chunk := response.read(1024 * 1024):
            digest.update(chunk)
            stream.write(chunk)
    if digest.hexdigest() != expected:
        raise ValueError("Downloaded source bytes disagree with the release lock: " + path.name)
    temporary.replace(path)
    return path.name


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("kind", choices=["data", "model"])
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.kind == "data":
        lock = json.loads((ROOT / "datasets/vul4j/source-lock.json").read_text(encoding="utf-8"))
        inputs = [(lock["dataset_csv"]["url"], args.output / "vul4j_dataset.csv", lock["dataset_csv"]["sha256"])]
        inputs.append((lock["dataset_licence"]["url"], args.output / "licences/Vul4J-DATA-LICENSE", lock["dataset_licence"]["sha256"]))
        inputs += [(r["url"], args.output / "patches" / (r["id"] + ".patch"), r["sha256"]) for r in lock["patches"] if r["status"] == "downloaded"]
        inputs += [(r["url"], args.output / "licences" / r["path"], r["sha256"]) for repo in lock["licences"] for r in repo["files"]]
    else:
        lock = json.loads((ROOT / "configs/codebert-lock.json").read_text(encoding="utf-8"))
        inputs = [(f"https://huggingface.co/{lock['model_id']}/resolve/{lock['revision']}/{f}", args.output / f, digest) for f, digest in lock["files_sha256"].items()]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for name in pool.map(fetch_one, inputs):
            print("Verified " + name, flush=True)


if __name__ == "__main__":
    main()
