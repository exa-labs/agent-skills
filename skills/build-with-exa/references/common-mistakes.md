# Common Mistakes Reference

Frequent Exa parameter-shape and deprecation mistakes, with corrections.

## Canonical Docs Links

- Base docs URL: `https://exa.ai/docs`
- Search coding-agent reference: `/reference/search-api-guide-for-coding-agents`
- Contents coding-agent reference: `/reference/contents-api-guide-for-coding-agents`
- Monitors coding-agent reference: `/reference/monitors-api-guide-for-coding-agents`

## Corrections

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
| `livecrawl` as new default guidance | Prefer `maxAgeHours` for new examples |
| `livecrawl: "true"` | Do not pass the string `"true"`; it can silently fall back to `never` |
| Stacking `text`, `highlights`, and `summary` on every search | Pick one. `summary` adds a per-result LLM call; combining `text` and `highlights` doubles billing for two views of the same page |
| `category: "github"`, `"documentation"`, `"qa"`, `"pdf"` | Stick to the documented category set. For code queries use `type: "fast"` or the `/context` endpoint |
| `stream: true` on `/contents` | `/contents` does not support streaming |
| raw JSON field names copied into core Python SDK methods like `search()` | Convert to `snake_case` |
| Python `maxCharacters` | Use `max_characters` |
| Python `outputSchema` | Use `output_schema` |
| Python `numResults` | Use `num_results` |
| `searchParams` on monitors | Use `search` |
| `schedule: "1h"` on monitors | Use `trigger: { "type": "interval", "period": "1h" }` |

## High-Risk Shape Confusions

### Search vs Contents

- search endpoint: nested `contents`
- contents endpoint: top-level `text`, `highlights`, `summary`

### Context vs Search

- context endpoint: `tokensNum`
- search endpoint: content sizing belongs under `contents.text.maxCharacters`
