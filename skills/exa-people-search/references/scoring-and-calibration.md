# Scoring, calibration & ranking

Apply these after discovery (Step 4) and after the corroboration pass (Step 6). They're simple, transparent
heuristics — tune the weights for your search. The goal is honest triage, not false precision.

## 1. Dimension score (Step 4)

Per person, sum the graded dimensions using the weight table for each dimension's scale:

- **capability** dimensions: `strong = 2, partial = 1, none = 0, unknown = 0`
- **strength** dimensions: `strong = 2, medium = 1.5, weak = 1, none = 0, unknown = 0`

Call that sum `dimSum`.

## 2. Base score (uncapped)

```
base = tier_points + confidence_adj + dimSum * 1.4 + location_bonus

tier_points       : exceptional=90, strong=76, moderate=58, weak=38, unknown=50   (from overallFit.tier)
confidence_adj    : high=+6, medium=0, low=-6                                       (from overallFit.confidence)
location_bonus    : +4 if the person's location matches a target location, else 0   (skip if locations empty)
```

Do NOT cap the base at 100. The displayed score is a percentage of the rubric's maximum (step 3);
capping collapses every good match onto the same number and the ranking stops discriminating.

## 3. Calibration (Step 6) — keep thin/unconfirmed profiles from floating up

```
max_possible = 90 + 6 + n_dimensions * 2 * 1.4 + (4 if you have target locations else 0)

penalty = 0
if currentAffiliation is blank/"unknown"/"n/a":  penalty += 15
if location is blank:                            penalty += 10
elif location set but not a target location (and you have target locations): penalty += 6
if confidence == low:                            penalty += 10
# (high confidence is already rewarded in the base score; do not double-count it here)
if the corroboration pass ran:
  exists == "not_found":                         penalty += 25
  exists == "uncertain":                         penalty += 8

calibrated = (base - penalty) * 100 / max_possible
# hard cap: if affiliation OR location is missing, calibrated = min(calibrated, 82)
calibrated = round(min(100, max(0, calibrated)))
```

Note on affiliation: for people who are genuinely independent (a solo open-source maintainer, a
freelance writer), "independent" or "self-employed" is a *known* affiliation, not a blank — the
penalty is for profiles where nothing could be established, not for people without an employer.

## 4. Eligibility filter (Step 6) — drop before ranking

Remove a person if **any** of:
- corroboration verdict `exists == "not_found"`
- corroboration verdict `matches_criteria == "no"`
- `currently_excluded == true` (they actually are at the excluded org)
- they have **neither** a LinkedIn URL, **nor** a profile URL, **nor** a known affiliation
  (nothing to act on)

## 5. Final ranking (Step 6)

Sort ascending by this key (confirmed + strong matches first, then best calibrated score):

```
1. exists rank:            confirmed=0, likely=1, uncertain/unchecked=2, not_found=3
2. matches_criteria rank:  strong=0, partial=1, unchecked=1, weak=2, no=3
3. -calibrated             (higher calibrated score first)
```

Then keep the top `target` people and write the CSV / markdown table.
