import copy
import json
import os
import unittest

from util import PIPELINE_DIR

from harness.scoring import compare, component_scores, gate_failures, run_score, suite_score

with open(os.path.join(PIPELINE_DIR, "config.json")) as f:
    SCORING = json.load(f)["scoring"]


def scorecard(**over):
    base = {
        "scenario": "t001", "completed": True, "failure": None,
        "stats": {"returned": 10, "requested": 10},
        "violations": [], "violation_counts": {},
        "grounding": {"candidates_checked": 10, "claims_checked": 30,
                      "claims_supported": 30, "claims_contradicted": 0,
                      "claims_unreachable": 0, "identity_supported": 10,
                      "unlabeled": 0},
        "ux": {"checkpoint_quality": 5, "clarity": 5, "efficiency": 5, "trust": 5},
        "regression_hits": [],
    }
    base.update(over)
    return base


class TestComponents(unittest.TestCase):
    def test_perfect_run(self):
        comps = component_scores(scorecard())
        self.assertEqual(comps, {"constraints": 100.0, "grounding": 100.0,
                                 "delivery": 100.0, "ux": 100.0})

    def test_violations_reduce_constraints(self):
        sc = scorecard(violations=[
            {"type": "excluded_employer_leak", "rank": "1", "name": "A", "detail": ""},
            {"type": "location_violation", "rank": "2", "name": "B", "detail": ""}])
        self.assertEqual(component_scores(sc)["constraints"], 80.0)

    def test_incomplete_run_zeroes_delivery_and_constraints(self):
        comps = component_scores(scorecard(completed=False))
        self.assertEqual(comps["constraints"], 0.0)
        self.assertEqual(comps["delivery"], 0.0)

    def test_contradictions_penalize_grounding(self):
        sc = scorecard(grounding=dict(scorecard()["grounding"],
                                      claims_supported=27, claims_contradicted=3))
        self.assertLess(component_scores(sc)["grounding"], 60.0)

    def test_unlabeled_candidates_do_not_penalize_grounding(self):
        # a coverage multiplier would reward returning only the historically
        # labeled shortlist and punish surfacing new candidates
        sc = scorecard(grounding=dict(scorecard()["grounding"], unlabeled=10))
        self.assertEqual(component_scores(sc)["grounding"], 100.0)


class TestGates(unittest.TestCase):
    def test_gated_violation_fails(self):
        sc = scorecard(violation_counts={"must_have_violation": 2})
        self.assertEqual(gate_failures(sc, SCORING["hard_gates"]), ["must_have_violation x2"])

    def test_ungated_type_passes(self):
        sc = scorecard(violation_counts={"malformed_output": 1})
        self.assertEqual(gate_failures(sc, SCORING["hard_gates"]), [])

    def test_incomplete_and_regression_hits_fail(self):
        sc = scorecard(completed=False, regression_hits=["li:bad-guy"])
        fails = gate_failures(sc, SCORING["hard_gates"])
        self.assertIn("session_incomplete", fails)
        self.assertIn("regression_hits x1", fails)


class TestCompare(unittest.TestCase):
    def suite(self, composites=(80.0,), gate_pairs=(), comps=None, hits=0):
        """gate_pairs: 'scenario:gate_type' strings, as suite_score emits."""
        runs = {f"s{i:03d}": {"composite": c, "components": comps or
                              {"constraints": c, "grounding": c, "delivery": c, "ux": c},
                              "gate_failures": []}
                for i, c in enumerate(composites)}
        n = len(composites)
        mean = {k: round(sum((comps or {"constraints": c, "grounding": c,
                                        "delivery": c, "ux": c})[k]
                             for c in composites) / n, 2)
                for k in ("constraints", "grounding", "delivery", "ux")}
        return {"runs": runs, "mean_components": mean,
                "composite": round(sum(composites) / n, 2),
                "gate_failed_runs": sorted({p.split(":")[0] for p in gate_pairs}),
                "gate_failure_pairs": sorted(gate_pairs),
                "regression_hits": hits, "scenario_count": n}

    def test_accepts_clear_improvement(self):
        v = compare(self.suite((70.0,)), self.suite((75.0,)), SCORING)
        self.assertEqual(v["verdict"], "accept")
        self.assertEqual(v["deltas"]["composite"], 5.0)

    def test_rejects_no_improvement(self):
        v = compare(self.suite((70.0,)), self.suite((70.5,)), SCORING)
        self.assertEqual(v["verdict"], "reject")

    def test_rejects_new_gate_failure_despite_score_gain(self):
        v = compare(self.suite((70.0,)),
                    self.suite((90.0,), gate_pairs=["s000:must_have_violation"]), SCORING)
        self.assertEqual(v["verdict"], "reject")
        self.assertIn("new gate failures", v["reasons"][0])

    def test_rejects_swapped_gate_type_in_same_scenario(self):
        # baseline s000 fails on location; the edit fixes location but
        # introduces a duplicate in the same scenario — must NOT be masked
        base = self.suite((70.0,), gate_pairs=["s000:location_violation"])
        cand = self.suite((75.0,), gate_pairs=["s000:duplicate_candidate"])
        v = compare(base, cand, SCORING)
        self.assertEqual(v["verdict"], "reject")
        self.assertIn("s000:duplicate_candidate", v["reasons"][0])

    def test_rejects_component_regression_despite_composite_gain(self):
        base = self.suite((70.0,))
        cand = self.suite((80.0,))
        cand["mean_components"]["grounding"] = base["mean_components"]["grounding"] - 5.0
        v = compare(base, cand, SCORING)
        self.assertEqual(v["verdict"], "reject")

    def test_rejects_new_regression_hits(self):
        v = compare(self.suite((70.0,)), self.suite((80.0,), hits=1), SCORING)
        self.assertEqual(v["verdict"], "reject")

    def test_fixing_a_gate_accepts_flat_composite(self):
        base = self.suite((70.0,), gate_pairs=["s000:must_have_violation"])
        cand = self.suite((70.0,))
        v = compare(base, cand, SCORING)
        self.assertEqual(v["verdict"], "accept")
        self.assertEqual(v["accepted_on"], "gate_fix")
        self.assertEqual(v["fixed_gate_failures"], ["s000:must_have_violation"])


