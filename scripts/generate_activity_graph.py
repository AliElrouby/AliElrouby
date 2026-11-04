#!/usr/bin/env python3
"""Generate a self-hosted GitHub contributions SVG for a profile README.

Uses only the Python standard library and GitHub's authenticated GraphQL API.
Required environment variables: GH_TOKEN, GH_USER.
"""

from __future__ import annotations

import json
import math
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape

DAYS = 90
OUTPUT = Path("assets/activity-graph.svg")
WIDTH, HEIGHT = 1100, 355
LEFT, RIGHT = 64, 1044
TOP, BOTTOM = 116, 284
BASE = "#101014"
LIME = "#C7F85E"
VIOLET = "#BB91F7"
COPPER = "#D89A65"
TEXT = "#EEECE8"
MUTED = "#97959C"
GRID = "#313039"

QUERY = """
query($user: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $user) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def get_contributions(username: str, token: str, today: date) -> list[int]:
    start = today - timedelta(days=DAYS - 1)
    payload = {
        "query": QUERY,
        "variables": {
            "user": username,
            "from": f"{start.isoformat()}T00:00:00Z",
            "to": f"{today.isoformat()}T23:59:59Z",
        },
    }
    request = Request(
        "https://api.github.com/graphql",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "ali-neural-atlas-activity-generator",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            result = json.load(response)
    except HTTPError as exc:
        details = exc.read().decode("utf-8", "replace")[:800]
        raise RuntimeError(f"GitHub GraphQL HTTP {exc.code}: {details}") from exc
    except URLError as exc:
        raise RuntimeError(f"Cannot reach GitHub GraphQL: {exc.reason}") from exc

    if result.get("errors"):
        raise RuntimeError("GitHub GraphQL error: " + json.dumps(result["errors"])[:1000])
    user = (result.get("data") or {}).get("user")
    if not user:
        raise RuntimeError(f"GitHub did not return contribution data for '{username}'.")
    weeks = user["contributionsCollection"]["contributionCalendar"]["weeks"]
    counts_by_date = {
        day["date"]: int(day["contributionCount"])
        for week in weeks
        for day in week["contributionDays"]
    }
    return [counts_by_date.get((start + timedelta(days=i)).isoformat(), 0) for i in range(DAYS)]


def y_axis_ceiling(max_value: float) -> int:
    if max_value <= 4:
        return 4
    rough = max_value / 4
    magnitude = 10 ** math.floor(math.log10(rough))
    step = next((s * magnitude for s in (1, 2, 2.5, 5, 10) if s * magnitude >= rough), 10 * magnitude)
    return math.ceil(max_value / (4 * step)) * int(4 * step) if step >= 1 else math.ceil(max_value / (4 * step)) * 4 * step


def build_svg(counts: list[int], username: str, today: date) -> str:
    if len(counts) != DAYS or any(not isinstance(n, int) or n < 0 for n in counts):
        raise ValueError(f"Expected {DAYS} nonnegative integer daily counts")
    start = today - timedelta(days=DAYS - 1)
    total = sum(counts)
    active_days = sum(n > 0 for n in counts)
    peak = max(counts)
    averages = [sum(counts[max(0, i - 6):i + 1]) / min(i + 1, 7) for i in range(DAYS)]
    ymax = max(4, int(y_axis_ceiling(max(peak, max(averages)))))
    plot_width = RIGHT - LEFT
    plot_height = BOTTOM - TOP

    def px(i: int) -> float:
        return LEFT + i * plot_width / (DAYS - 1)

    def py(n: float) -> float:
        return BOTTOM - n / ymax * plot_height

    line = " ".join(("M" if i == 0 else "L") + f"{px(i):.2f},{py(v):.2f}" for i, v in enumerate(averages))
    area = line + f" L{RIGHT},{BOTTOM} L{LEFT},{BOTTOM} Z"

    p = [f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="{WIDTH}" height="{HEIGHT}" role="img" aria-label="GitHub activity chart for {escape(username)} with the past 90 days of daily contributions and a 7-day rolling average">
  <defs>
    <linearGradient id="atlasArea" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0%" stop-color="{LIME}" stop-opacity=".20"/>
      <stop offset="100%" stop-color="{LIME}" stop-opacity=".005"/>
    </linearGradient>
    <linearGradient id="atlasBar" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0%" stop-color="{VIOLET}" stop-opacity=".88"/>
      <stop offset="100%" stop-color="{VIOLET}" stop-opacity=".25"/>
    </linearGradient>
  </defs>
  <rect x="1" y="1" width="1098" height="353" rx="18" fill="{BASE}" stroke="#37313A"/>
  <rect x="27" y="26" width="5" height="25" rx="2" fill="{LIME}"/>
  <text x="44" y="44" font-size="18" font-weight="700" font-family="monospace" fill="{TEXT}">ACTIVITY // NEURAL SIGNAL</text>
  <text x="44" y="69" font-size="12" font-family="monospace" fill="{MUTED}">github.com/{escape(username)} · last 90 days</text>
  <text x="740" y="34" font-size="10" font-family="monospace" fill="{MUTED}">CONTRIBUTIONS</text>
  <text x="740" y="60" font-size="24" font-weight="700" font-family="monospace" fill="{LIME}">{total:,}</text>
  <text x="869" y="34" font-size="10" font-family="monospace" fill="{MUTED}">ACTIVE DAYS</text>
  <text x="869" y="60" font-size="24" font-weight="700" font-family="monospace" fill="{VIOLET}">{active_days}</text>
  <text x="999" y="34" font-size="10" font-family="monospace" fill="{MUTED}">PEAK</text>
  <text x="999" y="60" font-size="24" font-weight="700" font-family="monospace" fill="{COPPER}">{peak}</text>
  <line x1="27" x2="1073" y1="86" y2="86" stroke="{GRID}" stroke-width="1"/>
''']
    for tick in range(5):
        v = ymax * tick / 4
        y = py(v)
        p.append(f'  <line x1="{LEFT}" y1="{y:.2f}" x2="{RIGHT}" y2="{y:.2f}" stroke="{GRID}" stroke-dasharray="3 6"/>')
        lab = f"{v:.1f}".rstrip("0").rstrip(".") if v % 1 else str(int(v))
        p.append(f'  <text x="{LEFT-13}" y="{y+4:.2f}" text-anchor="end" font-family="monospace" font-size="11" fill="{MUTED}">{lab}</text>')

    for i, amount in enumerate(counts):
        d = start + timedelta(days=i)
        if d.day == 1 or i == 0:
            x = px(i)
            p.append(f'  <line x1="{x:.2f}" y1="{TOP}" x2="{x:.2f}" y2="{BOTTOM}" stroke="{GRID}" stroke-opacity=".65"/>')
            label = d.strftime("%b %Y") if i == 0 else d.strftime("%b")
            anchor = "start" if i == 0 else "middle"
            p.append(f'  <text x="{x:.2f}" y="306" text-anchor="{anchor}" font-family="monospace" font-size="11" fill="{MUTED}">{label}</text>')
        if amount:
            x, y = px(i), py(amount)
            p.append(f'  <rect x="{x-3.25:.2f}" y="{y:.2f}" width="6.5" height="{max(1, BOTTOM-y):.2f}" rx="2.3" fill="url(#atlasBar)" opacity=".67"/>')

    p.append(f'  <path d="{area}" fill="url(#atlasArea)"/>')
    p.append(f'  <path d="{line}" fill="none" stroke="{LIME}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')
    p.append(f'  <circle cx="{RIGHT}" cy="{py(averages[-1]):.2f}" r="5" fill="{LIME}" stroke="{BASE}" stroke-width="2"/>')
    p.append(f'''  <line x1="64" x2="84" y1="331" y2="331" stroke="{LIME}" stroke-width="3"/>
  <text x="92" y="335" font-size="11" font-family="monospace" fill="{MUTED}">7-DAY ROLLING AVERAGE</text>
  <rect x="316" y="326" width="10" height="10" rx="2" fill="{VIOLET}"/>
  <text x="333" y="335" font-size="11" font-family="monospace" fill="{MUTED}">DAILY CONTRIBUTIONS</text>
  <text x="1045" y="335" font-size="11" font-family="monospace" text-anchor="end" fill="{MUTED}">UPDATED {today.isoformat()}</text>
</svg>''')
    return "\n".join(p)


def main() -> None:
    username = os.getenv("GH_USER", "").strip()
    token = os.getenv("GH_TOKEN", "").strip()
    if not username or not token:
        raise SystemExit("GH_USER and GH_TOKEN must be set by GitHub Actions.")
    today = datetime.now(timezone.utc).date()
    counts = get_contributions(username, token, today)
    svg = build_svg(counts, username, today)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(svg, encoding="utf-8")
    print(f"Created {OUTPUT} ({sum(counts)} contributions over {DAYS} days)")


if __name__ == "__main__":
    main()
