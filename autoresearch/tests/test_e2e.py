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

from util import (CLEAN_ROWS, PEOPLE_CLEAN_ROWS, PEOPLE_CSV_COLUMNS,
                  fake_claude_env, make_pipeline, write_csv)

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
        self.assertGreater(suite["skill_size"]["chars"], 0)  # parsimony metric recorded
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

    def test_flaky_user_turn_is_retried_once(self):
        # one unparseable user reply (cents) must not abandon the whole
        # session (dollars); the raw text is persisted for diagnosis
        sentinel = os.path.join(self.tmp, "bad-json-tripped")
        os.environ["FAKE_USER_BAD_JSON_ONCE"] = sentinel
        self.addCleanup(os.environ.pop, "FAKE_USER_BAD_JSON_ONCE", None)
        info, _ = run_one(self.config, "t001", "main", "live")
        self.assertTrue(os.path.exists(sentinel))  # the flake actually fired
        self.assertTrue(info["completed"], info["failure"])
        run_dir = os.path.join(self.config.path("runs"), info["run_id"])
        dumps = [n for n in os.listdir(run_dir) if n.startswith("user-unparseable-")]
        self.assertEqual(len(dumps), 1)
        with open(os.path.join(run_dir, dumps[0])) as f:
            self.assertIn("without any valid", f.read())

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

    def _plant_state(self, run_id):
        outdir = os.path.join(self.config.path("runs"), run_id, "outdir")
        os.makedirs(outdir)
        with open(os.path.join(outdir, "sourcing_state.json"), "w") as f:
            json.dump({"pool": [{"name": "Ana Ruiz",
                                 "linkedinUrl": "https://linkedin.com/in/ana-ruiz"}],
                       "verdicts": {}}, f)

    def test_suite_style_run_id_records_flat_bundle(self):
        # run_suite passes run_id="<suite_id>/<scenario>"; the recording id
        # must be flattened or the bundle nests one level below where
        # latest_bundle() looks and every suite recording is invisible to replay
        run_id = "20990101-000000-suite-main-live/t001"
        self._plant_state(run_id)
        info, _ = run_one(self.config, "t001", "main", "live",
                          run_id=run_id, record=True)
        self.assertTrue(info["completed"], info["failure"])
        bundle = info["fixture_bundle"]
        self.assertIsNotNone(bundle)
        self.assertEqual(os.path.dirname(bundle),
                         os.path.join(self.config.path("fixtures"), "t001"))
        self.assertTrue(os.path.isfile(os.path.join(bundle, "pool.json")))

    def test_incomplete_session_records_no_bundle(self):
        # a partial pool from an aborted run must never freeze into fixtures
        run_id = "fixed-incomplete-run"
        self._plant_state(run_id)
        os.environ["FAKE_CLAUDE_ERROR"] = "network down"
        self.addCleanup(os.environ.pop, "FAKE_CLAUDE_ERROR", None)
        info, _ = run_one(self.config, "t001", "main", "live",
                          run_id=run_id, record=True)
        self.assertFalse(info["completed"])
        self.assertIsNone(info["fixture_bundle"])
        from harness.recorder import latest_bundle
        self.assertEqual(os.path.basename(
            latest_bundle(self.config.path("fixtures"), "t001")), "rec-001")


class TestPeopleSearchEndToEnd(unittest.TestCase):
    """Same plumbing as above, through the exa-people-search profile: the
    session must look for people.csv, load the per-skill prompt overrides,
    validate against the people columns (currentAffiliation, profileUrl), and
    key Cara — who has no LinkedIn — by her url: profile key."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.config = make_pipeline(self.tmp, skill_name="exa-people-search")
        canned = write_csv(os.path.join(self.tmp, "canned.csv"), PEOPLE_CLEAN_ROWS,
                           columns=PEOPLE_CSV_COLUMNS)
        self._saved = dict(os.environ)
        os.environ.update(fake_claude_env(canned, output_csv="people.csv"))

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._saved)

    def test_live_then_replay(self):
        config = self.config
        self.assertEqual(config.profile["output_csv"], "people.csv")

        info, scorecard = run_one(config, "t001", "main", "live")
        self.assertTrue(info["completed"], info["failure"])
        self.assertEqual(scorecard["violation_counts"], {})
        self.assertEqual(scorecard["grounding"]["candidates_checked"], 3)

        # all three frozen as labels, Cara under her url: key
        labels = load_labels(config.path("regression"))
        self.assertEqual(len(labels), 3)
        self.assertIn(("t001", "url:github.com/cara-mott"), labels)

        info2, scorecard2 = run_one(config, "t001", "main", "replay")
        self.assertTrue(info2["completed"], info2["failure"])
        run_dir2 = os.path.join(config.path("runs"), info2["run_id"])
        self.assertTrue(os.path.isfile(os.path.join(run_dir2, "outdir", "people.csv")))
        self.assertEqual(scorecard2["grounding"]["unlabeled"], 0)
        self.assertEqual(scorecard2["regression_hits"], [])
        score = run_score(scorecard2, config["scoring"])
        self.assertEqual(score["gate_failures"], [])
        self.assertGreater(score["composite"], 90)

    def test_missing_people_csv_fails_delivery(self):
        os.environ["FAKE_INNER_NO_CSV"] = "1"
        try:
            info, scorecard = run_one(self.config, "t001", "main", "replay")
        finally:
            os.environ.pop("FAKE_INNER_NO_CSV", None)
        self.assertFalse(info["completed"])
        self.assertIn("people.csv", info["failure"])


if __name__ == "__main__":
    unittest.main()
