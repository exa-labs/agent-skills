# Candidate sourcing from a job description (prompt)

Paste this to an agent that already has the Exa `build-with-exa` skill loaded. It uses the
Exa Agent API but does not re-explain it: for every "create a run / poll / continue / pass
exclusions / send rows" instruction below, use the Agent API exactly as documented in
`build-with-exa` (`references/agent.md`) — endpoints, `effort`, polling, `previousRunId`,
`input.exclusion`, `input.data`. Confirm your key has Agent API access first (a default search
key returns HTTP 429 on `POST /agent/runs`).

---

Source and rank real candidates for the job description I give you (a URL or pasted text; fetch
it if it is a URL). Produce a ranked, verified list of real people with LinkedIn URLs, each with
two independent scores: a match score (fit to the role; drives the ranking) and a likely-to-move
score (propensity to actually switch jobs, from dated tenure signals; display-only). The
quality comes from four choices, so do not skip them: a graded rubric, a fan-out across several
talent segments, a verification pass, and a calibration step. Follow these six steps.

## 1. Read the JD and write a search plan

Write a short plan with these fields:

- **role** — one line.
- **dimensions** — 4 to 8 rubric dimensions from the JD's requirements. Give each a scale:
  `capability` (`strong / partial / none / unknown`) for "can they do X" requirements, or
  `strength` (`none / weak / medium / strong / unknown`) for "how much of a plus is X" signals.
