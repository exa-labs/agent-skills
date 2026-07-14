# People search from a criteria brief (prompt)

Paste this to an agent that already has the Exa `build-with-exa` skill loaded. It uses the
Exa Agent API but does not re-explain it: for every "create a run / poll / continue / pass
exclusions / send rows" instruction below, use the Agent API exactly as documented in
`build-with-exa` (`references/agent.md`) — endpoints, `effort`, polling, `previousRunId`,
`input.exclusion`, `input.data`. (If the agent does not have `build-with-exa`, the same API
documentation ships with this skill as `references/exa-agent-api.md`.) Confirm your key has
Agent API access first (a default search key returns HTTP 429 on `POST /agent/runs`).

---

Find and rank real people matching the criteria brief I give you (a list of criteria, a
paragraph, or a URL; fetch it if it is a URL). Produce a ranked, evidence-cited list of real
people, each with a LinkedIn URL and/or another confirmed public profile URL, graded against a
rubric built from the criteria. The quality comes from four choices: a graded rubric, **one
deep discovery run by default** (fan out across segments only for a genuinely complex brief),
a **corroboration pass run only when the user flags quality or a defect turns up**, and a
calibration step. Follow these six steps.

## 1. Read the brief and write a search plan

Write a short plan with these fields:

- **objective** — one line: who to find and for what.
- **dimensions** — 1 to 5 rubric dimensions from the criteria (a narrow ask can be a single
  dimension). Give each a scale:
  `capability` (`strong / partial / none / unknown`) for "do they actually do X" criteria, or
  `strength` (`none / weak / medium / strong / unknown`) for "how much of a plus is X" signals.
- **must_haves / signals** — hard criteria vs. nice-to-haves, pulled from the brief. Every
  person returned must satisfy every must-have.
- **locations** — target regions or metros, or empty for any location.
- **exclude_org** — if "not from X" is part of the brief (the requester's own organization, a
  competitor, a sponsor), set it here so you never surface that org's own people, and so you
  de-skew that org's vocabulary (value the equivalent profile elsewhere, not one org's internal
  titles or jargon).
