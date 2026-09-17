# Exa Agent Skills

[![skills.sh](https://skills.sh/b/exa-labs/agent-skills)](https://skills.sh/exa-labs/agent-skills)

Connect AI assistants to Exa's API skills: search, contents extraction, answer, Agent API, monitors, and OpenAI-compatible endpoints.

> [!NOTE]
> Get an API key from the [Exa Dashboard](https://dashboard.exa.ai/) and expose it as `EXA_API_KEY` to the agent environment.

## Choose by task

| I want to… | Use |
| --- | --- |
| Add Exa to an application, choose an endpoint, or debug an SDK/API request | `build-with-exa` |
| Search the web directly through `POST /search` without an SDK | `exa-search` |
| Extract content from URLs I already have through `POST /contents` | `exa-contents` |
| Research a company, market, competitors, funding, news, or leadership | `company-research` |
| Build and enrich an ICP-based prospect list or CSV | `lead-generation` |

```text
BUILD          SEARCH         EXTRACT        RESEARCH        PROSPECT
Integrate Exa  Find URLs      Read URLs      Understand      Build lists
```

## Skills

| Skill | Boundary |
| --- | --- |
| `build-with-exa` | Build applications and agents with Exa's API Platform: search, contents extraction, answer, Agent API, monitors, OpenAI-compatible endpoints, and `exa-py` / `exa-js`. |
| `exa-search` | Call Exa Search directly with cURL or raw HTTP for semantic web search, ranked results, content extraction, structured output, filters, freshness, and streaming search responses. |
| `exa-contents` | Call Exa Contents directly with cURL or raw HTTP for extracted text, highlights, summaries, links, image links, subpages, and freshness-controlled crawling from known URLs. |
| `company-research` | Research companies, competitors, funding, news, leadership, and market context with Exa Agent and advanced search. |
| `lead-generation` | Generate enriched ICP-based lead lists with Exa Agent, including structured scoring and CSV output. |

Any agent supported by the Skills CLI:

```bash
npx skills add exa-labs/agent-skills
```

Codex plugin:

```bash
codex plugin marketplace add exa-labs/agent-skills
codex plugin add agent-skills@exa-agent-skills
```

The native plugin manifests point to the same root `skills/` tree. No agent-specific skill copies are maintained.

## Develop

```bash
node scripts/validate-repo.js
node scripts/run-routing-evals.js
```

See [docs/skill-anatomy.md](docs/skill-anatomy.md) for the lightweight contribution contract.
