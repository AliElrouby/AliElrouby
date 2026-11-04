#!/usr/bin/env python3
"""Generate the all-time Retro Arcade contribution snake (dark theme).

One continuous contribution grid covers every week since the first push
(first commit); the empty stretch before it is skipped. A pixel snake slithers through it week by week, in date order,
eats every active day, then respawns them on its way back along the lower lane.

Uses only the Python standard library and GitHub's GraphQL API
(GITHUB_TOKEN is provided automatically inside GitHub Actions).
--demo renders clearly labelled synthetic data for design checks only.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import random
import urllib.error
import urllib.request
from xml.sax.saxutils import escape

USER = "AliElrouby"
WIDTH = 1280
GRID_LEFT, GRID_RIGHT = 96, 1232  # horizontal span shared by all week columns
MAX_PITCH = 24.0                  # cell pitch cap; short histories get big cells
STEPS_PER_SECOND = 12             # snake speed, in grid cells per second
BODY = 6                          # body segments trailing the head
FLASH_SECONDS = 0.35              # how long an eaten cell flashes before going dark

# Neural Atlas palette (matches the header, stat cards and 3D city).
BG = "#101014"
PANEL = "#16161C"
EDGE = "#2E2C36"
INK = "#EEECE8"
MUTED = "#8E8B95"
LIME = "#C7F85E"
VIOLET = "#BB91F7"
COPPER = "#D89A65"
LEVELS = ["#22212A", "#3A4A24", "#5E8A2F", "#97CC45", "#D9FF8F"]
SNAKE_BODY = ["#BB91F7", "#AA86EA", "#997BDC", "#8870CD", "#7766BD", "#675CAC"]
MONO = 'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"'


# --------------------------------------------------------------------------- data

def graphql(query: str, variables: dict, token: str) -> dict:
    if not token:
        raise RuntimeError("GITHUB_TOKEN must be set (automatically available in GitHub Actions).")
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "User-Agent": "AliElrouby-retro-arcade-snake/2.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read(500).decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub GraphQL request failed ({exc.code}): {detail}") from exc
    if payload.get("errors"):
        raise RuntimeError(f"GitHub GraphQL errors: {payload['errors']}")
    user = (payload.get("data") or {}).get("user")
    if user is None:
        raise RuntimeError(f"GitHub user {variables.get('login')!r} not found or response missing user data")
    return user


def account_created(username: str, token: str) -> date:
    user = graphql("query($login: String!) { user(login: $login) { createdAt } }", {"login": username}, token)
    return datetime.fromisoformat(user["createdAt"].replace("Z", "+00:00")).date()


def get_contributions(username: str, first: date, last: date, token: str) -> tuple[dict[date, int], date | None]:
    """Daily contribution counts for [first, last], plus the day of the first visible commit (push)."""
    query = """query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar { weeks { contributionDays { date contributionCount } } }
          commitContributionsByRepository(maxRepositories: 100) {
            contributions(first: 1, orderBy: {direction: ASC}) { nodes { occurredAt } }
          }
        }
      }
    }"""
    result: dict[date, int] = {}
    first_commit: date | None = None
    cursor = first
    # Small windows stay well inside the GraphQL contribution-calendar limits (max 1 year).
    while cursor <= last:
        stop = min(cursor + timedelta(days=119), last)
        user = graphql(query, {
            "login": username,
            "from": cursor.isoformat() + "T00:00:00Z",
            "to": stop.isoformat() + "T23:59:59Z",
        }, token)
        collection = user["contributionsCollection"]
        for week in collection["contributionCalendar"]["weeks"]:
            for day in week["contributionDays"]:
                d = date.fromisoformat(day["date"])
                if first <= d <= last:
                    result[d] = int(day["contributionCount"])
        if first_commit is None:
            commits = [date.fromisoformat(node["occurredAt"][:10])
                       for repo in collection["commitContributionsByRepository"]
                       for node in repo["contributions"]["nodes"]]
            if commits:
                first_commit = max(min(commits), cursor)
        cursor = stop + timedelta(days=1)

    # Missing days indicate an API problem, not zero contributions.
    expected = (last - first).days + 1
    if len(result) != expected:
        missing = [str(first + timedelta(days=i)) for i in range(expected)
                   if first + timedelta(days=i) not in result]
        raise RuntimeError(f"Incomplete contribution data, missing {len(missing)} days, sample={missing[:4]}")
    return result, first_commit


def grid_start(data: dict[date, int], first_commit: date | None, fallback: date) -> date:
    """Start on the first push; without one, on the first active day."""
    if first_commit is not None:
        return first_commit
    return min((d for d, v in data.items() if v > 0), default=fallback)


def example_data(first: date, last: date) -> dict[date, int]:
    rng = random.Random(12661)
    result = {}
    for i in range((last - first).days + 1):
        activity = rng.random()
        result[first + timedelta(days=i)] = (
            0 if activity < 0.43 else
            1 if activity < 0.68 else
            2 if activity < 0.83 else
            rng.randint(3, 5) if activity < .94 else rng.randint(6, 10))
    return result


def years_before(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year - years)
    except ValueError:  # Feb 29
        return d.replace(year=d.year - years, day=28)


def color_level(count: int) -> int:
    return 0 if count == 0 else 1 if count <= 1 else 2 if count <= 3 else 3 if count <= 6 else 4


def longest_streak(data: dict[date, int]) -> int:
    best = run = 0
    for d in sorted(data):
        run = run + 1 if data[d] > 0 else 0
        best = max(best, run)
    return best


# ------------------------------------------------------------------------- layout

@dataclass(frozen=True)
class Grid:
    first: date
    last: date
    sunday: date  # Sunday of the first week column
    columns: int
    pitch: float
    box: float
    left: float   # x of column 0
    top: float    # y of row 0 (Sunday)

    @classmethod
    def build(cls, first: date, last: date, top: float) -> "Grid":
        sunday = first - timedelta(days=(first.weekday() + 1) % 7)
        columns = (last - sunday).days // 7 + 1
        span = GRID_RIGHT - GRID_LEFT
        pitch = min(MAX_PITCH, int(span / columns * 100) / 100)
        left = GRID_LEFT + (span - columns * pitch) / 2
        return cls(first, last, sunday, columns, pitch, round(pitch * 0.78, 2), left, top)

    def col(self, d: date) -> int:
        return (d - self.sunday).days // 7

    def cx(self, col: float) -> float:
        return self.left + col * self.pitch + self.pitch / 2

    def cy(self, row: float) -> float:
        return self.top + row * self.pitch + self.pitch / 2

    @property
    def bottom(self) -> float:
        return self.top + 7 * self.pitch

    def days(self):
        """Every in-range day in snake order: down even weeks, up odd weeks."""
        for col in range(self.columns):
            for row in (range(7) if col % 2 == 0 else range(6, -1, -1)):
                d = self.sunday + timedelta(days=7 * col + row)
                if self.first <= d <= self.last:
                    yield col, row, d


@dataclass
class Route:
    points: list[tuple[float, float]]
    eat_at: dict[date, float]     # path distance at which the head reaches each day
    respawn_at: dict[int, float]  # path distance at which each column respawns
    length: float


def build_route(grid: Grid, lane_y: float) -> Route:
    points: list[tuple[float, float]] = []
    dist = [0.0]

    def go(x: float, y: float) -> None:
        if points:
            px, py = points[-1]
            if (x, y) == (px, py):
                return
            if x != px and y != py:  # insert a corner so every move stays axis-aligned
                go(x, py)
                px, py = points[-1]
            dist.append(dist[-1] + abs(x - px) + abs(y - py))
        points.append((x, y))

    eat_at = {}
    for col, row, d in grid.days():
        go(grid.cx(col), grid.cy(row))
        eat_at[d] = dist[-1]

    # Return trip: right gutter -> lower respawn lane -> left gutter -> start.
    right, left = grid.cx(grid.columns), grid.cx(-1)
    start_y = points[0][1]
    go(right, points[-1][1])
    go(right, lane_y)
    lane_start = dist[-1]
    respawn_at = {c: lane_start + right - grid.cx(c) for c in range(grid.columns)}
    go(left, lane_y)
    go(left, start_y)
    go(*points[0])
    return Route(points, eat_at, respawn_at, dist[-1])


def num(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


def path_data(points: list[tuple[float, float]]) -> str:
    """Compact SVG path using H/V commands, merging straight runs."""
    def direction(a, b):
        return ((b[0] > a[0]) - (b[0] < a[0]), (b[1] > a[1]) - (b[1] < a[1]))

    kept = [points[0]]
    for i in range(1, len(points)):
        if i + 1 < len(points) and direction(kept[-1], points[i]) == direction(points[i], points[i + 1]):
            continue
        kept.append(points[i])
    out = [f"M{num(kept[0][0])} {num(kept[0][1])}"]
    for a, b in zip(kept, kept[1:]):
        out.append(f"H{num(b[0])}" if a[1] == b[1] else f"V{num(b[1])}")
    return "".join(out)


def safe(text: str) -> str:
    return escape(text, {'"': "&quot;"})


# -------------------------------------------------------------------------- render

def render_svg(username: str, first: date, last: date, data: dict[date, int], demo: bool) -> str:
    in_range = {d: v for d, v in data.items() if first <= d <= last}
    total = sum(in_range.values())
    active = sum(1 for v in in_range.values() if v > 0)
    streak = longest_streak(in_range)
    days = (last - first).days + 1

    panel_top = 141
    grid = Grid.build(first, last, top=panel_top + 82)
    p = grid.pitch
    lane_y = round(grid.cy(7) + 3, 2)
    panel_bottom = lane_y + p / 2 + 15
    footer_y = panel_bottom + 14
    height = round(footer_y + 33 + 20)

    route = build_route(grid, lane_y)
    dur = round(route.length / p / STEPS_PER_SECOND, 2)

    def key(distance: float) -> str:
        return f"{min(max(distance / route.length, 0.0001), 0.9999):.4f}"

    out: list[str] = []
    add = out.append
    add(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" role="img" aria-labelledby="title desc">')
    add('<title id="title">Ali Elrouby Retro Arcade all-time contribution snake</title>')
    add(f'<desc id="desc">Animated pixel snake travels through every week of GitHub contributions from '
        f'{first.isoformat()} to {last.isoformat()}: {total} contributions on {active} active days.</desc>')
    add(f'<defs><path id="route" d="{path_data(route.points)}"/></defs>')

    # Cabinet frame.
    add(f'<rect width="{WIDTH}" height="{height}" rx="16" fill="{BG}"/>')
    add(f'<rect x="2" y="2" width="{WIDTH - 4}" height="{height - 4}" rx="14" fill="none" stroke="{EDGE}" stroke-width="2"/>')

    # Header HUD.
    add(f'<rect x="22" y="22" width="1236" height="101" rx="8" fill="{PANEL}" stroke="{EDGE}" stroke-width="1.5"/>')
    add(f'<rect x="38" y="36" width="12" height="12" fill="{LIME}"/><rect x="55" y="36" width="12" height="12" fill="{VIOLET}"/>'
        f'<rect x="72" y="36" width="12" height="12" fill="{COPPER}"/>')
    add(f'<text x="100" y="47" fill="{MUTED}" font-size="13" font-weight="bold" letter-spacing="2" {MONO}>ALI.EXE  /  PIXEL ARCADE</text>')
    add(f'<text x="37" y="99" fill="{INK}" font-size="37" font-weight="900" letter-spacing="-1" {MONO}>CONTRIBUTION <tspan fill="{LIME}">SNAKE</tspan></text>')
    boxes = [
        ("SINCE 1ST PUSH", f"{days:,} DAYS", LIME, "#1B2214"),
        ("TOTAL POINTS", "DEMO" if demo else f"{total:,}", VIOLET, "#201A2B"),
        ("ACTIVE DAYS", "DEMO" if demo else f"{active:,}", COPPER, "#261D16"),
        ("BEST STREAK", "DEMO" if demo else f"{streak} DAY{'S' if streak != 1 else ''}", INK, "#1F1F25"),
    ]
    for i, (label, value, accent, fill) in enumerate(boxes):
        x = 476 + i * 193
        add(f'<rect x="{x}" y="40" width="181" height="66" rx="5" fill="{fill}" stroke="{accent}" stroke-opacity=".55"/>')
        add(f'<text x="{x + 14}" y="63" fill="{MUTED}" font-size="12" font-weight="bold" letter-spacing="1" {MONO}>{label}</text>')
        add(f'<text x="{x + 14}" y="91" fill="{accent}" font-size="20" font-weight="bold" {MONO}>{safe(value)}</text>')

    # Level panel.
    add(f'<rect x="22" y="{panel_top}" width="1236" height="{num(panel_bottom - panel_top)}" rx="8" fill="{PANEL}" stroke="{EDGE}" stroke-width="1.5"/>')
    add(f'<rect x="38" y="{panel_top + 16}" width="112" height="30" rx="3" fill="#241C33" stroke="{VIOLET}" stroke-width="1.4"/>')
    add(f'<text x="51" y="{panel_top + 37}" fill="{INK}" font-size="15" font-weight="bold" {MONO}>LEVEL 01</text>')
    span_text = (f"FIRST PUSH  ·  {first.strftime('%b %d %Y').upper()} → {last.strftime('%b %d %Y').upper()}"
                 f"  ·  {grid.columns} WEEKS")
    add(f'<text x="166" y="{panel_top + 36}" fill="{MUTED}" font-size="12" font-weight="bold" letter-spacing=".5" {MONO}>{span_text}</text>')
    lx = 1110
    add(f'<text x="{lx - 8}" y="{panel_top + 36}" fill="{MUTED}" font-size="11" font-weight="bold" text-anchor="end" {MONO}>LESS</text>')
    for i, c in enumerate(LEVELS):
        add(f'<rect x="{lx + i * 17}" y="{panel_top + 25}" width="13" height="13" rx="1" fill="{c}"/>')
    add(f'<text x="{lx + 5 * 17 + 4}" y="{panel_top + 36}" fill="{MUTED}" font-size="11" font-weight="bold" {MONO}>MORE</text>')

    # Month labels; January shows the year instead, with a stepped divider through the grid.
    labels: list[tuple[float, str, bool]] = []
    m = date(first.year, first.month, 1)
    while m <= last:
        if m.month == 1 and m > first:
            jan_col, jan_row = grid.col(m), (m.weekday() + 1) % 7
            jx = grid.left + jan_col * p
            step = (f"M{num(jx + p)} {num(grid.top - 3)}V{num(grid.top + jan_row * p)}H{num(jx)}V{num(grid.bottom + 2)}"
                    if jan_row else f"M{num(jx)} {num(grid.top - 3)}V{num(grid.bottom + 2)}")
            add(f'<path d="{step}" fill="none" stroke="{VIOLET}" stroke-opacity=".55" stroke-width="1.2" stroke-dasharray="2 2"/>')
        first_sunday = max(m + timedelta(days=(6 - m.weekday()) % 7), first)
        if first_sunday <= last:
            is_year = m.month == 1 and m > first
            labels.append((grid.left + grid.col(first_sunday) * p, str(m.year) if is_year else m.strftime("%b").upper(), is_year))
        m = date(m.year + (m.month == 12), 1 if m.month == 12 else m.month + 1, 1)
    year_xs = [x for x, _, is_year in labels if is_year]
    last_x = -999.0
    for x, text, is_year in labels:
        crowded = x - last_x < 30 or any(0 < yx - x < 34 for yx in year_xs)
        if is_year or not crowded:
            color, size = (LIME, 12) if is_year else (MUTED, 10)
            add(f'<text x="{num(x)}" y="{num(grid.top - 9)}" fill="{color}" font-size="{size}" font-weight="bold" {MONO}>{text}</text>')
            last_x = x

    # Weekday ticks left of the snake's return gutter (dropped once rows get too thin to label).
    tick_size = num(min(12, p))
    for row, name in ((1, "MON"), (3, "WED"), (5, "FRI")) if p >= 6 else ():
        add(f'<text x="{num(grid.cx(-1) - p / 2 - 5)}" y="{num(grid.cy(row) + 3.5)}" fill="{MUTED}" font-size="{tick_size}" text-anchor="end" {MONO}>{name}</text>')

    # Respawn lane (the snake's return track).
    add(f'<path d="M{num(grid.cx(-1))} {num(lane_y)}H{num(grid.cx(grid.columns))}" stroke="{EDGE}" stroke-width="1.2" stroke-dasharray="1 4" stroke-linecap="round"/>')

    # Contribution cells; active days are eaten, flash, then respawn on the return lap.
    b = grid.box
    inset = (p - b) / 2
    for col, row, d in grid.days():
        x, y = grid.left + col * p + inset, grid.top + row * p + inset
        count = in_range.get(d, 0)
        fill = LEVELS[color_level(count)]
        cell = f'<rect x="{num(x)}" y="{num(y)}" width="{num(b)}" height="{num(b)}" rx="1" fill="{fill}"'
        if count:
            eat = route.eat_at[d]
            add(f'{cell}><animate attributeName="fill" calcMode="discrete" dur="{dur}s" repeatCount="indefinite" '
                f'values="{fill};{INK};{LEVELS[0]};{fill}" '
                f'keyTimes="0;{key(eat)};{key(eat + FLASH_SECONDS * route.length / dur)};{key(route.respawn_at[col])}"/></rect>')
        else:
            add(cell + "/>")

    # Blinking cursor on today's cell.
    tx, ty = grid.left + grid.col(last) * p + inset, grid.top + ((last.weekday() + 1) % 7) * p + inset
    add(f'<rect x="{num(tx - 2)}" y="{num(ty - 2)}" width="{num(b + 4)}" height="{num(b + 4)}" rx="2" fill="none" stroke="{COPPER}" stroke-width="1.4">'
        '<animate attributeName="opacity" values="1;.15;1" dur="1.6s" repeatCount="indefinite"/></rect>')

    # The snake: body segments trail the head by one cell each along the shared route.
    motion = (f'<animateMotion dur="{dur}s" begin="{{begin}}" repeatCount="indefinite" rotate="auto">'
              '<mpath href="#route" xlink:href="#route"/></animateMotion>')
    add('<g aria-label="animated pixel snake">')
    for s in range(BODY, 0, -1):
        lag = s * p / route.length * dur
        add(f'<rect x="{num(-b / 2)}" y="{num(-b / 2)}" width="{num(b)}" height="{num(b)}" rx="1" '
            f'fill="{SNAKE_BODY[s - 1]}" stroke="{BG}" stroke-width=".7">{motion.format(begin=f"-{dur - lag:.3f}s")}</rect>')
    h = round(b + 1.4, 2)
    eye = round(max(1.3, h * 0.2), 2)
    add('<g>')
    add(f'<rect x="{num(h / 2)}" y="-.6" width="{num(h * .45)}" height="1.2" fill="{COPPER}">'
        '<animate attributeName="opacity" values="0;0;1;0" dur="1s" repeatCount="indefinite"/></rect>')
    add(f'<rect x="{num(-h / 2)}" y="{num(-h / 2)}" width="{num(h)}" height="{num(h)}" rx="1.4" fill="{LIME}" stroke="{BG}" stroke-width=".8"/>')
    for ey in (-h / 2 + h * .17, h / 2 - h * .17 - eye):
        add(f'<rect x="{num(h / 2 - eye - h * .14)}" y="{num(ey)}" width="{num(eye)}" height="{num(eye)}" fill="{BG}"/>')
    add(motion.format(begin="0s"))
    add('</g></g>')

    # Footer HUD.
    add(f'<rect x="22" y="{num(footer_y)}" width="1236" height="33" rx="4" fill="#1B1B22" stroke="{EDGE}"/>')
    fy = num(footer_y + 21.5)
    add(f'<text x="40" y="{fy}" fill="{LIME}" font-size="13" font-weight="bold" {MONO}>▶ PRESS START  ·  {safe(username.upper())}</text>')
    add(f'<text x="640" y="{fy}" fill="{INK}" font-size="12" text-anchor="middle" {MONO}>SYNCED {last.isoformat()}  ·  WEEKLY / MON 04:23 UTC</text>')
    add(f'<text x="1240" y="{fy}" fill="{COPPER}" font-size="12" text-anchor="end" {MONO}>STYLE PREVIEW / DEMO DATA</text>' if demo else
        f'<text x="1240" y="{fy}" fill="{VIOLET}" font-size="12" text-anchor="end" {MONO}>REAL GITHUB DATA</text>')
    add('</svg>')
    return "\n".join(out) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the all-time retro arcade contribution snake.")
    parser.add_argument("--output", default="assets/arcade-snake.svg")
    parser.add_argument("--user", default=USER)
    parser.add_argument("--demo", action="store_true", help="Use explicit synthetic demo data for preview only")
    parser.add_argument("--date", default=None, help="Override today's date for deterministic testing, YYYY-MM-DD")
    parser.add_argument("--since", default=None, help="Override the start date (default: first push), YYYY-MM-DD")
    args = parser.parse_args()

    today = date.fromisoformat(args.date) if args.date else datetime.now(timezone.utc).date()
    token = os.getenv("GITHUB_TOKEN", "")
    if args.demo:
        first = date.fromisoformat(args.since) if args.since else years_before(today, 3)
        data = example_data(first, today)
    else:
        created = account_created(args.user, token)
        data, first_commit = get_contributions(args.user, created, today, token)
        first = date.fromisoformat(args.since) if args.since else grid_start(data, first_commit, created)
    if first > today:
        raise SystemExit(f"Start date {first} is after {today}")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_svg(args.user, first, today, data, args.demo), encoding="utf-8")
    print(f"Generated {out} | {first} -> {today} | {len(data)} calendar days | sample_data={args.demo}")


if __name__ == "__main__":
    main()
