# Contents Endpoint Reference

Known-URL extraction surface via `POST /contents`.

## Canonical Docs Links

- Base docs URL: `https://exa.ai/docs`
- Contents reference: `/reference/get-contents`
- Contents coding-agent reference: `/reference/contents-api-guide-for-coding-agents`
- Contents best practices: `/reference/contents-best-practices`
- Content freshness: `/reference/livecrawling-contents`

## Contents

- Overview
- Request shape
- Top-level content fields
- Freshness controls
- Response and statuses
- Critical pitfalls

## Overview

Use the contents endpoint when:

- you already know the URLs
- you need clean extraction without first running a search query
- freshness and crawl behavior matter enough to control directly
- you want the search endpoint and contents endpoint separated into two explicit calls

## Request Shape

```json
POST https://api.exa.ai/contents
{
  "urls": ["https://arxiv.org/abs/2307.06435"],
  "highlights": {
    "query": "methodology"
  }
}
```

### Core Request Parameters

| Parameter | Type | Notes |
| --- | --- | --- |
| `urls` | string[] | Primary way to pass known URLs |
| `ids` | string[] | Backwards-compatible alias for document IDs from prior Exa calls |
| `text` | boolean or object | Top-level text extraction control |
| `highlights` | boolean or object | Top-level highlights extraction control |
| `summary` | boolean or object | Top-level summary extraction control |
| `maxAgeHours` | integer | Normative freshness control |
| `livecrawlTimeout` | integer | Timeout in milliseconds |
| `subpages` | integer | Crawl linked subpages |
| `subpageTarget` | string or string[] | Focus which subpages to crawl |
| `extras` | object | Extra link and image extraction |

## Top-Level Content Fields

This is the most important shape difference in the Exa platform:

- on the search endpoint, content fields are nested inside `contents`
- on the contents endpoint, `text`, `highlights`, and `summary` are top-level request fields

```python
from exa_py import Exa

exa = Exa(api_key="YOUR_EXA_API_KEY")
result = exa.get_contents(
    ["https://docs.exa.ai"],
    highlights=True
)
```

### Content Field Behavior

| Field | Best For | Notes |
| --- | --- | --- |
| `text` | Full extraction | Supports `maxCharacters`, `includeHtmlTags`, `verbosity`, `includeSections`, `excludeSections` |
| `highlights` | Token-efficient excerpts | Good default for agent pipelines |
| `summary` | Per-page compression | Each page adds its own synthesis step, so use only when you explicitly need Exa-side summaries |

Pick one of `text`, `highlights`, or `summary` by default. Stacking them is unnecessary. `summary` adds a per-page LLM call, and combining `text` with `highlights` increases billing for two views of the same page.

## Freshness Controls

Use `maxAgeHours` as the normative control for new integrations:

| Value | Behavior |
| --- | --- |
| omitted | Default behavior; cached content first, crawl fallback when needed |
| positive integer | Accept cache up to that age, then live crawl |
| `0` | Always live crawl |
| `-1` | Cache only |

Set `livecrawlTimeout` whenever live crawling matters so slow pages do not block the whole request longer than expected.

Do not send `livecrawl` and `maxAgeHours` together; prefer `maxAgeHours` in new requests and examples.

## Response and Statuses

The contents endpoint can return HTTP 200 even when some requested URLs fail. Always inspect `statuses`.

```json
{
  "results": [
    {
      "url": "https://example.com",
      "text": "..."
    }
  ],
  "statuses": [
    { "id": "https://example.com", "status": "success" },
    { "id": "https://bad.example", "status": "error" }
  ]
}
```

Common status/error tags include crawl timeout, unsupported URL, source unavailable, and not found conditions. Treat `statuses` as part of normal control flow, not as a rare exception path.

## Critical Pitfalls

1. Do not wrap `text`, `highlights`, or `summary` inside a `contents` object on `/contents`.
2. Do not assume HTTP 200 means every URL succeeded; inspect `statuses`.
3. Do not add `stream: true`; the contents endpoint does not support streaming.
4. Prefer `maxAgeHours` over older `livecrawl` strings in new examples.
5. In Python SDK calls, remember `snake_case` inside nested options such as `max_characters` and `max_age_hours`.
