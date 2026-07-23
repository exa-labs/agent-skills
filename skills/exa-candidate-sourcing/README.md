# Exa candidate sourcing

An agent skill for building and iteratively refining verified recruiting shortlists with Exa.

The default workflow is calibration-first:

1. Confirm a durable recruiting brief with hard constraints and preferences.
2. Run one lightweight sample across all proposed talent segments.
3. Apply recruiter feedback to the existing brief and candidate pool.
4. Expand only approved segments, then verify and rank the shortlist.

Every hard condition is executable: location/employer/seniority use typed fields, while other rules
use evidence-backed `meets` / `fails` / `unknown` checks with an explicit unknown policy. Exact
agent-generated employer exclusion lists must be recruiter-confirmed before execution.

Agents with Python and a filesystem use `orchestrator/source_candidates.py`. Agents without them
follow the Exa MCP procedure linked from `SKILL.md`; no JSON files are required for that path.

## Orchestrator

The agent creates an internal config from `orchestrator/config.example.json`. Recruiters should not
need to edit it.

```bash
# One provisional sample across every segment
python3 orchestrator/source_candidates.py --config config.json --calibrate

# After initial calibration, expand the approved segments and verify the shortlist
python3 orchestrator/source_candidates.py --config config.json --more --target 50

# On later iterations, instantly re-filter/rescore the fully discovered pool
python3 orchestrator/source_candidates.py --config config.json --reuse --target 50
```

Generated runtime files:

- `sourcing_state.json`: machine-owned cache and current-brief snapshot;
- `calibration.csv` / `calibration.html`: provisional segment sample;
- `candidates.csv` / `.xlsx` / `.html`: final deliverables.

By default these files are written beside `config.json`, not into the installed skill. Use
`--output-dir` to override that session directory. Every run prints its elapsed seconds and records
them in `sourcing_state.json`.

The durable brief lives in the config. `sourcing_state.json` keeps lightweight calibration rows
separate from fully graded candidates and preserves high-effort verification facts across
policy-only changes. A materially changed verification question invalidates those verdicts.
