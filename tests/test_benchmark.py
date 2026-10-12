from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest

from patchlens.benchmark import load_embeddings, run_benchmark
from patchlens.data import load_dataset
from patchlens.io import load_json, write_json

ROOT = Path(__file__).resolve().parents[1]


class PublicBenchmarkIntegrationTests(unittest.TestCase):
    def test_publishes_complete_reference_and_seed_reports_with_all_models(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            protocol = load_json(ROOT / "configs/public-benchmark.json")
            protocol.update(epochs=2, training_seeds=[17])
            protocol["probe"]["epochs"] = 2
            protocol["bootstrap"]["draws"] = 200
            write_json(p / "protocol.json", protocol)
            with redirect_stdout(io.StringIO()):
                run_benchmark(ROOT / "datasets/vul4j/dataset.jsonl", ROOT / "datasets/vul4j/cohort-manifest.json",
                              p / "protocol.json", p / "run", embedding_cache=ROOT / "examples/public-benchmark/encoder")
            reference = load_json(p / "run/report.json")
            self.assertEqual(reference, load_json(p / "run/seed-17/report.json"))
            self.assertEqual({r["id"] for r in reference["runs"]}, {"linear", "supervised", "contrastive", "weighted", "codebert", "constant"})
            self.assertEqual(reference["config"]["benchmark_protocol"], protocol)
            self.assertIn("codebert", (p / "run/seed-17/workbench/report-data.js").read_text())

    def test_saved_embedding_hash_rejects_corruption(self):
        source = ROOT / "examples/public-benchmark/encoder"
        samples = load_dataset(ROOT / "datasets/vul4j/dataset.jsonl")
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            (p / "embeddings.npz").write_bytes((source / "embeddings.npz").read_bytes() + b"corrupted")
            write_json(p / "embedding-provenance.json", load_json(source / "embedding-provenance.json"))
            with self.assertRaisesRegex(ValueError, "Embedding byte fingerprint"):
                load_embeddings(samples, p)


if __name__ == "__main__":
    unittest.main()
