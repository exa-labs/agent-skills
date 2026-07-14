# Exa company research

Turn a freeform ask ("find me companies that …") into a **ranked, verified list of real
companies** — with the exact data columns you care about — using the Exa Agent API. Two ways to
run it:

| | **Skill** (recommended start) | **Python orchestrator** |
| --- | --- | --- |
| What it is | `SKILL.md` — a markdown procedure an agent (Claude, Kiro, Devin) follows | `orchestrator/research_companies.py` — a self-contained script |
| Best for | One ask at a time, tweaking per ask, transparency | Deterministic bulk runs, repeatable watchlists, weaker coding models that shouldn't assemble the calls themselves |
| You need | An agent + `EXA_API_KEY` with Agent API access | Python 3 + `EXA_API_KEY` |

Both implement the same pipeline; the agent's real job either way is **filling in the research
plan** (Step 1 of `SKILL.md` / the config JSON) from the user's ask.

Four ideas do the work (this is where the quality comes from):

1. **Hard criteria filter, soft criteria score** — requirements that make a company *wrong*
   (stage, geography, category) are verified and enforced; nice-to-haves are graded
   `{level, signals}` so the ranking stays explainable.
2. **Segment fan-out** — several searches across the *discovery angles* where qualifying
   companies actually surface (funding news, VC portfolios, GitHub, directories, launch
   communities, events) instead of one broad query.
3. A **verification pass** — a second, high-effort run that fact-checks existence, website
   ownership, and every hard criterion before ranking. Criteria drift (the "Series A" company
   that quietly raised a C) is the #1 failure mode of company lists.
4. **Dedupe** — by normalized domain, against both the run's own segments and any existing list
   you already have, so the output is all-new rows.

The columns are **query-dependent**: a sales list wants funding and headcount, a competitor scan
wants pricing and traffic. The plan built in Step 1 defines them, and the output schema, the
[Exa Connect](https://exa.ai/docs) data partners (Similarweb, Fiber.ai, Baselayer, …), the CSV,
and the HTML viewer are all generated from that plan. Providers are attached **only when a
requested column needs them** (`references/exa-connect-providers.md`).

Every run ends with `companies.csv`, then a self-contained interactive viewer:

```bash
python3 orchestrator/render_viewer.py companies.csv companies.html \
  --title "US Series A/B AI infra startups" --table-cols "funding_stage,total_raised_usd_m,monthly_visits"
```

sortable/searchable table, segment & verification filters, expandable per-company details,
clickable website and source-citation links. The CSV stays the source artifact; the HTML is a
view over it.

## Files

- `SKILL.md` — the procedure (6 steps: plan → schema → discovery → consolidate → verify → rank).
- `references/exa-agent-api.md` — endpoints, effort/cost, query templates, copy-paste curl loop,
  verification query + schema.
- `references/company-schema.json` — the output-schema template (filled in for the worked example).
- `references/scoring-and-verification.md` — dedup keys, scoring/calibration/ranking heuristics,
  CSV conventions.
- `references/exa-connect-providers.md` — which data partner to attach for which column, and the
  only-when-relevant rule.
- `references/worked-example-ai-infra.md` — a complete plan for "US Series A/B AI-infrastructure
  startups", plus segment-design guidance.
- `references/example-plans.md` — condensed plans for four very different asks: a lead list with
  a strict relevance bar, a competitor scan for an investor, and two time-windowed event
  watchlists.
- `orchestrator/research_companies.py` + `config.example.json` — the self-contained bulk
  orchestrator (stdlib only; openpyxl optional for .xlsx).
- `orchestrator/render_viewer.py` + `viewer/company-viewer.template.html` — the CSV → HTML viewer
  renderer (stdlib only).
- `examples/` — drop your own asks here as `.md` files; they become worked examples and test queries.
- `sample-output/` — four real end-to-end runs (2026-07-08), one per ask in `examples/`; each
  folder has the `companies.csv` artifact, the `companies.html` viewer, and the `config.json`
  plan that produced them:
  - `japan-ai-leads/` — lead list with a strict relevance bar (Fiber.ai; top 10 confirmed).
  - `europace-competitors/` — exhaustive competitor scan (Fiber.ai + Similarweb; 22 confirmed
    competitors; verification correctly killed same-group Hypoport JVs as non-competitors).
  - `ksa-uae-rhq/` — one-month event watchlist; verification failed 7 of 15 discovered rows on
    the dated-RHQ criterion, all 8 survivors in-window with announcement URLs.
  - `swf-cooperation/` — one-month SWF watchlist; corrections reclassified deal types and
    flagged one row whose claimed MOU had no public evidence.

## Python orchestrator (bulk)

```bash
export EXA_API_KEY=<a key with Agent API access>
python3 orchestrator/research_companies.py --config orchestrator/config.example.json
# smoke test: add --limit-segments 1 --no-verify
# exhaustive "find EVERY company" asks: add --rounds 3 (keeps digging per segment until dry)
# need more after a run? add --more (continues each segment's previous run, keeps verdicts)
```

Edit `config.example.json` per ask (objective, hard/soft criteria, columns + Exa Connect
providers, segments, existing list, optional time_window/seed_company). Writes `companies.csv`
+ `companies.html` (the interactive viewer, rendered automatically; `table_cols` in the config
picks the main-table columns) + `companies.xlsx` if openpyxl is installed, plus
`research_state.json` so `--more` can continue the same session later (dedupes against
everything already found and keeps verification verdicts).

## Setup

Drop the `exa-company-research/` folder into your agent's skills directory (e.g.
`~/.claude/skills/exa-company-research/`), then ask the agent to "build me a list of companies
that <criteria>". You need an `EXA_API_KEY` with **Agent API access** — a default search key
returns HTTP 429 on `POST /agent/runs`; verify with the curl one-liner at the top of `SKILL.md`.
