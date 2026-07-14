# Example plans — four very different asks

Condensed Step-1 plans showing how the same plan format flexes. The full worked example (with
schema and segment-design guidance) is `references/worked-example-ai-infra.md`; the raw asks
these came from are in `examples/`.

## 1. Lead list with a relevance bar — "Japanese companies with AI initiatives a web search API could improve"

The trap here is relevance inflation: every large company has "an AI initiative". The ask even
says "do not stretch the truth" — so the *specific, dated initiative* is a hard criterion with
evidence, and "how much would web search help" is graded, strictly.

```jsonc
{
  "objective": "Japanese companies with a recent, concrete AI initiative that involves or would clearly benefit from a web search API (agents, RAG, research assistants, market/news intelligence)",
  "mode": "ranked", "target_count": 30,
  "hard_criteria": [
    {"key": "japaneseCompany",   "text": "Japanese company (HQ in Japan)."},
    {"key": "concreteInitiative","text": "Has a specific, dated (last ~18 months), publicly documented AI initiative — a named product, deployment, business unit, or funded program; not a vague 'exploring AI' statement."}
  ],
  "soft_criteria": [
    {"key": "searchApiRelevance", "scale": "capability", "text": "The initiative plausibly needs live web data or search: agents, RAG over external content, research/intel tools, news monitoring. Grade STRICTLY — 'strong' only if the initiative itself retrieves or reasons over web-scale external content; do not stretch low-relevance initiatives."},
    {"key": "buildVsBuy",         "scale": "strength",   "text": "Signals they build in-house and buy APIs: engineering hiring, tech blog, existing API vendor usage."},
    {"key": "initiativeScale",    "scale": "strength",   "text": "Executive sponsorship, budget, or company-level strategy attached to the initiative."}
  ],
  "columns": [
    {"key": "initiative_name",    "type": "string",  "desc": "the named initiative/product",            "source": "web"},
    {"key": "initiative_date",    "type": "string",  "desc": "when it was announced/launched (YYYY-MM)", "source": "web"},
    {"key": "why_search_api",     "type": "string",  "desc": "one sentence: the concrete way a web search API fits — no stretching", "source": "web"},
    {"key": "initiative_summary", "type": "string",  "desc": "2-3 sentences on what the initiative is",  "source": "web"},
    {"key": "employee_count",     "type": "number",  "desc": "approximate headcount",                    "source": "fiber_ai"}
  ],
  "data_sources": ["fiber_ai"],
  "verify_columns": ["initiative_name", "initiative_date"],
  "segments": [
    {"label": "jp_tech_press",   "focus": "Japanese tech/business press on enterprise AI initiatives — Nikkei, ITmedia, ASCII, PR Times releases, in Japanese; search in Japanese (AI エージェント, 生成AI 導入, RAG)."},
    {"label": "earnings_ir",     "focus": "Investor-relations decks and earnings calls of listed Japanese companies announcing AI strategies or AI business units."},
    {"label": "ai_products",     "focus": "Japanese companies that shipped AI-powered products with search/agent/RAG features — product pages, launch posts, App/API docs."},
    {"label": "partnerships",    "focus": "Japanese companies in announced partnerships with LLM vendors (OpenAI, Anthropic, Google) or cloud AI programs."},
    {"label": "hiring_signals",  "focus": "Japanese companies hiring for LLM/RAG/search engineers (Wantedly, Green, LinkedIn) tied to a named AI initiative."}
  ]
}
```

Notes: search Japanese-language sources in Japanese (say so in the query). The `why_search_api`
column is the deliverable — a lead without a non-stretched sentence there is a bad lead, and
the strict `searchApiRelevance` grade is what keeps it honest.

**This plan was live-tested end-to-end on 2026-07-08** (3 segments, `fiber_ai`, an existing
list, full verification): 31 unique companies for ~$2 in ~8 minutes, top-10 all
verification-confirmed with named dated initiatives (Stockmark, Uzabase, LY Corporation,
Nikkei, FRONTEO, …); the verify pass corrected two initiative dates and one subsidiary
attribution. Output: `sample-output/japan-ai-leads/`.

## 2. Competitor scan for an investor — "competitors of europace.de"

Seed-company mode. Columns are investor-flavored and people-heavy (exec team → `fiber_ai`);
traffic (→ `similarweb`) is a natural comparison metric, and Similarweb's similar-site data
doubles as a discovery segment. No target-count pressure — the market decides the size.

