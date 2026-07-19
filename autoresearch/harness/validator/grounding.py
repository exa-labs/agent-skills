"""Grounded fact-checking of a run's candidates.

Live (record-time) path: a Validator-LLM agent re-fetches each candidate's
cited sources and judges whether they actually support the claimed identity,
employer, and the scenario's semantic must-haves. Its per-candidate verdicts
are frozen into the regression store, so they double as labels.

Replay path: no network. Candidates in a replay run can only come from frozen
fixtures, so their verdicts are joined back out of the regression store by
candidate key. A replay candidate with no stored label means the fixtures and
labels are out of sync — surfaced as `unlabeled`, never silently passed.

Verdict shape per candidate:
  {"key", "name", "identity": supported|unsupported|contradicted|unreachable,
   "claims_checked", "claims_supported", "claims_contradicted", "claims_unreachable",
   "must_haves": meets|unclear|violates,
   "in_location": yes|no|unknown, "at_excluded_org": yes|no|unknown,
   "confident": bool, "notes"}

A `contradicted` identity becomes a fabricated_identity violation; a
*confident* must-have `violates` becomes a must_have_violation. An unconfident
"violates" is downgraded to `unclear` so a noisy judge can't flip hard gates
run to run.

in_location / at_excluded_org are the ADJUDICATED semantic constraint calls —
regex tripwires in deterministic.py only mark rows `*_suspected`; the gated
excluded_employer_leak / location_violation types come from here, where the
judge has fetched the person's actual sources. Same noise guard: "no" /
"yes-at-excluded" only count when confident, else downgraded to unknown.
"""
import json

from ..claude_cli import run_claude
from ..prompt_render import render
from .deterministic import candidate_key

BATCH = 8

VERDICT_KEYS = ("identity", "claims_checked", "claims_supported",
                "claims_contradicted", "claims_unreachable", "must_haves",
                "confident", "notes")


def _claim_rows(rows, max_sources):
    out = []
    for r in rows:
        sources = [s.strip() for s in (r.get("sources") or "").split("|") if s.strip()]
        claim = {
            "key": candidate_key(r),
            "name": r.get("name"),
            # column names differ per skill (candidate-sourcing vs people-search)
            "claimed_title": r.get("currentTitle") or r.get("currentRole"),
            "claimed_company": r.get("currentCompany") or r.get("currentAffiliation"),
            "claimed_location": r.get("location"),
            "linkedin_url": r.get("linkedinUrl"),
            "sources": sources[:max_sources],
        }
        if r.get("profileUrl"):
            claim["profile_url"] = r.get("profileUrl")
        out.append(claim)
    return out


def check_grounding_live(rows, scenario, config, run_dir):
    """Fact-check candidates in batches with the Validator LLM. Returns
    (verdicts_by_key, total_cost_usd)."""
    with open(config.prompt_path("validator_grounding.md")) as f:
        template = f.read()
    max_src = config.limit("grounding_max_sources_per_candidate")
    cap = config.limit("grounding_max_candidates")
    rows = rows[:cap]
    verdicts, cost = {}, 0.0
    loc_cfg = scenario.expectations.get("location") or {}
    location_requirement = (
        "The location constraint is STRICT. A person is in-bounds only if their "
        "actual location satisfies the brief's stated region (see the brief; "
        f"unknown-location is {'tolerated' if loc_cfg.get('allow_unknown') else 'NOT tolerated'})."
        if loc_cfg.get("strict") else
        "There is no strict location constraint — answer in_location: \"unknown\" for everyone.")
    excluded_orgs = scenario.expectations.get("exclude_employer_terms", [])
    excluded_orgs_txt = (json.dumps(excluded_orgs) if excluded_orgs
                         else "(none — answer at_excluded_org: \"unknown\" for everyone)")
    for i in range(0, len(rows), BATCH):
        batch = _claim_rows(rows[i:i + BATCH], max_src)
        prompt = render(template,
                        must_haves=json.dumps(scenario.expectations.get("must_haves_semantic", []), indent=2),
                        location_requirement=location_requirement,
                        excluded_orgs=excluded_orgs_txt,
                        jd=scenario.jd,
                        batch=json.dumps(batch, indent=2))
        res = run_claude(prompt,
                         model=config.model("validator"),
                         cwd=run_dir,
                         timeout_s=config.limit("validator_timeout_s"),
                         env_extra=config.actor_env("validator"),
                         allowed_tools=["WebFetch", "WebSearch", "Bash(curl:*)"],
                         disallowed_tools=["Write", "Edit", "NotebookEdit"])
        cost += res.cost_usd
        if not res.ok:
            for b in batch:
                verdicts[b["key"]] = _error_verdict(b, f"validator turn failed: {res.error}")
            continue
        try:
            payload = res.json_payload()
            got = {v["key"]: _sanitize(v) for v in payload["candidates"] if v.get("key")}
        except (KeyError, ValueError, TypeError) as e:
            got = {}
            note = f"unparseable validator output: {e}"
        else:
            note = "validator returned no verdict for this candidate"
        for b in batch:
            verdicts[b["key"]] = got.get(b["key"]) or _error_verdict(b, note)
    return verdicts, cost


