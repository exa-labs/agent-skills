---
name: build-with-exa
description: "Build applications and agents with Exa's API: search, contents extraction, answer, context, Agent API, monitors, websets, OpenAI-compatible endpoints, and exa-py/exa-js SDKs. Use when choosing Exa endpoints, writing Exa API calls, integrating semantic web search or research into products, or debugging Exa request shapes."
metadata:
  author: Exa
  version: "0.2.0"
  docs: "https://exa.ai/docs"
---

# Build with Exa

## Scope

Included by default:

- Core retrieval APIs: search endpoint, contents endpoint, answer endpoint, context endpoint
- Long-running research workflows: Agent API (`/agent`)
- Async and recurring workflows: Monitors API
- Legacy surface: Websets API (existing integrations only; new collection-building work uses the Agent API)
- SDK guidance: Python `exa-py`, TypeScript `exa-js`

> Note on data retention: `/search`, `/answer`, and `/agent/` offer Zero Data Retention (ZDR). Websets and Monitors are not ZDR. If a use case requires ZDR, stay on the ZDR surfaces or contact Exa.

## Installation

```bash
# Python
pip install exa-py

# TypeScript / JavaScript
npm install exa-js
```

Install the latest SDK release with the package manager so it resolves the latest release and all SDK surfaces will be available.

## Authentication

```bash
export EXA_API_KEY="your_api_key_here"
```

Exa accepts either the `x-api-key` header or `Authorization: Bearer <key>`.

The recommended Exa search request is the query plus token-efficient content extraction, and nothing else. Content extraction is a recommendation, not a server default: omit `contents` and results carry only metadata (title, URL, dates), no page content.

```json
{
  "query": "latest developments in LLMs",
  "type": "auto",
  "contents": { "highlights": true }
}
```

**Every other request field is gated: add it only when the user's task explicitly requires it.** Do not restate server defaults, and do not add controls because they seem plausibly useful. In particular:

- `type` defaults to `auto`; stating `type: "auto"` explicitly is fine, but do not send another mode unless the task requires it (for example a latency-critical UX or deep synthesis).
- `numResults` defaults to 10; omit `numResults` unless the task requires a different number of results. Set it only as an intentional product decision, not as boilerplate.
- Omit `category`. Use it only when the user explicitly asks for category-constrained retrieval.
- `includeDomains` and `excludeDomains` should be set only when the user explicitly requests a hard allowlist or blocklist and supplies or approves its contents. Express source preferences through query phrasing or `systemPrompt` instead.
- `maxAgeHours` should be set only when extracted page content must be current. It caps cache age before a live crawl; it is not a publication-recency filter.
- For "recent stories" tasks, express the window in the query or use `startPublishedDate` / `endPublishedDate`. Do not reach for `maxAgeHours`.
- `highlights` should be set to `true` by default for all tasks unless otherwise specified. Do not add `maxCharacters` or other highlight options without an explicit budget requirement in the task.

## API Decision Workflow

Before picking an endpoint, decide which workflow shape fits:

- Raw web content for your own LLM or agent: use `/search` with the recommended request above
- Synthesized structured output: use `/search` and add `outputSchema` (and `systemPrompt` if behavior guidance is needed)
- Long-running multi-step research, list-building, or enrichment with structured output: use the Agent API (`/agent`)

**Default to the search endpoint.** Use the search endpoint (`/search`) for most new integrations, then move to a more specialized Exa surface only when the task shape clearly calls for it.

1. Need general semantic web retrieval, synthesized output, or content extraction from search results: use the search endpoint (`/search`)
2. Already know the URLs and need clean page extraction or freshness controls: use the contents endpoint (`/contents`)
3. Need pages related to a known seed URL: use the search endpoint (`/search`) with a query derived from the page (for example title, topic, or text from `/contents`)
4. Need a grounded answer with citations and no LLM of your own doing generation: use the answer endpoint (`/answer`). If the product already has a chat LLM, give it `/search` as a tool instead.
5. Need code-focused retrieval from repos, docs, and Stack Overflow: use the context endpoint (`/context`)
6. Need OpenAI SDK drop-in compatibility for chat or responses clients: use the OpenAI-compatible endpoints (`/chat/completions`, `/responses`)
7. Need asynchronous multi-step research, list-building, enrichment, or follow-up questions over prior research: use the Agent API (`/agent`)
8. Need scheduled recurring search with webhook delivery: use the Monitors API (`/monitors`)
9. Maintaining an existing Websets integration: see the migration guide (`references/migrate-websets-to-agent.md`) and transition to the Agent API (`references/agent.md`). Do not use Websets for new work; use the Agent API instead.

## Quick Start

For more complete examples, see the relevant reference file in the table below.

**Python** (`/search`):

