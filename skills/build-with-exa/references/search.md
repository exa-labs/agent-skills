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
- Recommended request
- Other request parameters
- Search types
- Nested contents options
- Structured output
- Category
- Streaming and response shape
- Critical pitfalls

## Overview

Use the search endpoint when you need:

- general semantic web retrieval
- synthesized output controlled by `systemPrompt` and `outputSchema`
- content extraction attached to search results through the nested `contents` object

For most new integrations, this is the default Exa surface.
For list-building and enrichment workflows, use the Agent API (`/agent`), not this endpoint.

## Recommended Request

A bare query returns only result metadata (title, URL, author, published date) with no page content. Most integrations need content, so the recommended request adds token-efficient highlights — and nothing else:

```json
POST https://api.exa.ai/search
{
  "query": "latest developments in LLMs",
  "type": "auto",
  "contents": {
    "highlights": true
  }
}
```

| Parameter | Type | Notes |
| --- | --- | --- |
| `query` | string | Required natural-language query |
| `type` | string | `auto` is the server default; stating it explicitly is fine, other modes need a task reason |
| `contents` | object | Content extraction per result; `{ "highlights": true }` is the recommendation, not a server default — omit `contents` and results carry no content |

Encode intent in the query itself: subject, constraints, time window, and source preferences all belong in natural language before they belong in request parameters.

## Other Request Parameters

Every parameter below changes behavior away from the server defaults. Add one only when the task requires it.

| Parameter | Type | Add only when |
| --- | --- | --- |
| `numResults` | integer | A specific result count is an intentional product decision. The server default is 10. |
| `category` | string | The user explicitly requests category-constrained retrieval. See Category. |
| `includeDomains` | string[] | The user explicitly requests a hard allowlist and supplies or approves its contents. Supports paths and wildcards such as `openai.com/blog` or `*.substack.com`. |
| `excludeDomains` | string[] | The user explicitly requests a hard blocklist and supplies or approves its contents. Do not convert source preferences or examples into filters; use query phrasing or `systemPrompt`. |
| `userLocation` | string | The task is location-sensitive. Two-letter ISO country code. |
| `systemPrompt` | string | The task uses synthesized output and needs behavior, emphasis, or source-preference guidance. |
| `outputSchema` | object | The task requires structured output in `output.content`. |
| `stream` | boolean | The caller consumes typed SSE chunks for synthesized output. |

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

`auto` is the server default. Stay on it unless the use case clearly prioritizes real-time speed, deeper reasoning, or configuration control.
`outputSchema` works across search types, so do not pick a deep variant only because you want structured output.

## Nested Contents Options

On the search endpoint, all content-extraction controls live inside `contents`. The preferred default is bare highlights:

```json
{
  "query": "battery breakthroughs",
  "contents": {
    "highlights": true
  }
}
```

### `contents` Parameters

`contents.highlights: true` is the recommended extraction mode; the server returns no content at all unless `contents` is sent. Every other option below needs an explicit task requirement.

| Parameter | Type | Add only when |
| --- | --- | --- |
| `contents.highlights` | boolean or object | Recommended as bare `true`. Object options such as `maxCharacters` require an explicit budget requirement; avoid values below about 400 because they truncate too aggressively for downstream LLM use. |
| `contents.text` | boolean or object | Downstream logic truly needs broad page context. Object form supports `maxCharacters`, `includeHtmlTags`, `verbosity`, `includeSections`, `excludeSections`. |
| `contents.summary` | boolean or object | The user explicitly requests Exa-side per-result synthesis. Each result adds its own LLM call. A summarized final product is not sufficient justification; use highlights and synthesize downstream. |
| `contents.maxAgeHours` | integer | The task states a content-freshness requirement. Caps cached page content age before live crawl. `0` forces live crawl, `-1` is cache only. |
| `contents.livecrawlTimeout` | integer | Live crawling is in use and slow pages must not block the request. Milliseconds. |
| `contents.subpages` | integer | The task requires crawling linked subpages per result. |
| `contents.subpageTarget` | string or string[] | `subpages` is in use and needs focusing. |
| `contents.extras.links` | integer | The task requires extracted links. |
| `contents.extras.imageLinks` | integer | The task requires extracted image URLs. |

### Text vs Highlights vs Summary

Pick exactly one:

- `highlights` is the recommended mode for agent workflows and multi-step chains
- `text` only when downstream logic truly needs broad page context
- `summary` only when the user explicitly requests Exa-side per-result synthesis

Do not stack `text`, `highlights`, and `summary` in one request. `summary` adds a per-result LLM call, so N results means N extra synthesis steps. Bare `highlights: true` auto-selects an appropriate excerpt length per page, so there is nothing to tune in the recommended case.

## Structured Output

`systemPrompt` and `outputSchema` do different jobs:

- `systemPrompt` controls behavior, emphasis, and source preferences
- `outputSchema` controls the shape of `output.content`

```python
from exa_py import Exa

exa = Exa(api_key="YOUR_EXA_API_KEY")
result = exa.search(
    "Who leads OpenAI's safety work?",
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

## Category

Do not set `category` unless the user explicitly requests category-constrained retrieval. Mapping task nouns to categories — news tasks to `news`, people tasks to `people`, paper tasks to `publication` — is a mistake: the default index already handles those queries, and the query text itself is the right place to express the topic.

When a user does explicitly request it, documented values include `company`, `people`, `publication`, `news`, `personal site`, and `financial report`. Never invent categories such as `github`, `documentation`, `qa`, or `pdf`. For coding queries, prefer the `/context` endpoint or plain `/search`.

### People and Company Routing

List-building and enrichment workflows do not belong here. Finding stakeholders, sourcing candidates, mapping companies, or enriching entity rows are Agent API workflows: use `/agent` (see [agent.md](agent.md)). `category: "people"` and `category: "company"` are only for retrieving raw people or company documents as search results.

When those categories are legitimately in use, they restrict which filters are valid:

- `people` does not support date or crawl-date filters, and does not support `excludeDomains`
- for `people`, `includeDomains` only accepts LinkedIn domains
- `company` does not support date or crawl-date filters
- `company` supports `excludeDomains`
- unsupported category/filter combinations return a 400 error

For `people` search in particular, push the filtering logic into the natural-language query.

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

1. Do not decorate the recommended request without reason. Send `query`, `type: "auto"`, and `contents.highlights: true`; add anything else only when the task explicitly requires it.
2. Do not send a boilerplate `numResults`; the server default is 10, and a different count is a product decision.
3. Do not set `category` or domain filters without an explicit user request. Source preferences belong in query phrasing or `systemPrompt`.
4. Do not place `text`, `highlights`, or `summary` at the top level on `/search`.
5. Do not stack `text`, `highlights`, and `summary` on the same call. Pick one. `summary` fires a per-result LLM call and requires an explicit user request.
6. Do not use `category: "people"` or `category: "company"` for list-building or enrichment; those workflows use `/agent` (see [agent.md](agent.md)).
7. Do not use `tokensNum` on `/search`; text sizing belongs under `contents.text.maxCharacters` when the task requires a cap.
8. Treat `useAutoprompt`, `numSentences`, and `highlightsPerUrl` as deprecated; do not add them to new examples.
9. Use `contents.maxAgeHours` instead of `livecrawl`.
10. Never invent `category` values such as `github`, `documentation`, `qa`, or `pdf`.