import os
import tempfile
import unittest

from util import PIPELINE_DIR  # noqa: F401  (sys.path setup)

from harness.regression import (append_labels, auto_label_from_verdicts,
                                load_labels, regression_hits)


class TestRegressionStore(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "labeled.jsonl")

    def test_auto_labels_from_verdicts(self):
        # labels follow IDENTITY only: a must-have miss (li:miss) is a
        # property of that run's row, not of the person — the person labels
        # valid so future runs including them aren't permanent regression
        # hits, while the kept verdict still carries the miss into replay
        verdicts = {
            "li:good": {"name": "Good Person", "identity": "supported",
                        "must_haves": "meets"},
            "li:fake": {"name": "Fake Person", "identity": "contradicted",
                        "must_haves": "unclear"},
            "li:miss": {"name": "Miss Musthave", "identity": "supported",
                        "must_haves": "violates"},
        }
        entries = auto_label_from_verdicts("t001", verdicts, "run-1")
        by_key = {e["key"]: e["label"] for e in entries}
        self.assertEqual(by_key, {"li:good": "valid", "li:fake": "violation",
                                  "li:miss": "valid"})
        miss = next(e for e in entries if e["key"] == "li:miss")
        self.assertEqual(miss["verdict"]["must_haves"], "violates")

    def test_unchecked_candidates_get_no_label(self):
        # unreachable/unsupported = the validator never established anything;
        # freezing "valid" would permanently poison the store
        verdicts = {
            "li:down": {"name": "Site Down", "identity": "unreachable",
                        "must_haves": "unclear"},
            "li:thin": {"name": "Thin Sources", "identity": "unsupported",
                        "must_haves": "unclear"},
        }
        self.assertEqual(auto_label_from_verdicts("t001", verdicts, "run-1"), [])

    def test_human_override_beats_auto(self):
        append_labels(self.path, [
            {"scenario": "t001", "key": "li:x", "label": "valid", "provenance": "auto"}])
        append_labels(self.path, [
            {"scenario": "t001", "key": "li:x", "label": "violation", "provenance": "human"}])
        append_labels(self.path, [
            {"scenario": "t001", "key": "li:x", "label": "valid", "provenance": "auto"}])
        labels = load_labels(self.path)
        self.assertEqual(labels[("t001", "li:x")]["label"], "violation")

    def test_regression_hits_scoped_to_scenario(self):
        append_labels(self.path, [
            {"scenario": "t001", "key": "li:bad", "label": "violation", "provenance": "auto"},
            {"scenario": "t002", "key": "li:other", "label": "violation", "provenance": "auto"}])
        labels = load_labels(self.path)
        self.assertEqual(regression_hits("t001", labels, ["li:bad", "li:other", "li:ok"]),
                         ["li:bad"])

    def test_missing_file_is_empty(self):
        self.assertEqual(load_labels(self.path), {})


if __name__ == "__main__":
    unittest.main()
