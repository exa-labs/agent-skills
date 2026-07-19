"""Freeze a live run's Exa traffic into a replay fixture bundle.

Live search is non-deterministic, so everything downstream of search
(consolidation, filtering, ranking, UX) iterates against frozen data. A
bundle is the normalized interface replay runs consume:

  fixtures/<scenario>/<recording_id>/
    meta.json             provenance
    pool.json             raw discovery candidates (each with _segment, _sources)
    verify_verdicts.json  verification verdicts keyed by candidate dedup key
    raw/                  the captured evidence the bundle was derived from

Derivation sources, in fidelity order:
  1. sourcing_state.json — the orchestrator writes its whole pool + verdicts.
  2. exa_http.jsonl      — the env-shim capture (curl PATH shim + sitecustomize).
  3. transcript.jsonl    — best-effort scan of the session transcript's tool
                           results for completed Exa run bodies.
"""
import glob
import json
import os
import re
import shutil

from .validator.deterministic import candidate_key as _candidate_key

# skills name their structured result list differently (candidate-sourcing:
# `candidates`; people-search: `people`) — harvest either
_CAND_FIELD = re.compile(r"^structured\.(?:candidates|people)\[(\d+)\](?:\.|$)")
_LIST_KEYS = ("candidates", "people")

# orchestrator session-state files, per skill (highest-fidelity source)
_STATE_FILES = ("sourcing_state.json", "people_search_state.json")


def _grounding_by_index(grounding):
    by = {}
    if not isinstance(grounding, list):
        return by
    for e in grounding:
        if not isinstance(e, dict):
            continue
        m = _CAND_FIELD.match(e.get("field") or "")
        cites = e.get("citations")
        if not m or not isinstance(cites, list):
            continue
        urls = by.setdefault(int(m.group(1)), [])
        for c in cites:
            u = c.get("url") if isinstance(c, dict) else None
            if isinstance(u, str) and u.strip() and u not in urls:
                urls.append(u)
    return by


def _from_state(path):
    with open(path) as f:
        state = json.load(f)
    pool = state.get("pool") or []
    verdicts = state.get("verdicts") or {}
    return pool, verdicts


def _harvest_body(body, pool, verdicts, seg_counter):
    """Pull candidates/verdicts out of one completed Exa run response body."""
    out = (body.get("output") or {})
    structured = out.get("structured") or {}
    cands = next((structured.get(k) for k in _LIST_KEYS
                  if isinstance(structured.get(k), list)), None)
    if isinstance(cands, list) and cands:
        seg = f"seg{seg_counter[0]:02d}"
        seg_counter[0] += 1
        grounded = _grounding_by_index(out.get("grounding"))
        for i, c in enumerate(cands):
            if not isinstance(c, dict):
                continue
            c = dict(c)
            c.setdefault("_segment", seg)
            if i in grounded:
                c.setdefault("_sources", grounded[i])
            pool.append(c)
    vs = structured.get("verdicts")
    if isinstance(vs, list):
        for v in vs:
            if isinstance(v, dict) and v.get("id"):
                verdicts[v["id"]] = v


def _json_candidates_in(text):
    """Best-effort: parse a text blob as (or containing) a JSON object."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            obj = json.loads(text[start:end + 1])
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None


def _harvest_once(body, pool, verdicts, seg_counter, seen_run_ids):
    """A completed run is observed repeatedly (every poll returns the same
    body); harvesting it twice would inflate seg_counter and duplicate
    candidates under wrong segment labels."""
    rid = body.get("id")
    if rid and rid in seen_run_ids:
        return
    if rid:
        seen_run_ids.add(rid)
    _harvest_body(body, pool, verdicts, seg_counter)


def _from_http_log(path):
    pool, verdicts, seg_counter, seen = [], {}, [1], set()
    with open(path) as f:
        for line in f:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("kind") != "exchange":
                continue
            body = _json_candidates_in(entry.get("response_body"))
            if body and body.get("status") == "completed":
                _harvest_once(body, pool, verdicts, seg_counter, seen)
    return pool, verdicts


def _from_transcripts(paths):
    pool, verdicts, seg_counter, seen = [], {}, [1], set()
    for path in paths:
        with open(path) as f:
            for line in f:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                for text in _texts_in(event):
                    body = _json_candidates_in(text)
                    if body and body.get("status") == "completed":
                        _harvest_once(body, pool, verdicts, seg_counter, seen)
    return pool, verdicts


def _texts_in(obj):
    """All string leaves of a transcript event (tool results bury bodies at
    varying depths)."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _texts_in(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _texts_in(v)


