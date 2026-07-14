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
    "structured": { "companies": [ { "name": "…", "website": "…", "...": "…" } ] },
    "grounding": [ { "field": "...", "citations": [ { "url": "...", "title": "..." } ], "confidence": "high" } ]
  },
  "usage": { "agentComputeUnits": 12.5, "searches": 3 },
  "costDollars": { "total": 0.42 }
}
```

### output.grounding — citations for the structured output

Each entry maps one output field to the sources supporting it: `field` (a path into the
output), `citations` (`[{url, title}]`), and `confidence` (`low | medium | high`). `field`
arrives at three granularities:

- `structured.companies[3]` — supports one whole company row (the common case).
- `structured.companies[3].totalRaisedUsdM` — supports one field; roll it up to its company.
- `structured` — a run-level citation dump (the research trail); it supports no single
  company, so drop it when attributing sources.

Attribute entries to companies by the index in the path and dedup citation URLs per company.
Coverage is partial — some runs ground every row, others only some — so a company without an
entry is normal, not an error.

## Request body

```jsonc
{
  "query": "…natural-language instructions…",   // required
  "effort": "medium",                            // minimal|low|medium|high|xhigh|auto
  "outputSchema": { /* JSON Schema (draft 2020-12) */ },
  "input": {
    "exclusion": [ { "company": "Acme", "website": "acme.com" } ],  // optional: keep these out
    "data": [ { "id": "dom:acme.com", "name": "Acme" } ]            // optional: rows to process/enrich
  },
  "dataSources": [ { "provider": "similarweb" } ],  // optional: Exa Connect data partners
  "previousRunId": "run_..."                        // optional: continue a completed run's context
}
```

- `outputSchema` — when set, `output.structured` matches it. Use `additionalProperties:false`,
  list everything in `required`, and bound arrays with `maxItems` so the agent can't omit fields
  or run up cost. (Template: `company-schema.json`.)
- `input.exclusion` — pass already-known companies so runs don't re-return them: your
  already-found companies plus the user's existing list. Cap it around 100 entries (prioritize
  the ones most likely to be re-found — the well-known names); dedupe the rest locally after.
- `input.data` — structured rows the run should process; give each row a stable `id` and make
  the output schema echo it so results join back exactly (used by the verification pass).
- `dataSources` — attaches premium Exa Connect partners; see
  `exa-connect-providers.md` for when to attach which. Mention the attached source in the query
  AND in the schema field descriptions (e.g. `"monthlyVisits": {"description": "from Similarweb"}`)
  so the agent routes each field to the right tool.
- `previousRunId` — starts a new run that carries over a completed run's research context; use
  for "find N more" follow-ups together with `input.exclusion` of everything already seen.
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
| `auto` | variable | scope unknown ahead of time; measured much more expensive per run for the same quality in fan-outs, so prefer `medium` here |

Exa Connect adds a small per-call provider charge on top (see `exa-connect-providers.md`).

## Discovery query template (Step 3)

Fill the `{...}` from your Step-1 research plan; one run per segment:

```
Find real companies matching: {objective}.

HARD REQUIREMENTS (every company must satisfy ALL of these): {hard_criteria joined}

