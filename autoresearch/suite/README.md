# Suite layout — one folder per skill

```
suite/
  inbox/<skill-name>/       drop raw JDs / queries for that skill here
  scenarios/<skill-name>/   scenario packages created by `cli.py import`
```

The active skill is `skill.name` in `pipeline/config.json`; all pipeline
paths (inbox, scenarios, fixtures, regression labels, experiment logs)
resolve per-skill from it, so nothing collides when a second skill is
targeted.

Each scenario package:

| file | role |
|---|---|
| `scenario.json` | id, title, target_count, status (`needs_review` → `drafted` → `ready`) |
| `jd.md` | the JD/query the simulated user supplies |
| `persona.md` | the User-LLM script: preferences revealed only when asked, scripted curveballs, acceptance criteria |
| `expectations.json` | machine-checkable END-state constraints for the deterministic validator (after all curveballs) |

Only scenarios with `"status": "ready"` enter suite runs.

`expectations.json` keys (candidate-sourcing profile): `target_count`,
`exclude_employer_terms` (lowercase substrings banned from `currentCompany`),
`excluded_people`, `location` (`strict` / `accept_patterns` regexes /
`allow_unknown`), `must_have_column_patterns` (regexes over rubric column
names whose value must never be `none`), `must_haves_semantic` (hard
requirements in prose, for the grounded fact-checker).
