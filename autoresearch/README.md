# Skill optimization pipeline

Improves a skill by editing it against a **score**, not a vibe. The active
target is `skill.name` in `config.json` (currently `exa-candidate-sourcing`);
every data path (inbox, scenarios, fixtures, labels, experiment logs) is
scoped per-skill, so adding `exa-company-research` later means a new validator
profile + config switch, not a migration. The skill lives in this monorepo at
`skill.path` (e.g. `skills/exa-candidate-sourcing`); `skill.repo` is the repo
root. This harness clones the repo into `workspace/`, runs experiments on
branches (scoped to the skill's subdir), and promotes winners to a
`pipeline/candidate` branch (never `main` — you review and merge that). A
standalone skill still works: leave `skill.path` empty and point `skill.repo`
at its own repo.

Four LLM roles, all `claude -p` subprocesses (stdlib-only Python around them):

| role | model (config.json) | job |
|---|---|---|
| **User** | haiku | plays the recruiter from each scenario's persona: opening ask, checkpoint answers, scripted curveballs, final UX survey |
| **Inner** | sonnet | runs the skill exactly as written, multi-turn (`--resume`), in an isolated run dir |
| **Validator** | sonnet | re-fetches cited sources, judges identity + semantic must-haves; verdicts freeze into the regression label store |
| **Outer** | fable | reads the whole suite's scorecards + experiment history, proposes edits, applies them on `exp/NNN-*` branches |

There is no answer key for live search, so the pipeline never measures recall.
It measures what a run's own output makes checkable: does every returned
candidate satisfy the stated constraints, and is every claim backed by its
cited source.

## Quick start

```bash
# 0. one-time: make sure `claude` and EXA_API_KEY work (source ~/.zshrc)
cd autoresearch

# 1. drop your JDs into suite/inbox/exa-candidate-sourcing/ (company-research
#    queries go in suite/inbox/exa-company-research/ for phase two), then:
python3 cli.py import --enrich        # scaffold scenarios + LLM-draft persona/expectations
#    -> REVIEW each suite/scenarios/<skill>/sNNN-*/persona.md + expectations.json,
#       then set "status": "ready" in its scenario.json

# 2. record: one live run per scenario (costs real Exa + LLM dollars)
python3 cli.py suite --mode live --record
#    freezes search outputs into fixtures/ and grounding verdicts into regression/

# 3. baseline + optimize (cheap: replays frozen fixtures, no Exa spend)
python3 cli.py suite --mode replay
python3 cli.py optimize               # 4 experiments/round per config.json

# 4. inspect and iterate
python3 cli.py status
cat experiments/round-*.json
```

## How a run is judged

Every run gets a `scorecard.json`:

- **Deterministic checks** (`harness/validator/deterministic.py`, no LLM):
  excluded-employer leaks, excluded-people leaks, strict-location violations,
  must-have dimensions the run itself graded `none`, kept candidates that
  verification marked `not_found`/`no`, malformed identities (bad LinkedIn
  URLs, placeholder names), duplicates. Caveat: the must-have column check is
  best-effort — dimension column names are invented per run by the Inner LLM,
  so `must_have_column_patterns` can miss. The scorecard's
  `must_have_columns_checked` shows what actually matched (watch for `[]`);
  the authoritative must-have gate is the grounded semantic check below.
- **Grounded fact-check** (Validator LLM, live runs only): fetches each
  candidate's cited sources; contradicted identity → `fabricated_identity`;
  confident evidence a must-have is missed → `must_have_violation`. Replay
  runs join the frozen verdicts from `regression/labeled.jsonl` instead.
- **UX survey**: the simulated recruiter rates checkpoint quality, clarity,
  efficiency, trust (1–5).

Score = weighted composite of constraints / grounding / delivery / ux
(weights in `config.json`). **Hard gates** sit outside the composite: one
violation of a gated type, a session that never completes, or a labeled-bad
candidate reappearing (**regression hit**) fails the run outright.

The grounding component is computed only over candidates that were actually
checked; unlabeled candidates are reported (`grounding.unlabeled`) but never
scale the score — penalizing them would teach the optimizer to return only the
historically labeled shortlist and stop surfacing new people. Watch the
`unlabeled` stat instead: if it climbs, record a fresh live run to extend
label coverage.

## How an edit is kept

`optimize` runs the Outer LLM over the whole suite's scorecards (never a
single run, so it can't overfit one JD) plus the experiment log (so failed
ideas aren't re-proposed). Each proposal becomes an `exp/NNN-slug` branch;
the suite is re-run against it and compared to baseline
(`harness/scoring.py::compare`). Kept only if:

1. no new gate failures,
2. no component regresses beyond tolerance (default 2 pts),
3. no new regression hits,
4. composite improves ≥ 1 pt — **or** it fixes a baseline gate failure
   without regressing anything.

Winners merge into `pipeline/candidate` in the repo. If that merge
conflicts (two rounds touching the same lines), the round still completes: the
report carries `promotion_conflict` and the winner branch stays pushed for a
manual merge. The workspace clone always re-syncs to the source repo's tip on
checkout, so changes you land in the real repo between rounds are picked
up. Proposals that
touch the **search stage** can't be measured against frozen fixtures — they're
parked as `needs_live`; rerun them with `optimize --mode live` (or `suite
--mode live --ref exp/NNN-...`) when you're ready to spend. Config's
`live_confirm_winners: true` means: before merging `pipeline/candidate` to
main, confirm with one live suite run on that branch.

The must-have-violation bug is deliberately **not** an optimization target —
it's a missing hard gate in the skill. Fix it deterministically (an edit that
adds an explicit drop-gate step), then the Validator keeps it at zero; the
`must_have_violation` hard gate makes any recurrence an automatic reject.

