# Exa Connect — when to attach which data partner

Exa Connect plugs premium data partners into the same Agent run: add a `dataSources` array to
`POST /agent/runs` and the agent queries the partner's database alongside Exa web search, then
blends both into one grounded structured answer. Pricing is additive: normal run cost plus a
small per-call provider charge.

**The rule: attach a provider only when a requested column or criterion actually needs its
data.** Attaching irrelevant providers wastes money and can distract the agent. Derive the
provider list from the plan's columns/criteria (Step 1), not from habit. When you do attach one:

1. name it in the **query** ("use Similarweb for traffic estimates"), and
2. name it in the **schema field description** (`"monthlyVisits": {"description": "estimated
   monthly visits, from Similarweb"}`) — the agent routes each field to the matching tool from
   the description.

If a create fails because a provider isn't enabled on the account, drop the `dataSources` entry
and rerun on plain web search; the schema stays the same (fields just come back with lower
confidence or null).

## Provider → use-case map

| Provider | `provider` id | Data | Attach when the plan needs… | Price |
| --- | --- | --- | --- | --- |
| Fiber.ai | `fiber_ai` | B2B company & people database (GTM/recruiting) | firmographics: funding stage/amounts, headcount, industry; founder/exec names; contact discovery | $.02/call |
| Similarweb | `similarweb` | Web analytics | monthly visits, traffic rank, audience geo; also competitor/similar-site **discovery segments** | $.03/call |
| Baselayer | `baselayer` | US KYB / compliance | legal registration, officers, risk signals — vendor-diligence or compliance-flavored lists | $.022/call |
| Financial Datasets | `financial_datasets` | Ticker-based news, US public companies | lists of/columns about **public** companies (news, ticker-keyed facts) | $.01/call |
| Affiliate.com | `affiliate` | Product catalog search: pricing, brands, merchants | commerce/product columns: what they sell, price points, merchant presence | $.015/call |
| Particle | `particle` | Podcast transcripts w/ speaker attribution | media-presence columns ("mentioned on podcasts"), founder thought-leadership signals | $.005/call |
| Jinko | `jinko` | Travel: destination fares | travel-industry lists needing fare data (rare) | $.005/call |

More providers exist on request (contact Exa). Full docs: https://exa.ai/docs (Exa Connect).

## Typical mappings for company research

- "how big are they / how funded are they" columns (`employeeCount`, `totalRaisedUsdM`,
  `fundingStage`) → **fiber_ai**
- "how much traction does their site have" columns (`monthlyVisits`, `trafficRank`) → **similarweb**
- "are they a legitimate registered business / who are the officers" → **baselayer** (US only)
- list is public companies, or columns need ticker-keyed news/financials → **financial_datasets**
- "what do they sell and at what price" (e-commerce/DTC lists) → **affiliate**
- "are the founders visible on podcasts / media" → **particle**

A plain "find companies matching X" list with no such columns needs **no** `dataSources` at all —
Exa web search alone is the right tool, and it's cheaper.

## Attach syntax

```jsonc
{
  "query": "… Use Fiber.ai for funding and headcount; use Similarweb for traffic estimates. …",
  "dataSources": [ { "provider": "fiber_ai" }, { "provider": "similarweb" } ],
  "outputSchema": { /* field descriptions name the source, see company-schema.json */ }
}
```

Attach the same providers on the **verification pass** when the facts being checked came from
them (e.g. re-check funding stage with fiber_ai attached) — verifying a partner-sourced number
with only web search downgrades good data to "unknown".
