# Skill Anatomy

Each skill lives at `skills/<name>/SKILL.md`. Keep the entrypoint concise and put conditional detail in a colocated `references/` directory.

## Required contract

- YAML frontmatter contains `name` and `description`.
- `name` is kebab-case and matches its directory.
- `description` says what the skill does and when to use it. It should distinguish nearby skills rather than list every feature.
- Instructions identify required tools or credentials when they are not universally available.
- Multi-step or artifact-producing workflows include evidence-based verification.
- Networked or asynchronous workflows explain terminal failures and bounded retry behavior.
- Local references stay inside the skill directory and are linked from `SKILL.md`.
- Instructions describe capabilities such as file writing, shell execution, browsers, and isolated subtasks without assuming a specific agent host.

## Recommended shape

Use only the sections that improve behavior. Common choices are:

- Overview or scope
- When to use and when not to use
- Prerequisites or tool selection
- Workflow
- Failure handling
- Red flags or common mistakes
- Output contract
- Verification

Equivalent headings are fine. Do not add empty sections or a large template to satisfy appearances.

## Progressive disclosure

Keep shared decisions and constraints in `SKILL.md`. Move substantial endpoint details, schemas, or mode-specific examples into `skills/<name>/references/`. Link references directly and say when they matter.

Do not create repository-root shared references. A skill installed on its own must carry everything it needs.

## Verification standard

Verification must name observable evidence: a valid response shape, terminal run state, cited sources, requested row count, a parseable artifact, or a successful request. “Looks correct” is not verification.