## Record / replay mechanics

Live Exa traffic is intercepted at the **environment level** — the skill is
never modified: a `curl` PATH shim plus a `sitecustomize.py` on `PYTHONPATH`
(covers the orchestrator's urllib) tee every `api.exa.ai` exchange to
`exa_http.jsonl`. The recorder normalizes captures into a fixture bundle
(`fixtures/<scenario>/<recording>/pool.json` + `verify_verdicts.json`),
preferring the orchestrator's `sourcing_state.json`, then the shim log, then
the session transcript. In replay, the same shims *refuse* live calls
(`LIVE_EXA_DISABLED`) and the bundle is materialized as `./exa_runs/` in the
run dir; the Inner agent does the Step-1 checkpoint live, then consolidates /
filters / ranks the frozen pool per the skill.

## Directory map

```
autoresearch/
  cli.py                 entrypoint (import|record|run|suite|compare|optimize|label|validate|status)
  config.json            models, weights, gates, budget, paths
  harness/               the library (stdlib only)
  prompts/               role prompt templates
  shims/                 curl PATH shim + sitecustomize (record/replay interception)
  suite/inbox/<skill>/   <- DROP YOUR JDs / QUERIES HERE (one folder per skill)
  suite/scenarios/<skill>/  scenario packages (created by `import`)
  fixtures/<skill>/      frozen search outputs per scenario
  regression/<skill>/    accumulating label store (labeled.jsonl) — see regression/README
  experiments/<skill>/   log.jsonl + per-round reports
  runs/                  per-run artifacts (gitignored)
  workspace/             monorepo clone for experiments (gitignored)
  tests/                 offline suite: python3 -m unittest discover tests -t tests
```

## Costs & cautions

- A live scenario run ≈ a few dollars (6 discovery runs @ ~$0.10 + verify
  batches @ ~$0.50, plus Inner/Validator LLM turns). Replay runs cost only
  LLM turns — no Exa spend. Estimate per-round spend before `--mode live`.
- The harness runs `claude` with `--permission-mode bypassPermissions` inside
  per-run directories. Keep the repo checked out on `skill.base_ref` while the
  pipeline runs (branches are pushed back to it; that base branch itself is
  never pushed).
- Python 3.14 on this Mac needs `certifi` for the orchestrator's TLS; the
  harness sets `SSL_CERT_FILE` automatically when certifi is importable.
- Inner sessions run with `--strict-mcp-config` (no inherited MCP servers —
  an Exa MCP tool would bypass the shims) and, in replay, with
  WebFetch/WebSearch disallowed, so replay genuinely cannot reach live data.
- Verify on the FIRST live run: (a) that `--permission-mode
  bypassPermissions` is honored in your environment, and (b) that summed
  per-turn `total_cost_usd` isn't cumulative across `--resume` turns (if it
  is, session cost totals are inflated and `claude_cli.py` should diff
  successive values instead).
- Suites only include scenarios whose `scenario.json` has `"status":
  "ready"` (imports start as `needs_review`); un-reviewed scenarios are
  listed under `skipped`.
- Re-running `cli.py validate` on a live run joins the frozen labels instead
  of re-fetching sources; pass `--refetch` to deliberately re-spend validator
  cost and refresh the labels.
- After the first live `record`, eyeball the recorded
  `fixtures/<scenario>/<run>/pool.json` and `verify_verdicts.json` once — the
  offline stub can't prove the harvest path against real transcript shapes.
- Tests are fully offline (a scripted `fake_claude.py` plays all roles):
  `cd autoresearch && python3 -m unittest discover tests -t tests` — 71 tests.