class TestParsimony(unittest.TestCase):
    """A smaller skill at the same quality is strictly better — but only at
    the same quality, and only a real shrink."""

    suite = TestCompare.suite  # same suite-dict builder

    def _sizes(self, base_chars, cand_chars):
        return ({"chars": base_chars, "words": base_chars // 6, "md_files": 3},
                {"chars": cand_chars, "words": cand_chars // 6, "md_files": 3})

    def test_shrink_with_flat_quality_accepts(self):
        base_size, cand_size = self._sizes(10000, 9000)  # -10%
        v = compare(self.suite((70.0,)), self.suite((70.0,)), SCORING,
                    baseline_size=base_size, candidate_size=cand_size)
        self.assertEqual(v["verdict"], "accept")
        self.assertEqual(v["accepted_on"], "parsimony")
        self.assertEqual(v["deltas"]["skill_shrink_pct"], 10.0)

    def test_small_shrink_below_threshold_rejects(self):
        base_size, cand_size = self._sizes(10000, 9800)  # -2% < 5% threshold
        v = compare(self.suite((70.0,)), self.suite((70.0,)), SCORING,
                    baseline_size=base_size, candidate_size=cand_size)
        self.assertEqual(v["verdict"], "reject")

    def test_shrink_that_drops_quality_rejects(self):
        base_size, cand_size = self._sizes(10000, 8000)  # -20%, but composite -3
        v = compare(self.suite((70.0,)), self.suite((67.0,)), SCORING,
                    baseline_size=base_size, candidate_size=cand_size)
        self.assertEqual(v["verdict"], "reject")

    def test_shrink_cannot_mask_new_gate_failure(self):
        base_size, cand_size = self._sizes(10000, 8000)
        v = compare(self.suite((70.0,)),
                    self.suite((70.0,), gate_pairs=["s000:duplicate_candidate"]),
                    SCORING, baseline_size=base_size, candidate_size=cand_size)
        self.assertEqual(v["verdict"], "reject")

    def test_growth_is_reported_in_deltas(self):
        base_size, cand_size = self._sizes(10000, 11000)  # skill GREW 10%
        v = compare(self.suite((70.0,)), self.suite((75.0,)), SCORING,
                    baseline_size=base_size, candidate_size=cand_size)
        self.assertEqual(v["verdict"], "accept")  # improvement path, unchanged
        self.assertEqual(v["accepted_on"], "improvement")
        self.assertEqual(v["deltas"]["skill_shrink_pct"], -10.0)

    def test_no_sizes_means_no_parsimony_path(self):
        v = compare(self.suite((70.0,)), self.suite((70.0,)), SCORING)
        self.assertEqual(v["verdict"], "reject")
        self.assertNotIn("skill_shrink_pct", v["deltas"])


class TestSuiteScore(unittest.TestCase):
    def test_aggregates_runs(self):
        cards = [scorecard(), scorecard(scenario="t002", completed=False)]
        cards[1]["scenario"] = "t002"
        s = suite_score(cards, SCORING)
        self.assertEqual(s["scenario_count"], 2)
        self.assertEqual(s["gate_failed_runs"], ["t002"])
        self.assertLess(s["composite"], run_score(cards[0], SCORING)["composite"])


if __name__ == "__main__":
    unittest.main()
