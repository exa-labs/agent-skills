---
name: company-research
description: Company research using Exa. Finds company info, competitors, news, financials, LinkedIn profiles, builds company lists. Use when researching companies, doing competitor analysis, market research, or building company lists.
context: fork
---

# Company Research

## Tool Selection (Critical)

Two Exa surfaces, two jobs:

- **Exa Agent** (`agent_create_run` / `agent_wait_for_run` / `agent_get_run_output`) — the default for company research. Use it for deep dives, competitor analysis, multi-angle research (product + funding + news + people), and building company lists. One Agent run handles query decomposition, multi-step searching, and synthesis internally — do not orchestrate many manual searches for work an Agent run covers.
- **`web_search_advanced_exa`** — quick, low-latency lookups: a fast `category: "company"` discovery pass, a single news check, or finding a homepage.

Do NOT use other Exa tools.

## Deep Dives and Lists: Exa Agent

Agent runs are async: create the run, wait for it, then read the output.

1. `agent_create_run` with a natural-language `query` and, when you want repeatable structure, an `outputSchema` (bound arrays with `maxItems`). Returns an `agent_run_...` ID.
2. `agent_wait_for_run` until the run is `completed` (call again if still running).
3. `agent_get_run_output` — read `output.text` or `output.structured`, plus `output.grounding` citations.

Useful inputs: `systemPrompt` (source preferences, dedup rules), `input.exclusion` (companies to avoid), `previousRunId` (follow-up runs), `effort` (`"auto"` default; `"high"` for hard research).

### Example: company deep dive

```
agent_create_run {
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
agent_create_run {
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

Never dump raw search results into main context. Spawn Task agents for Advanced Search calls; for Agent runs, go straight from `output.structured` to the final answer.

## Browser Fallback

Fall back to Claude in Chrome only when content is auth-gated or requires JavaScript rendering.

## Output Format

Return:
1) Results (structured list; one company per row)
2) Sources (URLs; 1-line relevance each — use `output.grounding` from Agent runs)
3) Notes (uncertainty/conflicts)

## References

- Exa Agent guide: https://docs.exa.ai/reference/agent-api-guide
- Company Search reference: https://docs.exa.ai/reference/verticals/company-for-coding-agents
- Exa MCP setup: https://docs.exa.ai/reference/exa-mcp
- Full docs for LLMs: https://docs.exa.ai/llms.txt
