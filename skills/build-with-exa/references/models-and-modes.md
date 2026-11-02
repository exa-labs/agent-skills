# Models and Modes Reference

Stable selection guidance for Exa search types and compatibility-layer model routing.

## Canonical Docs Links

- Base docs URL: `https://exa.ai/docs`
- Search reference: `/reference/search`
- OpenAI SDK compatibility: `/integrations/openai-sdk`

## Search Types

Exa's primary search modes for new work:

| Type | Use When | Tradeoff |
| --- | --- | --- |
| `auto` | You want the default; omit `type` entirely rather than sending it | Best general-purpose starting point |
| `lite` | Low-latency, low-cost chat, voice, autocomplete, and agent loops | Cached retrieval with a reduced parameter set |
| `deep-lite` | You want lightweight synthesis | More reasoning than default modes |
| `deep` | You need deeper synthesized retrieval, or a wide `outputSchema` whose fields take more than one search to fill | Higher latency; runs several searches, so more schema fields come back filled |
| `deep-reasoning` | You want the strongest research-style reasoning | Highest latency |

With `type: "lite"`, supported parameters are `query` (a single string), `objective`, `userIdentifier`, `metadata`, `category`, `numResults`, `contents.highlights`, `contents.text`, `contents.snapshotAsOf`, `userLocation`, `includeDomains`, `excludeDomains`, `startPublishedDate`, `endPublishedDate`, `moderation`, and `compliance`. Other documented search parameters are rejected, including `outputSchema`, `systemPrompt`, `stream`, and freshness options such as `contents.maxAgeHours`. Lite serves cached content without fetching pages at query time.

## How Output Controls Affect Behavior

- `outputSchema` adds synthesis work and latency on supported search types. Lite does not support it
- `systemPrompt` guides synthesis behavior but does not replace schema control
- `maxAgeHours: 0` forces fresh crawling and can increase latency substantially

Do not choose a deep variant only because you want structured output. Choose it when the retrieval task itself needs more reasoning or multi-step synthesis. A wide schema whose fields take more than one search to fill is one such task: `deep` runs several searches, so more of the fields come back filled. A compact schema (author and URL per article) stays on `auto`.

If you are optimizing for responsiveness, start with:

- `type: "lite"` when latency or cost matters more than maximum quality, or no `type` at all (default `auto`) otherwise
- no `outputSchema`
- default freshness behavior

Then add deeper reasoning or stronger freshness only when the use case requires it.

## Answer and Compatibility Models

In OpenAI-compatible flows, current model routing is:

| Model | Typical Use |
| --- | --- |
| `exa` | Answer-style compatibility via `/chat/completions` |
| `exa-agent` | Exa Agent runs via `/responses` |

These are compatibility-layer names. Native Exa endpoint choice remains the more important design decision.

Use `deep-reasoning` when:

- the task needs multi-step synthesized retrieval
- you want a current Exa-first path instead of the legacy research surface
- you need a replacement for legacy `/research/v1` structured output flows

## Practical Defaults

`auto` is almost always the right type, including for coding and agent workflows. Deviate only for a real latency or reasoning requirement:

- General retrieval: omit `type`; the server defaults to `auto`
- Latency-sensitive path or real-time UX: `type: "lite"` with `highlights`
