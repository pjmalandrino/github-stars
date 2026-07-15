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
import sys
from datetime import datetime, timezone
from urllib.request import Request, urlopen

PACKAGE_URL = os.environ.get(
    "PACKAGE_URL",
    "https://github.com/scub-france/Docling-Studio/pkgs/container/docling-studio",
)
OUTPUT = os.environ.get("DOWNLOADS_FILE", "downloads.json")

# GitHub renders the cumulative total inside an <h3> that follows the
# "Total downloads" label. Large counts are abbreviated for display
# ("1.33K", "1.2M"); when abbreviated, the exact value is kept in the
# element's title attribute. We locate the <h3> after the label and read
# the exact title when present, otherwise expand the abbreviated text.
H3_AFTER_LABEL_RE = re.compile(
    r"Total downloads.*?<h3\b([^>]*)>(.*?)</h3>",
    re.DOTALL | re.IGNORECASE,
)
TITLE_ATTR_RE = re.compile(r'title="([\d,]+)"')
ABBREV_RE = re.compile(r"^([\d.,]+)\s*([KMB]?)$", re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")
RECT_RE = re.compile(
    r'data-merge-count="(\d+)"\s+data-date="(\d{4}-\d{2}-\d{2})"'
)

_MULTIPLIERS = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}


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


def _parse_count(text):
    """Turn a rendered count ('979', '1,330', '1.33K') into an int, or None."""
    m = ABBREV_RE.match(text.strip())
    if not m:
        return None
    number, suffix = m.group(1), m.group(2).upper()
    try:
        value = float(number.replace(",", ""))
    except ValueError:
        return None
    return int(round(value * _MULTIPLIERS[suffix]))


def parse(html):
    m = H3_AFTER_LABEL_RE.search(html)
    if not m:
        raise RuntimeError("Could not find 'Total downloads' on package page")

    attrs, inner = m.group(1), m.group(2)
    total = None
    title = TITLE_ATTR_RE.search(attrs)
    if title:
        total = int(title.group(1).replace(",", ""))
    else:
        total = _parse_count(TAG_RE.sub("", inner))
    if total is None:
        raise RuntimeError(
            "Found 'Total downloads' but could not parse the count from the page"
        )

    daily = {date: int(count) for count, date in RECT_RE.findall(html)}
    return total, daily


def main():
    html = fetch_page()
    try:
        total, new_daily = parse(html)
    except RuntimeError as exc:
        # Scraping a public HTML page is inherently brittle: GitHub can
        # change the markup at any time. Don't fail the whole workflow (and
        # block the star-chart commit) over it — keep the existing data.
        print(f"warning: {exc}; keeping existing {OUTPUT}", file=sys.stderr)
        return
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
