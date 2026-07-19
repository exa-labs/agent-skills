import os
import tempfile
import unittest

from util import CLEAN_ROWS, CSV_COLUMNS, EXPECTATIONS, write_csv  # noqa: F401

from harness.validator.deterministic import check_run


def types(result):
    return sorted({v["type"] for v in result["violations"]})


class TestDeterministic(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def _check(self, rows):
        path = write_csv(os.path.join(self.tmp, "candidates.csv"), rows)
        return check_run(path, EXPECTATIONS)

    def test_clean_run_has_no_violations(self):
        result = self._check(CLEAN_ROWS)
        self.assertEqual(result["violations"], [])
        self.assertEqual(result["stats"]["returned"], 3)
        self.assertEqual(result["stats"]["identity_wellformed"], 3)
        self.assertEqual(result["stats"]["must_have_columns_checked"], ["backendEngineering"])

    def test_missing_csv_is_malformed(self):
        result = check_run(os.path.join(self.tmp, "nope.csv"), EXPECTATIONS)
        self.assertEqual(types(result), ["malformed_output"])

    def test_excluded_employer_is_suspected_not_gated(self):
        # substring matching cannot disambiguate org names ("citadel" matches
        # Citadel Federal Credit Union) — it trips a suspected flag for the
        # grounding validator to adjudicate, never a gated violation
        row = list(CLEAN_ROWS[0])
        row[4] = "BigCorp Cloud Division"
        result = self._check([row])
        self.assertIn("excluded_employer_suspected", types(result))
        self.assertNotIn("excluded_employer_leak", types(result))

    def test_excluded_person_leak(self):
        row = list(CLEAN_ROWS[0])
        row[1] = "Zed Nixon"
        row[2] = "https://linkedin.com/in/zed-nixon"
        self.assertIn("excluded_person_leak", types(self._check([row])))

    def test_duplicate_candidate(self):
        rows = [CLEAN_ROWS[0], list(CLEAN_ROWS[0])]
        rows[1] = list(rows[1]); rows[1][0] = "2"
        self.assertIn("duplicate_candidate", types(self._check(rows)))

    def test_fabricated_identity(self):
        bad_name = list(CLEAN_ROWS[0]); bad_name[1] = "Unknown"
        bad_url = list(CLEAN_ROWS[1]); bad_url[2] = "https://linkedin.com/company/acme"
        result = self._check([bad_name, bad_url])
        self.assertEqual([v["type"] for v in result["violations"]].count("fabricated_identity"), 2)

    def test_location_strict_splits_by_precision(self):
        # a non-matching location STRING is only suspected (regexes don't know
        # geography); a MISSING location under a strict constraint is the
        # run's own defect and stays gate-eligible
        elsewhere = list(CLEAN_ROWS[0]); elsewhere[5] = "Berlin, Germany"
        unknown = list(CLEAN_ROWS[1]); unknown[5] = ""
        result = self._check([elsewhere, unknown])
        by_type = [v["type"] for v in result["violations"]]
        self.assertEqual(by_type.count("location_suspected"), 1)
        self.assertEqual(by_type.count("location_violation"), 1)

    def test_location_not_strict_passes(self):
        row = list(CLEAN_ROWS[0]); row[5] = "Berlin, Germany"
        exp = dict(EXPECTATIONS, location={"strict": False, "accept_patterns": [],
                                           "allow_unknown": True})
        path = write_csv(os.path.join(self.tmp, "candidates.csv"), [row])
        self.assertEqual(check_run(path, exp)["violations"], [])

    def test_must_have_graded_none(self):
        row = list(CLEAN_ROWS[0]); row[CSV_COLUMNS.index("backendEngineering")] = "none"
        self.assertIn("must_have_violation", types(self._check([row])))

    def test_verify_leaks(self):
        not_found = list(CLEAN_ROWS[0]); not_found[CSV_COLUMNS.index("verify_exists")] = "not_found"
        no_match = list(CLEAN_ROWS[1]); no_match[CSV_COLUMNS.index("verify_match")] = "no"
        result = self._check([not_found, no_match])
        self.assertIn("verify_status_leak", types(result))
        self.assertIn("must_have_violation", types(result))


if __name__ == "__main__":
    unittest.main()
