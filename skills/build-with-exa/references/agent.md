# Agent API Reference

Async multi-step research, list-building, enrichment, and structured extraction via `POST /agent/runs`.

## Canonical Docs Links

- Agent API guide: `https://exa.ai/docs/reference/agent-api-guide`
- Create a run: `https://exa.ai/docs/reference/agent-api/create-a-run`
- Get a run: `https://exa.ai/docs/reference/agent-api/get-a-run`
- List runs: `https://exa.ai/docs/reference/agent-api/list-runs`
- List run events: `https://exa.ai/docs/reference/agent-api/list-run-events`
- Cancel a run: `https://exa.ai/docs/reference/agent-api/cancel-a-run`
- Delete a run: `https://exa.ai/docs/reference/agent-api/delete-a-run`
- Exa Connect overview: `https://exa.ai/docs/reference/agent-api/connect/overview`
- Connect combining providers: `https://exa.ai/docs/reference/agent-api/connect/combining-providers`
- Connect providers: `https://exa.ai/docs/reference/agent-api/connect/fiber`, `https://exa.ai/docs/reference/agent-api/connect/similarweb`, `https://exa.ai/docs/reference/agent-api/connect/baselayer`, `https://exa.ai/docs/reference/agent-api/connect/affiliatecom`, `https://exa.ai/docs/reference/agent-api/connect/particle`, `https://exa.ai/docs/reference/agent-api/connect/financialdatasets`, `https://exa.ai/docs/reference/agent-api/connect/jinko`, `https://exa.ai/docs/reference/agent-api/connect/additional-partners`

## Overview

Use `/agent` when a workflow needs more than a single search or extraction call:

- build lists from open-ended criteria, then enrich each result
- research entities across many fields with citations
- run multi-hop tasks such as "find companies, then find decision makers"
- produce structured JSON from a long-running web research task
- continue from a previous run with a follow-up request

For simpler low-latency retrieval, prefer `/search`.

## Request Shape

```json
POST https://api.exa.ai/agent/runs
{
  "query": "Find engineering leaders at AI infrastructure companies that raised a Series A or B in the last 6 months.",
  "effort": "auto",
  "outputSchema": {
    "type": "object",
    "properties": {
      "people": {
        "type": "array",
        "maxItems": 10,
        "items": {
          "type": "object",
          "properties": {
            "name": { "type": "string" },
            "job_title": { "type": "string" },
            "linkedin_url": { "type": "string", "format": "uri" }
          },
          "required": ["name", "job_title", "linkedin_url"]
        }
      }
    },
    "required": ["people"]
  }
}
```

## Core Fields

| Field | Type | Notes |
| --- | --- | --- |
| `query` | string | Required natural-language task |
| `input.data` | object[] | Existing rows to research or enrich |
| `input.exclusion` | object[] | Records or entities Agent should avoid surfacing |
| `outputSchema` | object | JSON Schema for validated `output.structured` |
| `previousRunId` | string | Continue from a completed prior run |
| `effort` | string | `minimal`, `low`, `medium`, `high`, `xhigh`, or `auto` |
| `dataSources` | object[] | Exa Connect providers to attach to the run, for example `{ "provider": "similarweb" }` |

`outputSchema` supports JSON Schema. Bound list outputs with `maxItems` where possible so output size and enrichment cost are predictable.

To request contact information, describe the desired contact fields in the schema. Use standard JSON Schema formats such as `{ "type": "string", "format": "email" }`, `{ "type": "string", "format": "phone" }`, and `{ "type": "string", "format": "uri" }`.

The current Agent spec also accepts `budget.maxCostDollars` for compatibility, but documents it as ignored. Do not treat it as a hard spend cap.

## Lifecycle

`/agent` is asynchronous:

1. Create a run with `POST /agent/runs`.
2. Save the returned `id`, which has the `agent_run_` prefix.
3. Poll `GET /agent/runs/{id}` until `status` is `completed`, `failed`, or `cancelled`, or stream/replay events from `GET /agent/runs/{id}/events`.
4. Read completed output from `output`.

Completed runs include:

