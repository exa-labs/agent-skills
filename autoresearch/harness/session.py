"""Drive one evaluation session: User LLM <-> Inner LLM, then validation.

The Inner LLM runs the skill exactly as written, as a resumed multi-turn
`claude -p` session working in <run_dir>/outdir/. The User LLM plays the
recruiter from the scenario's persona — it writes every recruiter message
(including the opener), answers the skill's mandatory Step-1 checkpoint,
throws the persona's scripted curveballs, and files a UX survey at the end.

Exa traffic is intercepted at the environment level (PATH curl shim +
sitecustomize on PYTHONPATH): recorded in live mode, refused in replay mode,
where the frozen fixture bundle is materialized as ./exa_runs/ instead.
"""
import json
import os
import shutil
import time

from .claude_cli import run_claude
from .prompt_render import render
from .recorder import prepare_replay
from .regression import (append_labels, auto_label_from_verdicts, load_labels,
                         labels_for_scenario, regression_hits)
from .validator import deterministic, grounding
from .validator.deterministic import candidate_key, load_candidates
from .validator.scorecard import build_scorecard, write_scorecard

SHIMS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shims")


def _prompt(config, name):
    with open(os.path.join(config.path("prompts"), name)) as f:
        return f.read()


def _inner_env(run_dir, mode):
    env = {
        "PATH": SHIMS_DIR + os.pathsep + os.environ.get("PATH", ""),
        "PYTHONPATH": SHIMS_DIR,
        "EXA_HTTP_MODE": "record" if mode == "live" else "replay",
        "EXA_HTTP_LOG": os.path.join(run_dir, "exa_http.jsonl"),
        "REAL_CURL": shutil.which("curl", path="/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin") or "/usr/bin/curl",
    }
    try:  # python 3.14 on macOS needs certifi for TLS in the orchestrator path
        import certifi
        env["SSL_CERT_FILE"] = certifi.where()
    except ImportError:
        pass
    return env


def _user_turn(config, scenario, conversation, survey_only=False):
    """One User-LLM decision. Returns {"action", "message", "ux"}."""
    template = _prompt(config, "user_llm.md")
    prompt = render(template,
                    persona=scenario.persona,
                    jd=scenario.jd,
                    conversation=json.dumps(conversation, indent=2),
                    survey_only="yes" if survey_only else "no")
    res = run_claude(prompt, model=config.model("user"), cwd=config.pipeline_dir,
                     timeout_s=config.limit("user_turn_timeout_s"),
                     disallowed_tools=["Bash", "Write", "Edit", "WebFetch", "WebSearch"])
    if not res.ok:
        return {"action": "abort", "message": "", "ux": None,
                "_error": f"user LLM turn failed: {res.error}", "_cost": res.cost_usd}
    try:
        payload = res.json_payload()
    except Exception as e:  # noqa: BLE001 — any parse failure ends the session cleanly
        return {"action": "abort", "message": "", "ux": None,
                "_error": f"user LLM returned unparseable output: {e}", "_cost": res.cost_usd}
    return {"action": payload.get("action", "continue"),
            "message": payload.get("message", ""),
            "ux": payload.get("ux"), "_cost": res.cost_usd}


