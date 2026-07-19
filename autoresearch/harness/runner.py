"""Run one scenario or the whole suite against a skill ref."""
import json
import os
import re
import time

from .recorder import latest_bundle, record_bundle
from .scenario import get_scenario, list_scenarios
from .scoring import suite_score
from .session import run_session, validate_run
from .workspace import Workspace, skill_size


def _safe(ref):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", ref)


def run_one(config, scenario_id, ref, mode, run_id=None, record=False):
    """One scenario end to end: checkout, session, validation, (optionally)
    fixture recording. Returns (session_info, scorecard)."""
    ws = Workspace(config.skill_repo, config.path("workspace"), config.skill_subpath)
    ws.checkout(ref)
    skill_dir = ws.skill_dir
    scenario = get_scenario(config.path("suite"), scenario_id)
    run_id = run_id or f"{time.strftime('%Y%m%d-%H%M%S')}-{scenario_id}-{_safe(ref)}-{mode}"

    bundle = latest_bundle(config.path("fixtures"), scenario_id) if mode == "replay" else None
    info = run_session(config, scenario, skill_dir, ref, mode, run_id, bundle_dir=bundle)

    # Only completed sessions may freeze fixtures — a partial pool from an
    # aborted run would silently become replay truth. recording_id must stay
    # flat: suite run_ids contain a slash (<suite_id>/<scenario>), which would
    # nest the bundle one level below where latest_bundle() looks.
    info["fixture_bundle"] = None
    if record and mode == "live" and info.get("completed"):
        run_dir = os.path.join(config.path("runs"), run_id)
        recorded = record_bundle(run_dir, config.path("fixtures"), scenario_id,
                                 recording_id=_safe(run_id), skill_ref=ref)
        info["fixture_bundle"] = recorded

    scorecard = validate_run(config, scenario, run_id, info)
    return info, scorecard


def run_suite(config, ref, mode, scenario_ids=None, record=False):
    """Every scenario (or the given subset) against one ref. Replay scenarios
    with no fixture bundle are skipped and reported — they need a record run
    first. Writes runs/<suite_id>/suite.json and returns it."""
    ws = Workspace(config.skill_repo, config.path("workspace"), config.skill_subpath)
    ws.checkout(ref)
    head = ws.head()

    scenarios = list_scenarios(config.path("suite"))
    if scenario_ids:
        scenarios = [s for s in scenarios if s.id in set(scenario_ids)]
    suite_id = f"{time.strftime('%Y%m%d-%H%M%S')}-suite-{_safe(ref)}-{mode}"

    scorecards, skipped = [], []
    for scenario in scenarios:
        # a scenario the user hasn't reviewed must not pollute the baseline
        # (imported ones start as needs_review; missing status means hand-made = ready)
        status = scenario.meta.get("status", "ready")
        if status != "ready":
            skipped.append({"scenario": scenario.id,
                            "reason": f"status={status!r} — review it and set \"ready\""})
            continue
        if mode == "replay" and not latest_bundle(config.path("fixtures"), scenario.id):
            skipped.append({"scenario": scenario.id, "reason": "no fixture bundle recorded"})
            continue
        run_id = f"{suite_id}/{scenario.id}"
        os.makedirs(os.path.join(config.path("runs"), run_id), exist_ok=True)
        _, scorecard = run_one(config, scenario.id, ref, mode,
                               run_id=run_id, record=record)
        scorecards.append(scorecard)

    result = {
        "suite_id": suite_id, "skill": config["skill"]["name"],
        "ref": ref, "head": head, "mode": mode,
        # instruction-text mass of the skill at this ref — the parsimony
        # rule in scoring.compare() reads this off both suites
        "skill_size": skill_size(ws.skill_dir),
        "score": suite_score(scorecards, config["scoring"]),
        "scorecard_runs": [sc["run_id"] for sc in scorecards],
        "skipped": skipped,
        "total_cost_usd": round(sum(sc["cost_usd"] for sc in scorecards), 4),
    }
    suite_dir = os.path.join(config.path("runs"), suite_id)
    os.makedirs(suite_dir, exist_ok=True)
    with open(os.path.join(suite_dir, "suite.json"), "w") as f:
        json.dump(result, f, indent=2)
    return result


def find_latest_suite(config, ref=None, mode=None, head=None):
    """Newest suite.json matching the filters (used as the baseline)."""
    runs_dir = config.path("runs")
    if not os.path.isdir(runs_dir):
        return None
    best = None
    for name in sorted(os.listdir(runs_dir)):
        path = os.path.join(runs_dir, name, "suite.json")
        if not os.path.isfile(path):
            continue
        with open(path) as f:
            suite = json.load(f)
        # runs/ is shared across skills; a baseline must never come from
        # another skill's suite (older suites without the field still match)
        if suite.get("skill") not in (None, config["skill"]["name"]):
            continue
        if ref and suite.get("ref") != ref:
            continue
        if mode and suite.get("mode") != mode:
            continue
        if head and suite.get("head") != head:
            continue
        best = suite
    return best
