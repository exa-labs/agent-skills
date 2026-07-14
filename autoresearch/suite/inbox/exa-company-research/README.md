# Inbox: exa-company-research

Drop one file per tough research query here — the raw ask as you'd type it
(e.g. "find all Series B fintechs in the GCC with >50 employees that use
Snowflake").

The pipeline's active target is set by `skill.name` in `pipeline/config.json`
(currently `exa-candidate-sourcing`); `cli.py import` reads the active
skill's inbox only, so files here wait untouched. Pointing the pipeline at
this skill additionally needs an expectations schema + validator profile for
its output format (the current validator judges a recruiting candidates.csv)
— collect queries now, wire that up as phase two.
