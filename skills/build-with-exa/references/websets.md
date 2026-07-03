# Websets API Reference

Async verified and enriched collection-building surface via `https://api.exa.ai/websets/v0`.

## Canonical Docs Links

- Base docs URL: `https://exa.ai/docs`
- Websets overview: `/reference/websets-api`
- Websets coding-agent reference: `/websets/api-guide-for-coding-agents`
- Websets API overview: `/websets/api/overview`
- How Websets works: `/websets/api/how-it-works`

## Contents

- Overview
- Core objects
- Lifecycle
- Endpoint families
- Create flow
- Webhooks, events, and monitors
- Critical pitfalls

## Overview

Use the Websets API when you need more than ordinary search results:

- find entities that match criteria
- verify that each candidate truly matches
- enrich each item with structured fields
- keep an evolving collection over time

This is Exa's async, event-driven collection-building surface. It is not the default for ordinary web search.
Use `externalId` for idempotency when you need to de-duplicate create calls across retries or job reruns.

## Core Objects

Current Websets guidance centers on four main objects:

- `Webset`: container for the collection
- `Search`: async discovery job that finds and verifies items
- `Item`: structured result stored in the webset
- `Enrichment`: async extraction job that adds more structured fields to items

Websets can represent entities such as companies, people, articles, or research papers.

## Lifecycle

Typical lifecycle:

1. Create a webset with a search definition
2. Websets finds candidate results
3. Websets verifies each result against your criteria
4. Matching results become items in the webset
5. Optional enrichments add more structured fields
6. Events and webhooks notify you as items and enrichments complete

This is intentionally asynchronous. Expect seconds-to-minutes behavior rather than ordinary request/response latency.

## Endpoint Families

The Websets API includes several grouped resource families:

| Family | Examples |
| --- | --- |
| Websets | create, get, list, update, delete, cancel, preview |
| Searches | create and inspect search jobs inside a webset |
| Items | list and inspect resulting structured items |
| Enrichments | create, update, cancel enrichment jobs |
| Imports | bring your own URLs or source data |
| Webhooks | register delivery targets for events |
| Events | inspect emitted system events |
| Teams | inspect team-level metadata |
| Monitors | Websets-owned monitor subresources |

This file keeps those Websets-owned monitor subresources inside the Websets architecture discussion. For the standalone recurring search product at `https://api.exa.ai/monitors`, use [monitors.md](monitors.md).

## Representative Create Flow

```json
POST https://api.exa.ai/websets/v0/websets
{
  "search": {
    "query": "Top AI research labs focusing on large language models",
    "count": 5
  },
  "enrichments": [
    {
      "description": "Find the company's founding year",
      "format": "number"
    }
  ]
}
```

This pattern says:

- define the entity discovery problem
- optionally add enrichment fields up front
- let Websets search, verify, and populate items over time

Use `POST /websets/preview` before creating a webset when you want to inspect how query decomposition, entity detection, or early preview items will behave without committing to a new resource.

## Searches, Criteria, and Enrichments

Websets search payloads typically include:

- `query`
- `count`
- optional `entity`
- optional `criteria`
- optional `enrichments`

Think of `criteria` as verification rules and `enrichments` as additional structured data you want extracted after matching.

This is the clearest distinction from the search endpoint:

- the search endpoint returns ranked results immediately
- the Websets API builds and maintains a structured collection over time

## Webhooks, Events, and Monitors

Websets is event-driven. Important consequences:

- create webhook subscriptions when downstream systems need progress or completion updates
- expect item creation and enrichment completion to happen incrementally
- use events and webhook attempts for debugging delivery issues

Websets also has monitor subresources under `/websets/v0/monitors` for keeping a webset fresh over time. Treat those as part of the Websets lifecycle rather than as the main Monitors API described in [monitors.md](monitors.md).

## SDK Notes

Both official SDKs expose Websets namespaces. Current docs and SDK source show dedicated `websets` clients rather than asking you to call raw `/websets/v0` paths by hand for every operation.

## Critical Pitfalls

1. Do not use the Websets API when ordinary search or contents retrieval is enough.
2. Treat Websets as async-first; do not assume one immediate final response.
3. Expect structured items, verification state, and enrichments rather than plain ranked result lists.
