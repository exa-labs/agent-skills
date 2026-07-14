# Search Endpoint Reference

Primary semantic retrieval surface for new Exa integrations via `POST /search`.

## Canonical Docs Links

- Base docs URL: `https://exa.ai/docs`
- Search reference: `/reference/search`
- Search coding-agent reference: `/reference/search-api-guide-for-coding-agents`
- Search best practices: `/reference/search-best-practices`
- Content freshness: `/reference/livecrawling-contents`

## Contents

- Overview
- Request shape
- Search types
- Nested contents options
- Structured output
- Category caveats
- Streaming and response shape
- Critical pitfalls

## Overview

Use the search endpoint when you need:

- general semantic web retrieval
- category-aware search such as `people`, `company`, `news`, or `financial report`
- synthesized output controlled by `systemPrompt` and `outputSchema`
- content extraction attached to search results through the nested `contents` object

For most new integrations, this is the default Exa surface.
For coding queries, prefer `type: "fast"` or the `/context` endpoint rather than inventing category filters like `github`.

## Request Shape

```json
POST https://api.exa.ai/search
{
  "query": "latest developments in LLMs",
  "type": "auto",
  "numResults": 10,
  "contents": {
    "highlights": true
  }
}
```

### Core Request Parameters

| Parameter | Type | Notes |
| --- | --- | --- |
| `query` | string | Required natural-language query |
| `type` | string | Primary search mode: `auto`, `fast`, `instant`, `deep-lite`, `deep`, `deep-reasoning` |
| `numResults` | integer | Default 10; practical limits depend on plan and mode |
| `category` | string | Optional specialized index such as `company`, `people`, `research paper`, `news`, `personal site`, `financial report` |
| `includeDomains` | string[] | Restrict results to specific domains. Also support path filters and wildcard patterns such as `openai.com/blog` or `*.substack.com`. |
| `excludeDomains` | string[] | Exclude domains, paths, or wildcard patterns. Specialized categories have extra caveats; see Category Caveats. |
| `userLocation` | string | Two-letter ISO country code |
| `systemPrompt` | string | Instructions for synthesized output and deep-search planning |
| `outputSchema` | object | JSON Schema for `output.content` |
| `stream` | boolean | Switches response to typed SSE chunks. |
| `contents` | object | Nested content extraction options for each result |

## Search Types

Use Exa's primary search types as latency/quality presets:

| Type | Best For | Tradeoff |
| --- | --- | --- |
| `auto` | General default | Best default balance of speed and quality |
| `fast` | Low-latency apps | Faster than `auto`, slightly less headroom for synthesis-heavy work |
| `instant` | Real-time apps | Lowest latency path |
| `deep-lite` | Lightweight synthesized output | More reasoning and synthesis than `auto` |
| `deep` | Multi-step synthesis | Higher latency, better for structured or research-like output |
| `deep-reasoning` | Hardest research tasks | Highest reasoning depth and highest latency |

Use `auto` unless the use case clearly prioritizes real-time speed or deeper reasoning.
`outputSchema` works across search types, so do not pick a deep variant only because you want structured output.

## Nested Contents Options

On the search endpoint, all content-extraction controls live inside `contents`.

```json
{
  "query": "battery breakthroughs",
  "contents": {
    "highlights": true,
    "maxAgeHours": 24
  }
}
```

### `contents` Parameters

| Parameter | Type | Notes |
| --- | --- | --- |
| `contents.text` | boolean or object | Full page text as markdown; object form supports `maxCharacters`, `includeHtmlTags`, `verbosity`, `includeSections`, `excludeSections` |
| `contents.highlights` | boolean or object | Token-efficient excerpts; `true` is the safest default |
| `contents.summary` | boolean or object | LLM-generated per-result summary; each result adds its own synthesis step, so use sparingly |
| `contents.maxAgeHours` | integer | Normative freshness control; `0` forces live crawl, `-1` is cache only |
| `contents.livecrawlTimeout` | integer | Live crawl timeout in milliseconds |
| `contents.subpages` | integer | Crawl additional subpages per result |
| `contents.subpageTarget` | string or string[] | Text used to choose which subpages matter |
| `contents.extras.links` | integer | Extract links from each page |
| `contents.extras.imageLinks` | integer | Extract image URLs from each page |

