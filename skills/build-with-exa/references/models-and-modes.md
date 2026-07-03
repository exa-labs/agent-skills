# Models and Modes Reference

Stable selection guidance for Exa search types and compatibility-layer model routing.

## Canonical Docs Links

- Base docs URL: `https://exa.ai/docs`
- Search reference: `/reference/search`
- OpenAI SDK compatibility: `/reference/openai-sdk`

## Search Types

Exa's primary search modes for new work:

| Type | Use When | Tradeoff |
| --- | --- | --- |
| `auto` | You want the default | Best general-purpose starting point |
| `fast` | Latency matters more than maximum synthesis quality | Lower latency |
| `instant` | Real-time UI and assistant flows | Lowest latency |
| `deep-lite` | You want lightweight synthesis | More reasoning than default modes |
| `deep` | You need deeper synthesized retrieval | Higher latency |
| `deep-reasoning` | You want the strongest research-style reasoning | Highest latency |

## How Output Controls Affect Behavior

- `outputSchema` adds synthesis work and therefore adds latency across search types
- `systemPrompt` guides synthesis behavior but does not replace schema control
- `maxAgeHours: 0` forces fresh crawling and can increase latency substantially

Do not choose a deep variant only because you want structured output. Choose it when the retrieval task itself needs more reasoning or multi-step synthesis.

If you are optimizing for responsiveness, start with:

- `type: "fast"` for coding or agent workflows, `type: "instant"` for real-time UX, or `type: "auto"` for general retrieval
- no `outputSchema`
- default freshness behavior

Then add deeper reasoning or stronger freshness only when the use case requires it.

## Answer and Compatibility Models

In OpenAI-compatible flows, current model routing is:

| Model | Typical Use |
| --- | --- |
| `exa` | Answer-style compatibility via `/chat/completions` |
| `exa-research` | Research-style compatibility |
| `exa-research-pro` | Higher-effort research-style compatibility |

These are compatibility-layer names. Native Exa endpoint choice remains the more important design decision.

Use `deep-reasoning` when:

- the task needs multi-step synthesized retrieval
- you want a current Exa-first path instead of the legacy research surface
- you need a replacement for legacy `/research/v1` structured output flows

## Practical Defaults

- General retrieval: `type: "auto"`
- Fast coding or agent path: `type: "fast"` with `highlights`
- Real-time UX: `type: "instant"` and minimal synthesis
