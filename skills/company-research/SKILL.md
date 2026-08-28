---
name: company-research
description: Research companies and markets with Exa, including competitors, funding, news, financials, and leadership. Use when doing a company deep dive, competitor analysis, or market research; use lead-generation instead for ICP-based prospect lists and CSV output.
---

# Company Research

## Tool Selection (Critical)

Two Exa surfaces, two jobs:

- **Exa Agent** (`agent_run`) — the default for company research. Use it for deep dives, competitor analysis, multi-angle research (product + funding + news + people), and building company lists. One Agent run handles query decomposition, multi-step searching, and synthesis internally — do not orchestrate many manual searches for work an Agent run covers.
- **`web_search_advanced_exa`** — quick, low-latency lookups: a fast `category: "company"` discovery pass, a single news check, or finding a homepage.

Do NOT use other Exa tools.

## Deep Dives and Lists: Exa Agent

Agent runs may stream to completion in one call. If a run outlives the MCP call window, continue waiting with its returned run ID.

1. Call `agent_run` with a natural-language `query` and, when you want repeatable structure, an `outputSchema` (bound arrays with `maxItems`).
2. If it returns `status: "running"` with a `runId`, call `agent_run` again with only that `runId` until `outputReady` is true.
3. Read `output.text` or `output.structured`, plus `output.grounding` citations, from the `agent_run` result.

Useful inputs: `systemPrompt` (source preferences, dedup rules), `input.exclusion` (companies to avoid), `previousRunId` (a new follow-up run based on a completed run), `effort` (`"low"` default; `"auto"` or `"high"` for more depth).

### Example: company deep dive

```
agent_run {
  "query": "Research Anthropic: product lines, funding history and valuation, key executives, main competitors, and notable news from the last 6 months.",
  "effort": "auto",
  "outputSchema": {
    "type": "object",
    "properties": {
      "overview": { "type": "string" },
      "funding": { "type": "array", "maxItems": 10, "items": { "type": "object", "properties": { "round": { "type": "string" }, "amount": { "type": "string" }, "date": { "type": "string" } }, "required": ["round"] } },
      "competitors": { "type": "array", "maxItems": 10, "items": { "type": "string" } },
      "key_people": { "type": "array", "maxItems": 10, "items": { "type": "object", "properties": { "name": { "type": "string" }, "title": { "type": "string" } }, "required": ["name", "title"] } }
    },
    "required": ["overview", "competitors"]
  }
}
```

### Example: build a company list

```
agent_run {
  "query": "Find 25 AI infrastructure startups headquartered in San Francisco. For each, include what they build and their latest funding stage.",
  "effort": "auto",
  "outputSchema": {
    "type": "object",
    "properties": {
      "companies": {
        "type": "array",
        "maxItems": 25,
        "items": {
          "type": "object",
          "properties": {
            "name": { "type": "string" },
            "website": { "type": "string", "format": "uri" },
            "description": { "type": "string", "description": "in 12 words or less" },
            "funding_stage": { "type": "string" }
          },
          "required": ["name", "website", "description"]
        }
      }
    },
    "required": ["companies"]
  }
}
```

## Quick Lookups: Advanced Search

Use `web_search_advanced_exa` when a single fast search answers the question. Tune `numResults` to intent (a few → 10-20; comprehensive → 50-100; specified → match it).

### Categories

- `company` → homepages, rich metadata (headcount, location, funding, revenue)
- `news` → press coverage, announcements
- `people` → public professional profiles
- No category (`type: "auto"`) → general web results, broader context

Default to `type: "auto"`. Prefer `highlights` for content extraction; do not stack text + highlights + summary in one call.

### Category-Specific Filter Restrictions

Unsupported category/filter combinations return 400 errors:

- `category: "company"` does not support published-date or crawl-date filters, `excludeDomains`, or exact-text filters; express constraints like "founded after 2020" in the query instead
- `category: "people"` does not support published-date, crawl-date, domain, or exact-text filters; put all filtering in the natural-language query
- Without a category (or with `news`), domain and date filters work fine

### Examples

Discovery pass:
```
web_search_advanced_exa {
  "query": "AI infrastructure startups San Francisco",
  "category": "company",
  "numResults": 20,
  "type": "auto"
}
```

News check:
```
web_search_advanced_exa {
  "query": "Anthropic AI safety",
  "category": "news",
  "numResults": 15,
  "startPublishedDate": "2025-01-01"
}
```

Key people:
```
web_search_advanced_exa {
  "query": "VP Engineering AI infrastructure",
  "category": "people",
  "numResults": 20
}
```

## Token Isolation

Do not dump raw search results into the final response. When the host supports isolated subtasks and the work is large enough to justify them, use that isolation for independent Advanced Search passes. For Agent runs, synthesize from `output.structured` and preserve the relevant grounding citations.

## Browser Fallback

Use an authenticated or JavaScript-capable browser only when the available retrieval tools cannot access required content and the host provides one.

## Failure Handling

- On authentication, connection, or rate-limit errors, surface the concrete failure and required setup; do not switch providers silently.
- If an Agent run reaches `failed` or `cancelled`, inspect its error and retry at most once after correcting the query or schema.
- If a quick search is thin or off-topic, try one materially different query angle before reporting limited coverage.
- Preserve conflicting company facts with source attribution rather than selecting one without evidence.

## Red Flags

- Using quick search for a multi-angle deep dive that needs synthesis.
- Returning company claims without URLs or grounding.
- Treating funding, headcount, or leadership data as current without checking dates.
- Calling a company list “complete” when the requested count or constraints were not met.

## Output Format

Return:
1) Results (structured list; one company per row)
2) Sources (URLs; 1-line relevance each — use `output.grounding` from Agent runs)
3) Notes (uncertainty/conflicts)

## Verification

- Confirm every material claim has a supporting URL or Agent grounding entry.
- Check that requested companies, fields, dates, and geographic constraints are represented.
- Deduplicate company entities and note unresolved conflicts or missing coverage.
- For structured output, verify required fields and array bounds before presenting it.

## References

- Exa Agent guide: https://docs.exa.ai/reference/agent-api-guide
- Company Search reference: https://docs.exa.ai/reference/verticals/company-for-coding-agents
- Exa MCP setup: https://docs.exa.ai/reference/exa-mcp
- Full docs for LLMs: https://docs.exa.ai/llms.txt