```python
from exa_py import Exa

exa = Exa(api_key="YOUR_EXA_API_KEY")
result = exa.search(
    "latest developments in LLMs",
    type="auto",
    contents={"highlights": True}
)

for item in result.results:
    print(item.title, item.url)
```

**TypeScript** (`/search`):

```typescript
import Exa from "exa-js";

const exa = new Exa();
const result = await exa.search("latest developments in LLMs", {
  type: "auto",
  contents: { highlights: true }
});

for (const item of result.results) {
  console.log(item.title, item.url);
}
```

**Raw HTTP** (`/search`):

```bash
curl -X POST "https://api.exa.ai/search" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $EXA_API_KEY" \
  -d '{
    "query": "latest developments in LLMs",
    "type": "auto",
    "contents": {
      "highlights": true
    }
  }'
```

## Critical Pitfalls

- Do not decorate the recommended request without reason. Adding `category`, domain filters, boilerplate `numResults`, or freshness controls without an explicit task requirement is the most common integration mistake.
- On the search endpoint, `text`, `highlights`, and `summary` belong inside `contents`, not at the top level.
- On the contents endpoint, `text`, `highlights`, and `summary` are top-level fields, not nested inside `contents`.
- Pick one of `highlights`, `text`, or `summary`. Do not stack them. `summary` requires an explicit user request for Exa-side per-result synthesis.
- Almost all tasks should use bare `highlights: true`. `numSentences` and `highlightsPerUrl` are deprecated, and `maxCharacters` needs an explicit budget requirement.
- List-building and enrichment workflows belong on the Agent API (`/agent`), not on `/search` with `category: "people"` or `category: "company"`. Those categories are only for retrieving raw people or company documents.
- `maxAgeHours` controls crawl/cache freshness (how old extracted page content may be before a live crawl), not publication recency. Do not use it as a "recent results" control; recency belongs in query phrasing or `startPublishedDate` / `endPublishedDate`.
- Never invent category values like `github`, `documentation`, `qa`, or `pdf`. When a user does request category-constrained retrieval, check the search reference first: specialized categories such as `people` and `company` restrict which filters are valid.
- OpenAI-compatible endpoints are for compatibility-first use cases. Prefer native Exa endpoints for new integrations when you want clearer request semantics.
- Do not treat `/agent` as a drop-in replacement for `/search`. It is higher-latency and async, so use the dedicated Agent reference when that workflow shape is the real fit. Prefer it over Websets for new collection-building work.
- Agent requests should always set `effort` explicitly, wait for a terminal status via polling or SSE and check how the run ended before reading `output`, and expose `output.grounding` when relevant in a product.
- Treat `/findSimilar` as deprecated. Prefer `/search` (optionally after `/contents` on the seed URL) for related-page discovery.

## Reference Files

| File | Topics |
|------|--------|
| [references/search.md](references/search.md) | Search endpoint request/response shape, search types, filters, nested contents, structured output |
| [references/contents.md](references/contents.md) | Contents endpoint extraction, freshness, statuses, top-level content fields |
| [references/answer.md](references/answer.md) | Grounded answer generation with citations and structured output |
| [references/context.md](references/context.md) | Code-focused retrieval with `tokensNum` |
| [references/agent.md](references/agent.md) | Agent API for async multi-step research, enrichment, structured output, polling, and events |
| [references/openai-compat.md](references/openai-compat.md) | OpenAI-compatible endpoints, model routing, `extra_body` usage |
| [references/monitors.md](references/monitors.md) | Standalone Monitors API for scheduled recurring search |
| [references/migrate-websets-to-agent.md](references/migrate-websets-to-agent.md) | Migrate Websets to the Agent API: call-site classification, request mapping, delivery rewrite, verification |
| [references/sdks.md](references/sdks.md) | Python and TypeScript SDK naming, methods, and shape differences |
| [references/http-requests.md](references/http-requests.md) | Minimal raw HTTP examples across major Exa surfaces |
| [references/models-and-modes.md](references/models-and-modes.md) | Search type selection, answer/research model routing, latency tradeoffs |
| [references/prompting-and-patterns.md](references/prompting-and-patterns.md) | Durable query, prompting, freshness, and output-schema patterns |
| [references/common-mistakes.md](references/common-mistakes.md) | Over-specification and parameter-shape corrections |

## Canonical Docs

- Docs home: `https://exa.ai/docs`
- Documentation index: `https://exa.ai/docs/llms.txt`
- Search reference: `https://exa.ai/docs/reference/search`
- Agent API guide: `https://exa.ai/docs/reference/agent-api-guide`
- Exa Connect overview: `https://exa.ai/docs/reference/agent-api/connect/overview`
- Python SDK spec: `https://exa.ai/docs/sdks/python-sdk-specification`
- TypeScript SDK spec: `https://exa.ai/docs/sdks/typescript-sdk-specification`
