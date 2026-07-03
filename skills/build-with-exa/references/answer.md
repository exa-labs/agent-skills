# Answer Endpoint Reference

Grounded answer generation surface via `POST /answer`.

## Canonical Docs Links

- Base docs URL: `https://exa.ai/docs`
- Answer reference: `/reference/answer`
- OpenAI-compatible guide: `/reference/openai-sdk`

## Contents

- Overview
- Request shape
- When to prefer `/answer`
- Structured output
- Streaming
- Response shape
- Critical pitfalls

## Overview

Use the answer endpoint when you want Exa to:

- run the retrieval step
- generate a direct answer or concise summary
- attach citations in one API response

This is the best fit when the application wants a grounded answer, not just ranked results.

## Request Shape

```json
POST https://api.exa.ai/answer
{
  "query": "What is the latest valuation of SpaceX?",
  "text": true
}
```

### Core Parameters

| Parameter | Type | Notes |
| --- | --- | --- |
| `query` | string | Required |
| `stream` | boolean | Enables SSE token streaming |
| `text` | boolean | Include full text in cited source objects |
| `outputSchema` | object | JSON Schema for structured answers |
| `systemPrompt` | string | Guide answer behavior |
| `userLocation` | string | Two-letter ISO country code |

## When To Prefer `/answer`

Use the answer endpoint when:

- you need a grounded answer with citations
- you do not need to manually inspect or rank raw results first
- the app interface is question-driven rather than retrieval-driven

Prefer the search endpoint when:

- your application needs the result list itself
- you want explicit control over `contents` modes on each result
- you want deeper synthesized search flows via `deep` or `deep-reasoning`

## Structured Output

```python
from exa_py import Exa

exa = Exa(api_key="YOUR_EXA_API_KEY")
response = exa.answer(
    "What is the latest valuation of SpaceX?",
    output_schema={
        "type": "object",
        "properties": {
            "valuation": {"type": "string"},
            "date": {"type": "string"}
        },
        "required": ["valuation", "date"]
    }
)
print(response.answer)
```

Use small, explicit schemas. The answer endpoint is good for question-shaped structured output, while the search endpoint is often the better fit for broader synthesized retrieval.

## Streaming

When `stream: true`, the answer endpoint returns server-sent events. In SDKs, use the dedicated streaming helpers instead of passing `stream=True` into ordinary non-streaming helper calls.

TypeScript:

```typescript
for await (const chunk of exa.streamAnswer("Explain quantum computing")) {
  if (chunk.content) {
    process.stdout.write(chunk.content);
  }
}
```

## Response Shape

Typical non-streaming response fields:

- `answer`
- `citations`
- `requestId`
- `costDollars`

Each citation object may include URL, title, author, published date, and optionally text if requested.

## Critical Pitfalls

1. Use the answer endpoint for answer-shaped output, not as a substitute for full search result inspection.
2. If you need rich per-result extraction controls, prefer the search endpoint.
3. For SDK streaming, prefer `stream_answer` or `streamAnswer` helpers over ad hoc raw flags.
