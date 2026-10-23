# OpenAI-Compatible Endpoints Reference

Compatibility layer for OpenAI SDK clients.

## Canonical Docs Links

- Base docs URL: `https://exa.ai/docs`
- OpenAI SDK compatibility: `/integrations/openai-sdk`
- Agent via the Responses API: `/integrations/openai-sdk#agent-via-responses-api`
- Agent API: `/agent/quickstart`

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
| `/chat/completions` | Chat Completions API | `exa` | Routes to `/answer` |
| `/responses` | Responses API | `exa-agent` | Routes to the Agent API |

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

## `/responses` for Agent Runs

Use model `exa-agent` to run Exa Agent (multi-step research, enrichment, list-building) through the OpenAI Responses interface. Pick an execution mode:

- Default: the request blocks and returns the completed response.
- `stream: true`: streams Responses events over SSE, ending with `response.completed`.
- `background: true`: returns an `in_progress` response at once. Poll `GET /responses/{id}` for the result.

Set `reasoning.effort` to trade cost against depth. `high`, `xhigh`, and `ultra` runs return `400` unless you set `stream` or `background`. Continue a completed run with `previous_response_id`.

```python
response = client.responses.create(
    model="exa-agent",
    input="Find the top 5 AI startups founded in 2025 with their funding amounts",
    reasoning={"effort": "medium"},
)

print(response.output_text)
```

## Critical Pitfalls

1. OpenAI-compatible endpoints are secondary to native Exa endpoints for new integrations.
2. Remember to use `extra_body` for Exa-specific fields on OpenAI SDK clients.
3. The compatibility layer forwards the last message; do not assume it preserves every native Exa feature in the same shape as the direct endpoints.
