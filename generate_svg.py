#!/usr/bin/env python3
"""
Generate an embeddable SVG star chart for GitHub README.
Style: Observatory / Carte stellaire.

Usage local (avec gh):
    python generate_svg.py

Usage CI (avec GITHUB_TOKEN):
    GITHUB_TOKEN=xxx python generate_svg.py

Env vars:
    REPO            override repo (default: scub-france/Docling-Studio)
    OUTPUT          output file (default: stars.svg)
    GITHUB_TOKEN    for CI usage (gh cli not needed)
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from urllib.request import Request, urlopen

REPO = os.environ.get("REPO", "scub-france/Docling-Studio")
OUTPUT = os.environ.get("OUTPUT", "stars.svg")


def fetch_stargazers():
    """Fetch all stargazers — tries gh cli first, falls back to urllib."""
    # Try gh cli
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{REPO}/stargazers",
             "-H", "Accept: application/vnd.github.v3.star+json",
             "--paginate"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0 and result.stdout.strip():
            raw = result.stdout.strip().replace("]\n[", ",").replace("][", ",")
            return parse_response(json.loads(raw))
    except FileNotFoundError:
        pass

    # Fallback: urllib with token
    token = os.environ.get("GITHUB_TOKEN")
    headers = {"Accept": "application/vnd.github.v3.star+json", "User-Agent": "star-chart"}
    if token:
        headers["Authorization"] = f"token {token}"

    all_data = []
    page = 1
    while True:
        req = Request(f"https://api.github.com/repos/{REPO}/stargazers?per_page=100&page={page}", headers=headers)
        with urlopen(req) as resp:
            data = json.loads(resp.read().decode())
        if not data:
            break
        all_data.extend(data)
        page += 1

    return parse_response(all_data)


def parse_response(data):
    stars = [{"user": s["user"]["login"], "date": s["starred_at"]} for s in data]
    stars.sort(key=lambda x: x["date"])
    return stars


def generate_svg(stars):
    total = len(stars)
    if total == 0:
        print("No stars found.")
        return

    W, H = 840, 320
    pt, pb, pl, pr = 80, 50, 60, 40
    cw = W - pl - pr
    ch = H - pt - pb

    dates = [datetime.fromisoformat(s["date"].replace("Z", "+00:00")) for s in stars]
    first, last = dates[0], dates[-1]
    span = (last - first).total_seconds() or 1

    points = []
    for i, d in enumerate(dates):
        x = pl + ((d - first).total_seconds() / span) * cw
        y = pt + ch - ((i + 1) / total) * ch
        points.append((x, y))

    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)

    area = f"M {points[0][0]:.1f},{pt + ch}"
    for x, y in points:
        area += f" L {x:.1f},{y:.1f}"
    area += f" L {points[-1][0]:.1f},{pt + ch} Z"

    # Y ticks
    step = max(1, total // 5)
    y_ticks = [(pt + ch - (v / total) * ch, v) for v in range(0, total + 1, step)]
    if y_ticks[-1][1] != total:
        y_ticks.append((pt, total))

    # X ticks (months)
    x_ticks = []
    seen = set()
    for d in dates:
        key = (d.year, d.month)
        if key not in seen:
            seen.add(key)
            x = pl + ((d - first).total_seconds() / span) * cw
            x_ticks.append((x, d.strftime("%b %y")))

    now = datetime.now(timezone.utc)
    this_week = sum(1 for d in dates if (now - d).total_seconds() < 7 * 86400)
    days_span = max(1, (last - first).days)
    per_week = total / (days_span / 7)
    gen_time = now.strftime("%d %b %Y %H:%M UTC")

    # Milestones
    milestones = [(points[t-1][0], points[t-1][1], t)
                  for t in [10, 25, 50, 100, 250, 500, 1000] if t <= total]

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <style>
    text {{ font-family: system-ui, -apple-system, 'Segoe UI', sans-serif; }}
  </style>
  <defs>
    <pattern id="h" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">
      <line x1="0" y1="0" x2="0" y2="6" stroke="rgba(26,25,21,0.07)" stroke-width="1"/>
    </pattern>
    <linearGradient id="lg" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#1a1915" stop-opacity="0.4"/>
      <stop offset="30%" stop-color="#1a1915"/>
      <stop offset="100%" stop-color="#8b2500"/>
    </linearGradient>
  </defs>

  <rect width="{W}" height="{H}" rx="4" fill="#f5f0e8"/>
  <rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="4" fill="none" stroke="rgba(26,25,21,0.12)"/>

  <!-- Header -->
  <text x="{pl}" y="32" font-size="11" font-weight="600" letter-spacing="0.14em" fill="#1a1915">OBSERVATOIRE</text>
  <text x="{pl+105}" y="32" font-size="11" fill="#c9a227" letter-spacing="0.08em">\u00b7</text>
  <text x="{pl+118}" y="32" font-size="11" font-weight="500" letter-spacing="0.06em" fill="rgba(26,25,21,0.45)">{REPO}</text>

  <!-- Count -->
  <text x="{W-pr}" y="30" font-size="34" font-weight="800" fill="#1a1915" text-anchor="end" letter-spacing="-0.02em">{total}</text>
  <text x="{W-pr}" y="46" font-size="10" fill="rgba(26,25,21,0.35)" text-anchor="end" font-style="italic">etoiles observees</text>

  <!-- Weekly badge -->
  <rect x="{W-pr-96}" y="54" width="96" height="20" rx="2" fill="none" stroke="rgba(201,162,39,0.35)"/>
  <text x="{W-pr-48}" y="67" font-size="9" font-weight="600" fill="#c9a227" text-anchor="middle" letter-spacing="0.04em">\u2197 +{this_week} THIS WEEK</text>

  <line x1="{pl}" y1="{pt-6}" x2="{W-pr}" y2="{pt-6}" stroke="rgba(26,25,21,0.1)"/>

'''

    # Y grid
    for y, v in y_ticks:
        svg += f'  <line x1="{pl}" y1="{y:.1f}" x2="{W-pr}" y2="{y:.1f}" stroke="rgba(26,25,21,0.05)"/>\n'
        svg += f'  <text x="{pl-8}" y="{y+3:.1f}" font-size="9" fill="rgba(26,25,21,0.3)" text-anchor="end" font-weight="500">{v}</text>\n'

    # X labels
    for x, label in x_ticks:
        svg += f'  <text x="{x:.1f}" y="{pt+ch+18}" font-size="9" fill="rgba(26,25,21,0.3)" font-weight="500" letter-spacing="0.03em">{label}</text>\n'

    # Axes
    svg += f'''
  <line x1="{pl}" y1="{pt}" x2="{pl}" y2="{pt+ch}" stroke="rgba(26,25,21,0.12)"/>
  <line x1="{pl}" y1="{pt+ch}" x2="{W-pr}" y2="{pt+ch}" stroke="rgba(26,25,21,0.12)"/>

  <path d="{area}" fill="url(#h)"/>
  <polyline points="{polyline}" fill="none" stroke="url(#lg)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>

  <circle cx="{points[-1][0]:.1f}" cy="{points[-1][1]:.1f}" r="4.5" fill="#8b2500"/>
  <circle cx="{points[-1][0]:.1f}" cy="{points[-1][1]:.1f}" r="2" fill="#f5f0e8"/>
'''

    # Milestones
    for mx, my, mv in milestones:
        svg += f'  <circle cx="{mx:.1f}" cy="{my:.1f}" r="2.5" fill="#c9a227" opacity="0.8"/>\n'
        svg += f'  <text x="{mx+6:.1f}" y="{my+3:.1f}" font-size="8" fill="#c9a227" font-weight="600">{mv}</text>\n'

    # Footer
    svg += f'''
  <line x1="{pl}" y1="{H-18}" x2="{W-pr}" y2="{H-18}" stroke="rgba(26,25,21,0.06)"/>
  <text x="{pl}" y="{H-6}" font-size="8" fill="rgba(26,25,21,0.25)" font-style="italic">{per_week:.1f} etoiles/sem \u00b7 maj {gen_time}</text>
  <text x="{W-pr}" y="{H-6}" font-size="7" fill="rgba(26,25,21,0.18)" text-anchor="end" letter-spacing="0.1em">OBSERVATOIRE MMXXVI</text>

</svg>'''

    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), OUTPUT)
    with open(output_path, "w") as f:
        f.write(svg)

    print(f"Generated {output_path}")
    print(f"  {total} stars, +{this_week} this week, {per_week:.1f}/week")


if __name__ == "__main__":
    stars = fetch_stargazers()
    generate_svg(stars)
