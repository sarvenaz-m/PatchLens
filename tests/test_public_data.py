import copy
import unittest

from patchlens.benchmark import head_tail
from patchlens.data import Example
from patchlens.public_data import canonical, parse_patch, split_components


PATCH = """diff --git a/src/main/java/Guard.java b/src/main/java/Guard.java
--- a/src/main/java/Guard.java
+++ b/src/main/java/Guard.java
@@ -1,3 +1,4 @@
 public void check(String value) {
-    use(value);
+    if (value == null) return;
+    use(value);
 }
diff --git a/src/test/java/GuardTest.java b/src/test/java/GuardTest.java
--- a/src/test/java/GuardTest.java
+++ b/src/test/java/GuardTest.java
@@ -1 +1 @@
-oldTest();
+newTest();
"""


class PublicSourceTests(unittest.TestCase):
    def test_extracts_actual_sides_and_excludes_tests(self):
        before, after, files, hunks = parse_patch(PATCH)
        self.assertEqual(before, "public void check(String value) {\n    use(value);\n}\n")
        self.assertIn("if (value == null) return;", after)
        self.assertNotIn("oldTest", before)
        self.assertEqual(files, ["src/main/java/Guard.java"])
        self.assertEqual(hunks[0]["old_count"], 3)
        self.assertNotIn("Guard.java", before)

    def test_rejects_truncated_hunk(self):
        with self.assertRaisesRegex(ValueError, "truncated_hunk"):
            parse_patch(PATCH.split("diff --git a/src/test")[0].replace("+1,4", "+1,5"))

    def test_rejects_spacing_comment_only_change(self):
        patch = PATCH.split("diff --git a/src/test")[0].replace("+1,4", "+1,3").replace("+    if (value == null) return;\n+    use(value);", "+    use ( value ); // spacing")
        with self.assertRaisesRegex(ValueError, "no_lexical_code_change"):
            parse_patch(patch)

    def test_canonical_keeps_security_relevant_literal_changes(self):
        self.assertNotEqual(canonical('allow("http")'), canonical('allow("https")'))

    def test_shared_cve_and_code_keep_repositories_together(self):
        candidates = [{"id": str(i), "repository": f"org/repo{i}", "cve": f"CVE-2020-{i}",
                       "before": f"call{i}();", "after": f"guard{i}();"} for i in range(10)]
        candidates[1]["cve"] = candidates[0]["cve"]
        candidates[3]["before"] = candidates[2]["before"]
        assignment, components, links = split_components(candidates)
        self.assertEqual(assignment["org/repo0"], assignment["org/repo1"])
        self.assertEqual(assignment["org/repo2"], assignment["org/repo3"])
        self.assertEqual({c["split"] for c in components}, {"train", "validation", "test"})
        self.assertEqual({x["reason"] for x in links}, {"shared_cve", "identical_lexical_context"})
        self.assertEqual(split_components(list(reversed(candidates)))[0], assignment)

    def test_head_tail_does_not_overrun_odd_budget(self):
        self.assertEqual(head_tail(list(range(10)), 5), [0, 1, 9])
        self.assertEqual(len(head_tail(list(range(1000)), 512)), 510)
        self.assertEqual(head_tail([1, 2], 4), [1, 2])

    def test_no_synthetic_cwe_assignment(self):
        from patchlens.data import fixture_path, load_dataset
        obj = load_dataset(fixture_path())[0].to_dict()
        obj["cwe"] = "CWE-unknown"
        self.assertEqual(Example.from_dict(obj).cwe, "CWE-unknown")


if __name__ == "__main__":
    unittest.main()