def _dedup_pool(pool):
    by = {}
    for c in pool:
        k = _candidate_key(c)
        if k.replace("nm:", "").strip() and k not in by:
            by[k] = c
    return list(by.values())


def record_bundle(run_dir, fixtures_dir, scenario_id, recording_id, skill_ref):
    """Derive a fixture bundle from a finished live run. Returns the bundle
    dir, or None if nothing recordable was captured."""
    state_path = next((p for p in (os.path.join(run_dir, "outdir", n) for n in _STATE_FILES)
                       if os.path.isfile(p)), None)
    log_path = os.path.join(run_dir, "exa_http.jsonl")
    transcripts = sorted(glob.glob(os.path.join(run_dir, "transcript*.jsonl")))

    pool, verdicts, source = [], {}, None
    if state_path:
        pool, verdicts = _from_state(state_path)
        source = "sourcing_state"
    if not pool and os.path.isfile(log_path):
        pool, verdicts = _from_http_log(log_path)
        source = "http_log"
    if not pool and transcripts:
        pool, verdicts = _from_transcripts(transcripts)
        source = "transcript"
    if not pool:
        return None

    pool = _dedup_pool(pool)
    bundle = os.path.join(fixtures_dir, scenario_id, recording_id)
    os.makedirs(os.path.join(bundle, "raw"), exist_ok=True)
    with open(os.path.join(bundle, "pool.json"), "w") as f:
        json.dump(pool, f, indent=2)
    with open(os.path.join(bundle, "verify_verdicts.json"), "w") as f:
        json.dump(verdicts, f, indent=2)
    with open(os.path.join(bundle, "meta.json"), "w") as f:
        json.dump({"scenario": scenario_id, "recording_id": recording_id,
                   "skill_ref": skill_ref, "source": source,
                   "candidates": len(pool), "verdicts": len(verdicts)}, f, indent=2)
    for p in (state_path, log_path):
        if p and os.path.isfile(p):
            shutil.copy(p, os.path.join(bundle, "raw", os.path.basename(p)))
    return bundle


def latest_bundle(fixtures_dir, scenario_id):
    d = os.path.join(fixtures_dir, scenario_id)
    if not os.path.isdir(d):
        return None
    recs = sorted(n for n in os.listdir(d)
                  if os.path.isfile(os.path.join(d, n, "pool.json")))
    return os.path.join(d, recs[-1]) if recs else None


def prepare_replay(bundle_dir, outdir):
    """Materialize a bundle into <outdir>/exa_runs/ for a replay session."""
    target = os.path.join(outdir, "exa_runs")
    os.makedirs(target, exist_ok=True)
    for name in ("pool.json", "verify_verdicts.json", "meta.json"):
        shutil.copy(os.path.join(bundle_dir, name), os.path.join(target, name))
    with open(os.path.join(target, "README.md"), "w") as f:
        f.write(
            "# Frozen Exa run outputs (replay session)\n\n"
            "Live search is disabled. These files are the raw outputs of the\n"
            "already-executed Exa Agent runs for this brief:\n\n"
            "- `pool.json` — every person returned by the discovery runs, exactly\n"
            "  as the API returned them. `_segment` is the search segment the\n"
            "  person came from; `_sources` are the grounding citation URLs for\n"
            "  that person's claims.\n"
            "- `verify_verdicts.json` — the verification pass's verdicts, keyed by\n"
            "  dedup key (linkedin slug `li:<slug>`, else profile url `url:<url>`,\n"
            "  else `nm:<name>`). A person absent from this map is `unchecked`.\n")
    return target


def load_bundle(bundle_dir):
    with open(os.path.join(bundle_dir, "pool.json")) as f:
        pool = json.load(f)
    with open(os.path.join(bundle_dir, "verify_verdicts.json")) as f:
        verdicts = json.load(f)
    return pool, verdicts
