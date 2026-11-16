"""Consumables: dated stock lines in a thing's notes, and what they say about use.

A stock line is a list item that starts with a date and a verb:

    ## Stock
    - 2026-11-02 bought 12 (3 → 15)
    - 2026-11-10 14:05 used 2 (15 → 13)
    - 2026-11-16 counted 9

The `(before → after)` part is optional; mapt writes it so the file reads on its own.
`qty:` in the frontmatter is the amount on hand; the lines are its history.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

VERBS = {
    "bought": "buy", "buy": "buy", "restocked": "buy", "received": "buy", "added": "buy",
    "used": "use", "use": "use", "took": "use", "consumed": "use", "gave": "use", "lost": "use",
    "counted": "count", "count": "count",
}
WRITE_VERB = {"buy": "bought", "use": "used", "count": "counted"}

LINE = re.compile(
    r"^\s*[-*+]\s+(?P<date>\d{4}-\d{2}-\d{2})(?:[ T](?P<time>\d{1,2}:\d{2}))?\s+"
    r"(?P<verb>[A-Za-z]+)\s+(?P<n>\d+(?:\.\d+)?)(?P<rest>.*)$")
ARROW = re.compile(r"\(\s*(-?\d+(?:\.\d+)?)\s*(?:→|->)\s*(-?\d+(?:\.\d+)?)\s*\)")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
WINDOW_DAYS = 365      # use older than this doesn't count toward the rate
MIN_SPAN_DAYS = 7      # a first purchase yesterday isn't a week's worth of evidence


@dataclass
class Event:
    ts: str               # 2026-11-10 or 2026-11-10T14:05
    kind: str             # buy | use | count
    n: float
    before: float | None
    after: float | None
    line: int


def num(v):
    """A number as YAML would like it: 3 rather than 3.0."""
    if v is None:
        return None
    v = float(v)
    return int(v) if v.is_integer() else round(v, 3)


def fmt(v) -> str:
    return "" if v is None else str(num(v))


def parse(body: str, first_line: int = 1) -> list[Event]:
    out = []
    for i, raw in enumerate(body.split("\n")):
        m = LINE.match(raw)
        if not m:
            continue
        kind = VERBS.get(m.group("verb").lower())
        if not kind:
            continue
        try:
            date.fromisoformat(m.group("date"))
        except ValueError:
            continue
        ts = m.group("date") + (f"T{int(m.group('time').split(':')[0]):02d}:{m.group('time').split(':')[1]}"
                                if m.group("time") else "")
        a = ARROW.search(m.group("rest"))
        before = float(a.group(1)) if a else None
        after = float(a.group(2)) if a else None
        out.append(Event(ts, kind, float(m.group("n")), before, after, first_line + i))
    return out


def apply(qty, kind: str, n: float):
    """The amount on hand after an event; None when it can't be known."""
    if kind == "count":
        return n
    if kind == "buy":
        return (qty or 0) + n
    if qty is None:
        return None
    return max(0.0, qty - n)


def line(kind: str, n: float, before, after, when: datetime) -> str:
    text = f"- {when:%Y-%m-%d %H:%M} {WRITE_VERB[kind]} {fmt(n)}"
    if before is not None and after is not None:
        text += f" ({fmt(before)} → {fmt(after)})"
    return text


def append(body: str, text: str) -> str:
    """Add a stock line at the end of the `## Stock` section, starting one if needed."""
    lines = body.split("\n")
    start = None
    level = 0
    for i, l in enumerate(lines):
        h = HEADING.match(l)
        if h and h.group(2).strip().lower() in ("stock", "stock log", "inventory"):
            start, level = i, len(h.group(1))
            break
    if start is None:
        body = body.rstrip("\n")
        return (body + "\n\n" if body.strip() else "") + "## Stock\n" + text + "\n"
    end = len(lines)
    for j in range(start + 1, len(lines)):
        h = HEADING.match(lines[j])
        if h and len(h.group(1)) <= level:
            end = j
            break
    last = start
    for j in range(start + 1, end):
        if lines[j].strip():
            last = j
    lines.insert(last + 1, text)
    return "\n".join(lines)


def _day(ts: str) -> date:
    return date.fromisoformat(ts[:10])


def stats(events: list[Event], qty, today: date | None = None) -> dict:
    """→ {last_bought, used (in the window), per_day, days_left, history: [(event, after)]}.

    Use is what `used` lines say, plus the drop when a count comes in under what
    was expected (things get used without anyone writing it down)."""
    today = today or date.today()
    since = today - timedelta(days=WINDOW_DAYS)
    running = None
    used = 0.0
    first = None
    last_bought = None
    history = []
    for e in sorted(events, key=lambda e: e.ts):
        before = e.before if e.before is not None else running
        after = e.after if e.after is not None else apply(before, e.kind, e.n)
        d = _day(e.ts)
        if e.kind == "buy":
            last_bought = e.ts
        if d >= since:
            first = first or d
            if e.kind == "use":
                used += e.n
            elif e.kind == "count" and before is not None and before > e.n:
                used += before - e.n
        history.append((e, after))
        running = after
    per_day = None
    if used > 0 and first is not None:
        per_day = used / max((today - first).days, MIN_SPAN_DAYS)
    days_left = qty / per_day if per_day and qty is not None else None
    return {"last_bought": last_bought, "used": used, "per_day": per_day,
            "days_left": days_left, "history": history}