```jsonc
{
  "objective": "Competitors of Europace (europace.de, German B2B mortgage/financing transaction platform) — for an investor evaluating Europace",
  "mode": "exhaustive", "seed_company": "Europace (europace.de, Hypoport group)",
  "hard_criteria": [
    {"key": "competesWithSeed", "text": "Operates a mortgage/consumer-financing brokerage platform, marketplace, or origination software competing for the same lenders/brokers/borrowers as Europace — in Germany/DACH or credibly expanding into it."},
    {"key": "activeCompany",    "text": "Currently operating (not shut down; if acquired, still operating as a distinct product)."}
  ],
  "soft_criteria": [
    {"key": "overlapWithEuropace", "scale": "capability", "text": "Direct product overlap with Europace's B2B platform model (vs adjacent: comparison portals, retail brokers, core-banking software)."},
    {"key": "traction",            "scale": "strength",   "text": "Transaction volume, lender/broker network size, growth signals."}
  ],
  "columns": [
    {"key": "exec_team",       "type": "string[]", "desc": "CEO and key execs, 'Name — role'", "source": "fiber_ai"},
    {"key": "funding_status",  "type": "string",   "desc": "latest round or ownership (e.g. 'Series B, $40M' / 'subsidiary of X' / 'listed')", "source": "fiber_ai"},
    {"key": "business_model",  "type": "string",   "desc": "how they make money, one line",    "source": "web"},
    {"key": "monthly_visits",  "type": "number",   "desc": "estimated monthly site visits",    "source": "similarweb"},
    {"key": "investor_notes",  "type": "string",   "desc": "2-3 sentences an investor in Europace should know: positioning vs Europace, threats, recent moves", "source": "web"}
  ],
  "data_sources": ["fiber_ai", "similarweb"],
  "verify_columns": ["funding_status", "exec_team"],
  "segments": [
    {"label": "similar_sites",    "focus": "Sites similar to europace.de per Similarweb similar-site data and 'Europace Alternativen' / competitor comparison pages."},
    {"label": "de_fintech_press", "focus": "German fintech press (Finanz-Szene, Finance Forward, deutsche-startups.de) on mortgage/baufinanzierung platforms and Hypoport competitors."},
    {"label": "mortgage_saas",    "focus": "European mortgage-tech and loan-origination software vendors selling to banks and brokers (DACH first, then EU players entering DACH)."},
    {"label": "broker_pools",     "focus": "German broker pools and B2B financing marketplaces (e.g. the ecosystems around Interhyp, Qualitypool, Fondsfinanz) that compete for Europace's broker base."}
  ]
}
```

**Live-tested 2026-07-08** (`sample-output/europace-competitors/`): 32 raw → 25 unique → 22
confirmed competitors, led by exactly the names a DACH mortgage analyst would expect
(Interhyp/Prohyp, BAUFINEX, Finmas, Starpool). The verify pass killed GENOPACE and DEX prime
as Hypoport-group ventures (same parent as Europace) — but kept BAUFINEX and Finmas, which are
*also* Hypoport JVs: group-affiliation judgment is inconsistent unless you make it explicit.
Lesson: when the seed company belongs to a group, put the group exclusion in the hard
criterion itself ("not owned by or a joint venture of Hypoport SE"). Exec teams filled 21/22
(Fiber), traffic 16/22 (Similarweb), investor notes 22/22. Search German-language sources in
German (say so in the segment focus).

## 3. Event watchlist — "every Western company that opened a KSA/UAE regional HQ in the last month"

Exhaustive + tight time window. Resolve "last month" to absolute dates **now** and put them in
every query. Ranking barely matters; completeness and date verification do. No Connect
providers — nothing in the columns needs one; this is pure news work.

