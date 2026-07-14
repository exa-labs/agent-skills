#!/usr/bin/env python3
"""Scripted stand-in for the `claude` binary (PIPELINE_CLAUDE_BIN points here).

Recognizes which harness role is calling from the prompt text and answers in
the exact output format the harness requested, so every layer above
claude_cli.py is exercised for real — subprocess, flag parsing, stream-json
transcripts, session resume, JSON payload extraction — without a model or
network.

Env knobs:
  FAKE_CANDIDATES_CSV  file the "inner agent" copies to cwd as candidates.csv
  FAKE_INNER_NO_CSV    when set, the inner agent produces no csv (failure path)
  FAKE_CLAUDE_ERROR    when set, every call returns an is_error result
"""
import json
import os
import shutil
import sys
import uuid


def parse_argv(argv):
    flags, prompt = {}, None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-p", "--print", "--verbose", "--strict-mcp-config",
                 "--dangerously-skip-permissions"):
            i += 1
        elif a.startswith("--"):
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                flags[a] = argv[i + 1]
                i += 2
            else:
                flags[a] = True
                i += 1
        else:
            prompt = a
            i += 1
    return flags, prompt or ""


def emit(flags, text, session_id=None, is_error=False):
    session_id = session_id or str(uuid.uuid4())
    if flags.get("--output-format") == "stream-json":
        print(json.dumps({"type": "system", "subtype": "init", "session_id": session_id}))
        print(json.dumps({"type": "result", "result": text, "session_id": session_id,
                          "total_cost_usd": 0.01, "is_error": is_error}))
    else:
        print(json.dumps({"result": text, "session_id": session_id,
                          "total_cost_usd": 0.01, "is_error": is_error}))


def user_role(flags, prompt):
    if "survey_only: yes" in prompt:
        emit(flags, json.dumps({"action": "accept", "message": "",
                                "ux": {"checkpoint_quality": 4, "clarity": 4,
                                       "efficiency": 3, "trust": 4,
                                       "notes": "solid run (survey)"}}))
    elif '"skill_agent"' not in prompt:
        emit(flags, json.dumps({"action": "continue", "ux": None,
                                "message": "Hi — here's my JD, I need about 3 strong "
                                           "candidates. JD follows the persona."}))
    elif "final shortlist" in prompt:
        emit(flags, json.dumps({"action": "accept", "message": "",
                                "ux": {"checkpoint_quality": 5, "clarity": 4,
                                       "efficiency": 4, "trust": 5,
                                       "notes": "asked the right questions"}}))
    else:
        emit(flags, json.dumps({"action": "continue", "ux": None,
                                "message": "Senior only, London is a hard requirement, "
                                           "no one currently at BigCorp. Go ahead."}))


def inner_role(flags, prompt):
    if "--resume" in flags:
        if not os.environ.get("FAKE_INNER_NO_CSV"):
            shutil.copy(os.environ["FAKE_CANDIDATES_CSV"], "candidates.csv")
        emit(flags, "Done — wrote candidates.csv. Here is your final shortlist: "
                    "3 verified candidates, ranked.", session_id=flags["--resume"])
    else:
        emit(flags, "I read the skill and built a search plan (role, dimensions, "
                    "segments). Before I search: seniority band? location strictness? "
                    "companies to exclude?")


def validator_role(flags, prompt):
    start = prompt.find("[", prompt.find("The candidates to audit"))
    end = prompt.find("\n# Method")
    batch = json.loads(prompt[start:prompt.rfind("]", start, end) + 1])
    out = [{"key": b["key"], "name": b["name"], "identity": "supported",
            "claims_checked": 3, "claims_supported": 3, "claims_contradicted": 0,
            "claims_unreachable": 0, "must_haves": "meets", "confident": True,
            "notes": "sources corroborate"} for b in batch]
    emit(flags, json.dumps({"candidates": out}))


def outer_role(flags, prompt):
    if "Propose exactly" in prompt:
        emit(flags, json.dumps({"proposals": [
            {"slug": "tighten-ranking", "hypothesis": "rank confirmed-first strictly",
             "stages": ["rank"], "expected": "constraints +2",
             "edit_instructions": "In SKILL.md Step 6, add one sentence: 'Break ties "
                                  "by verification status.'"},
            {"slug": "search-fanout", "hypothesis": "more segments",
             "stages": ["search"], "expected": "delivery +5",
             "edit_instructions": "In SKILL.md Step 3, raise segment count."}]}))
    else:  # apply
        with open("SKILL.md", "a") as f:
            f.write("\n<!-- exp edit: break ties by verification status -->\n")
        emit(flags, "Applied the edit to SKILL.md Step 6.")


def main():
    flags, prompt = parse_argv(sys.argv[1:])
    if os.environ.get("FAKE_CLAUDE_ERROR"):
        emit(flags, os.environ["FAKE_CLAUDE_ERROR"], is_error=True)
        return
    if "You are playing a RECRUITER" in prompt:
        user_role(flags, prompt)
    elif "skeptical fact-checker" in prompt:
        validator_role(flags, prompt)
    elif "Propose exactly" in prompt or "editor agent" in prompt:
        outer_role(flags, prompt)
    elif "Skill directory" in prompt or "--resume" in flags:
        inner_role(flags, prompt)
    else:
        emit(flags, "unrecognized role prompt")


if __name__ == "__main__":
    main()
