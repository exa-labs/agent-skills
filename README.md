# Exa Agent Skills

[![skills.sh](https://skills.sh/b/exa-labs/agent-skills)](https://skills.sh/exa-labs/agent-skills)

Connect AI assistants to Exa's API skills: search, contents extraction, answer, context, Agent API, monitors, websets, and OpenAI-compatible endpoints.


> [!NOTE]  
> You will need an API key to use the skills.
> You can get an API key from the [Exa Dashboard](https://dashboard.exa.ai/), then set it as `EXA_API_KEY` in your agent environment.

## Available Skills

| Skill | Description |
| --- | --- |
| `build-with-exa` | Build applications and agents with Exa's API Platform: search, contents extraction, answer, context, Agent API, monitors, websets, OpenAI-compatible endpoints, and `exa-py` / `exa-js`. |
| `exa-search` | Call Exa Search directly with cURL or raw HTTP for semantic web search, ranked results, content extraction, structured output, filters, freshness, and streaming search responses. |
| `exa-contents` | Call Exa Contents directly with cURL or raw HTTP for extracted text, highlights, summaries, links, image links, subpages, and freshness-controlled crawling from known URLs. |

## Installation

```bash
npx skills add exa-labs/agent-skills
```
