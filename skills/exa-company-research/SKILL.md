---
name: exa-company-research
description: Build a ranked, verified list of companies matching arbitrary criteria using the Exa Agent API. Use when asked to build a company list, find companies that match some criteria, source prospects / competitors / vendors / investment targets, or extend and dedupe an existing company list with custom data columns.
license: MIT
compatibility: Requires network access and an Exa API key with Agent API access (EXA_API_KEY env var, or ~/.config/exa/key via the bundled scripts/set-exa-key.sh). Uses curl (any HTTP client works, or the Exa MCP server when no shell is available); Python 3 renders the optional HTML viewer.
metadata:
  author: Exa
  version: "0.1"
---

# Company research from a freeform ask

Turn a freeform ask ("find me companies that …") into a **ranked, verified list of real
companies** with the exact data columns the user cares about, using the
[Exa Agent API](https://exa.ai/docs/reference/agent-api-guide). You — the agent running this
skill — do the orchestration: pin down the ask, design the search, fire several Exa Agent runs,
then consolidate, verify, and rank. You can run every step **by hand** (the default, and what
this document walks through) or drive the bundled **`orchestrator/research_companies.py`**, which
executes the same pipeline end to end from a `config.json` — pick whichever fits the situation.
**Whichever path you take, the Step 1 plan-and-preferences checkpoint is mandatory: build the
plan, confirm it, and gather the user's preferences before you run any search or write a config
for the orchestrator.**

Unlike a fixed pipeline, the **columns are query-dependent**: a sales list wants funding and
headcount, a competitor scan wants pricing and traffic, a vendor list wants compliance facts.
The plan you build in Step 1 defines them, and everything downstream (schema, Exa Connect
providers, CSV, viewer) is generated from that plan.

The quality comes from four choices, not from any one clever query:

1. **Hard criteria filter, soft criteria score** — requirements that make a company *wrong*
   (stage, geography, category) are verified and enforced; nice-to-haves are graded
   `{level, signals}` so the ranking is triage-able, not one opaque number.
2. **Several segment searches** instead of one — fan out across the *discovery angles* where
   qualifying companies actually surface (funding news, VC portfolios, GitHub, directories,
   communities, events). One broad query under-samples.
3. A **verification pass** — a second, high-effort run that fact-checks existence, website
   ownership, and **every hard criterion** before you rank. Criteria drift (the "Series A"
   company that quietly raised a C) is the #1 failure mode of company lists.
4. **Dedupe** — against itself (by normalized domain) and against the user's existing list, so
   the output is all-new rows they can act on.

**Output:** `companies.csv` (+ a compact markdown table in chat) — ranked, with the user's
columns, per-criterion grades, verification status, and source citations (`output.grounding`)
behind each row. Then render `companies.html` from the CSV with the bundled viewer (Step 6) so
the user can review the list interactively in a browser instead of only a spreadsheet.

## Prerequisites

- An Exa API key with **Agent API access** (not all keys have it). The skill resolves it in this
  order: **`EXA_API_KEY` in the environment first, then the credentials file `~/.config/exa/key`**
  (override the path with `EXA_KEY_FILE`). Quick check — this must return HTTP 200, not 429/401:
  ```bash
  KEY="${EXA_API_KEY:-$(cat ~/.config/exa/key 2>/dev/null)}"
  curl -s -o /dev/null -w "%{http_code}\n" -X POST https://api.exa.ai/agent/runs \
    -H "x-api-key: $KEY" -H "Content-Type: application/json" \
    -d '{"query":"Say hi in one word","effort":"low"}'
  ```
- **No key set (common on a first run, especially for non-technical users)?** Do **not** walk the
  user through editing a shell profile by hand, and do **not** accept a key pasted into the chat.
  Instead point them at the bundled setup script, which is the whole flow: they run one command in
  their own terminal, paste the key once at a hidden prompt, and it writes `~/.config/exa/key` and
  verifies it live. Give them exactly this (substitute the skill's base directory), then wait for
  them to say it's done and re-run the HTTP check above:
  ```
  sh <skill-base-dir>/scripts/set-exa-key.sh      # macOS/Linux
  powershell -ExecutionPolicy Bypass -File <skill-base-dir>\scripts\set-exa-key.ps1   # Windows
  ```
  Tell them: create/copy a key at dashboard.exa.ai/api-keys first; nothing appears on screen while
  they paste (that's intentional); no terminal restart is needed. The script handles quoting,
  strips stray whitespace, catches a double-paste, and is safe to re-run. It never routes the key
  through you.
- **Handling the key safely (hard rule).** The key is a secret. Only ever inspect it via a boolean
  presence/length check (`printf '%s' "${EXA_API_KEY:+set}"`, `${#EXA_API_KEY}`) or an HTTP status
  code — **never `cat`/`grep`/`sed`/`echo` a file or variable that may contain the key and print
  the result.** Regex "redaction" of an unknown-format key file is unreliable and has leaked keys;
  do not attempt it. If a key is ever exposed (pasted in chat, printed, committed), tell the user to
  rotate it at dashboard.exa.ai/api-keys.
- Endpoints: `POST /agent/runs` to start a run, `GET /agent/runs/{id}` to poll, `POST /agent/runs/{id}/cancel` to stop one.
  Full reference: `references/exa-agent-api.md`.
- **No shell / sandboxed (no curl)?** Don't skip the run or ask the user to curl for you. Use the
  **Exa MCP server**, whose tools map to the endpoints above: `agent_create_run` (same query,
  schema, `effort`, `dataSources`), `agent_wait_for_run` / `agent_get_run_output` to poll/read,
  `agent_cancel_run` to stop, and `web_fetch_exa` to read any URL the user gives you. Everything
  else in the skill is transport-agnostic.

## Step 1 — Pin down the ask and build a research plan

Read the ask (and any attachments — an existing list, a landscape doc, a URL to fetch). Then
write a short **research plan** with these fields:

- **objective** — one line: what list is being built and what it's for.
- **target_count** — how many companies the user wants back (default ~25 if unstated).
- **hard_criteria** — 2–5 requirements that make a company *wrong* if unmet (geography, stage,
  size band, category, business model, independence). Each `{key, text}`. These are filtered
  and verified, never scored.
- **soft_criteria** — 2–6 nice-to-haves graded `{level, signals}`. Each `{key, scale, text}`;
  scale `capability` (`strong/partial/none/unknown`) for "do they have X", `strength`
  (`none/weak/medium/strong/unknown`) for "how much of a plus is X".
- **columns** — the data fields the user wants to *read* per company, each
  `{key, type, desc, source}`. This is the freeform part: derive them from what the user said
  they care about, and propose 2–4 obviously-useful ones they didn't mention. `source` is
  `web` or an Exa Connect provider id. Don't reuse a key the pipeline already owns
  (`name, website, hq, description, rank, company, score, segment, sources, concerns,
  confidence, overall_tier, verify_*, corrections, overallFit`) — a colliding key clobbers
  the schema or produces duplicate CSV headers the viewer misreads.
- **data_sources** — the Exa Connect providers to attach, derived from the columns/criteria
  via `references/exa-connect-providers.md`. **Attach only providers a column actually
  needs** — a plain list with no firmographic/traffic/compliance columns attaches none.
- **existing_list** — if the user has one: the file/paste, and which fields to match on
  (domain if available, else name). Parse it now and report the count back to them.
- **geography** — hard requirement, preferred-but-optional regions, or absent. Preferred
  regions earn a small score bonus; hard ones go in `hard_criteria`.
- **time_window** *(optional)* — for event-based asks ("opened an HQ in the last month",
  "announced an initiative this quarter"): resolve relative phrases to **absolute dates** now
  ("between 2026-06-08 and 2026-07-08") and repeat them in every query, or the runs will
  interpret "recent" loosely.
- **mode** — `ranked` (default: a top-N shortlist) or `exhaustive` ("find EVERY company
  that…"): exhaustive changes Step 3 (continuation rounds per segment until they run dry) and
  Step 6 (completeness is the deliverable — don't trim to a target count, and say plainly that
  no web sweep proves exhaustiveness).
- **seed_company** *(optional)* — competitor/landscape scans around a named company: segments
  aim at its alternatives pages, category peers, and (if Similarweb is attached) similar-site
  data; never include the seed itself.
- **segments** — 4–8 **non-overlapping discovery angles**, each `{label, focus}`: different
  places qualifying companies *surface* (funding news, VC portfolios, accelerator batches,
  GitHub, launch communities, category directories, conference exhibitors, "alternatives to X"
  pages, hiring signals). Angle families and a full example plan:
  `references/worked-example-ai-infra.md`; condensed plans for four very different asks
  (lead list, competitor scan, event watchlists): `references/example-plans.md`.

### Checkpoint — confirm the plan AND elicit preferences (mandatory, before any search)

Applies **whether you run by hand or via the orchestrator**. A one-line ask says what the list
*is*, not everything the user *wants* — gather the rest before spending on a search.

**1. Show the plan you built** — objective, target count, hard vs. soft criteria, the proposed
columns, the providers you'll attach, the existing-list dedupe key, and the segment list — in a
form they can react to.

**2. Then explicitly ask what you may have missed.** Don't just ask "look right?" — surface the
implicit preferences a short ask omits. Pick the ones that fit this ask (don't interrogate) and
invite anything else:

- **The columns** — the freeform heart of this skill. Confirm the fields they want to *read* per
  company, and float the 2–4 obviously-useful ones you added. A wrong column set is the most
  expensive thing to discover after the fan-out.
- **Dealbreakers / must-not-haves** — companies or types to exclude beyond the stated criteria
  (no public companies, no agencies, no subsidiaries, specific competitors to leave out).
- **An existing list to dedupe against** — companies already in their CRM/pipeline/prior list to
  exclude. Running by hand, pass them as `input.exclusion` on the discovery runs. Via the
  orchestrator, point `existing_list.file` at a CSV or one-per-line text file (or list a few
  inline in `exclude_companies`, or pass `--exclude-file`); all of them seed `input.exclusion`
  and are filtered from the results.
- **Geography strictness** — hard requirement vs. nice-to-have; which regions, and is a global
  list acceptable?
- **Stage / size / recency** — funding stage or headcount bands, and whether there's a time
  window (resolve relative phrases like "this quarter" to absolute dates now).
- **Ranked vs. exhaustive** — a top-N shortlist, or *every* company that qualifies (the latter
  changes discovery to continuation rounds and drops the target-count trim).
- **Non-obvious context** — why they're building the list, a couple of exemplar companies that
  are clearly in or out, anything implicit. End with an open "anything I'm missing?"

**3. Note the rough cost** (see Tips — a couple dollars for a full fan-out + verification).

**Wait for their answer. Fold every preference into the plan** — adjust `columns`, add/loosen
`hard_criteria`, set `geography`/`time_window`/`mode`, extend the exclusion list — **before** you
run a single discovery search or write the orchestrator's `config.json`. Only then continue to
Step 2.

## Step 2 — Build the output schema

Each discovery run must return JSON matching a strict schema so results are comparable across
segments. Build it from your plan: identity fields (`name`, `website`, `hq`, `description`),
one `{met, evidence}` object per **hard criterion**, one `{level, signals}` object per **soft
criterion**, one typed nullable field per **column** (with a description that names its Exa
Connect source when one is attached — that's how the agent routes the field to the right tool),
and an `overallFit { tier, confidence, signalsUsed, concerns }`.

Use `references/company-schema.json` as the template — swap in your keys, and keep
`additionalProperties: false` with everything `required` so the agent can't omit fields. Bound
the list with `maxItems` (≈15 per call) to keep cost predictable.

## Step 3 — Discovery: one Exa Agent run per segment

For each segment, start an Exa Agent run with `effort: "medium"`, your output schema, and the
plan's `dataSources` (if any). The query should:

- State the objective, then the HARD REQUIREMENTS ("every company must satisfy ALL of these")
  and the NICE-TO-HAVE signals ("grade, don't filter") separately.
- Give the segment's `focus` as **where to look** — and say "a place to look, NOT ground truth;
  verify every company independently against the hard requirements."
- Name the attached Exa Connect providers and which fields they feed.
- Require: identity fields; `{met, evidence}` per hard criterion (and *do not include* a company
  whose hard criterion is `no`); graded `{level, signals}` per soft criterion; every column;
  an `overallFit`.
- **Calibrate the grading**: grade strictly and comparatively (`strong` only with direct public
  evidence; reserve tier `exceptional` for at most 1–2 near-perfect fits per batch;
  `confidence: high` only with multi-source corroboration). Without this, agents grade nearly
  everything at the maximum and the ranking can't discriminate.
- Say: search beyond the homepage (funding announcements, press, product docs and pricing
  pages, GitHub, case studies, LinkedIn company pages, job posts); corroborate across ≥2 sources.
- Say: use `null` / empty arrays / `"unknown"` when a fact isn't publicly supported; **NEVER
  fabricate** a company name, website, funding amount, or number. Exclude duplicates, absorbed
  subsidiaries, and dead/acquired companies (unless the ask includes them).

The exact query template and a copy-paste curl loop are in `references/exa-agent-api.md`.

**Create runs one at a time** (a parallel create burst can trip the account QPS limit and
silently drop a segment; retry once on a 429/5xx create), then poll the started runs
concurrently: that still runs 2–3 segments at once and saves wall-clock time. Pass the user's
**existing list** plus already-seen companies as `input.exclusion`
(`[{"company": "<name>", "website": "<domain>"}, ...]`, capped ~100 entries — prioritize
well-known names; local dedupe catches the rest). **Poll** `GET /agent/runs/{id}` every ~8s
until `status` is `completed` (read rows from `output.structured.companies`); if it
`failed`/`canceled` or the poll gets a non-429 4xx, skip it; if it runs longer than ~20 min,
cancel it and move on.

Completed runs also return **`output.grounding`**: source citations keyed to output fields
(e.g. `structured.companies[3]` with `[{url, title}]`). Attribute each entry to its company by
index and keep the citation URLs, so every row can carry the sources behind its claims.
Attribution rules are in `references/exa-agent-api.md`; coverage is partial, so treat "no
grounding entry" as normal, not an error.

**Need more companies after a run?** Start a new run per segment with `previousRunId` set to
that segment's last run id and a short "find N more matching the same brief" query, plus
everything already seen in `input.exclusion`; the agent keeps its research context instead of
starting cold. **In `exhaustive` mode this isn't optional**: keep running continuation rounds
per segment until a round adds almost nothing new (~2 rounds of <3 new companies), and report
to the user which segments went dry versus which were still producing.

## Step 4 — Consolidate

- **Dedup** across segments by normalized domain, falling back to normalized name (exact rules
  in `references/scoring-and-verification.md` §0). Merge colliding rows: keep the higher-scored
  copy, prefer non-null columns, union evidence and citations.
- **Dedup against the user's existing list** with the same keys. Report how many discovered
  rows were dropped as already-known — the user usually wants that number.
- **Drop** any row whose hard criterion came back `met == "no"` (shouldn't happen, but check).
- **Score** each company from its soft-criteria grades — exact weights in
  `references/scoring-and-verification.md`.

## Step 5 — Verify the shortlist

Take the top ~`target_count + 10` by score and run a **second, high-effort** Exa Agent run
(`effort: "high"`) in batches of ~8 that fact-checks each company: is it a real, currently
operating company (not dead, not acquired-and-absorbed, not a product mistaken for a company);
does the website actually belong to it; does it **actually satisfy each hard criterion today**;
and are the 1–3 most load-bearing column values right (funding stage drifts constantly). Attach
the same Exa Connect providers the claims came from, or good partner-sourced numbers get
downgraded to "unknown" by a web-only checker. Be skeptical — `exists ∈ {confirmed, likely,
uncertain, not_found}`, per-criterion `met ∈ {yes, no, unknown}`.

Send the shortlist as **`input.data` rows, each carrying a stable `id`** (the company's dedup
key, e.g. `dom:acme.com`), and require the verdict schema to echo that `id` back, then join
verdicts by id, not by name — two companies can share a name. Verify query + schema are in
`references/exa-agent-api.md`.

## Step 6 — Calibrate, rank, and write output

- **Calibrate** scores down for thin/unverified rows (missing website, low confidence,
  unresolved hard criteria) so they don't float to the top, and display each score as a
  **percentage of the rubric's maximum possible score** instead of clipping at 100 (clipping
  collapses every good company onto the same number); formulas in
  `references/scoring-and-verification.md`.
- **Drop the ineligible**: anyone verified `not_found`, **any hard criterion verified `no`**,
  existing-list matches, or no website + unconfirmed existence. Mention the near misses (name +
  failed criterion) in chat — often interesting, and it shows the filter worked.
- **Rank**: verified-first, then all-criteria-met, then by calibrated score.
- **Write** `companies.csv` with columns: rank, company, website, hq, description, score, the
  plan's columns (in order), one column per soft criterion (level), one per hard criterion
  (yes/no/unknown; post-verification value when verified), overall_tier, confidence, concerns,
  verify_exists, verify_website, corrections, sources, segment. Conventions (separators, empty
  cells, snake_case) in `references/scoring-and-verification.md` §6. Also print a compact
  markdown table of the top results in chat.
- **Render the interactive viewer** from the CSV with the bundled script (do not hand-build
  HTML or copy rows into a page yourself):
  ```bash
  python3 orchestrator/render_viewer.py companies.csv companies.html \
    --title "<objective>" --table-cols "funding_stage,total_raised_usd_m,monthly_visits"
  ```
  `--table-cols` picks which of the plan's columns show in the main table (the rest live in each
  row's expandable detail); choose the 2–4 the user cares most about. It embeds the CSV rows
  into `viewer/company-viewer.template.html` and writes one self-contained file: sortable
  columns, search, segment/verification filters, expandable per-company details with clickable
  website and source links. **Tell the user what it is and to open it**, or they may not realize
  it is meant to be opened: `companies.html` is the interactive viewer for the results (what
  they should actually review). Give them its path and tell them to open it in a browser. The
  CSV stays the source artifact.

## Tips

- **Cost** scales with runs × effort (`medium` discovery ≈ $0.10/run, `high` verify ≈
  $0.50/run, plus small per-call Exa Connect charges when attached). 6 segments + 3 verify
  batches ≈ a couple dollars. Lower effort or fewer segments to cut cost.
- **Quick smoke test:** run a single segment and skip Step 5 to confirm the API + schema work
  before fanning out.
- **Refreshing a list later:** rerun discovery with the previous output + existing list in
  `input.exclusion` — the deltas are the deliverable.
- **The ideas worth keeping even if you rebuild this:** hard criteria filter / soft criteria
  score; segments as discovery *angles*, not sub-categories; a second high-effort verification
  pass that re-checks every hard criterion (criteria drift is the #1 failure mode); Exa Connect
  providers derived from the columns, named in both query and schema descriptions; dedupe by
  normalized domain against both yourself and the user's existing list; carry
  `output.grounding` citations through so claims stay checkable.
