# Exa people search

Turn a criteria brief ("find me people who…") into a **ranked, evidence-cited list of real people**
(with profile URLs) using the Exa Agent API — speakers, experts, advisors, authors, panelists,
guests, leads. It is the general-purpose sibling of `exa-candidate-sourcing` (which stays the
right tool when the brief is a job description and the goal is hiring). It is an agent skill
with a scripted execution engine, and the two parts have distinct jobs:

| | **Skill** (`SKILL.md`) | **Python orchestrator** (the execution engine) |
| --- | --- | --- |
| What it is | A markdown procedure an agent (Kiro, Claude, Devin) follows | `orchestrator/search_people.py` — a self-contained script (stdlib only) |
| Its job | Read the brief, build the search plan, confirm it with the user, write the config, interpret results | Execute the pipeline from `config.json`: discovery (single run by default), corroboration only when flagged, scoring, CSV/XLSX/HTML out |
| Why split it this way | Planning and preference-gathering need a model | Moving people data must not: the script carries every name, URL, and score, so nothing gets mistranscribed or hallucinated between steps |

The agent drives the orchestrator by default; `SKILL.md` also documents the full pipeline as a
**by-hand fallback** for the cases where the script cannot run (no shell or Python, single-run
debugging, a deliberately tiny search).

Both paths implement the **same three ideas** (this is where the quality comes from):
1. a **graded rubric** — each dimension scored `{level, signals}`, not one opaque number;
2. **one deep run by default** — the discovery query itself carries the verification duties
   (confirm the current role, corroborate across 2+ sources, grade strictly, never fabricate,
   drop must-have failures); a multi-segment fan-out across the venues where matching people
   are visible is reserved for genuinely complex briefs (many criteria, disjoint surfaces);
3. a **corroboration pass only when flagged** — a second, high-effort run that
   concentrates deep research on the shortlist (current role, a second source, a confirmation
   status), run only when the user flags quality or the agent notices a concrete defect in the
   output — never by default, never as a proactive offer.

Each person's row carries the graded dimensions, an overall tier and confidence, concerns, a
LinkedIn URL and/or a best other public profile URL, corroboration status, and the source
citations the Agent API reports (`output.grounding`), so claims stay checkable.

Both paths end the same way: write `people.csv`, then render it into a self-contained
`people.html` viewer (`python3 orchestrator/render_viewer.py people.csv people.html`)
for interactive review — sortable/searchable table, filters, expandable details, clickable
profile and source links. The CSV stays the source artifact; the HTML is a view over it.

## Setup

Drop the `exa-people-search/` folder into your agent's skills directory (for Kiro:
`.kiro/skills/exa-people-search/` in a workspace, or `~/.kiro/skills/...` globally), then ask
the agent to "find people who <criteria>". Files:

- `SKILL.md` — the procedure (plan → checkpoint → run the orchestrator; Steps 2-6 document the pipeline and double as the by-hand fallback).
- `orchestrator/search_people.py` + `orchestrator/config.example.json` — the execution engine and its config template.
- `references/exa-agent-api.md` — endpoints, effort/cost, query templates, copy-paste curl loop.
- `references/person-schema.json` — the output schema template.
- `references/scoring-and-calibration.md` — the scoring/calibration/ranking heuristics.
- `references/worked-example-conference-speakers.md` — a complete filled-in plan for a
  conference-speaker search, plus how segments shift for other kinds of briefs.
- `orchestrator/render_viewer.py` + `viewer/people-viewer.template.html` — the CSV → HTML
  viewer renderer (stdlib only).

## Running the orchestrator directly (no agent)

```bash
export EXA_API_KEY=<a key with Agent API access>
python3 orchestrator/search_people.py --config orchestrator/config.example.json --target 15
# corroborate the shortlist afterwards: --verify-only (or --verify to do both in one invocation)
# smoke test before a fan-out: add --limit-segments 1
# need more people? add --more AND raise --target (the CSV only shows the top --target rows)
```

Edit `config.example.json` (objective, locations, exclude_org, dimensions, segments) per search.
Writes `people.csv` + `people.html` (the interactive viewer, rendered automatically) +
`people.xlsx`, plus `people_search_state.json` so `--more` can continue the same session later
(dedupes against everyone already found and keeps corroboration verdicts).

## Note on API keys

The Exa Agent API (`/agent/runs`) needs a key with **Agent API access** — a default search key
returns HTTP 429. Verify with the curl one-liner at the top of `SKILL.md`.
