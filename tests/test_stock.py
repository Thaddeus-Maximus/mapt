from datetime import date, datetime

from mapt import stock


def test_parse():
    body = "Notes\n\n## Stock\n- 2026-09-01 bought 12 (0 → 12)\n- 2026-10-01 14:05 used 4\n* 2026-10-20 counted 3\n- not a line"
    ev = stock.parse(body, 5)
    assert [(e.kind, e.n) for e in ev] == [("buy", 12), ("use", 4), ("count", 3)]
    assert ev[0].before == 0 and ev[0].after == 12
    assert ev[1].ts == "2026-10-01T14:05" and ev[1].line == 9


def test_stats():
    ev = stock.parse("- 2026-09-01 bought 12\n- 2026-10-01 used 4\n- 2026-10-31 counted 3")
    st = stock.stats(ev, 3, today=date(2026, 10, 31))
    assert st["used"] == 9               # 4 written down, 5 found missing at the count
    assert abs(st["per_day"] - 9 / 60) < 1e-9
    assert abs(st["days_left"] - 20) < 1e-9
    assert [a for _, a in st["history"]] == [12, 8, 3]


def test_append_into_existing_section():
    body = "Hi\n\n## Stock\n- 2026-01-01 bought 1\n\n## Other\nx"
    out = stock.append(body, "- 2026-01-02 used 1")
    assert out == "Hi\n\n## Stock\n- 2026-01-01 bought 1\n- 2026-01-02 used 1\n\n## Other\nx"


def test_append_new_section():
    assert stock.append("Hi\n", "- x") == "Hi\n\n## Stock\n- x\n"
    assert stock.append("", "- x") == "## Stock\n- x\n"


def test_line():
    assert stock.line("use", 2, 5, 3, datetime(2026, 11, 16, 9, 30)) == "- 2026-11-16 09:30 used 2 (5 → 3)"
    assert stock.line("buy", 1.5, None, None, datetime(2026, 11, 16, 9, 30)) == "- 2026-11-16 09:30 bought 1.5"