### Text vs Highlights vs Summary

- Start with one by default:
- Use `highlights` for agent workflows and multi-step chains
- Use `text` when downstream logic truly needs broad page context
- Use `summary` only when you explicitly want Exa-side per-result synthesis

Avoid stacking `text`, `highlights`, and `summary` in one request unless the use case clearly needs multiple views of the same page. `summary` adds a per-result LLM call, so N results means N extra synthesis steps. `highlights: true` auto-selects an appropriate excerpt length per page. Only set `highlights.maxCharacters` for fixed budgets, and avoid values below about 400 because they usually truncate too aggressively for downstream LLM use.

## Structured Output

`systemPrompt` and `outputSchema` do different jobs:

- `systemPrompt` controls behavior, emphasis, and source preferences
- `outputSchema` controls the shape of `output.content`

```python
from exa_py import Exa

exa = Exa(api_key="YOUR_EXA_API_KEY")
result = exa.search(
    "Who leads OpenAI's safety work?",
    type="auto",
    system_prompt="Prefer official sources and avoid duplicate results.",
    output_schema={
        "type": "object",
        "properties": {
            "leader": {"type": "string"},
            "title": {"type": "string"}
        },
        "required": ["leader", "title"]
    },
    contents={"highlights": True}
)
print(result.output.content if result.output else None)
```

Keep schemas small and explicit. Exa's structured output guidance favors compact, bounded schemas over deeply nested shapes. Use deeper search variants when the retrieval task itself needs more reasoning or synthesis depth.

## Category Caveats

Stick to documented category values only. Do not invent categories such as `github`, `documentation`, `qa`, or `pdf`. For coding queries, prefer `type: "fast"` or the `/context` endpoint instead of category filters.

The specialized `company` and `people` categories have extra restrictions:

- `people` does not support date or crawl-date filters, and does not support `excludeDomains`
- for `people`, `includeDomains` only accepts LinkedIn domains
- `company` does not support date or crawl-date filters
- `company` supports `excludeDomains`
- unsupported category/filter combinations return a 400 error

For `people` search in particular, push more of the filtering logic into the natural-language query.

## Streaming and Response Shape

Streaming is currently used only for synthesized output. When `stream: true` is paired with `outputSchema`, the search endpoint returns `text/event-stream` instead of a single JSON payload. Without `outputSchema`, it returns the normal JSON search response even when `stream` is `true`. Robust streaming consumers should branch on the chunk `type`. Current public chunk types are `text-delta`, `grounding`, `results`, `stream-reset`, `done`, and `error`.

Non-streaming responses typically include:

- `requestId`
- `results`
- optional `output`
- `costDollars`
- `searchTime`

Prefer reading citations and grounding from `output.grounding` when using structured or synthesized output.

## Critical Pitfalls

1. Do not place `text`, `highlights`, or `summary` at the top level on `/search`.
2. Do not stack `text`, `highlights`, and `summary` on the same call. Pick one. `summary` fires a per-result LLM call.
3. Do not use `tokensNum` on `/search`; use `contents.text.maxCharacters` if you need to cap text size.
4. Treat `useAutoprompt`, `numSentences`, and `highlightsPerUrl` as deprecated; do not add them to new examples.
5. Prefer `contents.maxAgeHours` over older `livecrawl` guidance.
6. Stick to documented `category` values. Do not invent values such as `github`, `documentation`, `qa`, or `pdf`.
7. Be careful with specialized categories, especially `people` and `company`, because some filters are invalid there.
