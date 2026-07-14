# Inbox: exa-candidate-sourcing

Drop one file per evaluation case here: a job description, a job posting
saved as text, or a hard sourcing brief. Any plain-text format (`.md`,
`.txt`); the filename becomes the scenario name.

Then:

```bash
python3 pipeline/cli.py import            # scaffold scenario packages (mechanical)
python3 pipeline/cli.py import --enrich   # + LLM-draft persona.md / expectations.json
```

Each file becomes `suite/scenarios/exa-candidate-sourcing/sNNN-<name>/`.
**Review the drafted persona.md and expectations.json** — they define what
counts as a violation — then set `"status": "ready"` in `scenario.json`.
Processed files move into the scenario dir as `jd.source`, so an empty inbox
means everything has been imported.
