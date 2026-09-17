# Exa Snapshot Reference

Historical page versions via `snapshotAsOf` on `POST /contents` and `POST /search`.

## Canonical Docs Links

- Base docs URL: `https://exa.ai/docs`
- Exa Snapshot: `/search/snapshot`
- Contents reference: `/reference/get-contents`
- Search reference: `/reference/search`

## Contents

- Overview
- Contents at a datetime
- Search at a datetime
- How snapshots work
- Snapshot vs freshness
- Limits
- Critical pitfalls

## Overview

Exa Snapshot keeps stored versions of the pages Exa has crawled. Sending `snapshotAsOf` (an ISO 8601 date-time) pins a request to that instant: Exa returns the newest stored version of each page at or before it and never fetches the live page.

Use Snapshot when the task needs page content as it was, not as it is:

- backtesting agents against what the web said at the time
- reproducible evals whose inputs must not drift between runs
- comparing earlier versions of docs, pricing pages, policies, or filings

"Snapshot" in Exa's product vocabulary always means this historical retrieval. A plain `/contents` call returns the current page; it is not a snapshot.

## Contents at a Datetime

`snapshotAsOf` is a top-level field on `/contents`, next to `urls` and the content fields.

```json
POST https://api.exa.ai/contents
{
  "urls": ["https://en.wikipedia.org/wiki/2026"],
  "snapshotAsOf": "2026-06-01T00:00:00Z",
  "text": true
}
```

```python
from exa_py import Exa

exa = Exa(api_key="YOUR_EXA_API_KEY")
result = exa.get_contents(
    ["https://en.wikipedia.org/wiki/2026"],
    snapshot_as_of="2026-06-01T00:00:00Z",
    text=True,
)
```

```typescript
import Exa from "exa-js";

const exa = new Exa();
const result = await exa.getContents(["https://en.wikipedia.org/wiki/2026"], {
  snapshotAsOf: "2026-06-01T00:00:00Z",
  text: true,
});
```

URLs with no stored version at or before the cutoff are omitted from `results` and reported in `statuses` with `"status": "error"` and `"tag": "CONTENT_NOT_CACHED"`. Served versions carry `"source": "cached"`.

## Search at a Datetime

On `/search`, `snapshotAsOf` goes inside `contents`, like every other content option.

```json
POST https://api.exa.ai/search
{
  "query": "latest stable Python release notes",
  "numResults": 3,
  "contents": {
    "snapshotAsOf": "2026-07-01T00:00:00Z",
    "highlights": true
  }
}
```

```python
result = exa.search(
    "latest stable Python release notes",
    num_results=3,
    contents={"snapshot_as_of": "2026-07-01T00:00:00Z", "highlights": True},
)
```

Exa discovers candidate URLs with its current retrieval signals, then keeps only pages with a stored version at or before `snapshotAsOf` and serves that version. The cutoff bounds the content, not the ranking: treat the results as evidence bounded by the datetime, not as a reconstruction of what a search would have ranked then.

## How Snapshots Work

| Field | Where | Meaning |
| --- | --- | --- |
| `snapshotAsOf` | `/contents` top level; `/search` inside `contents` | ISO 8601 date-time cutoff. Exa returns the newest stored version at or before this instant. |

For both endpoints:

- Returned page content comes from that stored version.
- Title, author, publication date, text, highlights, and summaries are generated only from that version.
- Pages without an eligible version in the retention window are omitted.

## Snapshot vs Freshness

`snapshotAsOf` and `maxAgeHours` answer opposite questions and are never sent together.

| Need | Field |
| --- | --- |
| The page as it was at a past instant | `snapshotAsOf` |
| The page as it is now, at most N hours old | `maxAgeHours` (see `references/contents.md`) |
| Results published within a date range | `startPublishedDate` / `endPublishedDate` (see `references/search.md`) |

Neither `maxAgeHours: 0` (force a live crawl) nor a published-date filter returns an earlier version of a page.

## Limits

- Retention is a rolling window, 5 months at launch.
- Available on pay as you go at 10 QPS. After 100 Snapshot requests, contact sales (`https://exa.ai/contact/sales`) to continue.

## Critical Pitfalls

1. Do not answer "snapshot" with a plain `/contents` request or with `maxAgeHours`; only `snapshotAsOf` returns a stored past version.
2. On `/contents` the field is top level; on `/search` it is nested inside `contents`.
3. Do not combine `snapshotAsOf` with `maxAgeHours` or `livecrawl`.
4. Search results under `snapshotAsOf` are content-bounded, not ranking-bounded; say so when the task is "what would a search have returned then".
5. Expect omissions: pages without a stored version before the cutoff are dropped (`CONTENT_NOT_CACHED` on `/contents`), so check `statuses` and result counts.
