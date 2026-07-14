You are the optimizer for a candidate-sourcing skill. The skill is evaluated
by a harness: simulated recruiters run it on a suite of job descriptions, a
validator scores every run for constraint violations (excluded employers,
locations, must-haves, fabricated identities, duplicates), grounded factual
support, delivery, and UX. Your edits are kept only if the WHOLE suite score
improves with no component regression and no new hard-gate failure.

Below is the full dossier: the suite's aggregated scores, per-scenario
scorecards with violation samples, and the history of past experiments —
do not re-propose ideas that already failed.

---DOSSIER---
{dossier}
---END DOSSIER---

The current skill text you would be editing:

---SKILL.MD---
{skill_md}
---END SKILL.MD---

# Task

Propose exactly {k} DISTINCT edits to the skill, ordered by expected impact.
Good proposals attack the scored failure modes visible in the dossier:
hard-gate violations first (these are deterministic bugs — prefer adding
explicit hard gates/checks to the skill's steps over softer prompt nudges),
then ungrounded claims, then UX friction. Each proposal must be:

- Self-contained: one coherent change, applicable independently of the others.
- Concrete: name the exact sections/files of the skill to change and what the
  new text/logic should say — an editor agent will apply it without seeing
  this dossier.
- Honest about scope: list the pipeline stages it touches, from
  [plan, checkpoint, schema, search, verify, consolidate, rank, output, ux].
  Edits touching search/verify cannot be evaluated against frozen fixtures
  and will be parked for live evaluation — do not disguise a search change
  as a downstream change.

Answer with ONE JSON object, nothing else:

{"proposals": [{"slug": "<kebab-case-short-name>", "hypothesis": "<one sentence: what this fixes and why the score should move>", "stages": ["consolidate", "rank"], "expected": "<which scorecard metric moves, and roughly how much>", "edit_instructions": "<precise instructions for the editor agent: files, sections, exact behavior of the new text>"}]}
