# MCP-only candidate sourcing

Use this workflow when Exa MCP tools are available but shell, Python, or persistent files are not.
The conversation is the session: retain the current brief, candidate pool, and run IDs in context.

## Contents

1. Session ledger
2. Calibration run
3. Feedback and reuse
4. Expansion runs
5. Consolidation and verification
6. Output

## 1. Session ledger

After the recruiter confirms the plan, maintain a compact current brief in the conversation:

```text
Role:
Hard constraints:
  Locations:
  Location mode: required | preferred
  Excluded current employers:
  Exclusion list confirmed: yes | no
  Required seniority:
  Other hard requirements:
    key / exact description / unknown policy (exclude | allow)
Preferences:
Rubric dimensions:
Segments:
Target:
Contact fields:
```

On follow-up feedback, update this ledger by patch. Show changed rules and preserved hard constraints
before calling Exa again. Never reconstruct the brief only from the latest user message.

Do not silently expand an employer category into a blacklist. If the recruiter says “companies with
noncompetes,” “agencies,” or similar, show the exact proposed employer list and obtain confirmation
before applying it. For any hard fact that may not be public, confirm whether `unknown` should exclude
the candidate or remain eligible.

Show all nonstandard hard requirements and unknown policies together before calibration. Treat each
confirmation as scoped to the item answered; a reply about contractor detection does not also
confirm a pending employer list. If the recruiter requests a proxy rule, record the observable rule
literally rather than claiming it proves another fact.

Keep these run-time items separately in conversation context:

- calibration run ID;
- last expansion run ID per segment;
- deduplicated candidate pool;
- identity-verification verdicts;
- the brief version used for role-fit verdicts.

Identity verification can survive a brief change. Role-fit verdicts cannot: recompute them whenever
role requirements change materially.

## 2. Calibration run

Call Exa `agent_run` once at `effort: "medium"`. Include the complete current brief and every
segment. Ask for up to two representative candidates per segment, exactly one segment assignment
per person, and no duplicates.

Construct the output schema in the call payload. Do not create a schema file. Use this shape:

```text
object, additionalProperties=false
  segmentResults: object, additionalProperties=false
    <one required property for every segment label>:
      coverage: enum(found, weak, none)
      notes: string
      candidates: array, maxItems=2
        name: string
        currentTitle: string
        currentCompany: string
        location: string|null
        linkedinUrl: string|null, format=uri
        seniorityLevel: enum(ic_mid, ic_senior, ic_staff_principal,
                             manager, director_plus, unknown)
        fitSummary: string
        concerns: string[]
        currentlyAtExcludedEmployer: boolean  # only when employer exclusions exist
        hardConstraintChecks:                 # only when other hard requirements exist
          <one required property per requirement key>:
            status: enum(meets, fails, unknown)
            signals: string[]
```

Set every listed object field as required and use `additionalProperties: false` throughout. Every
segment property must be required, but its candidates array may be empty. This guarantees that the
run accounts for each proposed pool without forcing a weak or invented candidate.

Calibration query requirements:

- Repeat all hard constraints verbatim and apply them to every segment.
- Require a check for every additional hard requirement. Use `meets` or `fails` only with direct
  public evidence and `unknown` otherwise.
- Never use short tenure, employer category, or another proxy for contractor status or another
  requested fact.
- Provide each segment label and focus.
- Mark the results provisional and suitable for talent-pool calibration.
- Require `coverage=weak` or `none` when credible matches are scarce.
- Prohibit duplicates across segments.
- Confirm only basic public identity, employer, title, location, and LinkedIn URL.
- Skip contacts, mobility, full rubric grading, and exhaustive corroboration.
- Never fabricate; return an empty array rather than weakening a hard requirement.

If `agent_run` returns a run ID instead of a completed result, call it again with `runId` to wait.
Present the completed sample grouped by segment and ask for concrete feedback.
Require explicit approval of the segments to expand. Feedback about keeping constraints strict is
not segment approval. If the sample predicts near-zero yield, explain that and confirm the larger
paid expansion separately.

## 3. Feedback and reuse

Classify the feedback before starting another search:

| Feedback | Action |
| --- | --- |
| Exclude named employers or people | Filter the pool immediately |
| Make a known location mandatory | Filter immediately |
| Change preference weights | Rescore existing evidence |
| Add a criterion absent from candidate data | Enrich surviving candidates with `input.data` |
| Reject or add a talent segment | Change the segment set |
| Request more under unchanged brief | Continue the relevant run IDs |

After filtering, report how many candidates remain. If the pool already meets the target, do not
run discovery again.

