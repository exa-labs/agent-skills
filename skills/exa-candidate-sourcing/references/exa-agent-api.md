# Exa Agent API — reference for this skill

Docs: https://exa.ai/docs/reference/agent-api-guide

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `https://api.exa.ai/agent/runs` | Start a run. Returns `{ "id": "...", "status": "running", ... }`. |
| GET | `https://api.exa.ai/agent/runs/{id}` | Poll a run. `status ∈ running \| completed \| failed \| canceled`. |
| POST | `https://api.exa.ai/agent/runs/{id}/cancel` | Cancel a queued/running run (no body). |

Auth header: `x-api-key: $EXA_API_KEY`. Content type: `application/json`.

The run is **async** — you `POST` to start, then `GET` every ~8s until `status == "completed"`,
then read structured results from `output.structured`. A completed run looks like:

```json
{
  "id": "run_...", "status": "completed",
  "output": {
    "text": "…natural-language summary…",
    "structured": { "candidates": [ { "name": "…", "linkedinUrl": "…", "...": "…" } ] },
    "grounding": [ { "field": "...", "citations": [ { "url": "...", "title": "..." } ], "confidence": "high" } ]
  },
  "usage": { "agentComputeUnits": 12.5, "searches": 3 },
  "costDollars": { "total": 0.42 }
}
```

### output.grounding — citations for the structured output

Each entry maps one output field to the sources supporting it: `field` (a path into the
output), `citations` (`[{url, title}]`), and `confidence` (`low | medium | high`, the
agent-reported reliability for that field). Observed across ~50 candidate-sourcing runs,
`field` arrives at three granularities:

- `structured.candidates[3]` — supports one whole candidate (the common case, usually the
  LinkedIn profile plus a secondary source).
- `structured.candidates[3].name` / `.currentTitle` — supports one field; roll it up to its
  candidate.
- `structured` — a run-level citation dump (sometimes dozens of URLs, the research trail);
  it supports no single candidate, so drop it when attributing sources.

Attribute entries to candidates by the index in the path and dedup citation URLs per candidate.
(`confidence` exists on each entry but was uniformly "medium" across those runs, so this skill
keeps only the citations.) Coverage is partial — roughly half of runs ground every candidate,
the rest only some — so a candidate without an entry is normal, not an error.

## Request body

```jsonc
{
  "query": "…natural-language instructions…",   // required
  "effort": "medium",                            // minimal|low|medium|high|xhigh|auto
  "outputSchema": { /* JSON Schema (draft 2020-12) */ },
  "input": {
    "exclusion": [ { "person": "Jane Doe" } ],   // optional: keep these out
    "data": [ { "id": "li:janedoe", "name": "Jane Doe" } ]  // optional: rows to process/enrich
  },
  "dataSources": [ { "provider": "fiber_ai" } ], // optional: Exa Connect data partners
  "previousRunId": "run_..."                     // optional: continue a completed run's context
}
```

- `outputSchema` — when set, `output.structured` matches it. Use `additionalProperties:false`,
  list everything in `required`, and bound arrays with `maxItems` so the agent can't omit fields
  or run up cost. (Full candidate schema: `candidate-schema.json`.)
- `input.exclusion` — pass already-seen names so later segment runs don't all return the same people.
- `input.data`: structured rows the run should process; give each row a stable `id` and make the
  output schema echo it so results join back exactly (used by the verification pass).
- `dataSources`: attaches premium Exa Connect partners (e.g. `fiber_ai`, a B2B people database);
  mention the attached source in the query so the agent uses it.
- `previousRunId`: starts a new run that carries over a completed run's research context; use for
  "find N more" follow-ups together with `input.exclusion` of everyone already seen.
- Creates can transiently fail with 429/5xx if several runs start at once; create runs one at a
  time and retry a failed create once before giving up on a segment.

## Effort / cost (fixed modes)

| Effort | ~Cost/request | Use for |
| --- | --- | --- |
| `minimal` | $0.012 | trivial lookups |
| `low` | $0.025 | narrow factual checks |
| `medium` | $0.10 | **default for discovery** |
| `high` | $0.50 | **verification pass** (more citations, stricter completeness) |
| `xhigh` | $1.00 | high-value, completeness over cost |
| `auto` | variable | scope unknown ahead of time; measured ~7x `medium` per run across 11 JDs (one segment each) with the same verified-real rate, so prefer `medium` here |

## Discovery query template (Step 3)

Fill the `{...}` from your Step-1 search plan; one run per segment:

```
Find real candidates for: {role}.

MUST-HAVE profile: {must_haves joined}

NICE-TO-HAVE signals: {signals joined}

FOCUS for this search (verify independently — do NOT treat as ground truth): {segment.focus}

Strongly prioritize people based in or near: {locations or "any location"}.

EXCLUDE anyone currently employed at {exclude_employer}; set currentlyAtExcludedEmployer=true if
they are and then do NOT include them. Do not bias toward that employer's own job-title
vocabulary — value the transferable profile and equivalent roles at other companies.
[omit this paragraph if no exclude_employer]

For EACH candidate, grade every rubric dimension with a level and the concrete public signals
that justify it, plus an overallFit (tier, confidence, signalsUsed, concerns).

For EACH candidate, also fill mobility from their dated public work history: monthsInCurrentRole
(months since they started the current position), monthsAtCurrentCompany, avgMonthsPerPriorRole
(mean months per position across roughly their last 3-5 previous positions), and seniorityVsRole
(would this role be a step_up, aligned, or step_down versus their current level; step_down means
they are overqualified). Put the dated evidence in mobility.signals (e.g. 'joined Acme as Staff
Engineer in Mar 2024 per LinkedIn'). Use null or 'unknown' when start dates are not public; never
estimate a tenure without a dated source.

Search beyond the LinkedIn headline: full work history, GitHub, conference/meetup talks, company
team pages, certification registries, blogs; corroborate across at least two sources where possible.

Use null, empty arrays, or the 'unknown' enum whenever a fact is not supported by public
evidence; NEVER fabricate a name, LinkedIn URL, employer, or number. If you cannot confirm a real
LinkedIn profile, set linkedinUrl to null.

Return up to 12 real candidates.
```

### Copy-paste discovery + poll loop

```bash
start_run () {  # $1 = JSON body file -> prints run id
  curl -s -X POST https://api.exa.ai/agent/runs \
    -H "x-api-key: $EXA_API_KEY" -H "Content-Type: application/json" \
    -d @"$1" | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])'
}

wait_run () {  # $1 = run id -> prints completed run JSON (or nothing on failure/timeout)
  for i in $(seq 1 150); do
    r=$(curl -s https://api.exa.ai/agent/runs/"$1" -H "x-api-key: $EXA_API_KEY")
    s=$(printf '%s' "$r" | python3 -c 'import sys,json;print(json.load(sys.stdin)["status"])')
    case "$s" in
      completed) printf '%s' "$r"; return 0 ;;
      failed|canceled|cancelled) echo "run $1 $s" >&2; return 1 ;;
      *) sleep 8 ;;
    esac
  done
  curl -s -X POST https://api.exa.ai/agent/runs/"$1"/cancel -H "x-api-key: $EXA_API_KEY" >/dev/null
  echo "run $1 timed out, cancelled" >&2; return 1
}
```

Start 2–3 segment runs first (collect their ids), then poll them — that runs them concurrently.
If you have multiple keys, spread runs across them to dodge the per-key concurrency limit.

## Verification pass (Step 5)

Run with `effort: "high"`, in batches of ~8 from the shortlist. Send the batch as `input.data`
rows carrying each candidate's stable dedup key as `id`; the verdict schema echoes the id back
so verdicts join onto exactly the right candidate even when two people share a name.

Query:
```
Fact-check this recruiting shortlist for: {role}. The input data has one row per person with an
id and their claimed name, title, company, location, and LinkedIn URL. For EACH row, use web
search to determine:
(1) are they a real, currently-active professional matching the claimed name/title/company;
(2) does the LinkedIn URL plausibly belong to them;
(3) how well does their real background match the role;
(4) do they CURRENTLY work at {exclude_employer} (set currently_excluded=true if so).  [if excluding]
Be skeptical: if you cannot find evidence, mark exists 'uncertain' or 'not_found'. Return exactly
one verdict per row, copying the row's id into the verdict's id field unchanged.
```

`input.data` (one row per person):
```json
[
  { "id": "li:janedoe", "name": "Jane Doe", "claimed_title": "Staff Engineer",
    "claimed_company": "Acme", "claimed_location": "SF Bay Area",
    "linkedin_url": "https://linkedin.com/in/janedoe" }
]
```

Verify `outputSchema` (include `currently_excluded` ONLY when an employer exclusion was
requested; otherwise agents repurpose it for unrelated doubts and good candidates get dropped):
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object", "additionalProperties": false, "required": ["verdicts"],
  "properties": { "verdicts": { "type": "array", "items": {
    "type": "object", "additionalProperties": false,
    "required": ["id", "name", "exists", "matches_role"],
    "properties": {
      "id": { "type": "string" },
      "name": { "type": "string" },
      "exists": { "type": "string", "enum": ["confirmed", "likely", "uncertain", "not_found"] },
      "linkedin_valid": { "type": "string", "enum": ["valid", "unverifiable", "wrong"] },
      "matches_role": { "type": "string", "enum": ["strong", "partial", "weak", "no"] },
      "currently_excluded": { "type": "boolean" },
      "verified_title_company": { "type": "string" }
    } } } }
}
```
