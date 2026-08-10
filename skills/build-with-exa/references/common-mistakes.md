# Common Mistakes Reference

Frequent Exa parameter-shape, over-specification, and deprecation mistakes, with corrections.

## Canonical Docs Links

- Base docs URL: `https://exa.ai/docs`
- Search coding-agent reference: `/reference/search-api-guide-for-coding-agents`
- Contents coding-agent reference: `/reference/contents-api-guide-for-coding-agents`
- Monitors coding-agent reference: `/reference/monitors-api-guide-for-coding-agents`

## Over-Specification

The most common failure mode is decorating the recommended request. The recommended search request is `query`, `type: "auto"`, plus `contents: {"highlights": true}` and nothing else; every other field needs an explicit task requirement.

| Wrong | Correct |
| --- | --- |
| `numResults` set as boilerplate on every request | Omit it unless a specific count is an intentional product decision |
| `category` inferred from task nouns (news task → `news`, people task → `people`, papers → `publication`) | Omit `category`; only set it when the user explicitly requests category-constrained retrieval |
| Source preferences or example sites converted into `includeDomains` / `excludeDomains` | Keep source preferences in query phrasing or `systemPrompt`; hard filters require the user to explicitly request and supply or approve the list |
| `summary` added because the deliverable is a summary | Use `highlights` and synthesize downstream; `summary` requires an explicit user request for Exa-side per-result synthesis |
| `category: "people"` or `category: "company"` for list-building, sourcing, or enrichment | Use the Agent API (`/agent`); those categories are only for retrieving raw people or company documents |
| `highlights: {"maxCharacters": ...}` as a default | Use bare `highlights: true`; `maxCharacters` requires an explicit budget requirement |
| `maxAgeHours` or date filters added without a stated freshness need | Omit freshness controls unless the task requires them |
| New collection-building on `/websets/v0` | Use the Agent API (`/agent`); see [migrate-websets-to-agent.md](migrate-websets-to-agent.md) |

## Shape and Deprecation Corrections

| Wrong | Correct |
| --- | --- |
| `text: true` at the top level on `/search` | Nest it: `"contents": {"text": true}` |
| `highlights: {...}` at the top level on `/search` | Nest it: `"contents": {"highlights": {...}}` |
| `summary: true` at the top level on `/search` | Nest it: `"contents": {"summary": true}` |
| `contents: { text: ... }` on `/contents` | On `/contents`, `text`, `highlights`, and `summary` are top-level fields |
| `tokensNum` on `/search` or `/contents` | `tokensNum` belongs to `/context`, not search or contents |
| `includeUrls` / `excludeUrls` | Use `includeDomains` / `excludeDomains` |
| `useAutoprompt` in new requests | Remove it; it is deprecated |
| `numSentences` for highlights | Use `maxCharacters` or `highlights: true` |
| `highlightsPerUrl` for highlights | Remove it; it is deprecated |
| Using `livecrawl` | Use `maxAgeHours` instead |
| Stacking `text`, `highlights`, and `summary` on every search | Pick one. `summary` adds a per-result LLM call; combining `text` and `highlights` doubles billing for two views of the same page |
| `category: "github"`, `"documentation"`, `"qa"`, `"pdf"` | Stick to the documented category set. |
| `stream: true` on `/contents` | `/contents` does not support streaming |
| camelCase top-level kwargs in core Python SDK methods (`numResults=`, `outputSchema=`) | Use `num_results=`, `output_schema=`; camelCase kwargs raise `TypeError` |
| Nested dict keys like `maxCharacters` in Python | Both casings are accepted, but use `max_characters` for consistency with the SDK style |
| `searchParams` on monitors | Use `search` |
| `schedule: "1h"` on monitors | Use `trigger: { "type": "interval", "period": "1h" }` |

## High-Risk Shape Confusions

### Search vs Contents

- search endpoint: nested `contents`
- contents endpoint: top-level `text`, `highlights`, `summary`

### Context vs Search

- context endpoint: `tokensNum`
- search endpoint: content sizing belongs under `contents.text.maxCharacters`
