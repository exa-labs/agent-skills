---
name: exa-candidate-sourcing
description: Source and rank real job candidates from a job description using the Exa Agent API. Use when asked to source candidates, find people for a role, build a recruiting shortlist, or turn a job posting / JD into a ranked, verified list of candidates with LinkedIn profiles.
license: MIT
compatibility: Requires network access, Python 3, and an EXA_API_KEY environment variable (or ~/.config/exa/key) with Exa Agent API access. The bundled Python orchestrator (stdlib only) executes the searches; by-hand HTTP calls (curl, or the Exa MCP server) are the fallback when it cannot run.
metadata:
  author: Exa
  version: "1.6"
---

# Candidate sourcing from a job description

Turn a job description (JD) into a **ranked, verified list of real candidates** using the
[Exa Agent API](https://exa.ai/docs/reference/agent-api-guide). You — the agent running this
skill — do the planning and the interpretation: read the JD, design the search with the
recruiter, then hand execution to the bundled **`orchestrator/source_candidates.py`** (the
default path), which runs the whole pipeline from a `config.json`: discovery fan-out,
verification, scoring, and the CSV + HTML viewer. The orchestrator exists so candidate data
never passes through you: every name, URL, and score is moved and computed by code, which
removes the transcription and hallucination errors that creep in when a model re-types
run outputs between steps. Run Steps 2-6 **by hand** only when the orchestrator cannot run:
no shell or Python available, debugging a single run, or a deliberately tiny search.
**Whichever path executes, the Step 1 plan-and-preferences checkpoint is mandatory:
build the plan, confirm it, and gather the recruiter's preferences before you write the
orchestrator's config or run any search.**

The quality comes from three choices, not from any one clever query:

1. A **graded rubric** — each dimension scored `{level, signals}` so the output is triage-able, not one opaque number.
2. **Several segment searches** instead of one — fan out across the talent pools where equivalent people actually work.
3. A **verification pass** — a second, high-effort run that fact-checks the shortlist before you rank it.

Every candidate gets **two independent scores**: a **match score** (how well they fit the role,
from the graded rubric; this drives the ranking) and a **likely-to-move score** (how likely they
are to actually take a new job, from dated work-history signals: time in the current role,
job-change cadence, and whether the role would be a step down for them; display-only, never
blended into the ranking).

**Output:** `candidates.csv` (+ a markdown table in chat) — ranked, with per-dimension levels,
an `overallFit` tier/confidence, a likely-to-move score plus the tenure/seniority signals
behind it, concerns, LinkedIn URL,
verification status, and the source citations (`output.grounding`) behind each candidate's claims.
Then render `candidates.html` from the CSV with the bundled viewer (Step 6) so the user can
review the shortlist interactively in a browser instead of only a spreadsheet.

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
  to stop, and `web_fetch_exa` to read a JD URL. Everything else in the skill is transport-agnostic.

## Step 1 — Read the JD and build a search plan

Read the JD (a URL or pasted text). If it is a URL, fetch it first. Then write a short **search plan** with these fields:

- **role** — one line (e.g. "Solutions Architect, ISV — customer-facing pre-sales cloud SA role").
- **dimensions** — 4–8 rubric dimensions to grade, derived from the JD's requirements. For each, pick a scale:
  - `capability` → `strong / partial / none / unknown` (use for "can they do X" requirements).
  - `strength` → `none / weak / medium / strong / unknown` (use for "how much of a plus is X" signals).
- **must_haves** / **signals** — prose pulled straight from the JD (hard requirements vs. nice-to-haves).
- **locations** — target metros, or empty for any location.
- **exclude_employer** — if you are sourcing *for* a company, set this to that company so you don't surface its own current employees (e.g. sourcing for AWS → `"Amazon / AWS"`). This also tells the search to **de-skew the JD's own job-title vocabulary** — value the transferable profile and equivalent roles elsewhere, not the hiring company's internal titles.
- **segments** — 4–8 **non-overlapping talent pools**, each `{ label, focus }`. Aim them where equivalent talent actually works (other clouds, ISVs, systems integrators, partners, security/networking vendors), **NOT** at the hiring company.

See `references/worked-example-aws-sa-isv.md` for a complete, filled-in plan for the AWS
"Solutions Architect, ISV" role.

### Checkpoint — confirm the plan AND elicit preferences (mandatory, before any search)

Applies **whether the orchestrator executes or you run by hand**. A JD says what the role *is*, not
what the recruiter *wants* — gather the rest before spending on a search.

**1. Show the plan you built** — role, dimensions, must-haves vs. signals, locations, excluded
employer, target count, and the segment list — in a form they can react to.

**2. Then explicitly ask what you may have missed.** Don't just ask "look right?" — surface the
implicit preferences a JD omits. Pick the ones that fit this role (don't interrogate) and invite
anything else:

- **What the rows should carry** — profiles for review, or contact-ready detail? If contact-ready,
  confirm the exact fields (such as work email or phone) and row cap because enrichment costs more
  per candidate. Ask about the desired output, not why they want it.
- **Seniority / level** — IC vs. manager vs. exec, and a years-of-experience band (matters most).
- **Dealbreakers / must-not-haves** — profiles, backgrounds, or companies to exclude beyond the
  `exclude_employer` (e.g. no agencies, no pure-research, must be hands-on).
- **Company / background preference** — types to favor or avoid (startup vs. big-tech, specific
  industries, open-source/research pedigree, competitors).
- **An existing list to dedupe against** — people already in their pipeline/ATS to exclude. Put
  them in the `exclude_people` config key (a name, a LinkedIn URL, or `{name, linkedinUrl}`) or
  pass a `--exclude-file` (one per line); both seed `input.exclusion` and are filtered from the
  results. Running by hand, pass them as `input.exclusion` on the discovery runs yourself.
- **Location strictness** — hard requirement vs. nice-to-have; is remote acceptable?
- **Non-obvious context** — team, why a past hire did or didn't work out, anything implicit they'd
  add. End with an open "anything I'm missing?"

**3. Note the rough cost** (see Tips — a couple dollars for a full fan-out + verification).

**Wait for their answer. Fold every preference into the plan** — tighten `role`, add/adjust
`dimensions`, extend `must_haves`, set the seniority target, add exclusions — **before** you write
the orchestrator's `config.json` or run a single discovery search. Only then continue.

## Run it — write the config and drive the orchestrator (default path)

Translate the confirmed plan into a `config.json` (template: `orchestrator/config.example.json`;
every key maps 1:1 to a plan field): `role`, `locations`, `exclude_employer`, `exclude_people`,
`contact_fields`,
`rubric_must_haves`, `rubric_signals`, `dimensions` (`{key, scale}`, optional `extra` string-array
fields), `segments` (`{label, focus}`), plus `max_per_call` (12), `discovery_effort` (`"medium"`),
`verify_effort` (`"high"`), and optional `data_sources` (e.g. `["fiber_ai"]` if the account has
Exa Connect people data). Then run:

```bash
python3 orchestrator/source_candidates.py --config config.json --target <how many to keep>
```

It executes Steps 2-6 below end to end and writes `candidates.csv`, `candidates.html` (the
interactive viewer, rendered automatically), `candidates.xlsx` (if openpyxl is installed), and
`sourcing_state.json`. Useful flags: `--limit-segments 1 --no-verify` (cheap smoke run before the
full fan-out), `--more` (continue the same session: fetch more per segment via `previousRunId`,
dedupe against everyone already found, keep verdicts), `--exclude-file <file>` (one name or
LinkedIn URL per line).

When it finishes, show the user a compact markdown table of the top rows **read from
`candidates.csv`** (never from memory of the run) and tell them `candidates.html` is the
interactive viewer to open in a browser. Do not re-type, re-rank, or "clean up" the results;
the CSV is the artifact. If a run fails partway, fix the config or flag and re-run; do not
finish the pipeline by hand from partial output.

**Steps 2-6 below describe the pipeline the orchestrator executes.** Read them to understand
what the config controls and what the output means; follow them manually only in the fallback
cases from the intro (no shell/Python, single-run debugging, or a deliberately tiny search).

## Step 2 — Build the graded output schema

Each Exa Agent discovery run must return JSON matching a strict schema so results are
comparable across segments. Build it from your dimensions: each dimension becomes a
`{ level, signals }` object (with the enum for its scale), plus identity fields, a `seniority`
object, an `overallFit { tier, confidence, signalsUsed, concerns }`, and a `mobility` object
(`{ monthsInCurrentRole, monthsAtCurrentCompany, avgMonthsPerPriorRole, seniorityVsRole, signals }`,
the dated work-history facts behind the likely-to-move score; the months fields are nullable and
`seniorityVsRole ∈ [step_up, aligned, step_down, unknown]`).

Use `references/candidate-schema.json` as the template — swap in your dimension keys/scales,
add `currentlyAtExcludedEmployer` (boolean) if you set `exclude_employer`, and keep
`additionalProperties: false` with everything `required` so the agent can't omit fields. Bound
the list with `maxItems` (≈12 per call) to keep cost predictable.

**Contact fields (only when the user asked for contact-ready candidates at the checkpoint).** Add
the requested fields to the candidate object and final output using nullable standard JSON Schema
formats: email uses `format: "email"`, phone uses `format: "phone"`, and another public profile URL
uses `format: "uri"`. List every contact field in `required`; return `null` when no public value can
be confirmed and never guess or fabricate one. Confirm the exact fields and row cap before running
because contact enrichment costs more per candidate. The orchestrator accepts shorthand
`contact_fields` entries (`"email"`, `"phone"`, `"uri"`) or custom entries such as
`{"key": "workEmail", "format": "email"}`.

## Step 3 — Discovery: one Exa Agent run per segment

For each segment, start an Exa Agent run with `effort: "medium"` and your output schema.
If your account has Exa Connect data partners, attach a people-data source with
`"dataSources": [{"provider": "fiber_ai"}]` and say so in the query. The query should:

- State the role + MUST-HAVE and NICE-TO-HAVE profile.
- Give the segment's `focus` as **where to look** — and say "verify independently, do NOT treat as ground truth."
- Prioritize the target `locations`.
- If `exclude_employer` is set: exclude current employees of that company; set `currentlyAtExcludedEmployer=true` and drop them. Don't bias toward that employer's own title vocabulary.
- Require a graded `{level, signals}` for **every** dimension plus an `overallFit`.
- Require `mobility` from the **dated** public work history: `monthsInCurrentRole` (months since they started the current position), `monthsAtCurrentCompany`, `avgMonthsPerPriorRole` (mean months per position across roughly the last 3-5 previous positions), and `seniorityVsRole` (would this role be a `step_up`, `aligned`, or `step_down` versus their current level; `step_down` means overqualified). Dated evidence goes in `mobility.signals`; use `null`/`unknown` when start dates are not public, and never estimate a tenure without a dated source.
- **Calibrate the grading**: grade strictly and comparatively — a dimension is `strong` only with direct public evidence, `partial` when inferred; reserve tier `exceptional` for at most 1–2 near-perfect fits per batch; `confidence: high` only with multi-source corroboration.
- Say: search beyond the LinkedIn headline (full work history, GitHub, talks, team pages, certs, blogs); corroborate across ≥2 sources.
- Say: use `null` / empty arrays / `"unknown"` when a fact isn't publicly supported; **NEVER fabricate** a name, LinkedIn URL, employer, or number. If a real LinkedIn profile can't be confirmed, set `linkedinUrl` to `null`.

**Create runs one at a time** (retry once on a 429/5xx create), then poll the started runs
concurrently. Pass already-seen names as `input.exclusion` (`[{"person": "<name>"}, ...]`) on
later batches so segments don't all return the same obvious people. **Poll** `GET /agent/runs/{id}` every ~8s
until `status` is `completed` (read candidates from `output.structured.candidates`); if it
`failed`/`canceled` or the poll gets a non-429 4xx, skip it; if it runs longer than ~20 min,
cancel it and move on.

Completed runs also return **`output.grounding`**: source citations keyed to output fields
(e.g. `structured.candidates[3]` with `[{url, title}]`). Attribute each entry to its candidate
by index and keep the citation URLs, so every shortlist row can carry the sources behind its
claims. Field paths and attribution rules are in `references/exa-agent-api.md`; coverage is
partial, so treat "no grounding entry" as normal, not an error.

**Need more candidates after a run?** Start a new run per segment with `previousRunId` set to
that segment's last run id and a short "find N more matching the same brief" query, plus every
already-seen name in `input.exclusion`; the agent keeps its research context instead of
starting cold.

The exact query template and a copy-paste curl loop are in `references/exa-agent-api.md`.

## Step 4 — Consolidate

- **Dedup** across segments by normalized LinkedIn slug (`linkedin.com/in/<slug>`), falling back to a normalized name. Keep the higher-scored copy.
- **Drop excluded** people: `currentlyAtExcludedEmployer == true`, or `currentCompany` matches `exclude_employer`.
- **Score** each candidate from its grades — see `references/scoring-and-calibration.md` for the exact weights.
- **Compute likely-to-move** from each candidate's `mobility` object with the fixed formula in `references/scoring-and-calibration.md`. It is a separate 0-100 score (null when no signal is known); it never feeds the match score or the ranking.

## Step 5 — Verify the shortlist

Take the top ~`target + 14` by score and run a **second, high-effort** Exa Agent run
(`effort: "high"`) in batches of ~8 that fact-checks each person: are they a real, currently
active professional matching the claimed name/title/company; does the LinkedIn URL plausibly
belong to them; how well does their real background match the role; and (if excluding) do they
currently work at the excluded employer. Be skeptical — `exists ∈ {confirmed, likely,
uncertain, not_found}`.

Send the shortlist as **`input.data` rows, each carrying a stable `id`** (the candidate's
dedup key), and require the verdict schema to echo that `id` back, then join verdicts by id,
not by name. Only include `currently_excluded` in the verdict schema when you set an excluded
employer. Verify query + schema are in `references/exa-agent-api.md`.

## Step 6 — Calibrate, rank, and write output

- **Calibrate** scores down for thin/unconfirmed profiles (missing company/location, low confidence) so they don't float to the top, and display each score as a **percentage of the rubric's maximum possible score** (not clipped at 100); heuristics in `references/scoring-and-calibration.md`.
- **Drop the ineligible**: anyone verified `not_found`, `matches_role == "no"`, currently at the excluded employer, or with neither a LinkedIn URL nor a known company.
- **Rank**: confirmed-first, then by match strength, then by calibrated score. The likely-to-move score is displayed next to the match score but never changes the order.
- **Write** `candidates.csv` with columns: rank, name, linkedinUrl, currentTitle, currentCompany, location, score, likely_to_move, months_in_current_role, avg_months_per_prior_role, seniority_vs_role, mobility_signals, overall_tier, confidence, one column per dimension, any requested contact columns, seniority, concerns, verify_exists, verify_match, sources, segment. The four mobility columns are tenure, job-change cadence, seniority vs the role, and the dated evidence from `mobility.signals` joined with `" | "`; leave them and likely_to_move empty when unknown. `sources` is the candidate's grounding citation URLs joined with `" | "`; leave it empty when unknown. Also print a compact markdown table of the top results in chat, including both scores.
- **Render the interactive viewer** from the CSV with the bundled script (the orchestrator does
  this automatically; do not hand-build HTML or copy rows into a page yourself):
  ```bash
  python3 orchestrator/render_viewer.py candidates.csv candidates.html --title "<role>"
  ```
  It embeds the CSV rows into `viewer/candidate-viewer.template.html` and writes one self-contained file: sortable columns, search, segment/verification filters, expandable per-candidate details with clickable LinkedIn and source links. **Tell the user what it is and to open it**, or they may not realize it is meant to be opened: `candidates.html` is the interactive viewer for the results (what they should actually review). Give them its path and tell them to open it in a browser in whatever way fits how they are working. The CSV stays the source artifact.

## Tips

- **Cost** scales with runs × effort (`medium` discovery ≈ $0.10/run, `high` verify ≈ $0.50/run); 6 segments + 2 verify batches ≈ a couple dollars. Lower effort or fewer segments to cut cost.
- **Quick smoke test:** `--limit-segments 1 --no-verify` on the orchestrator (by hand: run a single segment and skip Step 5) to confirm the key + schema work before fanning out.
