"""Scorecard: the single judged record of one run.

Assembled from the deterministic checks, the grounding verdicts, the User
LLM's UX survey, and the session's own completion status. Written to
<run_dir>/scorecard.json; scoring.py turns scorecards into numbers and
verdicts, this module only assembles facts.
"""
import json
import os


def build_scorecard(*, run_id, scenario, skill_ref, mode, completed, failure,
                    det_result, grounding_verdicts, grounding_stats_d,
                    ux_survey, conversation_turns, cost_usd,
                    grounding_violations_list=None):
    violations = list(det_result["violations"]) + list(grounding_violations_list or [])
    counts = {}
    for v in violations:
        counts[v["type"]] = counts.get(v["type"], 0) + 1
    return {
        "run_id": run_id,
        "scenario": scenario.id,
        "skill_ref": skill_ref,
        "mode": mode,
        "completed": completed,
        "failure": failure,
        "stats": det_result["stats"],
        "violations": violations,
        "violation_counts": counts,
        "grounding": grounding_stats_d,
        "grounding_verdicts": grounding_verdicts,
        "ux": ux_survey,
        "conversation_turns": conversation_turns,
        "cost_usd": round(cost_usd, 4),
    }


def write_scorecard(run_dir, scorecard):
    path = os.path.join(run_dir, "scorecard.json")
    with open(path, "w") as f:
        json.dump(scorecard, f, indent=2)
    return path


def load_scorecard(run_dir):
    with open(os.path.join(run_dir, "scorecard.json")) as f:
        return json.load(f)
