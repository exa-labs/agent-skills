# Scoring, calibration & ranking

Apply these after discovery (Step 4) and after verification (Step 6). They're simple, transparent
heuristics — tune the weights for your role. The goal is honest triage, not false precision.

## 1. Dimension score (Step 4)

Per candidate, sum the graded dimensions using the weight table for each dimension's scale:

- **capability** dimensions: `strong = 2, partial = 1, none = 0, unknown = 0`
- **strength** dimensions: `strong = 2, medium = 1.5, weak = 1, none = 0, unknown = 0`

Call that sum `dimSum`.

## 2. Base score (uncapped)

```
base = tier_points + confidence_adj + dimSum * 1.4 + location_bonus

tier_points       : exceptional=90, strong=76, moderate=58, weak=38, unknown=50   (from overallFit.tier)
confidence_adj    : high=+6, medium=0, low=-6                                       (from overallFit.confidence)
location_bonus    : +4 if the candidate's location matches a target metro, else 0   (skip if locations empty)
```

Do NOT cap the base at 100. The displayed score is a percentage of the rubric's maximum (step 3);
capping collapses every good candidate onto the same number and the ranking stops discriminating.

## 3. Calibration (Step 6) — keep thin/unconfirmed profiles from floating up

```
max_possible = 90 + 6 + n_dimensions * 2 * 1.4 + (4 if you have target metros else 0)

penalty = 0
if currentCompany is blank/"unknown"/"n/a":      penalty += 15
if location is blank:                            penalty += 10
elif location set but not a target metro (and you have target metros): penalty += 6
if confidence == low:                            penalty += 10
# (high confidence is already rewarded in the base score; do not double-count it here)
if verification ran:
  exists == "not_found":                         penalty += 25
  exists == "uncertain":                         penalty += 8

calibrated = (base - penalty) * 100 / max_possible
# hard cap: if company OR location is missing, calibrated = min(calibrated, 82)
calibrated = round(min(100, max(0, calibrated)))
```

## 4. Likely-to-move score (Step 4) — separate from the match score

A 0-100 propensity to actually switch jobs, computed from the `mobility` object with fixed
weights so it is comparable across segments and batches. It is **display-only**: it never feeds
the match score, the calibration, or the ranking. Fit and reachability are different questions;
blending them buries great candidates who merely just changed jobs.

```
tenure  = mobility.monthsInCurrentRole, falling back to mobility.monthsAtCurrentCompany
cadence = mobility.avgMonthsPerPriorRole

if tenure, cadence are both null and seniorityVsRole == "unknown": likely_to_move = null (no signal)

score = 50
tenure (months in current role):
  < 9        : -25   (just started; almost never moves)
  9 to <18   : -10   (still fresh)
  18 to 42   : +20   (the classic move window)
  >42 to 72  : +8    (long but plausible)
  > 72       : -8    (settled / entrenched)
cadence (avg months per prior role):
  <= 30      : +15   (habitual mover, likely due)
  >30 to 48  : +5
  > 48       : -8    (stays a long time everywhere)
seniorityVsRole (what this role would be for them):
  step_down  : -20   (overqualified; unlikely to accept)
  step_up    : +10   (a promotion attracts)
  aligned    : +5

likely_to_move = round(min(100, max(0, score)))
```

Null months and `unknown` seniorityVsRole contribute 0; a candidate with no known signal at all
gets `null`, reported as "no signal", never a fake neutral 50.

**Surface the inputs, not just the number.** Carry `months_in_current_role`,
`avg_months_per_prior_role`, `seniority_vs_role`, and the dated `mobility.signals` evidence into
the CSV next to `likely_to_move`. Each input maps to a band in the formula above, so a reader can
reconstruct any score (e.g. 28 mo in current role = the classic move window, avg 22 mo per prior
role = habitual mover, `step_up` = a promotion attracts). The bundled viewer composes these
columns into one "Likely to move" sentence in each candidate's detail row.

## 5. Eligibility filter (Step 6) — drop before ranking

Remove a candidate if **any** of:
- verification `exists == "not_found"`
- verification `matches_role == "no"`
- `currently_excluded == true` (they actually work at the excluded employer)
- they have **neither** a LinkedIn URL **nor** a known company (nothing to act on)

## 6. Final ranking (Step 6)

Sort ascending by this key (confirmed + strong matches first, then best calibrated score):

```
1. exists rank:        confirmed=0, likely=1, uncertain/unchecked=2, not_found=3
2. matches_role rank:  strong=0, partial=1, unchecked=1, weak=2, no=3
3. -calibrated         (higher calibrated score first)
```

Then keep the top `target` candidates and write the CSV / markdown table.