For targeted enrichment, send only surviving candidate rows through `input.data` with stable IDs.
Request only the newly needed evidence and echo each ID in the response. Join by ID, never by name.

## 4. Expansion runs

Expand only approved or underfilled segments. Use one `agent_run` per segment at `effort: "medium"`
so coverage, retries, and continuation remain isolated.

Do not place lightweight calibration records directly in the final ranking. Fully research approved
calibration profiles with the expansion schema first, or omit them until an expansion run returns
their complete rubric data.

Build the candidate schema dynamically from the current rubric. Each candidate object must contain:

- `name`, `currentTitle`, `currentCompany`, nullable `location`, nullable `linkedinUrl`, and nullable
  `yearsRelevantExperience`;
- `currentlyAtExcludedEmployer` only when employer exclusions exist;
- `hardConstraintChecks`, with one required `{status, signals}` object for every additional hard
  requirement;
- every requested contact field as a nullable formatted string, only when explicitly requested;
- one object per rubric dimension: `level` plus concrete `signals`;
- `seniority {level, signals}`;
- `overallFit {tier, confidence, signalsUsed, concerns}`;
- `mobility {monthsInCurrentRole, monthsAtCurrentCompany, avgMonthsPerPriorRole,
  seniorityVsRole, signals}`.

Use these enums:

- capability dimension: `strong`, `partial`, `none`, `unknown`;
- strength dimension: `none`, `weak`, `medium`, `strong`, `unknown`;
- seniority: `ic_mid`, `ic_senior`, `ic_staff_principal`, `manager`, `director_plus`, `unknown`;
- overall tier: `exceptional`, `strong`, `moderate`, `weak`, `unknown`;
- confidence: `low`, `medium`, `high`;
- seniority versus role: `step_up`, `aligned`, `step_down`, `unknown`.

Set all fields required, keep nullable values nullable, use `additionalProperties: false`, and bound
the candidates array to approximately 12.

Every discovery query must:

- repeat the complete current brief, including all hard constraints;
- evaluate every hard constraint from direct evidence; return `unknown` rather than substituting a
  proxy;
- describe the one segment as where to look, not as ground truth;
- grade every dimension using public evidence;
- use dated public history for mobility and return null when dates are unsupported;
- grade strictly: direct evidence for `strong`, inference for `partial`, and no more than one or two
  `exceptional` candidates per batch;
- search beyond headlines and corroborate where practical;
- never fabricate identity, URLs, dates, employers, or contacts.

Pass known people through `input.exclusion`. When requesting more under an unchanged brief, pass the
segment's last `previousRunId` and still repeat the complete current brief. If the brief or segment
focus changed, start a fresh run; do not continue stale research context.

## 5. Consolidation and verification

Deduplicate by normalized LinkedIn slug, falling back to normalized name. Apply all hard constraints
locally before scoring. Use [scoring-and-calibration.md](scoring-and-calibration.md) exactly.

Take approximately `target + 14` top candidates and verify in batches of about eight at
`effort: "high"`. Send rows through `input.data` with a stable `id`; require each verdict to echo it.
The verdict schema contains:

- `id`, `name`;
- `exists`: `confirmed`, `likely`, `uncertain`, `not_found`;
- `linkedin_valid`: `valid`, `unverifiable`, `wrong`;
- `matches_role`: `strong`, `partial`, `weak`, `no`;
- `verified_title_company`;
- `currently_excluded` only when employer exclusions exist.
- `hardConstraintChecks` when additional hard requirements exist.

Join verdicts by stable ID. Drop `not_found`, `matches_role=no`, excluded-employer matches, and rows
with neither a LinkedIn URL nor a known company. Also drop a candidate when a hard check is `fails`,
or when it is `unknown` and that requirement's unknown policy is `exclude`. Reuse identity verdicts
after a brief change, but rerun role-fit and hard-constraint evaluation under the updated brief.
When only an unknown policy changes, reuse the verified `meets`/`fails`/`unknown` facts and apply the
new policy; never replace them with earlier discovery checks.

Keep source URLs from `output.grounding`. Attribute `structured.candidates[i]` and its subfields to
candidate `i`; ignore run-level grounding that cannot support a specific candidate.

## 6. Output

Return a ranked markdown table with name, title/company, location, match score, likely-to-move,
verification, segment, LinkedIn URL, and sources. Also include per-dimension grades, concerns, and
the mobility inputs somewhere in the result so both scores remain explainable.

Because this path has no filesystem, do not promise CSV, XLSX, or HTML artifacts. Keep the structured
candidate pool in conversation context for the next refinement.
