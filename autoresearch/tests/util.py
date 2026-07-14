"""Shared scaffolding for offline tests: a throwaway pipeline dir, a throwaway
skill git repo, and canned run artifacts. No network, no real claude."""
import csv
import json
import os
import shutil
import subprocess
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PIPELINE_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, PIPELINE_DIR)

from harness.config import Config  # noqa: E402

FAKE_CLAUDE = os.path.join(TESTS_DIR, "fake_claude.py")
os.chmod(FAKE_CLAUDE, 0o755)

GIT_ENV = {"GIT_AUTHOR_NAME": "pipeline-test", "GIT_AUTHOR_EMAIL": "t@t.local",
           "GIT_COMMITTER_NAME": "pipeline-test", "GIT_COMMITTER_EMAIL": "t@t.local"}

CSV_COLUMNS = ["rank", "name", "linkedinUrl", "currentTitle", "currentCompany",
               "location", "score", "likely_to_move", "months_in_current_role",
               "avg_months_per_prior_role", "seniority_vs_role", "mobility_signals",
               "overall_tier", "confidence", "backendEngineering", "seniority",
               "concerns", "verify_exists", "verify_match", "sources", "segment"]

CLEAN_ROWS = [
    ["1", "Alice Warden", "https://linkedin.com/in/alice-warden", "Staff Engineer",
     "Streamline Ltd", "London, UK", "91", "72", "30", "28", "aligned", "",
     "strong", "high", "strong", "ic_staff_principal", "", "confirmed", "strong",
     "https://example.com/alice | https://example.com/alice2", "seg01"],
    ["2", "Bob Trellis", "https://linkedin.com/in/bob-trellis", "Senior Engineer",
     "Datagrove", "Greater London", "84", "", "", "", "", "",
     "strong", "medium", "strong", "ic_senior", "", "confirmed", "partial",
     "https://example.com/bob", "seg01"],
    ["3", "Cara Mott", "https://linkedin.com/in/cara-mott", "Backend Lead",
     "Finchline", "London", "78", "55", "20", "30", "step_up", "",
     "moderate", "medium", "partial", "ic_senior", "thin public footprint",
     "likely", "partial", "https://example.com/cara", "seg02"],
]

EXPECTATIONS = {
    "target_count": 3,
    "exclude_employer_terms": ["bigcorp"],
    "excluded_people": [{"name": "Zed Nixon"}],
    "location": {"strict": True, "accept_patterns": ["london"], "allow_unknown": False},
    "must_have_column_patterns": ["backend"],
    "must_haves_semantic": ["5+ years backend engineering", "based in London"],
}

POOL = [
    {"name": "Alice Warden", "linkedinUrl": "https://linkedin.com/in/alice-warden",
     "currentTitle": "Staff Engineer", "currentCompany": "Streamline Ltd",
     "location": "London, UK", "_segment": "seg01",
     "_sources": ["https://example.com/alice"]},
    {"name": "Bob Trellis", "linkedinUrl": "https://linkedin.com/in/bob-trellis",
     "currentTitle": "Senior Engineer", "currentCompany": "Datagrove",
     "location": "Greater London", "_segment": "seg01",
     "_sources": ["https://example.com/bob"]},
    {"name": "Cara Mott", "linkedinUrl": "https://linkedin.com/in/cara-mott",
     "currentTitle": "Backend Lead", "currentCompany": "Finchline",
     "location": "London", "_segment": "seg02",
     "_sources": ["https://example.com/cara"]},
]

VERIFY_VERDICTS = {
    "li:alice-warden": {"id": "li:alice-warden", "name": "Alice Warden",
                        "exists": "confirmed", "matches_role": "strong"},
    "li:bob-trellis": {"id": "li:bob-trellis", "name": "Bob Trellis",
                       "exists": "confirmed", "matches_role": "partial"},
}


def write_csv(path, rows, columns=None):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(columns or CSV_COLUMNS)
        w.writerows(rows)
    return path


