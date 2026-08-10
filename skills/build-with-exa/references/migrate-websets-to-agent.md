# Migrate Websets to the Agent API

Migrates code from Exa's Websets API (`POST /websets/v0/websets`, `exa.websets.*`) to the Agent API (`POST /agent/runs`, `exa.agent.runs.*`).

Both APIs are live; this is a contract migration — request shape, delivery model, response parsing — not a rewrite.
Do not start new collection-building work on Websets; new work goes directly to `/agent` (see [agent.md](agent.md)).

## Canonical Docs Links

- Agent API guide: `https://exa.ai/docs/reference/agent-api-guide`
- Create a run: `https://exa.ai/docs/reference/agent-api/create-a-run`
- Websets overview (legacy): `https://exa.ai/docs/reference/websets-api`

When this guide and the live docs disagree on an API fact, the docs win. Never invent model availability, limits, defaults, or API behavior: if a fact is in neither this guide nor the docs, verify it against the live API — or state that you could not.

## Contents

- Step 1: inventory Websets usage
- Step 2: classify each call site by integration style
- The strict-schema warning
- Request mapping
- Migration example
- Delivery and response mapping
- Top pitfalls
- Step-by-step procedure
- Verification loop
- Maintaining existing Websets integrations

## Step 1: Inventory Websets Usage

Find every call site before touching code:

```bash
rg -n "websets/v0|\.websets\.|Webset" -g '!node_modules'
```

Turn the hits into a file-by-file checklist. Each hit is either a call site to migrate, a webhook consumer to rewrite, or intentional legacy prose to leave alone.

## Step 2: Classify Each Call Site by Integration Style

Classify before touching code, and KEEP the style — do not "upgrade" raw HTTP to an SDK or swap SDKs.

- **(a) Raw HTTP** (`requests`, `fetch`, `curl` to `https://api.exa.ai/websets/v0/...`):
  migrate to `POST https://api.exa.ai/agent/runs` with the same HTTP library.
- **(b) Python SDK** (`exa.websets.*`):
  switch to `exa.agent.runs.create(...)` and `exa.agent.runs.poll_until_finished(run_id)`.
  Same client construction, same API key.
- **(c) TypeScript SDK** (`exa.websets.*`):
  switch to `exa.agent.runs.create({...})` and `exa.agent.runs.pollUntilFinished(runId)`.
- **(d) Webhook consumers**:
  the Agent API has no webhooks. Replace push delivery with polling `GET /agent/runs/{id}` or the SSE events stream (`GET /agent/runs/{id}/events`). If a downstream system needs push, keep a thin poller that forwards on terminal status.

**Do NOT migrate:**

- Ordinary `/search` or `/contents` code — different surfaces, unaffected.
- Code already on the Agent API (`/agent/runs`, `agent.runs.*`).
- The standalone Monitors API at `/monitors` — a different product ([monitors.md](monitors.md)). Only Websets-owned monitor subresources under `/websets/v0/monitors` are affected; recreate those on the standalone Monitors API.
- Historical or factual references to Websets in prose.

## The Strict-Schema Warning

> **THE #1 MIGRATION FAILURE:** `/agent/runs` rejects ANY unrecognized field with HTTP 400 and no run created:
> `{"error": {"type": "INVALID_REQUEST", ..., "detail": "[{\"code\": \"unrecognized_keys\", \"keys\": [\"count\"], ...}]"}}`
>
> Websets fields such as `count`, `entity`, `criteria`, `enrichments`, and `externalId` do not exist on Agent runs.
> Map every field per the table below; nothing gets carried over unmapped.

## Request Mapping

| Websets concept | Agent API equivalent |
| --- | --- |
| `Webset` container | A run (`POST /agent/runs`); follow-ups chain with `previousRunId` |
| `search.query` | `query` |
| `search.count` | `maxItems` on the output array in `outputSchema` |
| `search.entity` | Entity description inside `query` and the item shape in `outputSchema` |
| `criteria` (verification rules) | Constraints stated in `query`; the agent verifies before returning |
| `Enrichment` jobs | Fields on the item schema in `outputSchema`; contact fields via JSON Schema formats (`email`, `phone`, `uri`) |
| Imports / existing rows to enrich | `input.data` |
| Records to suppress | `input.exclusion` |
| Webhooks and events | Poll `GET /agent/runs/{id}` or stream `GET /agent/runs/{id}/events` |
| Websets monitor subresources | Standalone Monitors API (`/monitors`) |

## Migration Example

