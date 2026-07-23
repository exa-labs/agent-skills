---
name: exa-candidate-sourcing
description: Source, refine, and rank real job candidates from a job description with Exa. Use for recruiting shortlists, candidate searches, role-to-person matching, or iterative sourcing feedback such as changing locations, excluding employers, adjusting seniority, or expanding selected talent pools. Supports a bundled filesystem orchestrator and a no-filesystem Exa MCP workflow.
---

# Candidate sourcing with Exa

Build a verified shortlist through a fast calibration loop instead of committing immediately to a
full search. Treat recruiter feedback as a patch to the current brief: preserve every prior hard
constraint unless the recruiter explicitly changes it.

## Workflow

### 1. Build the current brief

Read the JD, then present a compact plan containing:

- role and target count;
- 4–8 graded rubric dimensions;
- must-haves versus preferred signals;
- locations and whether location is `required` or `preferred`;
- hiring company to exclude;
- other current employers or people to exclude;
- seniority requirements;
- 4–8 non-overlapping talent-pool segments;
- profiles-for-review versus requested contact fields.

Ask about seniority, dealbreakers, companies/backgrounds to favor or avoid, location strictness,
existing pipeline dedupe, and one piece of non-obvious hiring context. Wait for confirmation before
spending on a search.

Keep a canonical **current brief** for the rest of the conversation. Classify each rule as either:

- **hard constraint** — controls eligibility; or
- **preference** — affects ranking only.

Compile every confirmed hard rule into the executable brief. Use typed location, employer, and
seniority fields where available; put every other rule in `hard_constraints.requirements` with a
snake-case key, exact description, and explicit `unknown_policy` (`exclude` or `allow`). Require an
evidence-backed `meets`, `fails`, or `unknown` check for each candidate. Never replace a requested
fact with a proxy: short tenure does not prove contracting, and employment at a consultancy does not
prove that the person is a contractor.

Before calibration, show every nonstandard hard requirement and its unknown policy in one compact
table and obtain confirmation. Confirmation is scoped: a reply about one pending item does not
confirm a different employer list, unknown policy, segment, or search action. If the recruiter
explicitly requests a proxy-based exclusion, encode the observable rule literally (for example,
“exclude 3+ roles under 12 months”), not as proof of a different fact such as contractor status.

When the recruiter describes an employer category to avoid, propose the exact employer list and get
confirmation before saving it as a hard exclusion. Do not silently turn “companies with
noncompetes” or a similar category into an agent-generated company blacklist.

### 2. Calibrate the segments

Run one lightweight search across every proposed segment. Return at most two provisional candidates
per segment. Require every segment to report `found`, `weak`, or `none`; allow an empty result rather
than weakening a hard constraint or fabricating a candidate. Assign each person to one best-fit
segment and do not repeat people across segments.

This is exactly one combined Agent run. Expansion concurrency does not apply; never describe
calibration as several waves or infer its duration. Report the elapsed seconds printed by the
orchestrator.

For calibration, collect only identity, current title/company, location, LinkedIn URL, a short fit
summary, and concerns. Do not collect contact data, mobility, full rubric grades, or run high-effort
verification yet.

Show the sample by segment and ask which pools and profiles are promising or wrong. This replaces
asking the recruiter to approve abstract segment descriptions without seeing representative people.
Do not interpret feedback about constraint strictness as segment approval.

### 3. Apply feedback before searching again

Interpret feedback as a patch, never as a replacement prompt. Show:

1. **Changed** — rules or segments added, removed, or modified.
2. **Preserved** — all existing hard constraints that remain active.

Choose the cheapest valid action:

- Known-field exclusion or hard location change → filter the cached pool immediately.
- Preference change covered by existing evidence → rescore immediately.
- New fact needed for known candidates → enrich only surviving candidates.
- Segment added/changed or pool too small → search only current approved/underfilled segments.
- More candidates under an unchanged brief → continue previous runs.

Never silently relax a hard requirement to fill the target count. Report the shortfall and ask
whether the recruiter wants broader criteria.

