# SDKs Reference

Practical naming and surface guide for `exa-py` and `exa-js`.

## Canonical Docs Links

- Base docs URL: `https://exa.ai/docs`
- Python SDK spec: `/sdks/python-sdk-specification`
- TypeScript SDK spec: `/sdks/typescript-sdk-specification`
- Python README: `https://github.com/exa-labs/exa-py`
- JavaScript README: `https://github.com/exa-labs/exa-js`

## Contents

- Shared guidance
- Python SDK
- TypeScript SDK
- Raw HTTP vs SDK shapes
- Critical pitfalls

## Shared Guidance

- Use official docs as canonical for behavior
- Use SDK docs and repos to confirm method names, casing, and helper ergonomics
- Distinguish request-shape casing carefully:
  - raw HTTP: `camelCase`
  - Python core endpoint methods: `snake_case`
  - TypeScript SDK: `camelCase`
- Current Python Monitors and Websets docs often show `params={...}` dicts that keep API-shaped field names such as `numResults`. Treat those resource families as a surface-specific exception rather than forcing the core search/contents casing rule onto every SDK namespace.

## Python SDK (`exa-py`)

Install:

```bash
pip install exa-py
```

Instantiate:

```python
from exa_py import Exa

exa = Exa(api_key="YOUR_EXA_API_KEY")
```

### Current Primary Methods

- `search(...)`
- `stream_search(...)`
- `get_contents(...)`
- `answer(...)`
- `stream_answer(...)`
- `agent.runs.create(...)`
- `agent.runs.get(...)`
- `agent.runs.list(...)`
- `agent.runs.poll_until_finished(...)`
- `monitors.*`
- `websets.*`

### Naming Rules for Core Endpoint Methods

Use `snake_case` everywhere, including nested dict keys:

```python
result = exa.search(
    "latest AI funding rounds",
    num_results=10,
    contents={"text": {"max_characters": 4000}},
    output_schema={
        "type": "object",
        "properties": {"summary": {"type": "string"}},
        "required": ["summary"]
    }
)
```

### Documented Default-Contents Caveat

Current Python SDK docs explicitly say `search()` returns text contents with a 10,000-character default unless you disable contents. If you do not want that default behavior, pass `contents=False`.

### Helper Methods and Namespace Nuance

The Python SDK also exposes helpers such as `search_and_contents(...)`. They exist, but this skill treats them as helper ergonomics rather than the primary surface. Normative endpoint choice in this skill stays aligned to `/search` and `/contents`.

For newer resource families such as `monitors` and `websets`, current Exa examples often pass API-shaped `params` dicts rather than fully snake_cased keyword arguments. Follow the resource-specific docs there instead of assuming the core search-method casing rules apply unchanged.

## TypeScript SDK (`exa-js`)

Install:

```bash
npm install exa-js
```

Instantiate:

```typescript
import Exa from "exa-js";

const exa = new Exa();
```

### Current Primary Methods

- `search(...)`
- `streamSearch(...)`
- `getContents(...)`
- `answer(...)`
- `streamAnswer(...)`
- `agent.runs.create(...)`
- `agent.runs.get(...)`
- `agent.runs.list(...)`
- `agent.runs.pollUntilFinished(...)`
- `monitors.*`
- `websets.*`

### Naming Rules

Use `camelCase` everywhere:

```typescript
const result = await exa.search("latest AI funding rounds", {
  numResults: 10,
  contents: { text: { maxCharacters: 4000 } },
  outputSchema: {
    type: "object",
    properties: { summary: { type: "string" } },
    required: ["summary"]
  }
});
```

### Helper Methods

Examples and SDK source may show helpers such as `searchAndContents(...)`. They are valid helpers, but they are not the primary pattern in this skill. Prefer understanding the underlying endpoint family first.

## Raw HTTP vs SDK Shapes

| Concern | Raw HTTP | Python SDK | TypeScript SDK |
| --- | --- | --- | --- |
| Results count | `numResults` | `num_results` | `numResults` |
| Output schema | `outputSchema` | `output_schema` | `outputSchema` |
| System prompt | `systemPrompt` | `system_prompt` | `systemPrompt` |
| Text cap | `maxCharacters` | `max_characters` | `maxCharacters` |
| Freshness | `maxAgeHours` | `max_age_hours` | `maxAgeHours` |
| Search contents | nested `contents` | nested `contents` with snake_case keys | nested `contents` with camelCase keys |
| Contents endpoint text | top-level `text` | top-level `text` | top-level `text` |

## Critical Pitfalls

1. Do not paste raw JSON keys into core Python SDK methods such as `search()` unchanged, including nested `contents` dictionaries.
2. Do not assume helper methods define the canonical API shape.
3. Remember the Python SDK's documented `search()` default-contents behavior.
