#!/usr/bin/env python3
"""Render candidates.csv into a self-contained interactive HTML viewer.

Usage:  python3 render_viewer.py <input.csv> <output.html> [--title "Role name"]

Parses the CSV (stdlib only), embeds the rows as JSON into
viewer/candidate-viewer.template.html, and writes one HTML file that works
offline: sortable/filterable table, search, expandable per-candidate details,
clickable LinkedIn and source-citation links. The CSV stays the source
artifact; the HTML is just a view over it.
"""
import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "viewer" / "candidate-viewer.template.html"
PLACEHOLDER = "/*__PAYLOAD__*/ null"


def render(csv_path, html_path, title="Candidates"):
    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        try:
            headers = next(reader)
        except StopIteration:
            sys.exit(f"ERROR: {csv_path} is empty (expected a header row)")
        # pad/trim ragged rows to the header width
        rows = [r[:len(headers)] + [""] * (len(headers) - len(r)) for r in reader]

    template = TEMPLATE.read_text(encoding="utf-8")
    if template.count(PLACEHOLDER) != 1:
        sys.exit(f"ERROR: placeholder {PLACEHOLDER!r} not found once in {TEMPLATE}")

    payload = {"title": title, "csv": Path(csv_path).name,
               "generated": date.today().isoformat(), "headers": headers, "rows": rows}
    # < keeps embedded data from ever closing the <script> tag
    blob = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    Path(html_path).write_text(template.replace(PLACEHOLDER, blob), encoding="utf-8")
    print(f"wrote {html_path} ({len(rows)} rows); open it in a browser to review")
    return len(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("csv_path", help="input CSV (e.g. candidates.csv)")
    ap.add_argument("html_path", help="output HTML (e.g. candidates.html)")
    ap.add_argument("--title", default="Candidates", help="page title, e.g. the role")
    a = ap.parse_args()
    if not Path(a.csv_path).exists():
        sys.exit(f"ERROR: {a.csv_path} not found")
    render(a.csv_path, a.html_path, a.title)


if __name__ == "__main__":
    main()