def run_session(config, scenario, skill_dir, skill_ref, mode, run_id, bundle_dir=None):
    """Execute the conversation. Returns session info dict (also written to
    <run_dir>/session.json)."""
    run_dir = os.path.join(config.path("runs"), run_id)
    outdir = os.path.join(run_dir, "outdir")
    os.makedirs(outdir, exist_ok=True)

    if mode == "replay":
        if not bundle_dir:
            raise ValueError(f"replay for {scenario.id} needs a fixture bundle — record one first")
        prepare_replay(bundle_dir, outdir)

    bootstrap = _prompt(config, "inner_replay.md" if mode == "replay" else "inner_live.md")
    env = _inner_env(run_dir, mode)
    conversation, cost, session_id = [], 0.0, None
    failure, ux = None, None

    for turn in range(config.limit("max_user_turns")):
        user = _user_turn(config, scenario, conversation)
        cost += user.get("_cost", 0.0)
        if user.get("_error"):
            failure = user["_error"]
            break
        if user["action"] in ("accept", "abort") and conversation:
            ux = user.get("ux")
            if user["action"] == "abort":
                failure = failure or "recruiter aborted the session"
            break
        conversation.append({"role": "recruiter", "text": user["message"]})

        if session_id is None:
            prompt = render(bootstrap, skill_dir=skill_dir,
                            recruiter_message=user["message"])
        else:
            prompt = user["message"]
        # Exa traffic must flow through curl/urllib where the shims live:
        # MCP servers are cut in both modes; replay additionally blocks the
        # host-side web tools so a "replay" can never reach live data.
        inner_disallowed = (["WebFetch", "WebSearch"] if mode == "replay" else None)
        inner = run_claude(prompt, model=config.model("inner"), cwd=outdir,
                           timeout_s=config.limit("inner_turn_timeout_s"),
                           add_dirs=[skill_dir], resume=session_id,
                           env_extra=env, strict_mcp=True,
                           disallowed_tools=inner_disallowed,
                           transcript_path=os.path.join(run_dir, f"transcript-turn{turn:02d}.jsonl"))
        cost += inner.cost_usd
        session_id = inner.session_id or session_id
        if not inner.ok:
            failure = f"inner turn {turn} failed: {inner.error}"
            break
        if session_id is None:
            # without a session id the next turn would silently re-bootstrap
            # the skill from scratch instead of resuming
            failure = f"inner turn {turn} returned no session id; cannot resume"
            break
        conversation.append({"role": "skill_agent", "text": inner.text})

    if ux is None and not failure:
        survey = _user_turn(config, scenario, conversation, survey_only=True)
        cost += survey.get("_cost", 0.0)
        ux = survey.get("ux")

    csv_path = os.path.join(outdir, "candidates.csv")
    # a CSV left over from an earlier turn doesn't make a crashed/aborted
    # session a success — any failure means not completed
    completed = os.path.isfile(csv_path) and failure is None
    if not os.path.isfile(csv_path) and not failure:
        failure = "session ended without producing candidates.csv"

    info = {"run_id": run_id, "scenario": scenario.id, "skill_ref": skill_ref,
            "mode": mode, "completed": completed, "failure": failure,
            "turns": len(conversation), "ux": ux, "cost_usd": round(cost, 4),
            "bundle_dir": bundle_dir, "finished_at": int(time.time())}
    with open(os.path.join(run_dir, "conversation.json"), "w") as f:
        json.dump(conversation, f, indent=2)
    with open(os.path.join(run_dir, "session.json"), "w") as f:
        json.dump(info, f, indent=2)
    return info


def validate_run(config, scenario, run_id, session_info, refetch=False):
    """Judge a finished session: deterministic checks always; grounding via the
    Validator LLM on a live run's FIRST validation (verdicts frozen as
    regression labels), via the label store afterwards and in replay — so
    re-validating never re-spends fetches or re-appends labels unless
    `refetch` is set. Writes and returns the scorecard."""
    run_dir = os.path.join(config.path("runs"), run_id)
    csv_path = os.path.join(run_dir, "outdir", "candidates.csv")
    first_validation = not os.path.isfile(os.path.join(run_dir, "scorecard.json"))
    mode = session_info["mode"]
    cost = 0.0

    if os.path.isfile(csv_path):
        det = deterministic.check_run(csv_path, scenario.expectations)
        rows = load_candidates(csv_path)
    else:
        det = {"violations": [], "stats": {"returned": 0,
                                           "requested": scenario.expectations.get("target_count")}}
        rows = []
    det["stats"].setdefault("requested", scenario.expectations.get("target_count"))

    labels = load_labels(config.path("regression"))
    if rows and mode == "live" and (first_validation or refetch):
        verdicts, cost = grounding.check_grounding_live(rows, scenario, config, run_dir)
        append_labels(config.path("regression"),
                      auto_label_from_verdicts(scenario.id, verdicts, run_id))
        unlabeled = 0
    elif rows:
        per = {k: e for k, e in labels_for_scenario(labels, scenario.id).items()}
        verdicts, unlabeled_keys = grounding.join_labels(rows, per)
        unlabeled = len(unlabeled_keys)
    else:
        verdicts, unlabeled = {}, 0

    hits = regression_hits(scenario.id, labels, [candidate_key(r) for r in rows])

    scorecard = build_scorecard(
        run_id=run_id, scenario=scenario, skill_ref=session_info["skill_ref"],
        mode=mode, completed=session_info["completed"],
        failure=session_info["failure"], det_result=det,
        grounding_verdicts=verdicts,
        grounding_stats_d=grounding.grounding_stats(verdicts, unlabeled),
        ux_survey=session_info.get("ux"),
        conversation_turns=session_info["turns"],
        cost_usd=session_info["cost_usd"] + cost,
        grounding_violations_list=grounding.grounding_violations(rows, verdicts))
    scorecard["regression_hits"] = hits
    write_scorecard(run_dir, scorecard)
    return scorecard
