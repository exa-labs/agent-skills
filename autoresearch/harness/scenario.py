"""Scenario packages: one directory per JD under suite/scenarios/.

A scenario is everything one evaluation needs:
  scenario.json      — id, title, target_count, tags
  jd.md              — the job description the simulated recruiter supplies
  persona.md         — the User-LLM script: who the recruiter is, preferences
                       they reveal only when asked, scripted curveballs, and
                       what they consider a satisfying interaction
  expectations.json  — machine-checkable END-STATE constraints for the
                       deterministic validator (after any mid-flow curveball
                       has been applied)

Raw JDs / tough queries the user drops into suite/inbox/ are turned into
scenario packages by `import` — mechanically scaffolded, then (optionally)
enriched by the importer LLM into a drafted persona + expectations for human
review.
"""
import json
import os
import re

REQUIRED_FILES = ("scenario.json", "jd.md", "persona.md", "expectations.json")

EXPECTATION_DEFAULTS = {
    "target_count": 25,
    "exclude_employer_terms": [],
    "excluded_people": [],
    "location": {"strict": False, "accept_patterns": [], "allow_unknown": True},
    "must_have_column_patterns": [],
    "must_haves_semantic": [],
}


class ScenarioError(Exception):
    pass


class Scenario:
    def __init__(self, path):
        self.path = os.path.abspath(path)
        for f in REQUIRED_FILES:
            if not os.path.isfile(os.path.join(self.path, f)):
                raise ScenarioError(f"{os.path.basename(path)}: missing {f}")
        with open(os.path.join(self.path, "scenario.json")) as f:
            self.meta = json.load(f)
        with open(os.path.join(self.path, "expectations.json")) as f:
            raw = json.load(f)
        self.expectations = dict(EXPECTATION_DEFAULTS)
        self.expectations.update(raw)
        loc = dict(EXPECTATION_DEFAULTS["location"])
        loc.update(raw.get("location") or {})
        self.expectations["location"] = loc
        self.id = self.meta["id"]

    def read(self, name):
        with open(os.path.join(self.path, name)) as f:
            return f.read()

    @property
    def jd(self):
        return self.read("jd.md")

    @property
    def persona(self):
        return self.read("persona.md")


def list_scenarios(suite_dir):
    out = []
    if not os.path.isdir(suite_dir):
        return out
    for name in sorted(os.listdir(suite_dir)):
        path = os.path.join(suite_dir, name)
        if os.path.isdir(path) and os.path.isfile(os.path.join(path, "scenario.json")):
            out.append(Scenario(path))
    return out


def get_scenario(suite_dir, scenario_id):
    for s in list_scenarios(suite_dir):
        if s.id == scenario_id:
            return s
    raise ScenarioError(f"no scenario with id {scenario_id!r} in {suite_dir}")


def _slugify(name):
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:40] or "scenario"


def _next_id(suite_dir):
    ids = [s.id for s in list_scenarios(suite_dir)]
    nums = [int(m.group(1)) for i in ids if (m := re.match(r"s(\d+)", i))]
    return f"s{(max(nums) + 1 if nums else 1):03d}"


def import_inbox(inbox_dir, suite_dir):
    """Scaffold a scenario package from every raw file in the inbox.

    Mechanical only: jd.md gets the raw content; persona.md and
    expectations.json get TODO-marked templates. `cli.py import --enrich`
    then drafts them with the importer LLM for the user to review. Imported
    raw files are moved into the new scenario dir as jd.source so the inbox
    stays empty (= processed).
    """
    created = []
    os.makedirs(suite_dir, exist_ok=True)
    if not os.path.isdir(inbox_dir):
        os.makedirs(inbox_dir)
        return created
    for name in sorted(os.listdir(inbox_dir)):
        src = os.path.join(inbox_dir, name)
        if not os.path.isfile(src) or name.startswith(".") or name == "README.md":
            continue
        with open(src, encoding="utf-8", errors="replace") as f:
            raw = f.read()
        sid = _next_id(suite_dir)
        base = os.path.splitext(name)[0]
        sdir = os.path.join(suite_dir, f"{sid}-{_slugify(base)}")
        os.makedirs(sdir)
        with open(os.path.join(sdir, "jd.md"), "w") as f:
            f.write(raw)
        with open(os.path.join(sdir, "scenario.json"), "w") as f:
            json.dump({"id": sid, "title": base, "target_count": 25,
                       "tags": ["imported"], "status": "needs_review"}, f, indent=2)
        with open(os.path.join(sdir, "expectations.json"), "w") as f:
            json.dump({"_TODO": "fill from the JD (or run: cli.py import --enrich)",
                       **EXPECTATION_DEFAULTS}, f, indent=2)
        with open(os.path.join(sdir, "persona.md"), "w") as f:
            f.write("# Persona (TODO — draft by hand or run: cli.py import --enrich)\n\n"
                    "You are the hiring recruiter for the attached JD.\n\n"
                    "## Preferences you reveal only when asked\n- TODO\n\n"
                    "## Curveballs\n- (none)\n\n"
                    "## What satisfies you\n- TODO\n")
        os.rename(src, os.path.join(sdir, "jd.source"))
        created.append(sdir)
    return created
