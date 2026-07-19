---
name: lead-generation
description: Generate enriched lead lists using Exa Agent. Finds companies matching an ICP, enriches with signals/news/scores, and outputs CSV. Use when generating leads, building prospect lists, finding companies to sell to, doing outbound research, or ICP-based company discovery. Triggers on "leads", "lead gen", "prospect list", "find companies", "ICP", "outbound list".
---

# Lead Generation with Exa Agent

Generate enriched lead lists using the Exa Agent API. An Agent run is an asynchronous, multi-step web research task: you describe the list you want plus an output schema, and Exa handles query decomposition, searching, verification, enrichment, and structured output internally. You do NOT need to orchestrate parallel searches, subagents, or manual deduplication.

For very large or continuously maintained lead lists with per-item verification, consider Exa Websets instead: https://docs.exa.ai/websets/api/overview

## Prerequisites

This skill requires the Exa MCP server with the Agent tool enabled. Use the `agent_tools` URL selection alias to enable `agent_run`.

If the Agent tools are not available, tell the user:

> You need the Exa MCP server installed with the Agent tools and your API key.
> Instructions: https://docs.exa.ai/reference/exa-mcp

Then stop.

## Tool Restriction

Use `agent_run`, plus Write and Bash (for CSV output). Do NOT use generic web search for the lead list itself.

## Workflow

```
1. Confirm the ICP with the user (one small Agent run if research is needed)
2. Call `agent_run` with an outputSchema
3. If the result is still running, call `agent_run` again with its `runId`
4. Read `output.structured` from the `agent_run` result
5. Write the CSV
6. Optional: expand with follow-up runs (previousRunId + input.exclusion)
```

## Step 1: Understand the ICP

When the user says something like "Make a list of 200 leads for [company]", first establish the Ideal Customer Profile. If the user already described the ICP, confirm it. If not, run one small Agent run to research it:

```
agent_run {
  "query": "Research {company_name}: what they sell, who their existing customers are, and what their ideal customer profile is.",
  "effort": "low",
  "outputSchema": {
    "type": "object",
    "properties": {
      "company_description": { "type": "string", "description": "What the company does in 2 sentences or less" },
      "icp_description": { "type": "string", "description": "Concise ICP description that clearly defines target companies" },
      "sub_verticals": { "type": "array", "maxItems": 10, "items": { "type": "string" }, "description": "Sub-verticals breaking down the ICP" },
      "useful_enrichments": { "type": "array", "maxItems": 8, "items": { "type": "string" }, "description": "Enrichment columns useful for filtering high-signal companies" }
    },
    "required": ["company_description", "icp_description", "sub_verticals", "useful_enrichments"]
  }
}
```

Present the ICP to the user and confirm:

- Is the ICP description accurate?
- Any companies to exclude (competitors, existing customers)?
- How many leads do they want? (default 200)
- Any specific enrichment columns they care about?

## Step 2: Create the Lead-Gen Run

Design an `outputSchema` with a bounded `companies` array. Keep schemas small, flat, and explicit; always bound arrays with `maxItems`.

**Core fields to always include:**

- `company_name` (string)
- `website` (string)
- `product_description` (string, "in 12 words or less")
- `icp_fit_score` (integer, 1-10)
- `icp_fit_reasoning` (string, "compelling one-liner in 20 words or less")

Add enrichment fields tailored to the campaign (funding stage, headcount range, headquarters, hiring signals, etc.). Give string fields a length hint in their description to keep CSV output clean.

Use the run inputs for the pieces the old manual pipeline handled by hand:

- `query` — describe the list: the ICP, geography, stage, and how many companies you want
- `outputSchema` — the exact structure back, with `maxItems` bounding the companies array
- `systemPrompt` — scoring rules, source preferences, dedup/exclusion emphasis
- `input.exclusion` — companies to avoid (competitors, existing customers, results from earlier runs)
- `effort` — `"low"` by default; `"auto"`, `"high"`, or `"xhigh"` for large or hard lists

Example:

```
agent_run {
  "query": "Find 100 companies matching this ICP: {icp_description}. Prioritize {sub_verticals}. For each company, score ICP fit 1-10 for {user_company}.",
  "effort": "low",
  "systemPrompt": "Prefer official company sites and recent funding announcements. Do not include duplicates or subsidiaries of the same parent company.",
  "input": {
    "exclusion": [
      { "company_name": "{competitor_1}" },
      { "company_name": "{existing_customer_1}" }
    ]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "companies": {
        "type": "array",
        "maxItems": 100,
        "items": {
          "type": "object",
          "properties": {
            "company_name": { "type": "string" },
            "website": { "type": "string", "format": "uri" },
            "product_description": { "type": "string", "description": "in 12 words or less" },
            "icp_fit_score": { "type": "integer", "description": "1-10" },
            "icp_fit_reasoning": { "type": "string", "description": "one-liner in 20 words or less" }
          },
          "required": ["company_name", "website", "product_description", "icp_fit_score", "icp_fit_reasoning"]
        }
      }
    },
    "required": ["companies"]
  }
}
```

`agent_run` returns the completed result when possible. If it returns `status: "running"` with an `agent_run_...` ID, save the ID and continue with `agent_run` using only `runId`.

## Step 3: Wait and Read Output

1. If the run is still running, call `agent_run` with its `runId` until `outputReady` is true or the run reaches a terminal status (`failed` or `cancelled`).
2. Read the companies from `output.structured`, citations from `output.grounding`, and the run cost from `costDollars` in the `agent_run` result.

Do not paste the full raw output into the conversation — go straight to CSV.

## Step 4: Write the CSV

Write `output.structured.companies` to `{target_company}_leads_{YYYY-MM-DD}.csv`, sorted by `icp_fit_score` descending. Join any array fields with " | ". Use Python's `csv.writer` (handles quoting/escaping) via Bash, or Write directly for small lists.

Print a summary:

```
## Lead Generation Complete

- Total leads: {count}
- ICP score distribution: 8-10: {N} | 5-7: {N} | 1-4: {N}
- Run ID: {agent_run_id}
- Cost: ${costDollars}
- Output: {filename}
```

## Step 5: Expanding the List

If the user wants more leads than one run returned:

- Create a new follow-up run with `previousRunId` set to the completed run's ID, asking for additional companies
- Put the company records already collected into `input.exclusion` so the new run avoids them
- Append the new results to the CSV and re-deduplicate by normalized company name (strip "Inc"/"Ltd"/etc., case-insensitive)

For lists in the many hundreds, run a few runs sequentially this way rather than one giant run, and confirm scope with the user first: "This will require ~{N} Agent runs. Proceed?"

## Handling Failures

- If a run ends `failed`, read the error from the `agent_run` result, adjust the query or schema, and retry once with different wording
- If a client cancellation is needed, abort the in-progress `agent_run` call
- If results are consistently below the requested count, narrow the ICP into 2-3 sub-vertical runs instead of one broad run

## MCP Configuration

Requires an Exa API key. Get yours at https://dashboard.exa.ai/api-keys

```json
{
  "servers": {
    "exa": {
      "type": "http",
      "url": "https://mcp.exa.ai/mcp?tools=agent_tools",
      "headers": {
        "x-api-key": "YOUR_EXA_API_KEY"
      }
    }
  }
}
```

## References

- Exa Agent guide: https://docs.exa.ai/reference/agent-api-guide
- Exa MCP setup: https://docs.exa.ai/reference/exa-mcp
- Websets (verified list-building at scale): https://docs.exa.ai/websets/api/overview
- Full docs for LLMs: https://docs.exa.ai/llms.txt
