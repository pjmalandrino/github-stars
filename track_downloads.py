#!/usr/bin/env python3
"""
Scrape total + last-30-days download counts from a GHCR container package page
and merge into downloads.json.

The GitHub Packages REST API does not expose download counts for containers.
The public package page embeds the cumulative total in an <h3> and the per-day
counts of the last 30 days as SVG <rect> nodes with data-date / data-merge-count
attributes. We extract both.

Running the script periodically preserves days that fall out of the 30-day
window in the on-disk history.

Env:
    PACKAGE_URL   default: https://github.com/scub-france/Docling-Studio/pkgs/container/docling-studio
    OUTPUT        default: downloads.json
"""

import json
import os
import re
from datetime import datetime, timezone
from urllib.request import Request, urlopen

PACKAGE_URL = os.environ.get(
    "PACKAGE_URL",
    "https://github.com/scub-france/Docling-Studio/pkgs/container/docling-studio",
)
OUTPUT = os.environ.get("DOWNLOADS_FILE", "downloads.json")

TOTAL_RE = re.compile(r"Total downloads</span>\s*<h3[^>]*>(\d+)</h3>")
RECT_RE = re.compile(
    r'data-merge-count="(\d+)"\s+data-date="(\d{4}-\d{2}-\d{2})"'
)


def fetch_page():
    req = Request(
        PACKAGE_URL,
        headers={
            "User-Agent": "Mozilla/5.0 (downloads-tracker)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse(html):
    m = TOTAL_RE.search(html)
    if not m:
        raise RuntimeError("Could not find 'Total downloads' on package page")
    total = int(m.group(1))

    daily = {date: int(count) for count, date in RECT_RE.findall(html)}
    return total, daily


def main():
    html = fetch_page()
    total, new_daily = parse(html)
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), OUTPUT)

    try:
        with open(path) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {}
    except FileNotFoundError:
        data = {}

    merged = {d["date"]: d["count"] for d in data.get("daily", [])}
    merged.update(new_daily)

    daily_sorted = [
        {"date": d, "count": merged[d]} for d in sorted(merged)
    ]

    out = {
        "total": total,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "daily": daily_sorted,
    }

    with open(path, "w") as f:
        json.dump(out, f, indent=2)
        f.write("\n")

    print(f"total={total}, daily_entries={len(daily_sorted)}")


if __name__ == "__main__":
    main()