NICE-TO-HAVE signals (grade, don't filter): {soft_criteria joined}

FOCUS for this search (a place to look, NOT ground truth — verify every company independently
against the hard requirements): {segment.focus}

{geo line, e.g. "Only include companies headquartered in the US." — omit if no geography}

For EACH company, fill every requested field:
- identity: official company name, canonical website homepage URL, HQ city/region, a one-line
  description of what the company actually sells (not its slogan).
- for EACH hard requirement: met ∈ yes/no/unknown with the concrete public evidence; if a hard
  requirement is "no", do NOT include the company at all.
- for EACH nice-to-have: a graded level with the concrete public signals that justify it.
- the requested data columns: {column list with source hints, e.g. "monthlyVisits (from
  Similarweb)", "totalRaisedUsdM (from Fiber.ai, in millions USD)"}.
- an overallFit (tier, confidence, signalsUsed, concerns).

Calibrate the grading: grade strictly and comparatively. A nice-to-have is "strong" only with
direct public evidence, "partial"/"medium" when inferred; reserve tier "exceptional" for at most
1-2 near-perfect fits per batch; confidence "high" only with multi-source corroboration.

Search beyond the company homepage: funding announcements, Crunchbase/press coverage, product
docs and pricing pages, GitHub, customer case studies, LinkedIn company pages, job postings;
corroborate across at least two sources where possible.

Use null, empty arrays, or "unknown" whenever a fact is not supported by public evidence; NEVER
fabricate a company name, website, funding amount, or number. If you cannot confirm the
company's real website, set website to null. Do not include duplicate companies, subsidiaries
already covered by their parent, or companies that have shut down or been acquired (unless the
ask includes them).

Do not include any company from the exclusion list.

Return up to {maxItems} real companies.
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

## Verification pass (Step 5)

Run with `effort: "high"`, in batches of ~8 from the shortlist. Send the batch as `input.data`
rows carrying each company's stable dedup key as `id`; the verdict schema echoes the id back so
verdicts join onto exactly the right company even when two companies share a name.

Query:

```
Fact-check this company list for: {objective}. The input data has one row per company with an
id and its claimed name, website, HQ, description, and key claimed facts. For EACH row, use web
search (and the attached data sources, if any) to determine:
(1) is this a real, currently operating company (not shut down, not acquired-and-absorbed,
    not a product name mistaken for a company);
(2) does the claimed website actually belong to this company;
(3) for EACH of these hard requirements, does the company actually satisfy it TODAY:
    {hard_criteria as a numbered list} — check each one independently and cite evidence;
(4) verify or correct the claimed key facts where you can ({names of the 1-3 most
    load-bearing columns, e.g. funding stage / total raised}).
Be skeptical: companies drift out of criteria (a "Series A" company may have raised a C; an
"independent" company may have been acquired). If you cannot find evidence, mark it "unknown" —
never guess. Return exactly one verdict per row, copying the row's id into the verdict's id
field unchanged, with one criteria entry per hard requirement, setting each entry's key to
that requirement's key ({numbered key list, e.g. 1=hqInUs, 2=stageSeriesAOrB, ...}).
```

`input.data` (one row per company):

```json
[
  { "id": "dom:acme.com", "name": "Acme", "website": "https://acme.com",
    "claimed_hq": "San Francisco, CA", "claimed_description": "…",
    "claimed_facts": "Series A ($14M, 2025); ~40 employees" }
]
```

Verify `outputSchema` — one entry per hard criterion in `criteria`. Make `key` an **enum of
your hard-criterion keys** so the join back onto your plan is exact (no fuzzy text matching):

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object", "additionalProperties": false, "required": ["verdicts"],
  "properties": { "verdicts": { "type": "array", "items": {
    "type": "object", "additionalProperties": false,
    "required": ["id", "name", "exists", "website_valid", "criteria", "corrections"],
    "properties": {
      "id": { "type": "string" },
      "name": { "type": "string" },
      "exists": { "type": "string", "enum": ["confirmed", "likely", "uncertain", "not_found"] },
      "website_valid": { "type": "string", "enum": ["valid", "unverifiable", "wrong"] },
      "criteria": { "type": "array", "items": {
        "type": "object", "additionalProperties": false,
        "required": ["key", "met", "evidence"],
        "properties": {
          "key": { "type": "string", "enum": ["hqInUs", "stageSeriesAOrB", "devFacingAiInfra"] },
          "met": { "type": "string", "enum": ["yes", "no", "unknown"] },
          "evidence": { "type": "string" }
        } } },
      "corrections": { "type": "array", "items": { "type": "string" },
        "description": "claimed facts that are wrong or stale, with the corrected value and source" }
    } } } }
}
```