Websets create call:

```json
POST https://api.exa.ai/websets/v0/websets
{
  "search": {
    "query": "Top AI research labs focusing on large language models",
    "count": 5
  },
  "enrichments": [
    {
      "description": "Find the company's founding year",
      "format": "number"
    }
  ]
}
```

Agent API equivalent:

```json
POST https://api.exa.ai/agent/runs
{
  "query": "Find the top AI research labs focusing on large language models.",
  "outputSchema": {
    "type": "object",
    "properties": {
      "labs": {
        "type": "array",
        "maxItems": 5,
        "items": {
          "type": "object",
          "properties": {
            "name": { "type": "string" },
            "url": { "type": "string", "format": "uri" },
            "founding_year": { "type": "number" }
          },
          "required": ["name", "url", "founding_year"]
        }
      }
    },
    "required": ["labs"]
  }
}
```

## Delivery and Response Mapping

Websets pushes items incrementally through webhooks and events. Agent runs deliver once, at a terminal status:

1. Create the run; save the returned `id` (`agent_run_` prefix).
2. Poll `GET /agent/runs/{id}` until `status` is `completed`, `failed`, or `cancelled` — or stream events with `Accept: text/event-stream` (replay with `Last-Event-ID`).
3. Read `output.structured` (validated against `outputSchema`), `output.text`, `output.grounding` for citations, and `costDollars`.

Always check how the run ended before reading output; only `completed` carries results. Exiting only on `completed` hangs for failed runs.

## Top Pitfalls

1. **Leftover Websets fields → 400 `unrecognized_keys`.** Strict schema (above). Check every request body against the mapping table.
2. **No webhooks on Agent.** Consumers that only react to webhook delivery wait forever; rewrite to poll or stream events (Step 2d).
3. **Unbounded arrays.** `count` maps to `maxItems`; omitting it makes output size and enrichment cost unpredictable.
4. **`criteria` semantics must move into the query text.** The agent verifies against the query's constraints; dropping verification rules silently changes results. Call out any criteria you cannot express.
5. **Do not paste row sets into `query`.** Existing rows to enrich go in `input.data`; records to suppress go in `input.exclusion`.
6. **`previousRunId` must reference a completed run in the same team.** A follow-up is a new create request returning a new run ID; it does not reuse the prior run's object.
7. **`budget.maxCostDollars` is compatibility-only and documented as ignored.** Do not port Websets cost expectations onto it; bound cost through `maxItems` and `effort` instead.
8. **Websets-owned monitors are not part of the run.** Recreate recurring refresh on the standalone Monitors API (`/monitors`).
9. **Data retention changes in your favor.** `/agent` is a Zero Data Retention surface; Websets is not. Update compliance notes that assumed otherwise.

## Step-by-Step Procedure

1. **Inventory** with the `rg` pattern above; build a checklist.
2. **Classify** each call site by integration style (Step 2).
3. **Rewrite the request** per the mapping table: `query` absorbs `entity` and `criteria`; `outputSchema` absorbs `enrichments` and `count`; strip everything else.
4. **Rewrite delivery**: webhooks and event subscriptions become polling or SSE event consumption that handles all terminal statuses (`completed`, `failed`, and `cancelled`).
5. **Verify** per the loop below.

**Minimal-diff rule:** keep the author's structure, naming, and voice; do not refactor unrelated code. If a Websets feature has no Agent equivalent, remove it AND call the removal out in your migration notes; never drop user-facing output silently.

## Verification Loop

- Compile or typecheck every changed file.
- Run one real request per distinct call shape: a small `maxItems`, modest `effort`, poll to a terminal status, and confirm `output.structured` matches the schema. Never fabricate response JSON.
- Grep for leftovers: `websets/v0`, `\.websets\.`, `externalId`, `enrichments`, `criteria`. Every remaining hit must be intentional legacy prose.

## Maintaining Existing Websets Integrations

Only for code that stays on Websets during a staged migration:

- Base URL is `https://api.exa.ai/websets/v0`; both SDKs expose `websets` namespaces.
- Core objects: `Webset` (container), `Search` (async discovery job), `Item` (structured result), `Enrichment` (async extraction job).
- The lifecycle is async and event-driven: searches find and verify candidates, matching results become items, enrichments add fields, and webhooks/events report progress. Expect seconds-to-minutes latency.
- `externalId` provides idempotency for create calls across retries.
- Websets is not a Zero Data Retention surface.

Do not expand existing Websets integrations with new workflows; add those on `/agent`.
