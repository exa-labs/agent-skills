# OpenAI-Compatible Endpoints Reference

Compatibility layer for OpenAI SDK clients.

## Canonical Docs Links

- Base docs URL: `https://exa.ai/docs`
- OpenAI SDK compatibility: `/reference/openai-sdk`
- OpenAI Responses API with Exa: `/reference/openai-responses-api-with-exa`

## Overview

Exa exposes OpenAI-compatible endpoints so existing OpenAI SDK clients can route requests to Exa with minimal call-site changes.

This is useful when:

- you already depend on the OpenAI SDK
- you want a compatibility-first migration path
- you need drop-in chat or responses interfaces

For new Exa-first integrations, prefer native Exa endpoints because the request shapes are clearer and expose Exa-specific semantics directly.

## Not the Same as Tool Calling

These compatibility endpoints **replace** your LLM provider with Exa: you point the OpenAI SDK at `https://api.exa.ai` and Exa runs the answer or research itself.

If you instead want to **keep** your current agent and have it call Exa as one of its tools, see the tool calling pattern in [prompting-and-patterns.md](prompting-and-patterns.md).

## Endpoint Mapping

| Exa Endpoint | OpenAI Interface | Models | Primary Route |
| --- | --- | --- | --- |
| `/chat/completions` | Chat Completions API | `exa`, `exa-research`, `exa-research-pro` | Routes to `/answer` or legacy research behavior |
| `/responses` | Responses API | `exa-research`, `exa-research-pro` | Research-style compatibility path |

Exa's compatibility layer parses the conversation and forwards the last message into its underlying Exa route.

## Basic Setup

Python:

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://api.exa.ai",
    api_key="YOUR_EXA_API_KEY"
)
```

TypeScript:

```typescript
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "https://api.exa.ai",
  apiKey: process.env.EXA_API_KEY
});
```

## `/chat/completions` for Answer-Like Flows

Use model `exa` when you want compatibility access to Exa's grounded answer behavior.

```python
completion = client.chat.completions.create(
    model="exa",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What are the latest developments in quantum computing?"}
    ],
    extra_body={"text": True}
)

print(completion.choices[0].message.content)
```

Use `extra_body` to pass Exa-specific fields such as `text`.

## `/responses` for Research-Style Compatibility

Use `exa-research` or `exa-research-pro` when the caller expects the OpenAI Responses API shape.

```python
response = client.responses.create(
    model="exa-research",
    input="Summarize recent battery recycling policy developments."
)

print(response.output)
```

## Model Routing Guidance

- `exa`: chat-completions compatibility for answer-like flows
- `exa-research`: research-style compatibility
- `exa-research-pro`: higher-effort research-style compatibility

Treat these as compatibility-layer model names, not as replacements for learning Exa's native endpoint semantics.

## Critical Pitfalls

1. OpenAI-compatible endpoints are secondary to native Exa endpoints for new integrations.
2. Remember to use `extra_body` for Exa-specific fields on OpenAI SDK clients.
3. The compatibility layer forwards the last message; do not assume it preserves every native Exa feature in the same shape as the direct endpoints.