def make_skill_repo(path, subpath=""):
    """A git repo whose SKILL.md lives at <path>/<subpath>. subpath="" is a
    standalone skill (SKILL.md at the root); a non-empty subpath mirrors the
    monorepo layout where the skill is a subdir of a larger repo."""
    skill_dir = os.path.join(path, subpath)
    os.makedirs(skill_dir)
    with open(os.path.join(skill_dir, "SKILL.md"), "w") as f:
        f.write("# test skill\n\nStep 1: plan + checkpoint. Step 6: write candidates.csv.\n")
    env = dict(os.environ, **GIT_ENV)
    for cmd in (["git", "init", "-q", "-b", "main"], ["git", "add", "-A"],
                ["git", "commit", "-qm", "initial skill"]):
        subprocess.run(cmd, cwd=path, env=env, check=True, capture_output=True)
    return path


def make_pipeline(tmp):
    """A full temp pipeline dir wired to fake_claude and a temp skill repo.
    Directories come from the resolved config paths, so the per-skill
    ({skill}) layout is exercised exactly as production uses it."""
    pdir = os.path.join(tmp, "pipeline")
    os.makedirs(pdir)
    shutil.copytree(os.path.join(PIPELINE_DIR, "prompts"), os.path.join(pdir, "prompts"))

    with open(os.path.join(PIPELINE_DIR, "config.json")) as f:
        cfg = json.load(f)
    # exercise the real skill.path (monorepo subdir) against a temp repo whose
    # default branch is main, so base_ref must be overridden to match.
    skill_repo = make_skill_repo(os.path.join(tmp, "skill-repo"),
                                 cfg["skill"].get("path", ""))
    cfg["skill"]["repo"] = skill_repo
    cfg["skill"]["base_ref"] = "main"
    for k in ("inner_turn_timeout_s", "user_turn_timeout_s",
              "validator_timeout_s", "outer_timeout_s"):
        cfg["limits"][k] = 60
    with open(os.path.join(pdir, "config.json"), "w") as f:
        json.dump(cfg, f)

    config = Config.load(os.path.join(pdir, "config.json"))
    for key in ("suite", "inbox", "fixtures", "runs", "workspace"):
        os.makedirs(config.path(key), exist_ok=True)

    sdir = os.path.join(config.path("suite"), "t001-test-role")
    os.makedirs(sdir)
    with open(os.path.join(sdir, "scenario.json"), "w") as f:
        json.dump({"id": "t001", "title": "test role", "target_count": 3,
                   "status": "ready"}, f)
    with open(os.path.join(sdir, "jd.md"), "w") as f:
        f.write("# Senior Backend Engineer (London)\n5+ years backend. London based.\n")
    with open(os.path.join(sdir, "persona.md"), "w") as f:
        f.write("You are a recruiter at Finflow. Location London is hard. "
                "Exclude BigCorp employees. Accept when a ranked list arrives.\n")
    with open(os.path.join(sdir, "expectations.json"), "w") as f:
        json.dump(EXPECTATIONS, f)

    bundle = os.path.join(config.path("fixtures"), "t001", "rec-001")
    os.makedirs(os.path.join(bundle, "raw"))
    with open(os.path.join(bundle, "pool.json"), "w") as f:
        json.dump(POOL, f)
    with open(os.path.join(bundle, "verify_verdicts.json"), "w") as f:
        json.dump(VERIFY_VERDICTS, f)
    with open(os.path.join(bundle, "meta.json"), "w") as f:
        json.dump({"scenario": "t001", "recording_id": "rec-001",
                   "skill_ref": "main", "source": "test"}, f)

    return config


def fake_claude_env(candidates_csv):
    env = {"PIPELINE_CLAUDE_BIN": FAKE_CLAUDE,
           "FAKE_CANDIDATES_CSV": candidates_csv}
    env.update(GIT_ENV)
    return env
