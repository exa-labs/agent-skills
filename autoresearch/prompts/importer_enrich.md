You are preparing an evaluation scenario for a candidate-sourcing skill. The
current directory is a scenario package containing jd.md (a real job
description or sourcing query supplied by the user) plus TODO-templated
persona.md and expectations.json.

Read jd.md, then overwrite the two files:

## persona.md — the script for a simulated recruiter

Write it so an LLM can play a believable, busy recruiter hiring for this JD:

- Who they are (company/agency, tone) and their OPENING message (which pastes
  or references the JD and states the ask, e.g. "find me ~25 people").
- "Preferences you reveal only when asked": realistic ones a JD omits —
  seniority band, dealbreakers, company-background preferences, location
  strictness (hard vs nice-to-have), an exclusion of the hiring company's own
  employees where that makes sense. These must be consistent with
  expectations.json below.
- "Curveballs": 0-2 scripted mid-conversation moves with explicit triggers
  (e.g. "after the plan is presented, add: also exclude anyone currently at
  X"). Only add curveballs that make sense for this JD.
- "What satisfies you": when they should accept.

## expectations.json — machine-checkable END-STATE constraints

Fill the existing keys (keep the JSON shape, drop the _TODO key):
- target_count: from the persona's ask.
- exclude_employer_terms: lowercase substrings that must never appear in a
  returned candidate's currentCompany (the hiring company and anything the
  persona excludes — include common abbreviations/variants).
- excluded_people: any specific people the persona excludes (usually []).
- location: strict true/false per the persona; accept_patterns = downcased
  regexes matching acceptable location strings; allow_unknown.
- must_have_column_patterns: 1-3 lowercase regexes that would match the
  rubric-dimension column names a competent run derives from this JD's hard
  requirements (e.g. "rust|backend"); [] if too unpredictable.
- must_haves_semantic: the JD's hard requirements as short sentences, for the
  fact-checking validator. PERSON-INVARIANT facts only (role, employer,
  experience, location band) — never deliverable properties like "the row
  includes an email / phone / personalization"; those are graded per-run by
  the deterministic checks, while these verdicts freeze into permanent
  per-person labels that a later, better run cannot shake off.

## Ground-truth rule (hard)

Every graded constraint must derive from the JD or from a persona CHOICE you
script — never from your memory of the world (you have no web access here).
Do not invent world-facts as constraints (team sizes, org charts, market
figures) or cite sources you have not read; if the ask is open-ended
("as many as you can find"), set target_count to null rather than estimating.
Excluded people/companies are persona choices and must be communicated in
conversation before they are graded. For strict-location asks, accept_patterns
must be complete for the stated region — a missing pattern falsely fails a
legitimate candidate on a hard gate.

Constraints in expectations.json describe the state AFTER all curveballs.
Keep both files consistent with each other and with jd.md. Also update
scenario.json's "status" from "needs_review" to "drafted" and set a sensible
"target_count". Do not touch jd.md or jd.source. When done, summarize what
persona and constraints you chose in three sentences.
