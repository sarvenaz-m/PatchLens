import copy
import json
from pathlib import Path
import unittest

from patchlens.analysis import analyze_report, calibration, compare_reports, validate_report

REPORT = Path(__file__).resolve().parents[1] / "examples/fixture-run/report.json"


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.report = json.loads(REPORT.read_text())

    def test_perfect_probabilities_include_right_endpoint(self):
        result = calibration([0, 1], [0., 1.])
        self.assertEqual(result["brier"], 0.)
        self.assertEqual(result["ece"], 0.)
        self.assertEqual(result["bins"][0]["n"], 1)
        self.assertEqual(result["bins"][-1]["n"], 1)
        self.assertIsNone(result["bins"][4]["observed_rate"])
        self.assertGreater(result["bins"][0]["observed_wilson_95"][1], .7)

    def test_calibration_is_hand_calculable(self):
        result = calibration([0, 1, 1, 0], [.1, .6, .8, .3], bins=2)
        self.assertAlmostEqual(result["brier"], .075)
        self.assertAlmostEqual(result["ece"], .25)
        self.assertEqual([b["n"] for b in result["bins"]], [2, 2])

    def test_invalid_calibration_is_rejected(self):
        for bins in (True, 1, 21, 2.5):
            with self.assertRaises(ValueError):
                calibration([0, 1], [.1, .9], bins)
        with self.assertRaises(ValueError):
            calibration([0, 1], [.1, float("nan")])

    def test_diagnostics_match_reference_and_do_not_mutate(self):
        original = copy.deepcopy(self.report)
        result = analyze_report(self.report)
        self.assertEqual(result["metrics"]["f1"], 10 / 11)
        self.assertEqual(sum(s["n"] for s in result["by_cwe"].values()), 12)
        self.assertEqual(len(result["pair_margins"]), 6)
        self.assertEqual(self.report, original)

    def test_dataset_hash_cannot_mask_changed_code(self):
        self.report["samples"][0]["code"] += "\n// altered"
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            validate_report(self.report)

    def test_prediction_identity_is_exact(self):
        self.report["runs"][0]["predictions"][0] = self.report["runs"][0]["predictions"][1]
        with self.assertRaisesRegex(ValueError, "exact example"):
            validate_report(self.report)

    def test_paired_comparison_is_id_aligned_and_deterministic(self):
        candidate = copy.deepcopy(self.report)
        for run in candidate["runs"]:
            run["predictions"].reverse()
        first = compare_reports(self.report, candidate, draws=200, seed=43)
        second = compare_reports(self.report, candidate, draws=200, seed=43)
        self.assertEqual(first, second)
        self.assertEqual(first["outcomes"]["improved"], 1)
        self.assertEqual(first["outcomes"]["regressed"], 0)
        self.assertEqual(first["groups"], 6)
        self.assertEqual(first["bootstrap"]["unit"], "group_id")

    def test_self_comparison_has_zero_interval(self):
        result = compare_reports(self.report, self.report, "weighted", "weighted", draws=200)
        self.assertEqual(result["accuracy_delta"], 0.)
        self.assertEqual(result["bootstrap"]["accuracy_delta_percentile_95"], [0., 0.])
        self.assertEqual(result["outcomes"]["both_wrong"], 1)

    def test_whole_groups_are_resampled(self):
        baseline, candidate = copy.deepcopy(self.report), copy.deepcopy(self.report)
        labels = {s["id"]: s["label"] for s in baseline["samples"]}
        target = next(s["group_id"] for s in baseline["samples"] if s["split"] == "test")
        affected = {s["id"] for s in baseline["samples"] if s["group_id"] == target}
        for report in (baseline, candidate):
            for run in report["runs"]:
                run["threshold"] = .5
                run["operating_point"]["threshold"] = .5
                for p in run["predictions"]:
                    p["score"] = .9 if labels[p["id"]] else .1
                    if report is candidate and p["id"] in affected:
                        p["score"] = 1 - p["score"]
        result = compare_reports(baseline, candidate, draws=2000)
        self.assertAlmostEqual(result["accuracy_delta"], -1 / 6)
        self.assertEqual(result["bootstrap"]["accuracy_delta_percentile_95"], [-.5, 0.])

    def test_invalid_comparison_options_fail(self):
        conflict = copy.deepcopy(self.report)
        conflict["runs"][0]["threshold"] = .37
        with self.assertRaisesRegex(ValueError, "provenance"):
            validate_report(conflict)
        with self.assertRaises(ValueError):
            compare_reports(self.report, self.report, draws=199)
        with self.assertRaises(ValueError):
            analyze_report(self.report, run_id="missing")
        with self.assertRaises(ValueError):
            analyze_report(self.report, split="unknown")


if __name__ == "__main__":
    unittest.main()