```jsonc
{
  "objective": "Western companies (HQ in North America/Europe/Oceania) that announced or opened a regional headquarters in Saudi Arabia or the UAE between 2026-06-08 and 2026-07-08",
  "mode": "exhaustive",
  "time_window": "between 2026-06-08 and 2026-07-08",
  "hard_criteria": [
    {"key": "westernCompany", "text": "Global HQ in North America, Europe, or Oceania."},
    {"key": "rhqEvent",       "text": "Publicly announced opening (or receiving a license for) a regional headquarters in Saudi Arabia or the UAE, with the announcement dated between 2026-06-08 and 2026-07-08 — not merely an office, branch, or expansion talk."}
  ],
  "soft_criteria": [
    {"key": "eventSpecificity", "scale": "capability", "text": "The announcement names a location, license (e.g. Saudi RHQ program), or headcount — vs a vague intent statement."}
  ],
  "columns": [
    {"key": "event_date",    "type": "string", "desc": "announcement date, YYYY-MM-DD",              "source": "web"},
    {"key": "hq_location",   "type": "string", "desc": "Riyadh / Dubai / Abu Dhabi / ...",            "source": "web"},
    {"key": "which_program", "type": "string", "desc": "e.g. Saudi RHQ program license, DIFC, ADGM",  "source": "web"},
    {"key": "home_country",  "type": "string", "desc": "company's global HQ country",                 "source": "web"},
    {"key": "announcement_url", "type": "string", "desc": "URL of the dated announcement",            "source": "web"}
  ],
  "data_sources": [],
  "verify_columns": ["event_date", "hq_location"],
  "segments": [
    {"label": "gulf_biz_press",  "focus": "Gulf business press in the window — Arabian Business, Gulf News, Zawya, Arab News business, The National — RHQ/regional HQ announcements."},
    {"label": "gov_programs",    "focus": "Saudi RHQ program / MISA license announcements and UAE free-zone (DIFC, ADGM, DMCC) new-member news in the window."},
    {"label": "wire_services",   "focus": "PR Newswire, Business Wire, GlobeNewswire releases in the window mentioning a Saudi or UAE regional headquarters."},
    {"label": "western_press",   "focus": "Western business press (Reuters, Bloomberg, FT) on companies establishing Gulf regional HQs in the window."},
    {"label": "linkedin_moves",  "focus": "LinkedIn company announcements and exec posts in the window about opening a KSA/UAE regional HQ."}
  ]
}
```

The verification pass earns its cost here: it re-checks the **date** and that the event is an
RHQ (not a sales office). Present the output as a watchlist sorted by `event_date`, and tell
the user a monthly rerun with the previous output in `input.exclusion` gives the deltas.

**Live-tested 2026-07-08** (`sample-output/ksa-uae-rhq/`): 28 raw → 15 unique → verification
**failed 7 of 15** on the dated-RHQ criterion (office openings, out-of-window events, expansion
talk) — the single strongest demonstration of the verify pass in these tests. All 8 survivors
were confirmed, in-window, each with a dated announcement URL; corrections even flagged an
announcement-vs-republication off-by-one date and noted ownership context (Valvoline Global is
Aramco-owned).

## 4. Event watchlist with enrichment — "Western companies KSA/UAE SWFs invested in / signed MOUs with, last month"

Same skeleton as #3 (exhaustive, absolute window, news segments around PIF, Mubadala, ADIA,
ADQ, QIA-adjacent wires) plus enrichment columns: `cooperation_type`
(investment/MOU/JV/other — an enum-ish string), `counterparty_fund`, `deal_size_usd_m`
(number), `exec_team` (string[] → `fiber_ai`), `total_revenue_usd_m` (number → `fiber_ai`;
mark `unknown` freely — private-company revenue is usually unverifiable, and a guessed number
is worse than a blank), `event_date`, `announcement_url`. Verify `cooperation_type` and
`event_date` — press releases inflate MOUs into "investments" constantly, so the verify pass
should downgrade any "investment" without a dated primary source.

**Live-tested 2026-07-08** (`sample-output/swf-cooperation/`): a sparse-but-honest 6 rows, all
in-window and real (Repsol–Masdar, Intertek–EQT/ADIA, Mubadala–Pierre & Vacances, …).
Corrections reclassified deal structures precisely (an "investment in Equitix" was actually a
$200M purchase of Equitix's stake in an asset; a JV predated the window but its in-window
facility announcement qualified), and one row's claimed PIF MOU had **no public evidence** —
verification marked its criterion `unknown` and it sank to the bottom with the flag visible.
`total_revenue_usd_m` filled 0/6: honest nulls, but Fiber didn't return even public-company
revenue — treat revenue columns as best-effort. For true exhaustiveness run `--rounds 3`; one
round under-samples a news window.
