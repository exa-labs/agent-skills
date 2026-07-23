# Worked example — AWS "Solutions Architect, ISV"

A complete Step-1 search plan for [amazon.jobs/.../solutions-architect-isv](https://amazon.jobs/en/jobs/10425076/solutions-architect-isv).
Use it as a model for how to fill in the plan from a JD — note that the segments aim at *other*
clouds, ISVs, SIs, and partners, never at Amazon/AWS itself (the `exclude_employer`).

```json
{
  "role": "Solutions Architect, ISV (a customer-facing, pre-sales cloud solutions-architecture role)",
  "locations": ["San Francisco Bay Area", "New York City", "Austin TX", "Dallas TX"],
  "exclude_employer": "Amazon / AWS / Amazon Web Services",
  "hard_constraints": {
    "location_mode": "preferred",
    "excluded_current_employers": [],
    "excluded_current_employers_confirmed": false,
    "required_seniority_levels": [],
    "requirements": []
  },

  "rubric_must_haves": [
    "4+ years in a technical domain: software development, cloud computing, systems engineering, infrastructure, security, networking, or data & analytics.",
    "2+ years of design, implementation, or consulting experience with applications and infrastructure.",
    "Customer-facing / pre-sales ability: leading architecture discussions, customer enablement, relationships with senior technical stakeholders.",
    "Strong cloud-computing expertise (any major cloud) and application architecture at scale."
  ],
  "rubric_signals": [
    "Cloud migration / legacy modernization / cloud transformation experience.",
    "A pre-sales Solutions Architect / Sales Engineer / Customer Engineer title.",
    "Experience at or selling to ISVs (independent software vendors / SaaS companies).",
    "Thought leadership: blogs, whitepapers, conference talks, workshops.",
    "Multi-cloud breadth; software-development background."
  ],

  "dimensions": [
    {"key": "techDomainExperience",       "scale": "capability"},
    {"key": "designConsultingExperience", "scale": "capability"},
    {"key": "customerFacingPresales",     "scale": "capability"},
    {"key": "cloudArchitecture",          "scale": "capability", "extra": ["clouds"]},
    {"key": "migrationModernization",     "scale": "strength"},
    {"key": "thoughtLeadership",          "scale": "strength"}
  ],

  "segments": [
    {"label": "azure_presales",        "focus": "Microsoft Azure pre-sales talent — Azure Cloud Solution Architects, Cloud Solutions Architects, Technical Specialists, Sales Engineers, or Customer Engineers at Microsoft, Microsoft partners (CDW, SHI, Insight, WWT), and Azure-focused ISVs/consultancies."},
    {"label": "googlecloud_presales",  "focus": "Google Cloud (GCP) pre-sales talent — Customer Engineers, Cloud Solutions Architects, Sales Engineers, or Solutions Consultants at Google Cloud, Google Cloud partners, and GCP-focused ISVs/consultancies."},
    {"label": "isv_software_se",       "focus": "Solutions Architects, Solutions Engineers, and Sales Engineers at major data/SaaS/enterprise-software ISVs such as Snowflake, Databricks, MongoDB, Confluent, HashiCorp, Datadog, Elastic, GitLab, Salesforce, ServiceNow, Okta, Splunk."},
    {"label": "si_consultancy",        "focus": "Cloud architects and pre-sales / delivery consultants at systems integrators and consultancies such as Accenture, Deloitte, Slalom, Thoughtworks, Capgemini, Cognizant, Infosys, EPAM, with cloud migration/modernization and customer-facing architecture roles."},
    {"label": "security_network_isv",  "focus": "Solutions Engineers, Sales Engineers, and Solutions Architects at security and networking ISVs such as Palo Alto Networks, CrowdStrike, Zscaler, Fortinet, Cisco, Cloudflare, Okta, and Wiz, with cloud architecture depth."},
    {"label": "cloud_resellers",       "focus": "Pre-sales Solutions Architects, Cloud Architects, and Sales Engineers at cloud resellers, MSPs, and partners such as CDW, SHI, Insight, World Wide Technology (WWT), Presidio, Rackspace, NTT Data, and SADA."}
  ]
}
```

## Adapting to the other example roles

- **Solutions Architect, Travel & Hospitality** — same backbone, but add a GenAI/Agentic
  dimension (the JD is heavy on Generative AI / agentic solutions) and an industry-fit signal;
  consider an `industry_genai` segment (AI/ML SEs at OpenAI/Anthropic partners, Databricks,
  NVIDIA, travel-tech ISVs like Sabre/Amadeus/Expedia).
- **Senior Solutions Architect, ISV** — same plan, but raise the seniority bar: weight
  `seniority` toward `ic_staff_principal+`, expect more years, and bias `thoughtLeadership` higher.

## Calibration and expansion

- First run one combined calibration sample with up to two provisional candidates from each
  segment. Ask the recruiter which pools and profiles are directionally right.
- Patch the confirmed brief, preserving location and other hard constraints, before expansion.
- Expand only approved or underfilled segments.

## Notes from the test run

- Discovery returns ~10–12 graded candidates per segment with real LinkedIn URLs and per-dimension
  evidence; top hits were senior Azure/GCP/ISV pre-sales architects (e.g. Microsoft Cloud Solution
  Architects, Snowflake/Databricks Solutions Engineers).
- The verification pass is what catches inflated self-descriptions and stale titles — don't skip it
  for a real shortlist.