Require the recruiter to name or clearly approve the segments to expand. If calibration predicts a
near-zero result under the confirmed gates, state that plainly and obtain confirmation before the
larger paid expansion. “Keep everything strict” confirms the gates only; it does not approve every
segment or authorize the expansion.

### 4. Expand and verify

After calibration, expand only the approved segments. Discovery must return a strict graded object
for every rubric dimension plus identity, seniority, overall fit, mobility evidence, and requested
contact fields. Use `null`, empty arrays, or `unknown` when public evidence is absent; never invent a
person, URL, employer, date, or contact value.

Deduplicate by normalized LinkedIn slug, falling back to normalized name. Apply hard constraints
before ranking. Verify approximately `target + 14` top candidates at high effort, then rank using the
fixed formulas in [references/scoring-and-calibration.md](references/scoring-and-calibration.md).

Every candidate receives two independent scores:

- **match score** — role fit; drives ranking;
- **likely-to-move** — dated tenure/cadence/seniority signals; display only.

Never use likely-to-move to reorder, filter, or de-prioritize candidates. Calibration records are
provisional and lack the full rubric; require full discovery enrichment before allowing one into a
final ranking.

## Choose an execution path

### Filesystem and Python available — use the orchestrator

Use `orchestrator/config.example.json` as the internal config shape. The recruiter should not have
to edit or understand JSON. The agent owns the config; the script owns `sourcing_state.json`. Keep
the config in a per-search working directory. The script writes state and artifacts beside that
config by default, never into the installed skill directory; use `--output-dir` only to override it.

Check for an API key without printing it. Resolve `EXA_API_KEY`, then `~/.config/exa/key`, then
`orchestrator/.exa_key`. If absent, direct the user to the bundled setup script; never accept a key
in chat or print a key/file that may contain one.

Run calibration:

```bash
python3 orchestrator/source_candidates.py --config config.json --calibrate
```

Present `calibration.html`, collect feedback, and patch the same config. Use `--reuse` to reprocess an
existing fully discovered pool without network work:

```bash
python3 orchestrator/source_candidates.py --config config.json --reuse --target 50
```

If more candidates are needed, expand the current segments:

```bash
python3 orchestrator/source_candidates.py --config config.json --more --target 50
```

When the brief is unchanged, `--more` continues per-segment runs with `previousRunId`. When it
changed, the script preserves and re-filters the cached pool, invalidates incompatible verdicts,
and starts fresh searches for only the segments in the current config. Policy-only changes reuse
the verified facts and apply the new policy. `--reuse` never performs
discovery or verification. Immediately after calibration, use `--more` for the approved segments;
the orchestrator fully enriches retained calibration profiles before they can enter the final list.

The final artifacts are `candidates.csv`, `candidates.xlsx` when available, and the self-contained
interactive `candidates.html`, all in the session output directory. Read displayed rows from the
CSV; do not retype or rerank them. Use the orchestrator's printed elapsed time instead of estimating
from timestamps or rerunning a paid search. Treat all formats as one result set: never hand-correct
only one artifact or deliver a viewer known to contain different candidates. Fix or rerun the
orchestrator so every delivered format is regenerated from the same final rows.

### No filesystem or shell — use Exa MCP

Read and follow [references/mcp-workflow.md](references/mcp-workflow.md). Keep the canonical current
brief in the conversation; no config, state, or schema file is required. Construct JSON Schemas in
the MCP call payload, retain run IDs, and repeat the complete current brief on every continuation so
earlier hard constraints cannot disappear.

For endpoint details, grounding attribution, retries, and `previousRunId` behavior, read
[references/exa-agent-api.md](references/exa-agent-api.md).

## Output and optional ATS sync

Return a compact top-candidate table and link the generated viewer when using the orchestrator. Each
final row must include identity, LinkedIn URL, scores and evidence, dimension grades, concerns,
verification status, segment, and source URLs.

If Ashby is connected, read [references/ashby-integration.md](references/ashby-integration.md) for
pipeline dedupe or an explicitly confirmed shortlist push. Never push candidates silently.
