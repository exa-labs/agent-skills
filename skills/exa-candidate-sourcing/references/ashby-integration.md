# Ashby ATS integration (optional)

Ashby is one ATS; this skill's core pipeline is ATS-agnostic. Use this reference **only when the
Ashby MCP server is connected**. If it isn't, do not mention Ashby; the CSV/HTML output is the
deliverable.

**Offer, never auto-run.** Writing candidates, applications, notes, or stage changes into a live
ATS is outward-facing and hard to undo. Always propose it, confirm *which* candidates and *which*
job, and get a yes before any write. Read every candidate fact from `candidates.csv` (the
artifact), never from memory of the run — same rule as the rest of the skill.

Every Ashby tool takes a `reason` argument: a one-sentence summary of the goal (e.g. "push a
sourced shortlist into the ATS"). Never put raw conversation text in it.

## Where it plugs into the workflow

- **Entry point — start from an Ashby job (Step 1).** The ergonomic front door: when the user names
  or implies a role instead of pasting a JD, pull the JD from Ashby and build the plan from it.
- **Input side — dedupe against the live pipeline (Step 1 checkpoint).** Pull the people already on
  the job and feed them into `exclude_people` / `input.exclusion` so sourcing doesn't re-surface them.
- **Output side — push the verified shortlist (after Step 6).** Turn the ranked CSV into real
  candidate records + applications on the job, each with a note carrying the score, rubric, and
  sources. This is where the skill otherwise dead-ends at a file.

All three key off the **job id**, so resolve it once and reuse it:

```
search_records_by_name(entityType: "job", query: "<role / job title>", reason: "...")
```

If more than one job matches, show the matches (title · team · location) and let the user pick —
**never guess** (open reqs often have near-duplicate titles). If the user names no role, offer to
`filter_records(objectType: "job", filter: {"field":"status","operator":"equals","value":"Open"},
resultMode: "summary")` and let them pick from the open roster. Keep the resolved `jobId` for the
dedupe and push steps — don't re-resolve it.

## Entry point — pull the JD from an Ashby job (Step 1)

When the user starts from a role rather than pasted text, this replaces "read the pasted JD". Two
hydration calls after you have the `jobId`:

1. `get_record_details(entityType: "job", entityIds: [jobId])` → metadata (`title`, `team`,
   `location`, `confidential`) plus **`defaultJobPostingId`**. The JD body is *not* on the job.
2. `get_record_details(entityType: "job_posting", entityIds: [defaultJobPostingId])` → the
   **`description`** field is the full JD. Also returns structured `location` + `workplaceType`.

Then:

- **Confirm the resolved job before spending** — show `title · team · location` and a one-line JD
  snippet so a wrong duplicate match doesn't burn a run.
- Build the Step-1 plan from `description` exactly as you would from a pasted JD, and **auto-fill
  `locations`** from the posting's `location` / `workplaceType`.
- **Prime the rest in the same turn** (this was the chosen entry behavior): pull the pipeline for
  dedupe (see input side) and keep `jobId` for the push (see output side), so the checkpoint shows
  an already-primed plan.
- **Empty/unpublished posting?** `description` comes back null or thin — fall back to asking the
  user to paste the JD.

## Output side — push the shortlist

For each candidate the user chose to push (default suggestion: the confirmed, eligible top N):

1. **Dedupe first.** `search_records_by_name(entityType: "candidate", query: "<name>")`. If a
   plausible match exists, add the note to that existing candidate instead of creating a duplicate;
   `create_candidate` has no dedupe key of its own.
2. **Create the candidate** (skip if step 1 found them):
   ```
   create_candidate(
     name,
     email?, phoneNumber?,              # only if contact fields were enriched (Step 2)
     socialLinks: [ { url: "<linkedinUrl>", type: "LINKEDIN" },
                    { url: "<other profile>", type: "GITHUB" | "WEBSITE" | ... } ],
     reason: "..."
   ) -> candidateId
   ```
   Valid `socialLinks.type`: LINKEDIN, GITHUB, TWITTER, MEDIUM, STACK_OVERFLOW, WEBSITE, YOUTUBE,
   CODEPEN. Map the CSV's `linkedinUrl` to a LINKEDIN link; other public profile URLs as fitting.
3. **Add it to the job:** `consider_candidate_for_job(candidateId, jobId, reason)`. Starts at the
   first interview stage. To place it elsewhere, get a stage id from
   `get_interview_plan(jobId)` and pass `interviewStageId` (Hired/Archived stages are rejected).
4. **Attach the evidence as a note:** `add_note_to_candidate(candidateId, noteText, reason)`.
   `noteText` supports markdown. Build it from that candidate's CSV row, e.g.:
   ```
   **Sourced via Exa — match {score}% ({overall_tier}, confidence {confidence})**
   Current: {currentTitle} @ {currentCompany} · {location}
   Rubric: {dimension}: {level}; {dimension}: {level}; ...
   Likely-to-move: {likely_to_move} ({seniority_vs_role}, {months_in_current_role} mo in role)
   Concerns: {concerns}
   Verification: {verify_exists} / role match {verify_match}
   Sources: {sources}
   ```

## Input side — dedupe against the pipeline

`get_job_pipeline` returns only per-stage **counts**, not people — it can't dedupe. To get the
actual candidates already on the job, use `filter_records`:

1. Find the right field path first — don't invent one:
   `describe_object_fields(objectType: "application", searchTerm: "job stage archived")`.
2. `filter_records(objectType: "application", filter: <JSON: this job, not archived>,
   resultMode: "summary")` → application summaries (ids + candidate names). Paginate via `cursor`.
3. For LinkedIn URLs to strengthen the dedupe, `get_candidate(candidateIds: [...])` on the matches.
4. Feed the collected names (and LinkedIn URLs) into the Step 1 checkpoint's "existing list to
   dedupe against" → the `exclude_people` config key, or `input.exclusion` when running by hand.

## Guardrails recap

- Only when Ashby is connected; otherwise never mention it.
- Offer and confirm scope (which candidates, which job) before any write; ATS writes are hard to undo.
- Dedupe candidates before creating them.
- Facts come from `candidates.csv`, not memory.
- The orchestrator (`orchestrator/source_candidates.py`) is stdlib-only and cannot call the MCP —
  all Ashby steps are agent-driven, done by you after the pipeline produces the CSV.
