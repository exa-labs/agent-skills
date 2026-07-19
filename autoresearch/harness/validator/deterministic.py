"""Deterministic constraint checks over a run's output CSV.

These are the checks that need no LLM and no network. They come in two
precision tiers, and only the first is allowed to hard-gate a run:

  GATE-ELIGIBLE (high precision — true positives by construction):
    - self-consistency: the run's OWN columns admit the defect (a kept row
      graded 'none' on a must-have, verify_exists='not_found', verify_match='no')
    - syntax: malformed LinkedIn URLs, placeholder names, duplicate identities
    - exact identity: a person on the persona's exclusion list, matched by
      normalized key, appears in the output
    - policy: a row with no determinable location kept under a strict
      location constraint (the defect IS the missing verification)

  SUSPECTED (fuzzy string-matching — regexes cannot know geography or
  disambiguate org names, so these are tripwires, not verdicts):
    - excluded_employer_suspected: an excluded-org term appears in the org
      column ("citadel" also matches Citadel Federal Credit Union)
    - location_suspected: a location string matches no accept_pattern
      (no pattern list ever covers "Remote (CET)")
  Suspected types are reported on the scorecard but are NOT in hard_gates and
  do not reduce the constraints component. The authoritative call is the
  grounding validator's per-person adjudication (in_location /
  at_excluded_org), which fetches sources live and freezes into the label
  store — so replays get adjudicated answers for free.

Normalization mirrors the skill's own dedup logic (linkedin slug, profile
url, lowercased letters-only name) so the validator and the skill can't
disagree about identity.
"""
import csv
import re

BASE_COLUMNS = ["rank", "name", "linkedinUrl", "currentTitle", "currentCompany",
                "location", "score", "segment"]

_LI = re.compile(r"^https?://(www\.)?linkedin\.com/in/[^/?#\s]+/?$", re.IGNORECASE)
_PLACEHOLDER_NAMES = {"unknown", "n/a", "candidate", "tbd", "john doe", "jane doe"}


def norm_li(url):
    u = (url or "").lower().split("?")[0].rstrip("/")
    m = re.search(r"linkedin\.com/in/([^/]+)", u)
    return "li:" + m.group(1) if m else ""


def norm_name(name):
    return re.sub(r"[^a-z ]", "", (name or "").lower()).strip()


def norm_url(url):
    """Non-LinkedIn profile URL → stable key (people-search rows may have a
    profileUrl instead of a LinkedIn slug). Mirrors the people-search
    orchestrator's `_norm_url` exactly — same normalization, same `url:`
    prefix — so harness keys join the orchestrator's verdict keys."""
    u = (url or "").lower().split("?")[0].split("#")[0].rstrip("/")
    u = re.sub(r"^https?://(www\.)?", "", u)
    return "url:" + u if u else ""


def candidate_key(row):
    """Identity key, LinkedIn-first. Falls through to profileUrl (present in
    people-search output; absent in candidate-sourcing rows, where this is a
    no-op) and lastly the normalized name."""
    return (norm_li(row.get("linkedinUrl"))
            or norm_url(row.get("profileUrl"))
            or ("nm:" + norm_name(row.get("name"))))


