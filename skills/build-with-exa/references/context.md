# Context Endpoint Reference

Code-focused retrieval surface via `POST /context`.

## Canonical Docs Links

- Base docs URL: `https://exa.ai/docs`
- Context reference: `/reference/context`

## Contents

- Overview
- Request shape
- Parameters
- Response shape
- When it beats general search
- Integration examples
- Critical pitfalls

## Overview

The context endpoint, also called Exa Code, is tuned for coding agents and developer workflows. It searches across repositories, docs pages, Stack Overflow, and related technical sources to return token-efficient code context.

When the task is code-specific but you still want ranked web results rather than a formatted context blob, prefer `/search` with `type: "fast"`.

Use it when the query is about:

- framework or library usage
- API syntax examples
- implementation patterns
- setup or configuration guidance
- coding best practices sourced from real code and docs

## Request Shape

```json
POST https://api.exa.ai/context
{
  "query": "how to use React hooks for state management",
  "tokensNum": 5000
}
```

## Parameters

| Parameter | Type | Notes |
| --- | --- | --- |
| `query` | string | Required; max 2000 characters in the current docs |
| `tokensNum` | string or integer | Required; `"dynamic"` or a token count from 50 to 100000 |

Use `"dynamic"` for most cases. Set an explicit token count only when you need tighter output-size control.

## Response Shape

Typical fields:

- `requestId`
- `query`
- `response` as markdown/code context
- `resultsCount`
- `costDollars`
- `searchTime`
- `outputTokens`

The `response` field is already formatted as usable code context, not as a ranked list of URLs.

## When It Beats General Search

Prefer the context endpoint over the search endpoint when:

- code examples are more important than general web pages
- the consumer is a coding agent or developer tool
- token-efficient technical context is the main goal

Prefer the search endpoint when:

- the query is general web research, not code-specific
- you need specialized categories such as `people` or `company`
- you need result-level content extraction or synthesized `outputSchema` behavior

## Integration Examples

Python:

```python
import requests

response = requests.post(
    "https://api.exa.ai/context",
    headers={
        "Content-Type": "application/json",
        "x-api-key": "YOUR_API_KEY"
    },
    json={
        "query": "Express.js middleware for authentication",
        "tokensNum": "dynamic"
    }
)

print(response.json()["response"])
```

TypeScript:

```typescript
const response = await fetch("https://api.exa.ai/context", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "x-api-key": process.env.EXA_API_KEY!
  },
  body: JSON.stringify({
    query: "React hooks for state management examples",
    tokensNum: "dynamic"
  })
});

const result = await response.json();
console.log(result.response);
```

## Critical Pitfalls

1. `tokensNum` belongs to the context endpoint, not to the search or contents endpoints.
2. Do not assume the response looks like ranked search results; the main payload is the formatted `response` field.
3. Use the search endpoint instead when the task is general web retrieval rather than code retrieval.
