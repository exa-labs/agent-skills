# Regression set (accumulating)

`<skill-name>/labeled.jsonl` — append-only labels on candidates the skill
actually returned, one JSON object per line:

```json
{"scenario": "s001", "key": "li:jane-doe", "name": "Jane Doe",
 "label": "valid|violation", "provenance": "auto|human",
 "recorded_in": "<run_id>", "verdict": { ...frozen grounding verdict... }}
```

- `auto` labels are written by the grounded fact-checker at record time.
- Override any label by hand: `python3 pipeline/cli.py label --scenario s001
  --key li:jane-doe --label violation --notes "wrong person"` — human lines
  always beat auto lines.
- Replay runs join these labels instead of re-fetching sources, and any
  known-`violation` candidate reappearing in a final list is a **regression
  hit** that fails the edit under evaluation.
