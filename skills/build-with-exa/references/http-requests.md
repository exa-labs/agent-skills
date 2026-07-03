# Raw HTTP Requests Reference

Minimal cURL examples across the main Exa surfaces.

## Canonical Docs Links

- Base docs URL: `https://exa.ai/docs`
- Search reference: `/reference/search`
- Contents reference: `/reference/get-contents`
- Answer reference: `/reference/answer`
- Context reference: `/reference/context`
- OpenAI SDK compatibility: `/reference/openai-sdk`
- Agent API guide: `/reference/agent-api-guide`
- Exa Connect overview: `/reference/agent-api/connect/overview`
- Monitors guide: `/reference/monitors-api-guide`
- Websets overview: `/reference/websets-api`

## Contents

- Search
- Contents
- Answer
- Context
- Agent
- OpenAI-compatible chat completions
- OpenAI-compatible responses
- Monitors
- Websets

## Search

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

## Contents

```bash
curl -X POST "https://api.exa.ai/contents" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $EXA_API_KEY" \
  -d '{
    "urls": ["https://arxiv.org/abs/2307.06435"],
    "text": true,
    "maxAgeHours": 24
  }'
```

## Answer

```bash
curl -X POST "https://api.exa.ai/answer" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $EXA_API_KEY" \
  -d '{
    "query": "What is the latest valuation of SpaceX?",
    "text": true
  }'
```

## Context

```bash
curl -X POST "https://api.exa.ai/context" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $EXA_API_KEY" \
  -d '{
    "query": "how to use React hooks for state management",
    "tokensNum": 5000
  }'
```

## Agent

```bash
curl -s -X POST "https://api.exa.ai/agent/runs" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $EXA_API_KEY" \
  -d '{
    "query": "Find engineering leaders at AI infrastructure companies that raised a Series A or B in the last 6 months.",
    "effort": "auto",
    "outputSchema": {
      "type": "object",
      "properties": {
        "people": {
          "type": "array",
          "maxItems": 10,
          "items": {
            "type": "object",
            "properties": {
              "name": { "type": "string" },
              "job_title": { "type": "string" },
              "linkedin_url": { "type": "string", "format": "uri" }
            },
            "required": ["name", "job_title", "linkedin_url"]
          }
        }
      },
      "required": ["people"]
    }
  }'
```

## OpenAI-Compatible Chat Completions

```bash
curl -X POST "https://api.exa.ai/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $EXA_API_KEY" \
  -d '{
    "model": "exa",
    "messages": [
      {"role": "user", "content": "What are the latest developments in quantum computing?"}
    ]
  }'
```

## OpenAI-Compatible Responses

```bash
curl -X POST "https://api.exa.ai/responses" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $EXA_API_KEY" \
  -d '{
    "model": "exa-research",
    "input": "Summarize recent battery recycling policy developments."
  }'
```

## Monitors

```bash
curl -X POST "https://api.exa.ai/monitors" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $EXA_API_KEY" \
  -d '{
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
  }'
```

## Websets

```bash
curl -X POST "https://api.exa.ai/websets/v0/websets" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $EXA_API_KEY" \
  -d '{
    "search": {
      "query": "Top AI research labs focusing on large language models",
      "count": 5
    },
    "enrichments": [
      {
        "description": "Find the company founding year",
        "format": "number"
      }
    ]
  }'
```

Use the topical reference files for request semantics and tradeoffs. This file is intentionally minimal and shape-focused.