- **must_haves / signals** — hard requirements vs. nice-to-haves, pulled from the JD.
- **locations** — target metros, or empty for any location.
- **exclude_employer** — if sourcing *for* a company, set it here so you never surface that
  company's own current employees, and so you de-skew the JD's own job-title vocabulary (value the
  transferable profile and equivalent roles elsewhere, not the hiring company's internal titles).
- **segments** — 4 to 8 **non-overlapping** talent pools, each `{ label, focus }`, aimed where
  equivalent people actually work (other clouds, ISVs, systems integrators, partners, security /
  networking vendors), **not** at the hiring company. The fan-out is the coverage; one broad query
  under-samples.

## 2. Build the graded output schema (construct it, do not paste a fixed one)

Each discovery run must return JSON matching a strict schema built from *your* Step 1 dimensions:

- Top level `{ "candidates": [ ... ] }`, array `maxItems: 12`.
- Each candidate has identity fields: `name`, `currentTitle`, `currentCompany`,
  `location` (nullable), `linkedinUrl` (nullable), `yearsRelevantExperience` (nullable). Add
  `currentlyAtExcludedEmployer` (boolean) only if you set `exclude_employer`.
- **Each rubric dimension** becomes an object `{ "level": <enum for its scale>, "signals": string[] }`.
  Add an extra string-array field where you want a captured list (e.g. `clouds`).
- A `seniority` object `{ level ∈ [ic_mid, ic_senior, ic_staff_principal, manager, director_plus, unknown], signals[] }`.
- An `overallFit` object `{ tier ∈ [exceptional, strong, moderate, weak, unknown], confidence ∈ [low, medium, high], signalsUsed[], concerns[] }`.
- A `mobility` object `{ monthsInCurrentRole: number|null, monthsAtCurrentCompany: number|null, avgMonthsPerPriorRole: number|null, seniorityVsRole ∈ [step_up, aligned, step_down, unknown], signals[] }` — the dated work-history facts behind the likely-to-move score.
- Everywhere: `additionalProperties: false` and list **every** field in `required`, so the agent
  cannot omit fields.

## 3. Discovery — one Agent run per segment

Create one run per segment at `effort: "medium"` with your schema. (`medium` is the right default
for a per-segment fan-out; `auto` costs far more for the same verified-real rate.) If your account
has Exa Connect people data, attach it (`"dataSources": [{"provider": "fiber_ai"}]`) and say so in
the query. Each query should:

- State the role plus MUST-HAVE and NICE-TO-HAVE profile.
- Give the segment's `focus` as **where to look**, and say "verify independently, do NOT treat as
  ground truth."
- Prioritize the target `locations`.
- If `exclude_employer` is set: exclude its current employees, set `currentlyAtExcludedEmployer=true`
  and drop them, and do not bias toward that employer's title vocabulary.
- Require a graded `{level, signals}` for **every** dimension plus an `overallFit`.
- Require `mobility` from the dated public work history: monthsInCurrentRole, monthsAtCurrentCompany,
  avgMonthsPerPriorRole (mean months per position across roughly the last 3-5 previous positions),
  and seniorityVsRole (`step_down` means overqualified). Dated evidence goes in `mobility.signals`;
  use `null`/`unknown` when start dates are not public; never estimate a tenure without a dated source.
- **Calibrate the grading**: grade strictly and comparatively. `strong` only with direct public
  evidence, `partial` when inferred; reserve tier `exceptional` for at most 1 to 2 near-perfect fits
  per batch; `confidence: high` only with multi-source corroboration. Without this, agents grade
  nearly everyone at the maximum and the ranking cannot discriminate.
- Say: search beyond the LinkedIn headline (full work history, GitHub, talks, team pages, certs,
  blogs); corroborate across 2 or more sources.
- Say: use `null` / empty arrays / `"unknown"` when a fact is not publicly supported; **NEVER
  fabricate** a name, LinkedIn URL, employer, or number. If a real LinkedIn profile cannot be
  confirmed, set `linkedinUrl` to `null`.

Create runs one at a time (a parallel create burst can trip the account QPS limit and silently drop
a segment; retry once on a 429/5xx create), then poll the started runs concurrently. Pass
already-seen names as `input.exclusion` on later batches so segments do not all return the same
obvious people. Read candidates from `output.structured.candidates`, and keep each candidate's
citations from `output.grounding`: entries with `field` `structured.candidates[i]` (or a
sub-field of it) belong to candidate `i`; dedup URLs and drop run-level `structured` entries.
Coverage is partial, so a candidate without an entry is normal. Skip a run that fails or is
canceled; cancel and move on past any run over ~20 min. **Need more after a run?** Start a new run
per segment with `previousRunId` set to that segment's last run id, a short "find N more matching the
same brief" query, and every seen name in `input.exclusion`.

## 4. Consolidate

- **Dedup** across segments by normalized LinkedIn slug (`linkedin.com/in/<slug>`), falling back to a
  normalized name. Keep the higher-scored copy.
- **Drop excluded** people: `currentlyAtExcludedEmployer == true`, or `currentCompany` matches
  `exclude_employer`.
- **Score** each candidate with the formulas at the bottom of this prompt.
- **Compute likely-to-move** per candidate from `mobility` with the fixed formula at the bottom;
  it is a separate 0-100 score (null when no signal) and never feeds the match score or ranking.

## 5. Verify the shortlist

Take the top ~`target + 14` by score and run a **second, high-effort** run (`effort: "high"`) in
batches of ~8 that fact-checks each person: are they a real, currently active professional matching
the claimed name/title/company; does the LinkedIn URL plausibly belong to them; how well does their
real background match the role; and (if excluding) do they currently work at the excluded employer.
Be skeptical: `exists ∈ {confirmed, likely, uncertain, not_found}`,
`matches_role ∈ {strong, partial, weak, no}`.

Send the shortlist as `input.data` rows, each carrying a stable `id` (the candidate's dedup key), and
require the verdict schema to echo that `id` back; join verdicts by id, not by name. Include a
`currently_excluded` field in the verdict schema **only** when you set an excluded employer;
otherwise agents repurpose it for unrelated doubts and good candidates get dropped.

## 6. Calibrate, rank, and write output

- **Calibrate** with the formulas below so thin/unconfirmed profiles do not float up, and display
  each score as a **percentage of the rubric's maximum** (do not clip at 100).
- **Drop the ineligible** (see filter below).
- **Rank**: confirmed-first, then by match strength, then by calibrated score. Likely-to-move is
  shown next to the match score but never changes the order.
- **Write** `candidates.csv` with columns: rank, name, currentTitle, currentCompany, location, score,
  likely_to_move, months_in_current_role, avg_months_per_prior_role, seniority_vs_role,
  mobility_signals, overall_tier, confidence, one column per dimension, seniority, concerns,
  linkedinUrl, verify_exists, verify_match, sources, segment. The four mobility columns justify
  the likely-to-move score (tenure, job-change cadence, seniority vs the role, dated evidence
  from `mobility.signals` joined with `" | "`); leave them and likely_to_move empty when unknown.
  `sources` is the grounding citation URLs joined with `" | "`; leave it empty when unknown.
  Also print a compact markdown table of the top results in chat, including both scores.
- **Render a viewer** if the `exa-candidate-sourcing` skill folder is available: run
  `python3 orchestrator/render_viewer.py candidates.csv candidates.html --title "<role>"` and tell the user to
  open `candidates.html` in a browser for interactive review (sort, search, filters, expandable
  details). Do not hand-build HTML or copy CSV rows into a page yourself; without the renderer,
  stop at the CSV.

---

## Scoring, calibration & ranking (tuned constants — apply exactly)

**1. Dimension score (Step 4).** Sum the graded dimensions per candidate, by scale:
- `capability`: `strong = 2, partial = 1, none = 0, unknown = 0`
- `strength`: `strong = 2, medium = 1.5, weak = 1, none = 0, unknown = 0`

Call that sum `dimSum`.

**2. Base score (uncapped).**
```
base = tier_points + confidence_adj + dimSum * 1.4 + location_bonus

tier_points     : exceptional=90, strong=76, moderate=58, weak=38, unknown=50   (overallFit.tier)
confidence_adj  : high=+6, medium=0, low=-6                                     (overallFit.confidence)
location_bonus  : +4 if location matches a target metro, else 0                 (skip if no target metros)
```
Do NOT cap base at 100 (capping collapses good candidates onto one number).

**3. Calibration (Step 6).**
```
max_possible = 90 + 6 + n_dimensions * 2 * 1.4 + (4 if target metros else 0)

penalty = 0
if currentCompany blank/"unknown"/"n/a":                       penalty += 15
if location blank:                                             penalty += 10
elif location set but not a target metro (and metros exist):   penalty += 6
if confidence == low:                                          penalty += 10   (do not also re-reward high here)
if verification ran:
  exists == "not_found":                                       penalty += 25
  exists == "uncertain":                                       penalty += 8

calibrated = (base - penalty) * 100 / max_possible
if company OR location missing: calibrated = min(calibrated, 82)   # hard cap
calibrated = round(min(100, max(0, calibrated)))
```

**4. Likely-to-move score (Step 4) — display-only, apply exactly.**
```
tenure  = mobility.monthsInCurrentRole ?? mobility.monthsAtCurrentCompany
cadence = mobility.avgMonthsPerPriorRole
if tenure and cadence are null and seniorityVsRole == "unknown": likely_to_move = null ("no signal")

score = 50
tenure:   <9: -25 | 9-<18: -10 | 18-42: +20 | >42-72: +8 | >72: -8
cadence:  <=30: +15 | >30-48: +5 | >48: -8
seniorityVsRole: step_down: -20 | step_up: +10 | aligned: +5

likely_to_move = round(min(100, max(0, score)))
```
Null months and `unknown` contribute 0. Never blend this into the match score or the ranking.
Carry the formula's inputs into the CSV (the mobility columns in Step 6) so every score stays
explainable.

**5. Eligibility filter (Step 6) — drop before ranking** if **any**:
- verification `exists == "not_found"`
- verification `matches_role == "no"`
- `currently_excluded == true`
- neither a LinkedIn URL nor a known company (nothing to act on)

**6. Final ranking (Step 6).** Sort ascending by:
```
1. exists rank:       confirmed=0, likely=1, uncertain/unchecked=2, not_found=3
2. matches_role rank: strong=0, partial=1, unchecked=1, weak=2, no=3
3. -calibrated        (higher calibrated score first)
```
Keep the top `target` and write the CSV / markdown table.
