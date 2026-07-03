# Monitors API Reference

Standalone recurring-search surface via `https://api.exa.ai/monitors`.

## Canonical Docs Links

- Base docs URL: `https://exa.ai/docs`
- Monitors guide: `/reference/monitors-api-guide`
- Monitors coding-agent reference: `/reference/monitors-api-guide-for-coding-agents`

## Contents

- Overview
- Endpoint summary
- Create shape
- Search payload and trigger shape
- Runs, statuses, and updates
- Webhook handling
- Critical pitfalls

## Overview

The Monitors API runs Exa searches on a schedule and delivers results to a webhook. Use it for recurring monitoring workflows such as:

- competitor announcements
- funding events
- policy or regulatory changes
- new publications on a topic

This file covers the standalone Monitors API only. Websets has its own monitor subresources inside the Websets API family and is documented separately in [websets.md](websets.md).

## Endpoint Summary

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/monitors` | Create a monitor |
| `GET` | `/monitors` | List monitors |
| `GET` | `/monitors/{id}` | Get one monitor |
| `PATCH` | `/monitors/{id}` | Update a monitor |
| `DELETE` | `/monitors/{id}` | Delete a monitor |
| `POST` | `/monitors/{id}/trigger` | Trigger an on-demand run |
| `GET` | `/monitors/{id}/runs` | List runs |
| `GET` | `/monitors/{id}/runs/{runId}` | Get one run |

## Create Shape

```json
POST https://api.exa.ai/monitors
{
  "name": "AI Funding Tracker",
  "search": {
    "query": "AI startups that raised Series A funding",
    "numResults": 10
  },
  "trigger": {
    "type": "interval",
    "period": "1d"
  },
  "webhook": {
    "url": "https://example.com/webhook"
  }
}
```

### Create Fields

| Field | Type | Notes |
| --- | --- | --- |
| `name` | string | Optional display name |
| `search` | object | Required search payload |
| `trigger` | object | Optional interval schedule; omit for manual-only monitors |
| `outputSchema` | object | Optional structured output |
| `metadata` | object | Optional caller metadata |
| `webhook` | object | Required webhook configuration |

## Search Payload and Trigger Shape

- `query`
- optional `numResults`
- optional nested `contents`

For recurring behavior, the key extra concept is `trigger`:

```json
{
  "trigger": {
    "type": "interval",
    "period": "7d"
  }
}
```

`trigger` can be removed on update by setting it to `null`.

## Runs, Statuses, and Updates

Monitor statuses in current Exa docs:

- `active`: runs on schedule and accepts manual triggers
- `paused`: does not run on schedule but still accepts manual triggers
- `disabled`: system-disabled, not manually chosen in normal create flows

Update semantics:

- all update fields are optional
- `search` supports partial updates
- manual testing is done through `POST /monitors/{id}/trigger`

## Webhook Handling

Creating a monitor returns a one-time `webhookSecret`. Store it immediately. It is required for verifying webhook signatures and cannot be fetched later.

This is one of the most important operational details in the Monitors API.

## Python Example

```python
from exa_py import Exa

exa = Exa(api_key="YOUR_EXA_API_KEY")
monitor = exa.monitors.create(params={
    "name": "AI Funding Tracker",
    "search": {
        "query": "AI startups that raised Series A funding",
        "numResults": 10
    },
    "trigger": {
        "type": "interval",
        "period": "1d"
    },
    "webhook": {
        "url": "https://example.com/webhook"
    }
})

print(monitor.id)
print(monitor.webhook_secret)
```

Current Exa Python monitor examples use an API-shaped `params` dict, so the nested search payload commonly stays in `camelCase` even though the core Python search helpers are snake_case.

## Critical Pitfalls

1. Use `search`, not `searchParams`.
2. Use `trigger`, not a top-level `schedule` string.
3. Store `webhookSecret` immediately on create.
4. Keep this Monitors API separate from Websets-owned monitor subresources.
5. Manual triggers still work for `paused` monitors, but not for system-disabled ones.
