# Exa candidate sourcing

Turn a job description into a **ranked, verified list of real candidates** (with LinkedIn URLs)
using the Exa Agent API. It is an agent skill with a scripted execution engine, and the two parts
have distinct jobs:

| | **Skill** (`SKILL.md`) | **Python orchestrator** (the execution engine) |
| --- | --- | --- |
| What it is | A markdown procedure an agent (Kiro, Claude, Devin) follows | `orchestrator/source_candidates.py` — a self-contained script (stdlib only) |
| Its job | Read the JD, build the search plan, confirm it with the recruiter, write the config, interpret results | Execute the pipeline from `config.json`: discovery fan-out, verification, scoring, CSV/XLSX/HTML out |
| Why split it this way | Planning and preference-gathering need a model | Moving candidate data must not: the script carries every name, URL, and score, so nothing gets mistranscribed or hallucinated between steps |

The agent drives the orchestrator by default; `SKILL.md` also documents the full pipeline as a
**by-hand fallback** for the cases where the script cannot run (no shell or Python, single-run
debugging, a deliberately tiny search).

Both paths implement the **same three ideas** (this is where the quality comes from):
1. a **graded rubric** — each dimension scored `{level, signals}`, not one opaque number;
2. **segment fan-out** — several searches across the talent pools where equivalent people actually
   work, instead of one broad query;
3. a **verification pass** — a second, high-effort run that fact-checks the shortlist before ranking.

Each candidate gets two independent scores: a **match score** (fit to the role; drives the
ranking) and a **likely-to-move score** (propensity to actually switch jobs, from dated tenure
signals; display-only, and always exported with the tenure, job-change cadence, and
seniority-vs-role inputs that justify it). Each row also carries the source citations the Agent API reports for it
(`output.grounding`), so claims stay checkable.

Both paths end the same way: write `candidates.csv`, then render it into a self-contained
`candidates.html` viewer (`python3 orchestrator/render_viewer.py candidates.csv candidates.html`)
for interactive review — sortable/searchable table, filters, expandable details, clickable
LinkedIn and source links. The CSV stays the source artifact; the HTML is a view over it.

## Setup

Drop the `exa-candidate-sourcing/` folder into your agent's skills directory (for Kiro:
`.kiro/skills/exa-candidate-sourcing/` in a workspace, or `~/.kiro/skills/...` globally), then ask
the agent to "source candidates for <JD url or text>". Files:

- `SKILL.md` — the procedure (plan → checkpoint → run the orchestrator; Steps 2-6 document the pipeline and double as the by-hand fallback).
- `orchestrator/source_candidates.py` + `orchestrator/config.example.json` — the execution engine and its config template.
- `references/exa-agent-api.md` — endpoints, effort/cost, query templates, copy-paste curl loop.
- `references/candidate-schema.json` — the output schema template.
- `references/scoring-and-calibration.md` — the scoring/calibration/ranking heuristics.
- `references/worked-example-aws-sa-isv.md` — a complete filled-in plan for the AWS SA ISV role.
- `orchestrator/render_viewer.py` + `viewer/candidate-viewer.template.html` — the CSV → HTML
  viewer renderer (stdlib only).

## Running the orchestrator directly (no agent)

```bash
export EXA_API_KEY=<a key with Agent API access>
python3 orchestrator/source_candidates.py --config orchestrator/config.example.json --target 50
# smoke test: add --limit-segments 1 --no-verify
# need more people after a run? add --more (continues each segment's previous run)
```

Edit `config.example.json` (role, locations, exclude_employer, dimensions, segments) per role.
Writes `candidates.csv` + `candidates.html` (the interactive viewer, rendered automatically) +
`candidates.xlsx`, plus `sourcing_state.json` so `--more` can continue the same session later
(dedupes against everyone already found and keeps verification verdicts).

## Sample output

`sample-output/candidates.csv` — a real end-to-end run of this pipeline on the
[AWS "Solutions Architect, ISV"](https://amazon.jobs/en/jobs/10425076/solutions-architect-isv) JD
(4 segments → 48 found → verified → top 25). Every candidate is verification-confirmed, a strong
role match, graded on all six rubric dimensions, and has a LinkedIn URL.

## Note on API keys

The Exa Agent API (`/agent/runs`) needs a key with **Agent API access** — a default search key
returns HTTP 429. Verify with the curl one-liner at the top of `SKILL.md`.
