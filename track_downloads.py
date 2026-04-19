#!/usr/bin/env python3
"""
Append a daily snapshot of total GitHub release downloads to downloads.json.

Env:
    REPO            default: scub-france/Docling-Studio
    OUTPUT          default: downloads.json
    GITHUB_TOKEN    required in CI to avoid rate limits
"""

import json
import os
from datetime import datetime, timezone
from urllib.request import Request, urlopen

REPO = os.environ.get("DOWNLOADS_REPO", os.environ.get("REPO", "scub-france/Docling-Studio"))
OUTPUT = os.environ.get("DOWNLOADS_FILE", "downloads.json")


def fetch_total():
    token = os.environ.get("GITHUB_TOKEN")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "downloads-tracker"}
    if token:
        headers["Authorization"] = f"token {token}"

    total = 0
    page = 1
    while True:
        req = Request(
            f"https://api.github.com/repos/{REPO}/releases?per_page=100&page={page}",
            headers=headers,
        )
        with urlopen(req) as resp:
            data = json.loads(resp.read().decode())
        if not data:
            break
        for rel in data:
            for asset in rel.get("assets", []):
                total += asset.get("download_count", 0)
        if len(data) < 100:
            break
        page += 1
    return total


def main():
    total = fetch_total()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), OUTPUT)

    try:
        with open(path) as f:
            history = json.load(f)
    except FileNotFoundError:
        history = []

    if history and history[-1]["date"] == today:
        history[-1]["total"] = total
    else:
        history.append({"date": today, "total": total})

    with open(path, "w") as f:
        json.dump(history, f, indent=2)
        f.write("\n")

    print(f"{today}: {total} total downloads ({len(history)} snapshots)")


if __name__ == "__main__":
    main()
