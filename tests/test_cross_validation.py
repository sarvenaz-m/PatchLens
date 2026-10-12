import unittest

from patchlens.cross_validation import fold_assignment, pool_oof


class RepositoryFoldTests(unittest.TestCase):
    def test_each_component_is_tested_and_validated_once(self):
        cohort = {"components": [{"group_id": f"repo-{i}"} for i in range(40)]}
        assignments = [fold_assignment(cohort, fold) for fold in range(5)]
        for c in cohort["components"]:
            states = [a[c["group_id"]] for a in assignments]
            self.assertEqual(states.count("test"), 1)
            self.assertEqual(states.count("validation"), 1)
            self.assertEqual(states.count("train"), 3)
        for a in assignments:
            self.assertEqual(list(a.values()).count("test"), 8)

    def rows(self):
        return [{"id": "a-before", "pair_id": "a", "group_id": "repo-a", "label": 1, "fold": 0,
                 "score": .45, "threshold": .4, "decision": 1},
                {"id": "a-after", "pair_id": "a", "group_id": "repo-a", "label": 0, "fold": 0,
                 "score": .35, "threshold": .4, "decision": 0},
                {"id": "b-before", "pair_id": "b", "group_id": "repo-b", "label": 1, "fold": 1,
                 "score": .85, "threshold": .8, "decision": 1},
                {"id": "b-after", "pair_id": "b", "group_id": "repo-b", "label": 0, "fold": 1,
                 "score": .75, "threshold": .8, "decision": 0}]

    def test_pools_fold_decisions_instead_of_applying_a_global_threshold(self):
        result = pool_oof(self.rows())
        self.assertEqual(result["macro_balanced_accuracy"], 1)
        self.assertEqual(result["macro_pair_both_correct"], 1)
        self.assertEqual(result["pooled_counts"]["fp"], 0)

    def test_rejects_duplicate_out_of_fold_prediction(self):
        rows = self.rows()
        with self.assertRaisesRegex(ValueError, "unique originals"):
            pool_oof(rows + [rows[0]])

    def test_rejects_mixed_test_folds_for_one_repository(self):
        rows = self.rows()
        rows[1]["fold"] = 1
        with self.assertRaisesRegex(ValueError, "crosses test folds"):
            pool_oof(rows)

    def test_rejects_missing_sibling_and_bad_decision(self):
        with self.assertRaisesRegex(ValueError, "both code versions"):
            pool_oof(self.rows()[:-1])
        rows = self.rows()
        rows[0]["decision"] = 0
        with self.assertRaisesRegex(ValueError, "disagrees"):
            pool_oof(rows)


if __name__ == "__main__":
    unittest.main()
