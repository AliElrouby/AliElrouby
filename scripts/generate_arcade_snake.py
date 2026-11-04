#!/usr/bin/env python3
"""Generate a two-year animated Retro Arcade contribution snake for GitHub README.

Uses GitHub's GraphQL contribution calendar, queried in short date windows.
No non-standard Python packages required. Intended to run weekly in Actions.

--demo generates clearly labeled sample data for design inspection only.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import random
import urllib.error
import urllib.request
from xml.sax.saxutils import escape

USER = "AliElrouby"
WIDTH, HEIGHT = 1280, 610
X0, PITCH, BOX = 238, 17, 13
Y0 = (185, 396)
MAX_COLUMNS = 54
DURATION = 94
COLORS = ["#E8E4D9", "#D4E5B1", "#B2D765", "#87B957", "#548E57"]
BG = "#FBF8F0"
DARK = "#26242A"
VIOLET = "#9971C2"
ORANGE = "#E28C52"
LIME = "#C0E95B"


def anniversary(d: date, years: int) -> date:
    """Return the same calendar day N years before, allowing Feb 29."""
    try:
        return d.replace(year=d.year - years)
    except ValueError:
        return d.replace(year=d.year - years, day=28)


def get_contributions(username: str, first: date, last: date, token: str) -> dict[date, int]:
    if not token:
        raise RuntimeError("GITHUB_TOKEN must be set (automatically available in GitHub Actions).")
    result: dict[date, int] = {}
    cursor = first
    # Small windows avoid the large GraphQL contribution-calendar resource limit.
    while cursor <= last:
        stop = min(cursor + timedelta(days=119), last)
        query = """query($login: String!, $from: DateTime!, $to: DateTime!) {
          user(login: $login) {
            contributionsCollection(from: $from, to: $to) {
              contributionCalendar {
                weeks { contributionDays { date contributionCount } }
              }
            }
          }
        }"""
        body = {
            "query": query,
            "variables": {
                "login": username,
                "from": cursor.isoformat() + "T00:00:00Z",
                "to": stop.isoformat() + "T23:59:59Z",
            },
        }
        request = urllib.request.Request(
            "https://api.github.com/graphql",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/vnd.github+json",
                "User-Agent": "AliElrouby-retro-arcade-snake/1.0",
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
            raise RuntimeError(f"GitHub user {username!r} not found or response missing user data")
        weeks = user["contributionsCollection"]["contributionCalendar"]["weeks"]
        for week in weeks:
            for day in week["contributionDays"]:
                dt = date.fromisoformat(day["date"])
                if first <= dt <= last:
                    result[dt] = int(day["contributionCount"])
        cursor = stop + timedelta(days=1)

    # Missing days indicate an API problem, not zero contributions.
    expected = (last - first).days + 1
    if len(result) != expected:
        missing = [str(first + timedelta(days=i)) for i in range(expected)
                   if first + timedelta(days=i) not in result]
        raise RuntimeError(f"Incomplete contribution data, missing {len(missing)} days, sample={missing[:4]}")
    return result


def example_data(first: date, last: date) -> dict[date, int]:
    rng = random.Random(12661)
    result = {}
    for i in range((last - first).days + 1):
        day = first + timedelta(days=i)
        activity = rng.random()
        result[day] = (0 if activity < 0.43 else
                       1 if activity < 0.68 else
                       2 if activity < 0.83 else
                       rng.randint(3, 5) if activity < .94 else rng.randint(6, 10))
    return result


def color_level(count: int) -> int:
    return 0 if count == 0 else 1 if count <= 1 else 2 if count <= 3 else 3 if count <= 6 else 4


def safe(text: str) -> str:
    return escape(text, {'"': '&quot;'})


def panel_layout(first: date, last: date, y0: int, idx: int, values: dict[date, int]):
    sunday = first - timedelta(days=(first.weekday() + 1) % 7)
    last_sunday = last - timedelta(days=(last.weekday() + 1) % 7)
    columns = ((last_sunday - sunday).days // 7) + 1
    if columns > MAX_COLUMNS:
        raise RuntimeError(f"Calendar unexpectedly contains {columns} weeks (max {MAX_COLUMNS}).")
    cells = []
    by_row = [[] for _ in range(7)]
    for col in range(columns):
        for row in range(7):
            d = sunday + timedelta(days=7*col+row)
            x = X0+PITCH*col
            y = y0+PITCH*row
            valid = first <= d <= last
            count = values.get(d,0) if valid else None
            cells.append((x,y,valid,count,d))
            if valid:
                by_row[row].append((x+BOX/2,y+BOX/2))
    return cells, by_row, sunday, columns


def motion_path(row_sets):
    # Scan all actual days in both years, never visiting an outside-of-range date.
    # Year 1: left-to-right, then reverse per weekday row.
    # Year 2: right-to-left, then reverse per weekday row.
    points = []
    for level, rows in enumerate(row_sets):
        for weekday, row in enumerate(rows):
            points.extend(row if (weekday+level) % 2 == 0 else list(reversed(row)))
    x, y = points[0]
    commands = ["M0 0"]
    for a,b in points[1:]:
        commands.append(f"L{a-x:.1f} {b-y:.1f}")
    # Loop around the left edge, outside the contribution grid.
    commands.extend([f"L{X0-25-x:.1f} {points[-1][1]-y:.1f}",
                     f"L{X0-25-x:.1f} {points[0][1]-y:.1f}", "L0 0"])
    return " ".join(commands), points[0]


def render_svg(username: str, now: date, data: dict[date, int], demo: bool) -> str:
    first = anniversary(now, 2)
    middle = anniversary(now, 1)
    intervals = ((first, middle-timedelta(days=1)),(middle,now))
    total = sum(data[d] for d in data if first <= d <= now)
    active = sum(1 for d,v in data.items() if first<=d<=now and v>0)
    days = (now-first).days+1
    panels = [panel_layout(a,b,y,i,data) for i,((a,b),y) in enumerate(zip(intervals,Y0))]
    path,(start_x,start_y) = motion_path([p[1] for p in panels])
    line = []
    add = line.append
    add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">')
    add(f'<title id="title">Ali Elrouby Retro Arcade two-year contribution snake</title>')
    add(f'<desc id="desc">Animated pixel snake travels through two consecutive years of GitHub contribution calendars. Updated weekly. {safe(str(first))} to {safe(str(now))}.</desc>')
    add('<defs><pattern id="scan" width="18" height="18" patternUnits="userSpaceOnUse"><path d="M18 0H0V18" fill="none" stroke="#E9E5D9" stroke-width=".7"/></pattern><pattern id="stripe" width="10" height="10" patternUnits="userSpaceOnUse"><path d="M0 0L10 10" stroke="#E7E0CE" stroke-width="1"/></pattern></defs>')
    add(f'<rect width="{WIDTH}" height="{HEIGHT}" rx="16" fill="{BG}"/><rect x="3" y="3" width="{WIDTH-6}" height="{HEIGHT-6}" rx="12" fill="none" stroke="{DARK}" stroke-width="3"/>')
    add('<rect x="22" y="22" width="1236" height="101" rx="8" fill="#F0ECD9" stroke="#29242A" stroke-width="2"/>')
    add('<rect x="34" y="33" width="14" height="14" fill="#B3DB59"/><rect x="53" y="33" width="14" height="14" fill="#A884CE"/><rect x="72" y="33" width="14" height="14" fill="#E28C52"/>')
    add(f'<text x="104" y="46" fill="{DARK}" font-size="13" font-family="monospace" font-weight="bold" letter-spacing="2">ALI.EXE  /  PIXEL ARCADE</text>')
    add(f'<text x="39" y="93" fill="{DARK}" font-family="monospace" font-size="37" font-weight="900" letter-spacing="-1">CONTRIBUTION SNAKE</text>')
    add(f'<rect x="736" y="45" width="159" height="57" rx="4" fill="#E1F0BD" stroke="{DARK}"/>')
    add(f'<text x="750" y="67" fill="{DARK}" font-family="monospace" font-weight="bold" font-size="13">2 YEAR MODE</text>')
    add(f'<text x="750" y="88" fill="#517C3B" font-family="monospace" font-weight="bold" font-size="12">{days} DAYS</text>')
    add('<rect x="906" y="45" width="160" height="57" rx="4" fill="#E9DDF4" stroke="#29242A"/>')
    add(f'<text x="921" y="67" fill="{DARK}" font-family="monospace" font-weight="bold" font-size="13">TOTAL POINTS</text>')
    add(f'<text x="921" y="89" fill="{DARK}" font-family="monospace" font-weight="bold" font-size="19">{"DEMO" if demo else f"{total:,}"}</text>')
    add('<rect x="1077" y="45" width="162" height="57" rx="4" fill="#F8DFCA" stroke="#29242A"/>')
    add(f'<text x="1090" y="67" fill="{DARK}" font-family="monospace" font-weight="bold" font-size="13">ACTIVE DAYS</text>')
    add(f'<text x="1090" y="89" fill="{DARK}" font-family="monospace" font-weight="bold" font-size="19">{"DEMO" if demo else f"{active:,}"}</text>')

    for i,((begin,end),p) in enumerate(zip(intervals,panels)):
        y0=Y0[i]; cells,rows,sunday,cols=p
        top=y0-45
        add(f'<rect x="23" y="{top-3}" width="1234" height="{165}" rx="6" fill="#FFFFFF" stroke="#DCD6CB" stroke-width="2"/>')
        add(f'<rect x="35" y="{top+13}" width="168" height="{37}" fill="{["#E1F0BD","#E8DCF5"][i]}" stroke="{DARK}" stroke-width="1.4"/>')
        add(f'<text x="47" y="{top+36}" fill="{DARK}" font-family="monospace" font-size="16" font-weight="bold">LEVEL 0{i+1}</text>')
        add(f'<text x="45" y="{top+78}" fill="#666169" font-family="monospace" font-size="12" font-weight="bold">{begin.strftime("%b %Y").upper()}</text>')
        add(f'<text x="45" y="{top+99}" fill="#666169" font-family="monospace" font-size="12" font-weight="bold">{end.strftime("%b %Y").upper()}</text>')
        # Month labels aligned to real dates within each contribution calendar.
        m = date(begin.year, begin.month, 1)
        while m <= end:
            if m >= begin:
                col=(m-sunday).days//7
                if 0<=col<cols:
                    add(f'<text x="{X0+col*PITCH}" y="{y0-11}" fill="#655C66" font-family="monospace" font-size="11" font-weight="bold">{m.strftime("%b").upper()}</text>')
            m = date(m.year + (m.month==12), 1 if m.month==12 else m.month+1, 1)
        for x,y,valid,count,d in cells:
            color=COLORS[color_level(count)] if valid else "#F6F3EC"
            border="#D2CFC8" if valid else "#EEECE5"
            add(f'<rect x="{x}" y="{y}" width="{BOX}" height="{BOX}" rx="1" fill="{color}" stroke="{border}" stroke-width=".65"><title>{safe(d.isoformat())}: {count if valid else "outside range"} contributions</title></rect>')
        # Day-of-week ticks down the left of each grid.
        for row,day_name in ((0,"SU"),(2,"TU"),(4,"TH"),(6,"SA")):
            add(f'<text x="207" y="{y0+row*PITCH+11}" fill="#938B8F" font-family="monospace" font-size="10" text-anchor="end">{day_name}</text>')
        add(f'<text x="1185" y="{y0+94}" fill="{ORANGE if i==1 else VIOLET}" font-family="monospace" font-size="13" font-weight="bold">{chr(0x2605)} XP</text>')

    # Display a pixel sprite with six trailing segments; animation follows the two-year grids.
    add('<g id="snake" aria-label="animated pixel snake">')
    # Extra path invisible; helpful for debugging the animation in source.
    for s in range(6, -1, -1):
        delay=s*.15
        head=(s==0)
        color="#273524" if head else ["#6B9450","#87B957","#A4CF55","#BEE66A","#CBEF89","#DDF4AD"][min(s-1,5)]
        add(f'<g transform="translate({start_x:.1f} {start_y:.1f})">')
        add(f'<rect x="{-BOX/2:.1f}" y="{-BOX/2:.1f}" width="{BOX}" height="{BOX}" rx="1" fill="{color}" stroke="{DARK}" stroke-width="{1.8 if head else 0.8}"/>')
        if head:
            add(f'<rect x="1" y="-3.5" width="3" height="3" fill="{LIME}"/><rect x="1" y="1" width="3" height="3" fill="{LIME}"/>')
        add(f'<animateMotion dur="{DURATION}s" begin="-{delay:.2f}s" repeatCount="indefinite" rotate="0" path="{path}"/>')
        add('</g>')
    add('</g>')

    # Footer HUD.
    add('<rect x="23" y="557" width="1234" height="33" rx="3" fill="#28252B"/>')
    add(f'<text x="43" y="579" fill="#C9EF73" font-family="monospace" font-size="13" font-weight="bold">▶ PRESS START  ·  {safe(username.upper())}</text>')
    add('<text x="520" y="579" fill="#FFF7E3" font-family="monospace" font-size="12">WEEKLY SYNC  /  MON 04:23 UTC</text>')
    add('<text x="1016" y="579" fill="#C8B3EB" font-family="monospace" font-size="12">REAL GITHUB DATA</text>' if not demo else '<text x="946" y="579" fill="#FFD19C" font-family="monospace" font-size="12">STYLE PREVIEW / DEMO DATA</text>')
    add('</svg>')
    return "\n".join(line) + "\n"


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",default="assets/arcade-snake.svg")
    parser.add_argument("--user",default=USER)
    parser.add_argument("--demo",action="store_true",help="Use explicit synthetic demo data for preview only")
    parser.add_argument("--date",default=None,help="Date override for deterministic testing, YYYY-MM-DD")
    args=parser.parse_args()
    now=date.fromisoformat(args.date) if args.date else datetime.now(timezone.utc).date()
    first=anniversary(now,2)
    data=example_data(first,now) if args.demo else get_contributions(args.user,first,now,os.getenv("GITHUB_TOKEN",""))
    out=Path(args.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(render_svg(args.user,now,data,args.demo),encoding="utf-8")
    print(f"Generated {out} | {len(data)} real calendar days | sample_data={args.demo}")


if __name__=="__main__":
    main()