def load_candidates(csv_path):
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def check_run(csv_path, expectations, profile=None):
    """Returns {"violations": [...], "stats": {...}}.

    Each violation: {"type", "rank", "name", "detail"}.

    `profile` (config.Config.profile) supplies the skill's output contract —
    required columns and which column holds the person's current org. Omitted
    (as in older callers/tests) it defaults to the candidate-sourcing shape.
    """
    profile = profile or {}
    base_columns = profile.get("base_columns", BASE_COLUMNS)
    org_column = profile.get("org_column", "currentCompany")
    violations, stats = [], {}

    try:
        rows = load_candidates(csv_path)
    except (OSError, csv.Error) as e:
        return {"violations": [{"type": "malformed_output", "rank": None, "name": None,
                                "detail": f"cannot read candidates.csv: {e}"}],
                "stats": {"returned": 0}}

    header = rows[0].keys() if rows else []
    missing = [c for c in base_columns if rows and c not in header]
    if missing:
        violations.append({"type": "malformed_output", "rank": None, "name": None,
                           "detail": f"missing columns: {missing}"})

    def add(vtype, row, detail):
        violations.append({"type": vtype, "rank": row.get("rank"),
                           "name": row.get("name"), "detail": detail})

    # -- identity well-formedness + duplicates ------------------------------
    seen_keys = {}
    wellformed = 0
    for row in rows:
        name = (row.get("name") or "").strip()
        li = (row.get("linkedinUrl") or "").strip()
        ok = True
        if not name or norm_name(name) in _PLACEHOLDER_NAMES or len(name.split()) < 2:
            add("fabricated_identity", row, f"implausible or missing name {name!r}")
            ok = False
        if li and not _LI.match(li):
            add("fabricated_identity", row, f"malformed LinkedIn URL {li!r}")
            ok = False
        if ok:
            wellformed += 1
        key = candidate_key(row)
        if key.replace("nm:", "").strip():
            if key in seen_keys:
                add("duplicate_candidate", row,
                    f"duplicates rank {seen_keys[key]} (key {key})")
            else:
                seen_keys[key] = row.get("rank")

    # -- excluded employer ---------------------------------------------------
    terms = [t.strip().lower() for t in expectations.get("exclude_employer_terms", []) if t.strip()]
    for row in rows:
        co = (row.get(org_column) or "").lower()
        hit = next((t for t in terms if t in co), None)
        if hit:
            add("excluded_employer_suspected", row,
                f"{org_column} {row.get(org_column)!r} matches excluded term {hit!r} "
                "(substring tripwire — adjudicated by the grounding validator)")

    # -- excluded people (recruiter's ATS / dedupe list) ---------------------
    excl_keys = set()
    for p in expectations.get("excluded_people", []):
        if isinstance(p, str):
            p = {"linkedin": p} if "linkedin.com/in/" in p.lower() else {"name": p}
        if p.get("linkedin"):
            k = norm_li(p["linkedin"])
            if k:
                excl_keys.add(k)
        if p.get("name"):
            excl_keys.add("nm:" + norm_name(p["name"]))
    for row in rows:
        k_li, k_nm = norm_li(row.get("linkedinUrl")), "nm:" + norm_name(row.get("name"))
        if (k_li and k_li in excl_keys) or (norm_name(row.get("name")) and k_nm in excl_keys):
            add("excluded_person_leak", row, "matches the recruiter's exclusion list")

    # -- location ------------------------------------------------------------
    loc_cfg = expectations.get("location") or {}
    if loc_cfg.get("strict"):
        pats = [re.compile(p, re.IGNORECASE) for p in loc_cfg.get("accept_patterns", [])]
        for row in rows:
            loc = (row.get("location") or "").strip()
            if not loc or loc.lower() in ("unknown", "n/a"):
                # policy, not string-matching: keeping a person whose location
                # could not be determined under a hard location constraint is
                # the run's own defect — gate-eligible
                if not loc_cfg.get("allow_unknown", False):
                    add("location_violation", row, "location unknown but constraint is strict")
            elif pats and not any(p.search(loc) for p in pats):
                add("location_suspected", row,
                    f"location {loc!r} matches no accept_pattern "
                    "(regex tripwire — adjudicated by the grounding validator)")

    # -- must-haves (structural: the run's own grading admits the miss) ------
    mh_pats = [re.compile(p, re.IGNORECASE) for p in expectations.get("must_have_column_patterns", [])]
    mh_cols = [c for c in header if any(p.search(c) for p in mh_pats)] if rows else []
    for row in rows:
        for col in mh_cols:
            if (row.get(col) or "").strip().lower() == "none":
                add("must_have_violation", row,
                    f"must-have dimension {col!r} graded 'none' by the run itself")
        if (row.get("verify_match") or "").strip().lower() == "no":
            add("must_have_violation", row,
                "verification said matches_role='no' but candidate was kept")

    # -- verification-status leaks (skill says these must be dropped) --------
    for row in rows:
        if (row.get("verify_exists") or "").strip().lower() == "not_found":
            add("verify_status_leak", row, "verify_exists='not_found' but candidate was kept")

    stats = {
        "returned": len(rows),
        "requested": expectations.get("target_count"),
        "identity_wellformed": wellformed,
        "with_linkedin": sum(1 for r in rows if (r.get("linkedinUrl") or "").strip()),
        "with_sources": sum(1 for r in rows if (r.get("sources") or "").strip()),
        "verified_confirmed": sum(1 for r in rows
                                  if (r.get("verify_exists") or "").lower() == "confirmed"),
        "must_have_columns_checked": mh_cols,
    }
    return {"violations": violations, "stats": stats}
