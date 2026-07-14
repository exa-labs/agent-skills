"""Turn scorecards into numbers and edit verdicts.

Run score = weighted composite of four components (0-100 each):
  constraints — fraction of returned candidates free of any constraint violation
  grounding   — claim-support rate blended with identity-support rate over the
                candidates that were actually checked. Unlabeled candidates are
                reported as a health stat but do NOT scale the score: a coverage
                multiplier would reward edits that return only the historically
                labeled shortlist and punish surfacing new candidates — the
                opposite of the pipeline's goal.
  delivery    — returned/requested, zero if the session never completed
  ux          — the simulated recruiter's survey, scaled from 1-5 to 0-100

Hard gates sit outside the composite: one violation of a gated type (or a
session that never completed, or a regression hit) fails the run no matter
what the composite says. compare() is the promotion rule: a candidate edit is
kept only if it fails no gate the baseline passed, regresses no component
beyond tolerance, adds no regression hits, and improves the composite by at
least min_composite_delta.
"""


def _violating_candidates(scorecard):
    keys = set()
    for v in scorecard["violations"]:
        if v["type"] == "malformed_output":
            continue
        keys.add((v.get("rank"), v.get("name")))
    return keys


def component_scores(scorecard):
    stats = scorecard.get("stats", {})
    returned = stats.get("returned", 0) or 0
    requested = stats.get("requested") or 0

    if not scorecard.get("completed") or returned == 0:
        constraints = 0.0
    else:
        constraints = 100.0 * (1 - min(len(_violating_candidates(scorecard)), returned) / returned)

    g = scorecard.get("grounding", {})
    checked = g.get("claims_checked", 0)
    cands = g.get("candidates_checked", 0)
    if cands == 0:
        grounding = 0.0
    else:
        claim_rate = (g.get("claims_supported", 0) / checked) if checked else 0.0
        ident_rate = g.get("identity_supported", 0) / cands
        grounding = 100.0 * (0.6 * claim_rate + 0.4 * ident_rate)
        grounding = max(0.0, grounding - 15.0 * g.get("claims_contradicted", 0))

    if not scorecard.get("completed"):
        delivery = 0.0
    elif not requested:
        delivery = 100.0 if returned else 0.0
    else:
        delivery = 100.0 * min(returned / requested, 1.0)

    ux = scorecard.get("ux") or {}
    ratings = [v for v in ux.values() if isinstance(v, (int, float))]
    ux_score = (sum(ratings) / len(ratings)) / 5.0 * 100.0 if ratings else 60.0

    return {"constraints": round(constraints, 2), "grounding": round(grounding, 2),
            "delivery": round(delivery, 2), "ux": round(ux_score, 2)}


def gate_failures(scorecard, hard_gates):
    fails = []
    if not scorecard.get("completed"):
        fails.append("session_incomplete")
    for vtype, n in scorecard.get("violation_counts", {}).items():
        if vtype in hard_gates and n > 0:
            fails.append(f"{vtype} x{n}")
    if scorecard.get("regression_hits"):
        fails.append(f"regression_hits x{len(scorecard['regression_hits'])}")
    return fails


def run_score(scorecard, scoring_cfg):
    comps = component_scores(scorecard)
    weights = scoring_cfg["weights"]
    composite = sum(comps[k] * weights[k] for k in weights)
    return {"components": comps, "composite": round(composite, 2),
            "gate_failures": gate_failures(scorecard, scoring_cfg["hard_gates"])}


def _gate_type(failure):
    """'must_have_violation x2' -> 'must_have_violation' (counts change run to
    run; the pair (scenario, type) is what must never newly appear)."""
    return failure.rsplit(" x", 1)[0]


def suite_score(scorecards, scoring_cfg):
    per_run = {}
    for sc in scorecards:
        per_run[sc["scenario"]] = run_score(sc, scoring_cfg)
    n = max(len(per_run), 1)
    mean_comps = {k: round(sum(r["components"][k] for r in per_run.values()) / n, 2)
                  for k in ("constraints", "grounding", "delivery", "ux")}
    composite = round(sum(r["composite"] for r in per_run.values()) / n, 2)
    gate_failed_runs = sorted(s for s, r in per_run.items() if r["gate_failures"])
    gate_failure_pairs = sorted({f"{s}:{_gate_type(f)}"
                                 for s, r in per_run.items() for f in r["gate_failures"]})
    total_regression_hits = sum(len(sc.get("regression_hits") or []) for sc in scorecards)
    return {"runs": per_run, "mean_components": mean_comps, "composite": composite,
            "gate_failed_runs": gate_failed_runs,
            "gate_failure_pairs": gate_failure_pairs,
            "regression_hits": total_regression_hits,
            "scenario_count": len(per_run)}


def compare(baseline, candidate, scoring_cfg):
    """Promotion rule. Returns {"verdict": "accept"|"reject", "reasons": [...],
    "deltas": {...}}."""
    cmp_cfg = scoring_cfg["compare"]
    reasons = []

    # Diff (scenario, gate-type) pairs, not scenario ids: an edit that fixes
    # one gate in a scenario but introduces a different one there must fail.
    base_fails = set(baseline.get("gate_failure_pairs", baseline["gate_failed_runs"]))
    cand_fails = set(candidate.get("gate_failure_pairs", candidate["gate_failed_runs"]))
    new_fails = cand_fails - base_fails
    if new_fails:
        reasons.append(f"new gate failures: {sorted(new_fails)}")

    if candidate["regression_hits"] - baseline["regression_hits"] > cmp_cfg["regression_set_tolerance"]:
        reasons.append(
            f"regression hits rose {baseline['regression_hits']} -> {candidate['regression_hits']}")

    deltas = {}
    for k, base_v in baseline["mean_components"].items():
        d = round(candidate["mean_components"][k] - base_v, 2)
        deltas[k] = d
        if d < -cmp_cfg["component_regression_tolerance"]:
            reasons.append(f"component '{k}' regressed by {-d}")

    composite_delta = round(candidate["composite"] - baseline["composite"], 2)
    deltas["composite"] = composite_delta
    if not reasons and composite_delta < cmp_cfg["min_composite_delta"]:
        reasons.append(
            f"composite delta {composite_delta} below required {cmp_cfg['min_composite_delta']}")

    fixed_gates = base_fails - cand_fails
    # An edit that fixes a gate failure without introducing any problem is a
    # win even if the composite barely moves.
    if reasons == [f"composite delta {composite_delta} below required "
                   f"{cmp_cfg['min_composite_delta']}"] and fixed_gates and composite_delta >= 0:
        reasons = []

    return {"verdict": "reject" if reasons else "accept",
            "reasons": reasons, "deltas": deltas,
            "fixed_gate_failures": sorted(fixed_gates)}
