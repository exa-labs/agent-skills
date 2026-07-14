import unittest

from util import PIPELINE_DIR  # noqa: F401  (sys.path setup)

from harness.optimizer import _slug


class TestSlugSanitization(unittest.TestCase):
    def test_llm_slugs_become_valid_branch_names(self):
        cases = {
            "tighten-ranking": "tighten-ranking",
            "tighten ranking": "tighten-ranking",
            "fix: dupes!": "fix-dupes",
            "a/b nested": "a-b-nested",
            "Weird~^:?*Chars": "weird-chars",
            "": "edit",
            None: "edit",
            "x" * 100: "x" * 30,
        }
        for raw, expected in cases.items():
            self.assertEqual(_slug({"slug": raw}), expected, raw)

    def test_missing_slug_key(self):
        self.assertEqual(_slug({}), "edit")


if __name__ == "__main__":
    unittest.main()