- `output.text`: natural-language answer or summary
- `output.structured`: validated JSON matching `outputSchema`, when provided
- `output.grounding`: citations for text or structured fields, when emitted
- `costDollars`: run cost breakdown

## Polling

```bash
RUN_ID="agent_run_01j..."

while true; do
  RUN_JSON="$(curl -s "https://api.exa.ai/agent/runs/$RUN_ID" \
    -H "x-api-key: $EXA_API_KEY")"

  STATUS="$(echo "$RUN_JSON" | jq -r '.status')"
  echo "status=$STATUS"

  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ] || [ "$STATUS" = "cancelled" ]; then
    echo "$RUN_JSON" | jq .
    break
  fi

  sleep 4
done
```

SDK helpers are available:

- Python: `exa.agent.runs.poll_until_finished(run_id, poll_interval=4000)`
- TypeScript: `exa.agent.runs.pollUntilFinished(runId, { pollInterval: 4000 })`

## Streaming and Events

Set `Accept: text/event-stream` when creating a run to receive lifecycle events until a terminal status.

For stored event replay:

```bash
curl -N "https://api.exa.ai/agent/runs/agent_run_01j.../events" \
  -H "Accept: text/event-stream" \
  -H "Last-Event-ID: 1" \
  -H "x-api-key: $EXA_API_KEY"
```

Without SSE, `GET /agent/runs/{id}/events` returns paginated JSON. Use `cursor` for JSON pagination and `Last-Event-ID` for SSE replay.

## Follow-up Runs

Use `previousRunId` to ask follow-up questions over a completed prior run:

```json
{
  "query": "Narrow that list to companies hiring in San Francisco.",
  "previousRunId": "agent_run_01j..."
}
```

The previous run must be completed and belong to the same team. A follow-up is a new create request that returns a new run ID (`agent_run_*`); `previousRunId` supplies prior-run context, it does not reuse the prior run's ID or object.

## Connect Data Sources

Use `dataSources` to attach Exa Connect providers to a run. The agent can call those partner tools alongside Exa web search when the `query` and `outputSchema` explicitly ask for the partner-specific data.

```json
{
  "dataSources": [
    { "provider": "similarweb" },
    { "provider": "fiber_ai" }
  ]
}
```

Use the Connect docs for provider IDs, pricing, and field-specific examples:

- Overview: `https://exa.ai/docs/reference/agent-api/connect/overview`
- Combining providers: `https://exa.ai/docs/reference/agent-api/connect/combining-providers`
- Provider pages: `fiber`, `similarweb`, `baselayer`, `affiliatecom`, `particle`, `financialdatasets`, `jinko`, and `additional-partners` under `/reference/agent-api/connect/`

## SDK Naming

Python uses snake_case:

```python
from exa_py import Exa

exa = Exa()
run = exa.agent.runs.create(
    query="Find five recently launched developer tools for evaluating AI agents.",
    output_schema={
        "type": "object",
        "properties": {
            "tools": {
                "type": "array",
                "maxItems": 5,
                "items": {"type": "object"},
            }
        },
        "required": ["tools"],
    },
)
```

TypeScript uses camelCase:

```typescript
import Exa from "exa-js";

const exa = new Exa();
const run = await exa.agent.runs.create({
  query: "Find five recently launched developer tools for evaluating AI agents.",
  outputSchema: {
    type: "object",
    properties: {
      tools: {
        type: "array",
        maxItems: 5,
        items: { type: "object" }
      }
    },
    required: ["tools"]
  }
});
```

## Critical Pitfalls

- Do not treat `/agent` as a synchronous search endpoint. Create returns a run object; poll or stream before reading final output.
- Do not use `/agent` for simple low-latency SERP retrieval; prefer `/search`.
- Do not leave unbounded arrays in `outputSchema` when enrichment cost or result size matters.
- Use `input.data` for known rows to enrich; do not paste huge row sets into `query`.
- Use `input.exclusion` for records that should not be surfaced again.
- `previousRunId` must reference a completed run.
- `budget.maxCostDollars` is compatibility-only in the current spec; do not rely on it for enforcement.