- **segments** — **non-overlapping** pools, each `{ label, focus }`, aimed at the venues
  where matching people are actually visible: open-source projects, employers and industries,
  conference schedules and recorded talks, publication and author lists, communities,
  newsletters. **The default is ONE paid agent run: 1 segment, no separate corroboration
  pass** — most asks name a single pool, and the discovery query itself carries the
  verification duties (Step 3). Fan out to 2 to 5 segments only when the brief is genuinely
  complex: many criteria and disjoint surfaces to search, where one query under-samples and
  the fan-out is the coverage. A segment earns
  its place by naming a pool you expect *different people* from; never pad with overlapping
  segments (or one pool sliced by role or level) to look thorough. Likewise grade only what
  the brief asks: a binary-membership criterion ("works at X") is one dimension, not an
  invented rubric. If the user asks for "all"/"every" person in a set, say plainly that this
  pipeline ranks verified matches and cannot guarantee an exhaustive roster; propose a target
  and note when a primary source (an org's own team page) would answer better.

Then show the plan to the user and ask what you missed (experience or prominence level,
dealbreakers, an existing list to dedupe against, location strictness). Never ask what the list
is for or why they want it — that is the user's business; if they volunteer a purpose, use it to
set the stakes. Fold their answers in, and only then search.

## 2. Build the graded output schema (construct it, do not paste a fixed one)

Each discovery run must return JSON matching a strict schema built from *your* Step 1 dimensions:

- Top level `{ "people": [ ... ] }`, with `maxItems` sized to the rubric's depth: ≈12 when each
  person needs multi-dimension graded research (a fixed-effort run spreads its evidence too
  thin beyond that); omit `maxItems` when the per-person check is light (e.g. a binary
  company-roster ask) and tell the run to return every person it can verify.
- Each person has identity fields: `name`, `currentRole`, `currentAffiliation`,
  `location` (nullable), `linkedinUrl` (nullable), `profileUrl` (nullable; their best
  non-LinkedIn public profile: personal site, GitHub, Scholar, org bio page). Add
  `currentlyAtExcludedOrg` (boolean) only if you set `exclude_org`.
- **Each rubric dimension** becomes an object `{ "level": <enum for its scale>, "signals": string[] }`.
  Add an extra string-array field where you want a captured list (e.g. `projects`).
- An `overallFit` object `{ tier ∈ [exceptional, strong, moderate, weak, unknown], confidence ∈ [low, medium, high], signalsUsed[], concerns[] }`.
- Everywhere: `additionalProperties: false` and list **every** field in `required`, so the agent
  cannot omit fields.

## 3. Discovery — one Agent run per segment

Create one run per segment at `effort: "auto"` with your schema. (`auto` is the default;
it lets the agent size effort to each segment's scope. Note it can cost more than `medium`,
so set `discovery_effort: "medium"` if cost matters more than letting the agent scale.) If the search
targets business professionals and your account has Exa Connect people data, attach it
(`"dataSources": [{"provider": "fiber_ai"}]`) and say so in the query. Each query should:

- State the objective plus the MUST-HAVE criteria (every person returned must satisfy all of
  them) and NICE-TO-HAVE signals.
- Give the segment's `focus` as **where to look**, and say "verify independently, do NOT treat as
  ground truth."
- Prioritize the target `locations`.
- If `exclude_org` is set: exclude people currently at that org, set `currentlyAtExcludedOrg=true`
  and drop them, and do not bias toward that org's vocabulary.
- Require a graded `{level, signals}` for **every** dimension plus an `overallFit`.
- **Calibrate the grading**: grade strictly and comparatively. `strong` only with direct public
  evidence, `partial` when inferred; reserve tier `exceptional` for at most 1 to 2 near-perfect
  matches per batch; `confidence: high` only with multi-source corroboration. Without this,
  agents grade nearly everyone at the maximum and the ranking cannot discriminate.
- Say: confirm each person's **current** role and affiliation before including them; corroborate
  across 2 or more independent sources, preferring dated evidence; search widely (personal
  sites, LinkedIn, GitHub, Scholar, talks, org pages, publications, podcasts, blogs).
- Say: do NOT include anyone who fails a must-have — omit them entirely rather than including
  them with low grades.
- Say: use `null` / empty arrays / `"unknown"` when a fact is not publicly supported; **NEVER
  fabricate** a name, URL, affiliation, or number. If a real LinkedIn profile cannot be
  confirmed, set `linkedinUrl` to `null`; set `profileUrl` to the best other confirmed public
  profile or `null`.

Create runs one at a time (a parallel create burst can trip the account QPS limit and silently drop
a segment; retry once on a 429/5xx create), then poll the started runs concurrently. Pass
already-seen names as `input.exclusion` on later batches so segments do not all return the same
obvious people. Read people from `output.structured.people`, and keep each person's
citations from `output.grounding`: entries with `field` `structured.people[i]` (or a
sub-field of it) belong to person `i`; dedup URLs and drop run-level `structured` entries.
Coverage is partial, so a person without an entry is normal. Skip a run that fails or is
canceled; cancel and move on past any run over ~20 min. **Need more after a run?** Start a new run
per segment with `previousRunId` set to that segment's last run id, a short "find N more matching the
same brief" query, and every seen name in `input.exclusion`.

## 4. Consolidate

- **Dedup** across segments by normalized LinkedIn slug (`linkedin.com/in/<slug>`), falling back
  to a normalized `profileUrl`, then a normalized name. Keep the higher-scored copy.
- **Drop excluded** people: `currentlyAtExcludedOrg == true`, or `currentAffiliation` matches
  `exclude_org`.
- **Score** each person with the formulas at the bottom of this prompt.

## 5. Corroborate the shortlist (only when the user flags quality or you spot a defect)

This pass runs on exactly two signals: the user flags quality (asks for a double-check, says
accuracy matters, disputes a result), or you notice a concrete, nameable defect in the Step 4
output (a must-have contradiction, a mismatched profile URL, an entry you have real reason to
doubt — say what you noticed, then run it). Never offer it proactively; by default, skip to
Step 6 (the sources column carries each row's citations for spot-checking).

When it runs: take the top ~`target + 14` by score and run a **second, high-effort** run
(`effort: "high"`) in batches of ~8 that concentrates deep research on the people who will
actually ship: confirm each is a real, identifiable person whose current role and affiliation
match; confirm the profile URLs belong to them; grade how well their real background matches
the criteria; and (if excluding) check whether they are currently at the excluded org. The
world's claims go stale (titles change, headlines inflate, people share names), so instruct the
run to be skeptical: `exists ∈ {confirmed, likely, uncertain, not_found}`,
`matches_criteria ∈ {strong, partial, weak, no}`.

Send the shortlist as `input.data` rows, each carrying a stable `id` (the person's dedup key), and
require the verdict schema to echo that `id` back; join verdicts by id, not by name. Include a
`currently_excluded` field in the verdict schema **only** when you set an excluded org;
otherwise agents repurpose it for unrelated doubts and good matches get dropped.

## 6. Calibrate, rank, and write output

- **Calibrate** with the formulas below so thin/unconfirmed profiles do not float up, and display
  each score as a **percentage of the rubric's maximum** (do not clip at 100).
- **Drop the ineligible** (see filter below).
- **Rank**: confirmed-first, then by match strength, then by calibrated score.
- **Write** `people.csv` with columns: rank, name, linkedinUrl, profileUrl, currentRole,
  currentAffiliation, location, score, overall_tier, confidence, one column per dimension,
  concerns, verify_exists, verify_match, sources, segment. `sources` is the grounding citation
  URLs joined with `" | "`; leave it empty when unknown. Also print a compact markdown table of
  the top results in chat.
- **Render a viewer** if the `exa-people-search` skill folder is available: run
  `python3 orchestrator/render_viewer.py people.csv people.html --title "<objective>"` and tell
  the user to open `people.html` in a browser for interactive review (sort, search, filters,
  expandable details). Do not hand-build HTML or copy CSV rows into a page yourself; without the
  renderer, stop at the CSV.

---

## Scoring, calibration & ranking (tuned constants — apply exactly)

**1. Dimension score (Step 4).** Sum the graded dimensions per person, by scale:
- `capability`: `strong = 2, partial = 1, none = 0, unknown = 0`
- `strength`: `strong = 2, medium = 1.5, weak = 1, none = 0, unknown = 0`

Call that sum `dimSum`.

**2. Base score (uncapped).**
```
base = tier_points + confidence_adj + dimSum * 1.4 + location_bonus

tier_points     : exceptional=90, strong=76, moderate=58, weak=38, unknown=50   (overallFit.tier)
confidence_adj  : high=+6, medium=0, low=-6                                     (overallFit.confidence)
location_bonus  : +4 if location matches a target location, else 0              (skip if no target locations)
```
Do NOT cap base at 100 (capping collapses good matches onto one number).

**3. Calibration (Step 6).**
```
max_possible = 90 + 6 + n_dimensions * 2 * 1.4 + (4 if target locations else 0)

penalty = 0
if currentAffiliation blank/"unknown"/"n/a":                   penalty += 15
if location blank:                                             penalty += 10
elif location set but not a target (and targets exist):        penalty += 6
if confidence == low:                                          penalty += 10   (do not also re-reward high here)
if the corroboration pass ran:
  exists == "not_found":                                       penalty += 25
  exists == "uncertain":                                       penalty += 8

calibrated = (base - penalty) * 100 / max_possible
if affiliation OR location missing: calibrated = min(calibrated, 82)   # hard cap
calibrated = round(min(100, max(0, calibrated)))
```
(For genuinely independent people, "independent" / "self-employed" is a known affiliation, not a
blank; the penalty is for profiles where nothing could be established.)

**4. Eligibility filter (Step 6) — drop before ranking** if **any**:
- corroboration verdict `exists == "not_found"`
- corroboration verdict `matches_criteria == "no"`
- `currently_excluded == true`
- neither a LinkedIn URL, nor a profile URL, nor a known affiliation (nothing to act on)

**5. Final ranking (Step 6).** Sort ascending by:
```
1. exists rank:           confirmed=0, likely=1, uncertain/unchecked=2, not_found=3
2. matches_criteria rank: strong=0, partial=1, unchecked=1, weak=2, no=3
3. -calibrated            (higher calibrated score first)
```
Keep the top `target` and write the CSV / markdown table.
