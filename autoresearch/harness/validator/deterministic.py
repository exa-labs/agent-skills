"""Deterministic constraint checks over a run's candidates.csv.

These are the checks that need no LLM and no network: they hold whatever the
skill text says, so they are the stable floor of the scorecard. Every check
maps to a violation type listed in config scoring.hard_gates; one violation of
a gated type fails the run outright.

Normalization mirrors the skill's own dedup logic (linkedin slug, lowercased
letters-only name) so the validator and the skill can't disagree about
identity.
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


def candidate_key(row):
    return norm_li(row.get("linkedinUrl")) or ("nm:" + norm_name(row.get("name")))


def load_candidates(csv_path):
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def check_run(csv_path, expectations):
    """Returns {"violations": [...], "stats": {...}}.

    Each violation: {"type", "rank", "name", "detail"}.
    """
    violations, stats = [], {}

    try:
        rows = load_candidates(csv_path)
    except (OSError, csv.Error) as e:
        return {"violations": [{"type": "malformed_output", "rank": None, "name": None,
                                "detail": f"cannot read candidates.csv: {e}"}],
                "stats": {"returned": 0}}

    header = rows[0].keys() if rows else []
    missing = [c for c in BASE_COLUMNS if rows and c not in header]
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
        co = (row.get("currentCompany") or "").lower()
        hit = next((t for t in terms if t in co), None)
        if hit:
            add("excluded_employer_leak", row,
                f"currentCompany {row.get('currentCompany')!r} matches excluded term {hit!r}")

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
                if not loc_cfg.get("allow_unknown", False):
                    add("location_violation", row, "location unknown but constraint is strict")
            elif pats and not any(p.search(loc) for p in pats):
                add("location_violation", row, f"location {loc!r} outside accepted areas")

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
