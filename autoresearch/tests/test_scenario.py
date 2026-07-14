import json
import os
import tempfile
import unittest

from util import EXPECTATIONS  # noqa: F401  (sys.path setup)

from harness.scenario import (ScenarioError, get_scenario, import_inbox,
                              list_scenarios)


class TestScenario(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.inbox = os.path.join(self.tmp, "inbox")
        self.suite = os.path.join(self.tmp, "scenarios")
        os.makedirs(self.inbox)
        os.makedirs(self.suite)

    def test_import_scaffolds_and_empties_inbox(self):
        with open(os.path.join(self.inbox, "Staff Platform Engineer.md"), "w") as f:
            f.write("# Staff Platform Engineer\nKubernetes, 8+ years.\n")
        with open(os.path.join(self.inbox, "README.md"), "w") as f:
            f.write("ignore me")

        created = import_inbox(self.inbox, self.suite)
        self.assertEqual(len(created), 1)
        sdir = created[0]
        self.assertTrue(os.path.basename(sdir).startswith("s001-staff-platform"))
        for name in ("scenario.json", "jd.md", "persona.md", "expectations.json", "jd.source"):
            self.assertTrue(os.path.isfile(os.path.join(sdir, name)), name)
        self.assertEqual(sorted(os.listdir(self.inbox)), ["README.md"])

        s = get_scenario(self.suite, "s001")
        self.assertEqual(s.meta["status"], "needs_review")
        self.assertIn("Kubernetes", s.jd)
        # defaults merged
        self.assertFalse(s.expectations["location"]["strict"])
        self.assertEqual(s.expectations["excluded_people"], [])

    def test_ids_increment(self):
        for name in ("a.md", "b.md"):
            with open(os.path.join(self.inbox, name), "w") as f:
                f.write("jd")
        import_inbox(self.inbox, self.suite)
        self.assertEqual([s.id for s in list_scenarios(self.suite)], ["s001", "s002"])

    def test_partial_location_expectations_merge_defaults(self):
        with open(os.path.join(self.inbox, "c.md"), "w") as f:
            f.write("jd")
        sdir = import_inbox(self.inbox, self.suite)[0]
        with open(os.path.join(sdir, "expectations.json"), "w") as f:
            json.dump({"target_count": 10, "location": {"strict": True}}, f)
        s = get_scenario(self.suite, "s001")
        self.assertTrue(s.expectations["location"]["strict"])
        self.assertTrue(s.expectations["location"]["allow_unknown"])
        self.assertEqual(s.expectations["must_have_column_patterns"], [])

    def test_missing_scenario_raises(self):
        with self.assertRaises(ScenarioError):
            get_scenario(self.suite, "s999")


if __name__ == "__main__":
    unittest.main()
