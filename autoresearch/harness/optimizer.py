"""The Outer-LLM optimization loop.

One round:
  1. Establish the baseline: the latest suite result for the base ref (run it
     if missing).
  2. Build a dossier — skill text, aggregated scorecards across the WHOLE
     suite (never a single run, so an edit can't overfit one JD), worst
     violation excerpts, and the history of past experiments so failed ideas
     aren't re-proposed.
  3. Ask the Outer LLM for K distinct edit proposals, each declaring which
     stages it touches.
  4. For each proposal: branch exp/NNN-<slug> in the workspace clone, let the
     Outer LLM apply the edit with real Edit tools, commit, evaluate the full
     suite on the branch, and compare against baseline. Search-stage edits
     cannot be measured from frozen fixtures, so in replay mode they are
     parked as needs_live instead of being scored dishonestly.
  5. Keep = merge the best accepted branch into the promotion branch (never
     main). Everything is appended to experiments/log.jsonl.
"""
import json
import os
import re
import time

from .claude_cli import run_claude
from .prompt_render import render
from .runner import find_latest_suite, run_suite
from .validator.scorecard import load_scorecard
from .scoring import compare
from .workspace import PromotionConflict, Workspace

SEARCH_STAGES = {"search", "discovery", "verify", "verification"}


def _slug(proposal):
    """Proposal slugs come from an LLM; git rejects branch names with spaces,
    ':', '~' etc., and 'a/b' slugs create ref conflicts — sanitize hard."""
    s = re.sub(r"[^a-z0-9-]+", "-", str(proposal.get("slug") or "").lower()).strip("-")
    return s[:30] or "edit"


def _prompt(config, name):
    with open(os.path.join(config.path("prompts"), name)) as f:
        return f.read()


def _log_path(config):
    return config.path("experiment_log")


def read_log(config):
    path = _log_path(config)
    if not os.path.isfile(path):
        return []
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def append_log(config, entry):
    path = _log_path(config)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _trim_scorecard(sc, max_violations=10):
    return {
        "scenario": sc["scenario"], "completed": sc["completed"],
        "failure": sc["failure"], "stats": sc["stats"],
        "violation_counts": sc["violation_counts"],
        "violations_sample": sc["violations"][:max_violations],
        "grounding": sc["grounding"], "ux": sc["ux"],
        "regression_hits": sc.get("regression_hits", []),
    }


def build_dossier(config, baseline_suite, skill_dir):
    with open(os.path.join(skill_dir, "SKILL.md")) as f:
        skill_text = f.read()
    scorecards = []
    for run_id in baseline_suite["scorecard_runs"]:
        run_dir = os.path.join(config.path("runs"), run_id)
        scorecards.append(_trim_scorecard(load_scorecard(run_dir)))
    history = [{"branch": e.get("branch"), "hypothesis": e.get("hypothesis"),
                "verdict": e.get("verdict"), "reasons": e.get("reasons"),
                "deltas": e.get("deltas")} for e in read_log(config)]
    return {"skill_md": skill_text,
            "suite_score": baseline_suite["score"],
            "scorecards": scorecards,
            "experiment_history": history[-25:]}


def propose(config, dossier, k):
    prompt = render(_prompt(config, "outer_propose.md"),
                    k=k,
                    dossier=json.dumps({key: v for key, v in dossier.items() if key != "skill_md"},
                                       indent=2),
                    skill_md=dossier["skill_md"])
    res = run_claude(prompt, model=config.model("outer"), cwd=config.pipeline_dir,
                     timeout_s=config.limit("outer_timeout_s"),
                     env_extra=config.actor_env("outer"),
                     disallowed_tools=["Bash", "Write", "Edit", "WebFetch", "WebSearch"])
    if not res.ok:
        raise RuntimeError(f"outer propose failed: {res.error}")
    payload = res.json_payload()
    proposals = payload.get("proposals") or []
    if not proposals:
        raise RuntimeError(f"outer returned no proposals: {res.text[:300]!r}")
    return proposals[:k], res.cost_usd


def apply_edit(config, ws, proposal, branch):
    prompt = render(_prompt(config, "outer_apply.md"),
                    hypothesis=proposal.get("hypothesis", ""),
                    edit_instructions=proposal.get("edit_instructions", ""))
    res = run_claude(prompt, model=config.model("outer"), cwd=ws.skill_dir,
                     timeout_s=config.limit("outer_timeout_s"),
                     env_extra=config.actor_env("outer"),
                     allowed_tools=["Read", "Edit", "Write", "Grep", "Glob"],
                     disallowed_tools=["Bash", "WebFetch", "WebSearch"])
    if not res.ok:
        return None, res.cost_usd
    sha = ws.commit_all(f"exp({branch}): {str(proposal.get('hypothesis') or '')[:100]}")
    return sha, res.cost_usd


