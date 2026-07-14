"""The accumulating regression set.

There is no pre-made answer key for live sourcing, so labels are grown from
observed output: every grounded fact-check verdict from a record-time run is
frozen as an auto label (valid / violation) keyed by (scenario, candidate).
Humans can override any label by appending a line with provenance "human" —
the store is append-only JSONL, last human line wins, then last auto line.

Two uses:
  1. Replay validation joins these labels instead of re-fetching sources.
  2. Scoring counts known-violation candidates that reappear in a run's final
     list ("regression hits") — an edit that resurfaces a labeled-bad
     candidate is rejected regardless of its composite score.
"""
import json
import os


def load_labels(path):
    """Returns {(scenario, key): entry}, human provenance beating auto."""
    labels = {}
    if not os.path.isfile(path):
        return labels
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            k = (e.get("scenario"), e.get("key"))
            if None in k:
                continue
            prev = labels.get(k)
            if prev and prev.get("provenance") == "human" and e.get("provenance") != "human":
                continue
            labels[k] = e
    return labels


def append_labels(path, entries):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def labels_for_scenario(labels, scenario_id):
    return {key: e for (sid, key), e in labels.items() if sid == scenario_id}


def auto_label_from_verdicts(scenario_id, verdicts_by_key, run_id):
    """Turn grounding verdicts into auto labels. `violation` when sources
    contradict the identity or confidently show a must-have miss; `valid` only
    when the identity was positively supported (full verdict kept, so replay
    joins reproduce the exact grounding stats). A candidate the validator
    couldn't actually check (unreachable sources, errored batch, unsupported)
    gets NO label — freezing it as valid would poison the regression set with
    false negatives it could never recover from."""
    entries = []
    for key, v in verdicts_by_key.items():
        if v.get("identity") == "contradicted" or v.get("must_haves") == "violates":
            label = "violation"
        elif v.get("identity") == "supported":
            label = "valid"
        else:
            continue
        entries.append({"scenario": scenario_id, "key": key, "name": v.get("name"),
                        "label": label,
                        "provenance": "auto", "recorded_in": run_id,
                        "verdict": v})
    return entries


def regression_hits(scenario_id, labels, candidate_keys):
    """Known-violation candidates that appear in a run's final list."""
    per = labels_for_scenario(labels, scenario_id)
    return [k for k in candidate_keys
            if per.get(k, {}).get("label") == "violation"]