def _error_verdict(claim_row, note):
    return {"key": claim_row["key"], "name": claim_row["name"],
            "identity": "unreachable", "claims_checked": 0, "claims_supported": 0,
            "claims_contradicted": 0, "claims_unreachable": 0,
            "must_haves": "unclear", "in_location": "unknown",
            "at_excluded_org": "unknown", "confident": False, "notes": note}


def _sanitize(v):
    out = {"key": v.get("key"), "name": v.get("name")}
    out["identity"] = v.get("identity") if v.get("identity") in (
        "supported", "unsupported", "contradicted", "unreachable") else "unsupported"
    for k in ("claims_checked", "claims_supported", "claims_contradicted", "claims_unreachable"):
        out[k] = v[k] if isinstance(v.get(k), int) and v[k] >= 0 else 0
    mh = v.get("must_haves") if v.get("must_haves") in ("meets", "unclear", "violates") else "unclear"
    confident = bool(v.get("confident"))
    if mh == "violates" and not confident:
        mh = "unclear"
    out["must_haves"], out["confident"] = mh, confident
    # adjudicated semantic constraints; the incriminating answers only count
    # when the judge is confident, mirroring the must-have noise guard
    loc = v.get("in_location") if v.get("in_location") in ("yes", "no", "unknown") else "unknown"
    if loc == "no" and not confident:
        loc = "unknown"
    org = (v.get("at_excluded_org")
           if v.get("at_excluded_org") in ("yes", "no", "unknown") else "unknown")
    if org == "yes" and not confident:
        org = "unknown"
    out["in_location"], out["at_excluded_org"] = loc, org
    out["notes"] = str(v.get("notes") or "")[:500]
    return out


def join_labels(rows, labels_by_key):
    """Replay path: pull frozen verdicts for each candidate. Returns
    (verdicts_by_key, unlabeled_keys)."""
    verdicts, unlabeled = {}, []
    for r in rows:
        key = candidate_key(r)
        label = labels_by_key.get(key)
        if not label:
            unlabeled.append(key)
            continue
        verdict = label.get("verdict")
        if not verdict:
            # human label with no frozen verdict — synthesize one that carries
            # the label's meaning into the grounding stats and violations
            bad = label.get("label") == "violation"
            verdict = {"key": key, "name": label.get("name"),
                       "identity": "contradicted" if bad else "supported",
                       "claims_checked": 0, "claims_supported": 0,
                       "claims_contradicted": 0, "claims_unreachable": 0,
                       "must_haves": "unclear", "in_location": "unknown",
                       "at_excluded_org": "unknown", "confident": True,
                       "notes": f"human label: {label.get('notes') or label.get('label')}"}
        verdicts[key] = verdict
    return verdicts, unlabeled


def grounding_violations(rows, verdicts):
    """Convert verdicts into scorecard violations (same shape as deterministic).

    This is where the GATED semantic constraint types come from: the judge
    fetched the person's sources, so a confident in_location='no' /
    at_excluded_org='yes' is an adjudicated violation — unlike the regex
    tripwires in deterministic.py, which only mark rows `*_suspected`."""
    violations = []
    for r in rows:
        v = verdicts.get(candidate_key(r))
        if not v:
            continue
        if v["identity"] == "contradicted":
            violations.append({"type": "fabricated_identity", "rank": r.get("rank"),
                               "name": r.get("name"),
                               "detail": f"sources contradict claimed identity: {v['notes']}"})
        if v["must_haves"] == "violates":
            violations.append({"type": "must_have_violation", "rank": r.get("rank"),
                               "name": r.get("name"),
                               "detail": f"evidence shows a must-have is not met: {v['notes']}"})
        if v.get("in_location") == "no":
            violations.append({"type": "location_violation", "rank": r.get("rank"),
                               "name": r.get("name"),
                               "detail": f"adjudicated outside the required region: {v['notes']}"})
        if v.get("at_excluded_org") == "yes":
            violations.append({"type": "excluded_employer_leak", "rank": r.get("rank"),
                               "name": r.get("name"),
                               "detail": f"adjudicated currently at an excluded org: {v['notes']}"})
    return violations


def grounding_stats(verdicts, unlabeled_count=0):
    vs = list(verdicts.values())
    checked = sum(v["claims_checked"] for v in vs)
    return {
        "candidates_checked": len(vs),
        "claims_checked": checked,
        "claims_supported": sum(v["claims_supported"] for v in vs),
        "claims_contradicted": sum(v["claims_contradicted"] for v in vs),
        "claims_unreachable": sum(v["claims_unreachable"] for v in vs),
        "identity_supported": sum(1 for v in vs if v["identity"] == "supported"),
        "identity_contradicted": sum(1 for v in vs if v["identity"] == "contradicted"),
        "must_haves_meets": sum(1 for v in vs if v["must_haves"] == "meets"),
        "must_haves_violates": sum(1 for v in vs if v["must_haves"] == "violates"),
        "unlabeled": unlabeled_count,
    }