def optimize_round(config, experiments=None, mode="replay", promote=True):
    base_ref = config["skill"]["base_ref"]
    k = experiments or config["budget"]["outer_experiments_per_round"]
    ws = Workspace(config.skill_repo, config.path("workspace"), config.skill_subpath)
    ws.checkout(base_ref)
    skill_dir = ws.skill_dir

    baseline = find_latest_suite(config, ref=base_ref, mode=mode, head=ws.head())
    if baseline is None:
        baseline = run_suite(config, base_ref, mode)
    if baseline["score"]["scenario_count"] == 0:
        raise RuntimeError("baseline suite is empty — record fixtures first "
                           "(cli.py record) and check suite/scenarios/")

    dossier = build_dossier(config, baseline, skill_dir)
    proposals, cost = propose(config, dossier, k)

    seq = len(read_log(config))
    results = []
    for proposal in proposals:
        seq += 1
        branch = f"exp/{seq:03d}-{_slug(proposal)}"
        entry = {"branch": branch, "base_ref": base_ref, "base_head": baseline["head"],
                 "hypothesis": str(proposal.get("hypothesis") or ""),
                 "stages": proposal.get("stages", []), "mode": mode,
                 "started_at": int(time.time())}
        # a malformed proposal is logged and skipped, never a round-killer
        if not str(proposal.get("hypothesis") or "").strip() \
                or not str(proposal.get("edit_instructions") or "").strip():
            entry.update(verdict="apply_failed",
                         reasons=["proposal missing hypothesis or edit_instructions"])
            append_log(config, entry)
            results.append(entry)
            continue
        ws.create_branch(branch, base_ref)
        sha, apply_cost = apply_edit(config, ws, proposal, branch)
        cost += apply_cost
        if sha is None:
            entry.update(verdict="apply_failed", reasons=["edit produced no commit"])
            append_log(config, entry)
            results.append(entry)
            continue
        entry["commit"] = sha
        ws.push_branch(branch)

        touches_search = any(s.lower() in SEARCH_STAGES for s in proposal.get("stages", []))
        if mode == "replay" and touches_search:
            entry.update(verdict="needs_live",
                         reasons=["edit touches the search stage; frozen fixtures "
                                  "cannot measure it — evaluate with --mode live"])
            append_log(config, entry)
            results.append(entry)
            continue

        suite = run_suite(config, branch, mode)
        verdict = compare(baseline["score"], suite["score"], config["scoring"])
        entry.update(verdict=verdict["verdict"], reasons=verdict["reasons"],
                     deltas=verdict["deltas"], suite_id=suite["suite_id"],
                     composite=suite["score"]["composite"],
                     eval_cost_usd=suite["total_cost_usd"])
        append_log(config, entry)
        results.append(entry)

    accepted = [r for r in results if r.get("verdict") == "accept"]
    winner = max(accepted, key=lambda r: r["deltas"]["composite"]) if accepted else None
    promoted, promotion_conflict = None, None
    if winner and promote:
        try:
            promoted = ws.promote(winner["branch"], config["skill"]["promotion_branch"],
                                  base_ref)
        except PromotionConflict as e:
            # the winner stays valid (its branch is pushed); only the merge
            # into the promotion branch needs a human
            promotion_conflict = str(e)

    round_report = {
        "baseline_suite": baseline["suite_id"], "baseline_composite": baseline["score"]["composite"],
        "experiments": results, "winner": winner and winner["branch"],
        "promoted_to": bool(promoted) and config["skill"]["promotion_branch"],
        "promotion_head": promoted,
        "promotion_conflict": promotion_conflict,
        "needs_live_confirmation": bool(winner) and mode == "replay"
                                   and config["budget"].get("live_confirm_winners", True),
        "outer_cost_usd": round(cost, 4),
    }
    report_dir = os.path.dirname(_log_path(config))
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir,
                               f"round-{time.strftime('%Y%m%d-%H%M%S')}.json")
    with open(report_path, "w") as f:
        json.dump(round_report, f, indent=2)
    round_report["report_path"] = report_path
    return round_report
