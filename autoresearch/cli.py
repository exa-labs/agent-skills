#!/usr/bin/env python3
"""Skill-optimization pipeline CLI.

  python3 cli.py import [--enrich]        turn inbox drops into scenario packages
  python3 cli.py record --scenario s001   live run + freeze fixtures + auto-labels
  python3 cli.py run --scenario s001 --mode replay [--ref main]
  python3 cli.py suite --mode replay [--ref main] [--scenarios s001,s002] [--record]
  python3 cli.py compare --baseline <suite_id> --candidate <suite_id>
  python3 cli.py optimize [--experiments 4] [--mode replay] [--no-promote]
  python3 cli.py label --scenario s001 --key li:someone --label violation [--notes ...]
  python3 cli.py validate --run <run_id> --scenario s001
  python3 cli.py status
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from harness.claude_cli import run_claude          # noqa: E402
from harness.config import Config                  # noqa: E402
from harness.optimizer import optimize_round, read_log  # noqa: E402
from harness.recorder import latest_bundle         # noqa: E402
from harness.regression import append_labels, load_labels  # noqa: E402
from harness.runner import find_latest_suite, run_one, run_suite  # noqa: E402
from harness.scenario import get_scenario, import_inbox, list_scenarios  # noqa: E402
from harness.scoring import compare as compare_suites  # noqa: E402
from harness.session import validate_run           # noqa: E402


def _p(obj):
    print(json.dumps(obj, indent=2))


def cmd_import(config, args):
    created = import_inbox(config.path("inbox"), config.path("suite"))
    for path in created:
        print(f"scaffolded {os.path.relpath(path, config.pipeline_dir)}")
    if not created and not args.enrich:
        print("inbox empty — drop JD / query files into "
              f"{os.path.relpath(config.path('inbox'), config.pipeline_dir)}/ first")
    if args.enrich:
        with open(os.path.join(config.path("prompts"), "importer_enrich.md")) as f:
            prompt = f.read()
        targets = [s for s in list_scenarios(config.path("suite"))
                   if s.meta.get("status") == "needs_review"]
        for s in targets:
            print(f"enriching {s.id} ...")
            res = run_claude(prompt, model=config.model("importer"), cwd=s.path,
                             timeout_s=config.limit("validator_timeout_s"),
                             allowed_tools=["Read", "Write", "Edit"],
                             disallowed_tools=["Bash", "WebFetch", "WebSearch"])
            print(res.text if res.ok else f"  FAILED: {res.error}")
        if not targets:
            print("no scenarios with status needs_review to enrich")


def cmd_record(config, args):
    info, scorecard = run_one(config, args.scenario, args.ref, "live", record=True)
    _p({"run_id": info["run_id"], "completed": info["completed"],
        "failure": info["failure"], "fixture_bundle": info.get("fixture_bundle"),
        "violations": scorecard["violation_counts"],
        "cost_usd": scorecard["cost_usd"]})


def cmd_run(config, args):
    info, scorecard = run_one(config, args.scenario, args.ref, args.mode)
    _p({"run_id": info["run_id"], "completed": info["completed"],
        "failure": info["failure"], "violations": scorecard["violation_counts"],
        "grounding": scorecard["grounding"], "ux": scorecard["ux"],
        "cost_usd": scorecard["cost_usd"]})


def cmd_suite(config, args):
    ids = args.scenarios.split(",") if args.scenarios else None
    result = run_suite(config, args.ref, args.mode, scenario_ids=ids,
                       record=args.record)
    _p(result)


def cmd_compare(config, args):
    runs_dir = config.path("runs")
    suites = {}
    for label, sid in (("baseline", args.baseline), ("candidate", args.candidate)):
        path = os.path.join(runs_dir, sid, "suite.json")
        if not os.path.isfile(path):
            sys.exit(f"no suite.json under runs/{sid}/")
        with open(path) as f:
            suites[label] = json.load(f)
    _p(compare_suites(suites["baseline"]["score"], suites["candidate"]["score"],
                      config["scoring"]))


def cmd_optimize(config, args):
    report = optimize_round(config, experiments=args.experiments, mode=args.mode,
                            promote=not args.no_promote)
    _p(report)


def cmd_label(config, args):
    append_labels(config.path("regression"),
                  [{"scenario": args.scenario, "key": args.key, "name": args.name,
                    "label": args.label, "provenance": "human",
                    "notes": args.notes or "",
                    "verdict": None}])
    print(f"labeled ({args.scenario}, {args.key}) -> {args.label} [human]")


def cmd_validate(config, args):
    scenario = get_scenario(config.path("suite"), args.scenario)
    session_path = os.path.join(config.path("runs"), args.run, "session.json")
    with open(session_path) as f:
        info = json.load(f)
    scorecard = validate_run(config, scenario, args.run, info, refetch=args.refetch)
    _p({"violations": scorecard["violation_counts"],
        "grounding": scorecard["grounding"],
        "regression_hits": scorecard["regression_hits"]})


def cmd_status(config, args):
    scenarios = list_scenarios(config.path("suite"))
    labels = load_labels(config.path("regression"))
    rows = []
    for s in scenarios:
        bundle = latest_bundle(config.path("fixtures"), s.id)
        n_labels = sum(1 for (sid, _k) in labels if sid == s.id)
        rows.append({"id": s.id, "title": s.meta.get("title"),
                     "status": s.meta.get("status", "ready"),
                     "fixtures": bool(bundle), "labels": n_labels})
    log = read_log(config)
    latest = find_latest_suite(config, ref=config["skill"]["base_ref"])
    inbox = config.path("inbox")
    _p({"skill": config["skill"]["name"],
        "scenarios": rows,
        "inbox_pending": [n for n in sorted(os.listdir(inbox))
                          if not n.startswith(".") and n != "README.md"]
                         if os.path.isdir(inbox) else [],
        "latest_baseline_suite": latest and {
            "suite_id": latest["suite_id"], "mode": latest["mode"],
            "composite": latest["score"]["composite"],
            "gate_failed_runs": latest["score"]["gate_failed_runs"]},
        "experiments": [{"branch": e.get("branch"), "verdict": e.get("verdict")}
                        for e in log[-10:]]})


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None, help="path to config.json")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("import"); s.add_argument("--enrich", action="store_true")
    s = sub.add_parser("record"); s.add_argument("--scenario", required=True)
    s.add_argument("--ref", default=None)
    s = sub.add_parser("run"); s.add_argument("--scenario", required=True)
    s.add_argument("--mode", choices=["live", "replay"], required=True)
    s.add_argument("--ref", default=None)
    s = sub.add_parser("suite")
    s.add_argument("--mode", choices=["live", "replay"], required=True)
    s.add_argument("--ref", default=None); s.add_argument("--scenarios", default=None)
    s.add_argument("--record", action="store_true")
    s = sub.add_parser("compare"); s.add_argument("--baseline", required=True)
    s.add_argument("--candidate", required=True)
    s = sub.add_parser("optimize"); s.add_argument("--experiments", type=int, default=None)
    s.add_argument("--mode", choices=["live", "replay"], default="replay")
    s.add_argument("--no-promote", action="store_true")
    s = sub.add_parser("label"); s.add_argument("--scenario", required=True)
    s.add_argument("--key", required=True)
    s.add_argument("--label", choices=["valid", "violation"], required=True)
    s.add_argument("--name", default=None); s.add_argument("--notes", default=None)
    s = sub.add_parser("validate"); s.add_argument("--run", required=True)
    s.add_argument("--scenario", required=True)
    s.add_argument("--refetch", action="store_true",
                   help="re-run live grounding (spends validator cost, re-labels)")
    sub.add_parser("status")

    args = ap.parse_args()
    config = Config.load(args.config)
    if hasattr(args, "ref") and args.ref is None:
        args.ref = config["skill"]["base_ref"]

    {"import": cmd_import, "record": cmd_record, "run": cmd_run,
     "suite": cmd_suite, "compare": cmd_compare, "optimize": cmd_optimize,
     "label": cmd_label, "validate": cmd_validate, "status": cmd_status}[args.cmd](config, args)


if __name__ == "__main__":
    main()
