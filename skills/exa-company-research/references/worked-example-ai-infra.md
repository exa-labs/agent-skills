# Worked example — "US Series A/B AI-infrastructure startups"

A complete Step-1 research plan for the ask:

> "Build me a list of ~25 US-based Series A or B startups building developer-facing AI
> infrastructure — APIs, SDKs, or platforms other teams use to build AI products. For each:
> funding stage, total raised, headcount, monthly site traffic, whether they're open source,
> and pricing model. I already have a list in `existing.csv` (a `domain` column) — skip those."

Use it as a model for how to turn a freeform ask into the plan. Note the split: things that make
a company *wrong* (geography, stage, category) are **hard criteria**; things that make it *more
interesting* (traction, customers, momentum) are **soft criteria**; things the user wants to
*read* (funding, traffic, headcount) are **columns**. The columns drive the Exa Connect choice:
funding/headcount → `fiber_ai`, traffic → `similarweb`. A list with no such columns would attach
nothing.

```json
{
  "objective": "US-based Series A or B startups building developer-facing AI infrastructure (APIs, SDKs, platforms used to build AI products)",
  "target_count": 25,

  "hard_criteria": [
    {"key": "hqInUs",          "text": "Headquartered in the United States."},
    {"key": "stageSeriesAOrB", "text": "Most recent priced round is a Series A or Series B (not pre-seed/seed, not Series C+, not public, not acquired)."},
    {"key": "devFacingAiInfra","text": "Primary product is developer-facing AI infrastructure: an API, SDK, or platform other teams use to build AI products (inference, vector search, orchestration, evals, agents, data/RAG tooling) — not an end-user AI app."}
  ],

  "soft_criteria": [
    {"key": "developerTraction", "scale": "strength", "text": "Visible developer adoption: GitHub stars, package downloads, active community, developer-forum presence."},
    {"key": "notableCustomers",  "scale": "strength", "text": "Named customers or logos, case studies, marketplace listings."},
    {"key": "recentMomentum",    "scale": "strength", "text": "Signals from the last ~12 months: funding, launches, hiring surges, major partnerships."}
  ],

  "columns": [
    {"key": "funding_stage",      "type": "string|null",  "desc": "latest round, e.g. 'Series A'",              "source": "fiber_ai"},
    {"key": "total_raised_usd_m", "type": "number|null",  "desc": "total raised, millions USD",                 "source": "fiber_ai"},
    {"key": "employee_count",     "type": "number|null",  "desc": "approximate headcount",                      "source": "fiber_ai"},
    {"key": "monthly_visits",     "type": "number|null",  "desc": "estimated monthly website visits",           "source": "similarweb"},
    {"key": "open_source",        "type": "boolean|null", "desc": "core product is open source",                "source": "web"},
    {"key": "pricing_model",      "type": "string|null",  "desc": "'usage-based API', 'seat-based SaaS', 'open core', ...", "source": "web"}
  ],
  "data_sources": ["fiber_ai", "similarweb"],

  "existing_list": {"file": "existing.csv", "match_on": ["domain"]},
  "geography": {"hard": "US HQ", "preferred_regions": []},

  "segments": [
    {"label": "funding_news",     "focus": "Series A/B funding announcements for AI-infrastructure startups in the last 18 months — TechCrunch, VentureBeat, Axios Pro Rata, Fortune Term Sheet, company press releases."},
    {"label": "vc_portfolios",    "focus": "Portfolio pages of investors known for AI infrastructure — a16z (infra practice), Sequoia, Index, Amplify Partners, Basis Set, Conviction, Felicis, Innovation Endeavors — filtered to dev-facing AI infra at Series A/B."},
    {"label": "yc_accelerators",  "focus": "Y Combinator and Techstars alumni (last ~3 years) building AI developer tools/infra that have since raised a Series A or B."},
    {"label": "oss_github",       "focus": "Companies behind popular open-source AI-infrastructure projects on GitHub (vector DBs, LLM orchestration, eval frameworks, inference servers, agent frameworks) that have raised Series A/B."},
    {"label": "launch_communities","focus": "AI developer tools launched on Product Hunt or Hacker News (Show HN) in the last 2 years whose companies have since raised Series A/B."},
    {"label": "category_directories", "focus": "Vendor directories and analyst/category lists for LLMops, vector databases, AI inference platforms, AI evals, and agent platforms (G2, curated 'AI infra landscape' posts) — extract the Series A/B US companies."}
  ]
}
```

## Segment design notes (this is the part worth copying)

Segments are **discovery angles** — different places where qualifying companies *surface* — not
sub-categories of the criteria. Angle-based segments overlap less and find the long tail that a
single "search for AI infra startups" query misses. Good angle families to draw from:

- **money**: funding announcements, VC portfolio pages, accelerator batches
- **community**: Product Hunt, Show HN, Reddit/Discord ecosystems
- **code**: GitHub orgs behind popular OSS in the category
- **catalogs**: G2/Capterra categories, awesome-lists, marketplace/integration directories
- **events**: conference exhibitor & sponsor lists (e.g. AI Engineer Summit, KubeCon)
- **adjacency**: "alternatives to X" pages, competitors' comparison pages, partner pages of
  adjacent products; Similarweb similar-site discovery when it's attached anyway
- **hiring**: companies posting for roles that only exist if the criteria are true

Pick 4–8 angles the target category actually surfaces through. A B2B SaaS list leans on catalogs
and events; an e-commerce brand list leans on marketplaces and social; a biotech list leans on
trial registries and conference abstracts.

## Notes from the live test run (2026-07-08, via the orchestrator)

The end-to-end test ran **plan 1 of `example-plans.md`** (Japanese companies with AI
initiatives relevant to a web search API — 3 segments, `fiber_ai` attached, an existing list,
full verification); the pipeline is identical to this plan. Cross-cutting numbers:

- Discovery: 3 segments at `effort: medium` returned 12/11/12 companies in 1.5–4 min each;
  $0.52 total including 27 Fiber.ai calls. 35 raw → 31 unique after domain/name dedup; the
  `input.exclusion` list held (none of the excluded companies reappeared).
- Results were real and on-target: Stockmark, Uzabase (Speeda AI Agent), LY Corporation,
  Nikkei, FRONTEO, JPX — each with a named, dated initiative and a non-stretched
  `why_search_api` sentence. `initiative_date` filled 10/10, `employee_count` (Fiber) 6/10,
  grounding citations 8/10.
- Verification (top 20, `effort: high`, ~$0.50/batch of 8) confirmed all 20 existed — but still
  earned its cost via **corrections**: two wrong initiative dates fixed to the day, one
  initiative re-attributed to the right group subsidiary, one canonical-website correction.
  On a criteria-drift-prone plan (like this file's Series A/B stage criterion) expect it to
  also fail rows outright.
- Grading compresses at the top on target-rich queries (four scores of 100, two 99s) even with
  the strict-grading language — with only 3 soft criteria there are few points of
  discrimination. If separating the top matters, add 1–2 more discriminating soft criteria
  rather than trusting the tier alone.
- Whole run: ~8 minutes, ~$2.
