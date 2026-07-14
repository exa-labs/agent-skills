---
name: exa-people-search
description: Find and rank real people matching a list of criteria using the Exa Agent API. Use when asked to find people, experts, speakers, authors, advisors, panelists, or any list of individuals matching a brief, and turn it into a ranked, evidence-cited list with profile URLs. For hiring against a job description, prefer the exa-candidate-sourcing skill.
license: MIT
compatibility: Requires network access, Python 3, and an EXA_API_KEY environment variable (or ~/.config/exa/key) with Exa Agent API access. The bundled Python orchestrator (stdlib only) executes the searches; by-hand HTTP calls (curl, or the Exa MCP server) are the fallback when it cannot run.
metadata:
  author: Exa
  version: "2.5"
---

# People search from a criteria brief

Turn a brief — a list of criteria describing who someone is looking for — into a **ranked,
evidence-cited list of real people** using the
[Exa Agent API](https://exa.ai/docs/reference/agent-api-guide). You — the agent running this
skill — do the planning and the interpretation: read the brief, design the search with the
user, then hand execution to the bundled **`orchestrator/search_people.py`** (the
default path), which runs the whole pipeline from a `config.json`: discovery (a single run by
default), corroboration only when the user flags quality or a defect turns up, scoring, and the
CSV + HTML viewer. The orchestrator exists so people data
never passes through you: every name, URL, and score is moved and computed by code, which
removes the transcription and hallucination errors that creep in when a model re-types
run outputs between steps. Run Steps 2-6 **by hand** only when the orchestrator cannot run:
no shell or Python available, debugging a single run, or a deliberately tiny search.
**Whichever path executes, the Step 1 plan-and-preferences checkpoint is mandatory:
build the plan, confirm it, and gather the user's preferences before you write the
orchestrator's config or run any search.**

(If the brief is a job description and the goal is hiring, use the sibling
`exa-candidate-sourcing` skill instead — it adds recruiting-specific scoring such as a
likely-to-move estimate. This skill is for every other "find me people who…" request:
speakers, experts, advisors, authors, panelists, guests, leads.)

The quality comes from three choices, not from any one clever query:

1. A **graded rubric** — each dimension scored `{level, signals}` so the output is triage-able, not one opaque number.
2. **One deep run by default** — a single discovery run whose instructions carry the verification duties themselves: confirm the current role, corroborate across 2+ sources, grade strictly, never fabricate, and drop anyone failing a must-have. Fan out to multiple segments only for a genuinely complex brief.
3. **Corroboration only when flagged** — the separate high-effort pass on the shortlist runs only when the user flags quality (asks for a double-check, says accuracy matters, disputes a result) or when you notice a concrete defect in the output. It is never offered proactively or run as ritual.

**Output:** `people.csv` (+ a markdown table in chat) — ranked, with per-dimension levels,
an `overallFit` tier/confidence, concerns, profile URLs, the source citations
(`output.grounding`) behind each person's claims, and — when the corroboration pass has run —
a per-person confirmation status. Then render `people.html` from the
CSV with the bundled viewer (Step 6) so the user can review the list interactively in a browser
instead of only a spreadsheet.

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
- **No shell / sandboxed (no curl, no Python)?** Then the orchestrator can't run either — this is
  the main case for running Steps 2-6 by hand. Don't skip the run or ask the user to curl for you.
  Use the **Exa MCP server**, whose tools map to the endpoints above: `agent_create_run` (same query,
  schema, `effort`), `agent_wait_for_run` / `agent_get_run_output` to poll/read, `agent_cancel_run`
  to stop, and `web_fetch_exa` to read a brief given as a URL. Everything else in the skill is
  transport-agnostic.

## Step 1 — Read the brief and build a search plan

Read the brief (a list of criteria, a paragraph, or a URL — fetch it first if it is a URL).
Then write a short **search plan** with these fields:

- **objective** — one line describing who to find and for what (e.g. "speakers for an
  embedded-Rust conference: practitioners with public speaking evidence").
- **dimensions** — 1–5 rubric dimensions to grade, derived from the criteria (a narrow ask can be a single dimension). For each, pick a scale:
  - `capability` → `strong / partial / none / unknown` (use for "do they actually do X" criteria).
  - `strength` → `none / weak / medium / strong / unknown` (use for "how much of a plus is X" signals).
- **must_haves** / **signals** — the hard criteria vs. the nice-to-haves, pulled straight from
  the brief. Every person returned must satisfy every must-have.
- **locations** — target regions or metros, or empty for any location.
- **exclude_org** — if "not from X" is part of the brief (the requester's own organization, a
  competitor, a sponsor), set it here so you don't surface that org's own people. This also tells
  the search to **de-skew that org's vocabulary** — value the equivalent profile elsewhere, not
  one org's internal titles or jargon.
- **segments** — **non-overlapping pools**, each `{ label, focus }`. Aim them at the venues
  where matching people are actually *visible*: open-source projects, employers and industries,
  conference schedules and recorded talks, publication and author lists, communities, newsletters.

**The default plan is ONE agent run: a single segment and no separate corroboration pass.**
The discovery query itself carries the verification duties — confirm each person's current
role, corroborate across 2+ independent sources, grade strictly, never fabricate, omit anyone
failing a must-have — so one well-instructed run is the whole pipeline for most asks. "5
maintainers of X", "people who work at Y", "who runs the big Z meetups" are all one focused
run. Escalate only on evidence, never for the appearance of rigor:

- **Fan out to 2–5 segments** only when the brief is genuinely complex: many criteria AND
  disjoint surfaces to search (e.g. speakers who could equally come from open-source projects,
  industry teams, and the conference circuit, and one query would under-sample them). Every
  segment is one paid run.
- **Add the corroboration pass** (Step 5, ~$0.50 per ~8 shortlist rows) only when the user
  flags quality (asks for a double-check, says accuracy matters, disputes a result) or you
  notice a concrete defect in the output. Never offer it proactively or run it as ritual.

A segment earns its place by naming a pool you expect different people from; never pad with
overlapping segments (or segments that slice one pool by role or level) to look thorough. The
same rule applies to dimensions: grade only what the brief actually asks. If the only criterion
is binary membership ("works at X", "spoke at Y"), that is **one dimension** — do not invent
filler dimensions ("role clarity", "profile verifiability") to make the plan look rigorous.

**Size `max_per_call` to the rubric's depth.** One discovery run never returns more than
`max_per_call` people per segment, so set it and `target` together. ~12 is right when each
person needs multi-dimension graded research (asking one fixed-effort run for many deeply
researched people thins the evidence per person); when the per-person check is light — a binary
membership ask like a company roster — set it to `null` to drop the cap entirely, and one run
returns every person it can verify instead of stacking `--more` rounds.

If the user asks for **"all" or "every"** person in some set, say plainly at the checkpoint that
this pipeline ranks verified matches and cannot guarantee an exhaustive roster; propose a target,
offer `--more` to keep extending the list, and point out when a primary source (an org's own team
page, a member directory) would answer better than searching.

See `references/worked-example-conference-speakers.md` for a complete, filled-in plan (a
conference-speaker search) plus how the segments shift for advisor, podcast-guest, and
business-people briefs.

### Checkpoint — confirm the plan AND elicit preferences (mandatory, before any search)

Applies **whether the orchestrator executes or you run by hand**. A brief says what the person
*looks like*, not everything the user *wants* — gather the rest before spending on a search.

**1. Show the plan you built** — objective, dimensions, must-haves vs. signals, locations,
excluded org, target count, and the segment list — in a form they can react to.

**2. Then explicitly ask what you may have missed.** Don't just ask "look right?" — surface the
implicit preferences a brief omits. Pick the ones that fit this search and invite anything else;
for a simple ask, the plan plus one or two short questions is plenty (don't interrogate):

- **What the rows should carry** — just names and profiles to review, or contact-ready detail?
  Frame this around the output, never the motive: do **not** ask what the list is for or why
  they want it — that is the user's business, and the question reads as gatekeeping. If they
  volunteer a purpose, fine — use it. Don't pitch the corroboration pass here either; it comes
  up only if the user flags quality or you find a defect in the output (Step 5).
- **Experience / prominence level** — established names vs. rising practitioners; a
  years-of-experience or seniority band if it applies.
- **Dealbreakers / must-not-haves** — profiles, backgrounds, or organizations to exclude beyond
  the `exclude_org` (e.g. no vendors, no one who already spoke last year, no pure managers).
- **An existing list to dedupe against** — people already contacted, invited, or known. Put
  them in the `exclude_people` config key (a name, a profile URL, or `{name, linkedinUrl}`) or
  pass a `--exclude-file` (one per line); both seed `input.exclusion` and are filtered from the
  results. Running by hand, pass them as `input.exclusion` on the discovery runs yourself.
- **Location strictness** — hard requirement vs. nice-to-have; does remote/virtual count?
- **Non-obvious context** — why they want the list, what a past attempt missed, anything implicit
  they'd add. End with an open "anything I'm missing?"

**3. Note the rough cost** (see Tips — most asks are a single ~$0.10 run; a multi-segment
fan-out plus corroboration is a couple dollars).

**Wait for their answer. Fold every preference into the plan** — tighten `objective`, add/adjust
`dimensions`, extend `must_haves`, add exclusions — **before** you write the orchestrator's
`config.json` or run a single discovery search. Only then continue.

## Run it — write the config and drive the orchestrator (default path)

Translate the confirmed plan into a `config.json` (template: `orchestrator/config.example.json`;
every key maps 1:1 to a plan field): `objective`, `locations`, `exclude_org`, `exclude_people`,
`rubric_must_haves`, `rubric_signals`, `dimensions` (`{key, scale}`, optional `extra` string-array
fields), `segments` (`{label, focus}`), plus `max_per_call` (people per run: ≈12 for a
multi-dimension rubric, `null` for no cap on a light-rubric roster ask — see Step 1), `discovery_effort` (`"auto"`),
`verify_effort` (`"high"`), and optional `data_sources` (e.g. `["fiber_ai"]` if the account has
Exa Connect people data and the search targets business professionals). Then run:

```bash
python3 orchestrator/search_people.py --config config.json --target <how many to keep>
```

By default it executes discovery, scoring, and output (Steps 2-4 and 6) and writes `people.csv`,
`people.html` (the interactive viewer, rendered automatically), `people.xlsx` (if openpyxl is
installed), and `people_search_state.json`. Useful flags: `--verify` (include the Step 5
corroboration pass in the same invocation — only when the user asked for it at the checkpoint),
`--verify-only` (corroborate an existing session's shortlist after the fact, no new
discovery), `--limit-segments 1` (smoke run before a multi-segment fan-out), `--more` (continue
the same session: fetch more per segment via `previousRunId`, dedupe against everyone already
found, keep verdicts), `--exclude-file <file>` (one name or profile URL per line).

**When continuing with `--more`, raise `--target` in the same command** to cover the grown pool
(e.g. 50 found, asked for more → `--more --target 100`). `--target` is the keep-count for the
output: newly found people beyond it are kept in the state file but will not appear in the CSV,
so a `--more` run with an unchanged target pays for people it doesn't show.

**Do not offer or run the corroboration pass by default — present the single-run output
plainly** (the `sources` column carries each row's citations). The pass
(`python3 orchestrator/search_people.py --config config.json --verify-only`, ~$0.50 per ~8
shortlist rows) runs on exactly two signals:

- **The user flags quality** — they ask for a double-check, say accuracy matters, or dispute a
  row. (If they ask up front, use `--verify` on the initial invocation instead.)
- **You notice a concrete defect in the output** — a row that contradicts a must-have, a
  profile URL that doesn't match the person, an entry you have real reason to doubt. Name what
  you noticed, then run it. Vague unease is not a signal; a nameable defect is.

Then show the user a compact markdown table of the top rows **read from `people.csv`** (never
from memory of the run) and tell them `people.html` is the interactive viewer to open in a
browser. Do not re-type, re-rank, or "clean up" the results; the CSV is the artifact. If a run
fails partway, fix the config or flag and re-run; do not finish the pipeline by hand from
partial output.

**Steps 2-6 below describe the pipeline the orchestrator executes.** Read them to understand
what the config controls and what the output means; follow them manually only in the fallback
cases from the intro (no shell/Python, single-run debugging, or a deliberately tiny search).

## Step 2 — Build the graded output schema

Each Exa Agent discovery run must return JSON matching a strict schema so results are
comparable across segments. Build it from your dimensions: each dimension becomes a
`{ level, signals }` object (with the enum for its scale), plus identity fields (`name`,
`currentRole`, `currentAffiliation`, `location`, `linkedinUrl`, and `profileUrl` — the best
non-LinkedIn public profile: personal site, GitHub, Scholar, org bio page) and an
`overallFit { tier, confidence, signalsUsed, concerns }`.

Use `references/person-schema.json` as the template — swap in your dimension keys/scales,
add `currentlyAtExcludedOrg` (boolean) if you set `exclude_org`, and keep
`additionalProperties: false` with everything `required` so the agent can't omit fields. Bound
the list with `maxItems` (= `max_per_call`, ≈12) when each person needs deep multi-dimension
research, so one fixed-effort run isn't asked to spread its evidence too thin; drop `maxItems`
for a light-rubric roster ask and instead tell the run to return every person it can verify.

**Contact fields (only when the user asked for contact-ready rows at the checkpoint).** The
Agent returns contact data as part of the output schema, so a contact-ready list is one schema
change, not a separate step. Add the requested fields to the person object (and to the CSV
columns in Step 6) using standard JSON Schema shapes, each nullable so an unfound value comes
back as `null` rather than fabricated:

- email: `{ "type": ["string", "null"], "format": "email" }`
- phone: `{ "type": ["string", "null"], "format": "phone" }`
- other public profile URLs: `{ "type": ["string", "null"], "format": "uri" }`

List them in `required` like every other field. The people array's `maxItems` already bounds the
contact-enrichment cost, but that cost is higher per person, so confirm the exact field list and
the row cap at the checkpoint. Never fabricate a value to fill a contact field: return `null`
when no public contact detail is found.

## Step 3 — Discovery: one Exa Agent run per segment

For each segment, start an Exa Agent run with `effort: "auto"` and your output schema.
If the search targets business professionals and your account has Exa Connect data partners,
attach a people-data source with `"dataSources": [{"provider": "fiber_ai"}]` and say so in the
query. The query should:

- State the objective plus the MUST-HAVE criteria (every person returned must satisfy all of
  them) and NICE-TO-HAVE signals.
- Give the segment's `focus` as **where to look** — and say "verify independently, do NOT treat as ground truth."
- Prioritize the target `locations`.
- If `exclude_org` is set: exclude people currently at that org; set `currentlyAtExcludedOrg=true` and drop them. Don't bias toward that org's own vocabulary.
- Require a graded `{level, signals}` for **every** dimension plus an `overallFit`.
- **Calibrate the grading**: grade strictly and comparatively — a dimension is `strong` only with direct public evidence, `partial` when inferred; reserve tier `exceptional` for at most 1–2 near-perfect matches per batch; `confidence: high` only with multi-source corroboration.
- Say: confirm each person's **current** role and affiliation before including them; corroborate across ≥2 independent sources, preferring dated evidence; search widely (personal sites, LinkedIn, GitHub, Scholar, talks, org pages, publications, podcasts, blogs).
- Say: do **not** include anyone who fails a must-have — omit them entirely rather than including them with low grades.
- Say: use `null` / empty arrays / `"unknown"` when a fact isn't publicly supported; **NEVER fabricate** a name, URL, affiliation, or number. If a real LinkedIn profile can't be confirmed, set `linkedinUrl` to `null`; set `profileUrl` to the best other confirmed public profile or `null`.

**Create runs one at a time** (retry once on a 429/5xx create), then poll the started runs
concurrently. Pass already-seen names as `input.exclusion` (`[{"person": "<name>"}, ...]`) on
later batches so segments don't all return the same obvious people. **Poll** `GET /agent/runs/{id}` every ~8s
until `status` is `completed` (read people from `output.structured.people`); if it
`failed`/`canceled` or the poll gets a non-429 4xx, skip it; if it runs longer than ~20 min,
cancel it and move on.

Completed runs also return **`output.grounding`**: source citations keyed to output fields
(e.g. `structured.people[3]` with `[{url, title}]`). Attribute each entry to its person
by index and keep the citation URLs, so every row can carry the sources behind its
claims. Field paths and attribution rules are in `references/exa-agent-api.md`; coverage is
partial, so treat "no grounding entry" as normal, not an error.

**Need more people after a run?** Start a new run per segment with `previousRunId` set to
that segment's last run id and a short "find N more matching the same brief" query, plus every
already-seen name in `input.exclusion`; the agent keeps its research context instead of
starting cold.

The exact query template and a copy-paste curl loop are in `references/exa-agent-api.md`.

## Step 4 — Consolidate

- **Dedup** across segments by normalized LinkedIn slug (`linkedin.com/in/<slug>`), falling back to a normalized `profileUrl`, then a normalized name. Keep the higher-scored copy.
- **Drop excluded** people: `currentlyAtExcludedOrg == true`, or `currentAffiliation` matches `exclude_org`.
- **Score** each person from their grades — see `references/scoring-and-calibration.md` for the exact weights.

## Step 5 — Corroborate the shortlist (only when the user flags quality or you spot a defect)

Not part of the default plan, and never offered proactively. Run it on exactly two signals: the
user flags quality (asks for a double-check — `--verify` up front, `--verify-only` after — says
accuracy matters, or disputes a result), or you notice a concrete, nameable defect in the
output (a must-have contradiction, a mismatched profile URL, an entry you have real reason to
doubt — say what you noticed, then run it).
Take the top ~`target + 14` by score and run a **second, high-effort** Exa Agent run
(`effort: "high"`) in batches of ~8 that concentrates deep research on the people who will
actually ship: confirm each is a real, identifiable person whose current role and affiliation
match, confirm the profile URLs belong to them, grade how well their real background matches
the criteria, and (if excluding) check whether they are currently at the excluded org. The
world's claims go stale — titles change, headlines inflate, people share names — so the query
instructs the agent to be skeptical and grade `exists ∈ {confirmed, likely, uncertain,
not_found}`.

Send the shortlist as **`input.data` rows, each carrying a stable `id`** (the person's
dedup key), and require the verdict schema to echo that `id` back, then join verdicts by id,
not by name. Only include `currently_excluded` in the verdict schema when you set an excluded
org. Corroboration query + schema are in `references/exa-agent-api.md`.

## Step 6 — Calibrate, rank, and write output

- **Calibrate** scores down for thin/unconfirmed profiles (missing affiliation/location, low confidence) so they don't float to the top, and display each score as a **percentage of the rubric's maximum possible score** (not clipped at 100); heuristics in `references/scoring-and-calibration.md`.
- **Drop the ineligible**: anyone whose corroboration verdict is `not_found` or `matches_criteria == "no"`, anyone currently at the excluded org, and anyone with no profile URL of any kind and no known affiliation.
- **Rank**: confirmed-first, then by match strength, then by calibrated score.
- **Write** `people.csv` with columns: rank, name, linkedinUrl, profileUrl, currentRole, currentAffiliation, location, score, overall_tier, confidence, one column per dimension, any contact columns (email, phone) the schema requested, concerns, verify_exists, verify_match, sources, segment. `sources` is the person's grounding citation URLs joined with `" | "`; leave it empty when unknown. Also print a compact markdown table of the top results in chat.
- **Render the interactive viewer** from the CSV with the bundled script (the orchestrator does
  this automatically; do not hand-build HTML or copy rows into a page yourself):
  ```bash
  python3 orchestrator/render_viewer.py people.csv people.html --title "<objective>"
  ```
  It embeds the CSV rows into `viewer/people-viewer.template.html` and writes one self-contained file: sortable columns, search, segment/verification filters, expandable per-person details with clickable profile and source links. Running this script is the **only** way the HTML gets populated: the template file is an empty shell (its data payload is `null`) until the script injects the CSV rows, so never open, edit, or hand the user the template, and never write your own HTML from the results. And the HTML is a snapshot, not a live view of the CSV: if the CSV changes (you re-run, filter, or edit rows), re-run this script or the viewer shows stale data. **Always present `people.html`, do not just leave it on disk** (users may not realize it is meant to be opened): it is the interactive viewer for the results and what they should actually review. Surface it in the best way the harness supports. The file is fully self-contained (all CSS/JS and data inline, no external requests), so it drops straight into whatever preview, artifact, or open-in-browser mechanism the environment offers; use that when one exists. Otherwise give the user its path to open in a browser, or, if you can only render it in a sandbox that blocks local `file://` paths, serve the folder over HTTP (e.g. `python3 -m http.server`) and open the local URL. Never reproduce or hand-edit the file to reshape it for a host: it inlines the entire dataset, so rewriting it regenerates the whole payload token by token; derive any variant from the existing file with a shell command instead. The CSV stays the source of truth.

## Tips

- **Cost** scales with runs × effort (`medium` discovery ≈ $0.10/run, `high` corroboration ≈ $0.50/run). The default single-run search ≈ $0.10; a requested corroboration pass adds $0.50 per ~8 shortlist rows; a full 4-5 segment fan-out with corroboration ≈ a couple dollars. The segment count is the main lever; corroboration only spends when the user flags quality or a defect turns up.
- **Quick smoke test before a multi-segment fan-out:** `--limit-segments 1` on the orchestrator (by hand: run a single segment) to confirm the key + schema work before running the rest.
