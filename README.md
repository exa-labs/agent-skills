# Exa Agent Skills

[![skills.sh](https://skills.sh/b/exa-labs/agent-skills)](https://skills.sh/exa-labs/agent-skills)

Reusable workflows for Exa search, content extraction, research, enrichment, and API integration.

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
| `build-with-exa` | Product integration across Exa APIs and SDKs; not the direct-search workflow. |
| `exa-search` | Direct semantic search from a query; not extraction-only work for known URLs. |
| `exa-contents` | Extraction from known URLs; does not discover new results. |
| `company-research` | Cited company and market analysis; not outbound list production. |
| `lead-generation` | Structured, enriched prospect lists; not a single-company deep dive. |

## Install

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
