# Dedup, scoring, calibration & ranking

Apply these after discovery (Step 4) and after verification (Step 6). They're simple,
transparent heuristics — the goal is honest triage, not false precision. Hard criteria FILTER,
soft criteria SCORE: never convert a failed hard criterion into a low score, and never drop a
company for a weak nice-to-have.

## 0. Dedup keys (Step 4)

Primary key: **normalized domain** —

```
website → strip scheme, strip "www.", lowercase, drop path/query/fragment, drop a trailing dot
https://www.Acme.com/product?x=1 → acme.com
```

Fallback (no website): **normalized name** — lowercase; strip punctuation; collapse whitespace;
strip a *trailing* legal suffix from this list only: `inc`, `inc.`, `llc`, `ltd`, `ltd.`,
`limited`, `corp`, `corp.`, `corporation`, `co`, `co.`, `gmbh`, `plc`, `sas`, `bv`, `ab`, `oy`,
`pty`, `srl`, `sa`. Do **not** strip generic words like "labs", "ai", or "technologies" — they
distinguish real companies (Prisma vs Prisma Labs).

Use the same keys to dedupe against the **user's existing list**: normalize whatever identifier
columns it has (domain if present, else name) and drop any discovered company whose domain OR
name key matches. Domain match is authoritative; a name-only match against the existing list
should be checked by eye if the list is small, since name collisions happen.

When two discovered rows collide, keep the copy with the higher base score and merge: fill its
null/empty identity and column values from the other copy, and keep both copies' citations.

## 1. Soft-criterion score (Step 4)

Per company, sum the graded soft criteria using the weight table for each criterion's scale:

- **capability** criteria: `strong = 2, partial = 1, none = 0, unknown = 0`
- **strength** criteria: `strong = 2, medium = 1.5, weak = 1, none = 0, unknown = 0`

Call that sum `dimSum`.

## 2. Base score (uncapped)

```
base = tier_points + confidence_adj + dimSum * 1.4 + geo_bonus

tier_points    : exceptional=90, strong=76, moderate=58, weak=38, unknown=50   (from overallFit.tier)
confidence_adj : high=+6, medium=0, low=-6                                     (from overallFit.confidence)
geo_bonus      : +4 if HQ is in a *preferred* (not required) geography, else 0 (skip if geography is a hard criterion or absent)
```

Do NOT cap the base at 100. The displayed score is a percentage of the rubric's maximum (step 3);
capping collapses every good company onto the same number and the ranking stops discriminating.

## 3. Calibration (Step 6) — keep thin/unverified rows from floating up

```
max_possible = 90 + 6 + n_soft_criteria * 2 * 1.4 + (4 if a preferred geography exists else 0)

penalty = 0
if website is null/blank:                       penalty += 15
if hq is blank (and geography matters at all):  penalty += 10
if overallFit.confidence == low:                penalty += 10
if overallFit.tier == unknown:                  penalty += 8   (unknown's 50 base outscores an honest weak's 38; don't let unassessable rows float)
if any hard criterion is met == "unknown" at discovery time: penalty += 5 per criterion (cap 10)
if verification ran:
  exists == "not_found":                        penalty += 25   (usually dropped anyway, see §4)
  exists == "uncertain":                        penalty += 8
  website_valid == "wrong":                     penalty += 10
  any hard criterion verified "unknown":        penalty += 8 (total, not per criterion)

calibrated = (base - penalty) * 100 / max_possible
# hard cap: if website is missing, calibrated = min(calibrated, 82)
calibrated = round(min(100, max(0, calibrated)))
```

## 4. Eligibility filter (Step 6) — drop before ranking

Remove a company if **any** of:

- verification `exists == "not_found"`
- **any hard criterion verified `met == "no"`** — this is the whole point of the verification
  pass; criteria drift (a "Series A" company that raised a C, an "independent" company that got
  acquired) is the #1 failure mode of company lists
- discovery already said a hard criterion is `no` (shouldn't be in the results, but check)
- it matches the user's **existing list** (domain or name key)
- it has no website AND `exists != confirmed` (nothing actionable, nothing verified)

Companies dropped for a verified-failed criterion are worth listing in a short "near misses"
note to the user (name + which criterion failed) — they're often interesting context, and it
proves the filter is working.

## 5. Final ranking (Step 6)

Sort ascending by this key (verified + fully-qualified first, then best calibrated score):

```
1. exists rank:    confirmed=0, likely=1, uncertain/unchecked=2, not_found=3
2. criteria rank:  all hard criteria verified yes=0, some unknown (or unchecked)=1, any no=3
3. -calibrated     (higher calibrated score first)
```

Then keep the top `target_count` companies and write the CSV / markdown table.

## 6. CSV column conventions (Step 6)

Order: `rank, company, website, hq, description, score,` *(user columns, in the plan's order)*`,`
*(one column per soft criterion — the level)*`,` *(one column per hard criterion — yes/no/unknown,
post-verification value when verified)*`, overall_tier, confidence, concerns, verify_exists,
verify_website, corrections, sources, segment`.

- `concerns` (top 2), `corrections`: joined with `" | "`.
- `sources`: the company's grounding citation URLs joined with `" | "`; empty when unknown.
- booleans as `true`/`false`, unknown numeric/string values as empty cells — never `"N/A"` or a
  guessed value.
- column keys can be `snake_case` or `camelCase` (the viewer prettifies both for display);
  just never reuse a key the pipeline owns (`rank, company, website, hq, description, score,
  segment, sources, concerns, confidence, overall_tier, verify_*, corrections`).
