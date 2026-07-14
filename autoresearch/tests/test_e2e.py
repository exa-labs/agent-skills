"""The integration test: a full evaluation cycle with zero network and zero
real LLMs. fake_claude.py plays all four roles; the temp skill repo plays the
skill. This proves the plumbing — session loop with resume, env shims,
validation, labeling, suite scoring, and a whole optimizer round with
branching, apply, evaluation, and the needs_live parking rule — before a
single live dollar is spent."""
import json
import os
import subprocess
import tempfile
import unittest

from util import CLEAN_ROWS, fake_claude_env, make_pipeline, write_csv

from harness.optimizer import optimize_round, read_log
from harness.regression import load_labels
from harness.runner import find_latest_suite, run_one, run_suite
from harness.scoring import run_score


class TestEndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.config = make_pipeline(self.tmp)
        canned = write_csv(os.path.join(self.tmp, "canned.csv"), CLEAN_ROWS)
        self._saved = dict(os.environ)
        os.environ.update(fake_claude_env(canned))

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._saved)

    def test_full_cycle(self):
        config = self.config

        # -- 1. live run: session completes, validator grounds, labels freeze --
        info, scorecard = run_one(config, "t001", "main", "live")
        self.assertTrue(info["completed"], info["failure"])
        self.assertEqual(scorecard["violation_counts"], {})
        self.assertEqual(scorecard["grounding"]["candidates_checked"], 3)
        self.assertEqual(scorecard["grounding"]["claims_supported"], 9)
        self.assertIsNotNone(scorecard["ux"])
        self.assertGreaterEqual(info["turns"], 3)

        labels = load_labels(config.path("regression"))
        self.assertEqual(len(labels), 3)
        self.assertTrue(all(e["label"] == "valid" for e in labels.values()))

        run_dir = os.path.join(config.path("runs"), info["run_id"])
        for artifact in ("session.json", "conversation.json", "scorecard.json",
                         "transcript-turn00.jsonl"):
            self.assertTrue(os.path.isfile(os.path.join(run_dir, artifact)), artifact)

        score = run_score(scorecard, config["scoring"])
        self.assertEqual(score["gate_failures"], [])
        self.assertGreater(score["composite"], 90)

        # -- 2. replay run: fixtures in, labels joined, no live grounding -----
        info2, scorecard2 = run_one(config, "t001", "main", "replay")
        self.assertTrue(info2["completed"], info2["failure"])
        run_dir2 = os.path.join(config.path("runs"), info2["run_id"])
        self.assertTrue(os.path.isfile(os.path.join(run_dir2, "outdir", "exa_runs", "pool.json")))
        self.assertEqual(scorecard2["grounding"]["candidates_checked"], 3)
        self.assertEqual(scorecard2["grounding"]["unlabeled"], 0)
        self.assertEqual(scorecard2["regression_hits"], [])

        # -- 3. suite in replay mode ------------------------------------------
        suite = run_suite(config, "main", "replay")
        self.assertEqual(suite["score"]["scenario_count"], 1)
        self.assertEqual(suite["score"]["gate_failed_runs"], [])
        self.assertGreater(suite["score"]["composite"], 90)
        self.assertEqual(suite["skipped"], [])
        found = find_latest_suite(config, ref="main", mode="replay")
        self.assertEqual(found["suite_id"], suite["suite_id"])

        # -- 4. optimizer round: propose 2, park the search one, eval the other
        report = optimize_round(config, mode="replay", promote=True)
        self.assertEqual(len(report["experiments"]), 2)
        by_verdict = {e["branch"]: e for e in report["experiments"]}
        rank_exp = next(e for b, e in by_verdict.items() if "tighten-ranking" in b)
        search_exp = next(e for b, e in by_verdict.items() if "search-fanout" in b)
        self.assertEqual(search_exp["verdict"], "needs_live")
        self.assertIn(rank_exp["verdict"], ("accept", "reject"))
        self.assertIn("deltas", rank_exp)

        # both experiment branches were committed and pushed to the source repo
        out = subprocess.run(["git", "-C", config.skill_repo, "branch",
                              "--format=%(refname:short)"],
                             capture_output=True, text=True, check=True).stdout
        self.assertIn("tighten-ranking", out)
        self.assertIn("search-fanout", out)

        # log + report persisted
        self.assertEqual(len(read_log(config)), 2)
        self.assertTrue(os.path.isfile(report["report_path"]))

    def test_regression_hit_fails_gate(self):
        config = self.config
        from harness.regression import append_labels
        append_labels(config.path("regression"),
                      [{"scenario": "t001", "key": "li:cara-mott", "name": "Cara Mott",
                        "label": "violation", "provenance": "human",
                        "notes": "verified wrong person"}])
        _, scorecard = run_one(config, "t001", "main", "replay")
        self.assertEqual(scorecard["regression_hits"], ["li:cara-mott"])
        score = run_score(scorecard, config["scoring"])
        self.assertIn("regression_hits x1", score["gate_failures"])

    def test_unreviewed_scenario_is_skipped_from_suite(self):
        sdir = os.path.join(self.config.path("suite"), "t002-unreviewed")
        os.makedirs(sdir)
        with open(os.path.join(sdir, "scenario.json"), "w") as f:
            json.dump({"id": "t002", "title": "unreviewed", "target_count": 5,
                       "status": "needs_review"}, f)
        for name, content in (("jd.md", "jd"), ("persona.md", "TODO"),
                              ("expectations.json", "{}")):
            with open(os.path.join(sdir, name), "w") as f:
                f.write(content)
        suite = run_suite(self.config, "main", "replay", scenario_ids=["t002"])
        self.assertEqual(suite["score"]["scenario_count"], 0)
        self.assertEqual(suite["skipped"][0]["scenario"], "t002")
        self.assertIn("needs_review", suite["skipped"][0]["reason"])

    def test_inner_failure_is_scored_not_crashed(self):
        os.environ["FAKE_INNER_NO_CSV"] = "1"
        try:
            info, scorecard = run_one(self.config, "t001", "main", "replay")
        finally:
            os.environ.pop("FAKE_INNER_NO_CSV", None)
        self.assertFalse(info["completed"])
        self.assertFalse(scorecard["completed"])
        score = run_score(scorecard, self.config["scoring"])
        self.assertIn("session_incomplete", score["gate_failures"])
        self.assertEqual(score["components"]["delivery"], 0.0)


if __name__ == "__main__":
    unittest.main()
