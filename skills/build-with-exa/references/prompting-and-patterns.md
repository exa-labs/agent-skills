# Prompting and Patterns Reference

Durable usage patterns for Exa queries, output control, and content retrieval.

## Canonical Docs Links

- Base docs URL: `https://exa.ai/docs`
- Search best practices: `/reference/search-best-practices`
- Contents best practices: `/reference/contents-best-practices`
- Answer reference: `/reference/answer`
- Context reference: `/reference/context`

## Contents

- Query formulation
- `systemPrompt` vs `outputSchema`
- Highlights vs text
- Freshness patterns
- Endpoint-selection patterns
- Tool calling pattern
- Low-latency recipe
- Structured output patterns

## Query Formulation

Exa works best with explicit natural-language intent. Good queries usually encode:

- subject
- constraint
- time window if freshness matters
- source preference if domain-specific sources matter

Examples:

- `"recent battery recycling policy changes in the EU"`
- `"AI startups that raised Series A funding in 2026"`
- `"senior ML engineers at fintech companies"`

## `systemPrompt` vs `outputSchema`

Use them together, but give them different jobs:

- `systemPrompt`: source preferences, output style, dedup behavior, emphasis
- `outputSchema`: exact response shape

Pattern:

```json
{
  "query": "Compare recent frontier model launches",
  "systemPrompt": "Prefer official vendor announcements and avoid duplicate reporting.",
  "outputSchema": {
    "type": "object",
    "properties": {
      "summary": {"type": "string"},
      "models": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["summary", "models"]
  }
}
```

## Highlights vs Text

Pick exactly one:

- `highlights` is the recommended mode on `/search`: bare `highlights: true` auto-selects an appropriate excerpt length per page, anchored to the search query, so there is nothing to tune
- on `/contents` there is no search query to anchor to, so the default is full `text` (also the server default); when using highlights there, provide the object form with a `query`
- use `text` on `/search` only when broad page context is necessary for downstream logic
- use `summary` only when the user explicitly requests Exa-side per-result LLM compression; a summarized final product is not sufficient justification

Do not stack `text`, `highlights`, and `summary`. `summary` adds a per-result LLM call, which means N results create N extra synthesis steps and higher latency. Combining `text` and `highlights` also increases billing for two views of the same page.

## Freshness Patterns

Use `maxAgeHours` to control how old cached page content may be before Exa livecrawls the page.

It is not a publication-date filter. For publication recency, phrase the time window in the query or use `startPublishedDate` / `endPublishedDate` on `/search`.

- omit it for the default balanced behavior
- set a small value when the extracted page content must be near-current
- set `0` only when the app truly requires live crawling every time
- set `-1` when the latency-critical path should stay cache-only

Freshness is most important on:

- news
- company announcements
- live policy or market updates

It matters less on:

- historical content
- stable docs
- evergreen educational material

## Endpoint-Selection Patterns

- Question-first UI with no app-side LLM: consider `/answer`
- App already has a chat LLM, or search-results-first UI: use `/search`
- Known URLs: use `/contents`
- Code retrieval: use `/context`
- Repeated recurring tracking: use `/monitors`
- List-building and enrichment: use `/agent`

## Tool Calling Pattern

For existing agent loops, the common Exa integration is to expose `exa.search` as a tool the LLM picks. This is different from the OpenAI-compatible endpoints in [openai-compat.md](openai-compat.md): tool calling keeps your existing LLM provider, the compat endpoints replace it.

OpenAI tool definition:

```python
TOOLS = [{
    "type": "function",
    "function": {
        "name": "exa_search",
        "description": "Search the live web and return the most relevant URLs and content. Use for fresh information beyond the model's training data.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
}]
```

Anthropic tool definition:

```python
TOOLS = [{
    "name": "exa_search",
    "description": "Search the live web and return the most relevant URLs and content. Use for fresh information beyond the model's training data.",
    "input_schema": {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
}]
```

The tool body is the same Exa call either way:

```python
def exa_search(query: str):
    return exa.search(query, type="auto", contents={"highlights": True})
```

Design tips:

- Say "search the live web" in the description so the LLM picks Exa for fresh-info queries
- Keep `query` the only required field; let the LLM compose natural-language queries
- Do not expose or hardcode categories, domain filters, or result counts the user never asked for
- Return `highlights` rather than full `text` to keep tool-result tokens small
- Add separate `exa_answer` or `exa_get_contents` tools instead of overloading one search tool when the agent also needs grounded answers or known-URL extraction
- Echo `tool_call_id` (OpenAI) or `tool_use_id` (Anthropic) back exactly; mismatches fail silently

## Low-Latency Recipe

For a latency-critical UX, start with:

```json
{
  "type": "instant",
  "contents": {
    "highlights": true,
    "maxAgeHours": -1
  }
}
```

This keeps the path fast: `instant` minimizes retrieval latency, bare `highlights` keeps payloads compact, and `maxAgeHours: -1` skips live-crawl overhead by using cache only.

## Structured Output Patterns

Keep schemas:

- small
- bounded
- explicit

Prefer:

- 1 to 5 root fields
- simple arrays or flat objects

Avoid:

- deeply nested schemas
- loose catch-all maps
- asking the model to invent citation fields that Exa already provides elsewhere
