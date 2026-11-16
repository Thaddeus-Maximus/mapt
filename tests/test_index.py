import json

from mapt import imgsize


def ids(rows):
    return [r["id"] for r in rows]


def test_pins_and_unplaced(index):
    assert ids(index.pins("Shop")) == ["Paint Room", "Red Toolbox", "Shop Towels"]
    assert ids(index.unplaced("Shop")) == ["Drill"]
    assert ids(index.pins("shop")) == ids(index.pins("Shop"))       # names are case-insensitive


def test_nesting(index):
    s = index.item("Socket Set")
    assert json.loads(s["chain"]) == ["Shop", "Red Toolbox", "Drawer 2"]
    assert s["map_place"] == "Shop"
    assert s["pin"] == "Red Toolbox"          # it shows on the shop map as its toolbox
    box = index.item("Red Toolbox")
    assert box["things"] == 2 and box["children"] == 2
    assert "socket set" in box["search"] and "hammer" in box["search"]
    paint = index.item("Spray Paint")
    assert paint["map_place"] == "Paint Room" and paint["pin"] == "Spray Paint"
    room = index.item("Paint Room")
    assert room["map_place"] == "Shop" and room["pin"] == "Paint Room"
    assert ids(index.homes()) == ["Shop"]


def test_maps(index):
    shop = index.item("Shop")
    assert shop["map"] == "attachments/shop.svg"
    assert round(shop["map_w"] / shop["map_h"], 3) == 2.0
    paint = index.item("Paint Room")
    assert (paint["map_w"], paint["map_h"]) == (60, 50)


def test_warnings(index):
    codes = {(w["path"], w["code"]) for w in index.warnings()}
    assert ("things/Lost Thing.md", "unresolved") in codes


def test_stock_stats(index):
    t = index.item("Shop Towels")
    assert t["qty"] == 3 and t["low"] == 1
    assert t["last_bought"] == "2026-09-01"
    assert t["per_day"] > 0                   # 4 used + 5 more gone by the count
    assert len(index.stock_events("Shop Towels")) == 3


def test_search(index):
    assert ids(index.search("towel"))[0] == "Shop Towels"
    assert "Hammer" in ids(index.search("claw"))           # in the notes
    assert "Drill" in ids(index.search("power"))           # a tag


def test_changes_are_picked_up(index, root):
    (root / "things" / "Wrench.md").write_text('---\nplace: "[[Drawer 2]]"\n---\n', encoding="utf-8")
    assert index.refresh()
    assert index.item("Red Toolbox")["things"] == 3
    assert not index.refresh()


def test_cycle_is_cut(index, root):
    (root / "places" / "A.md").write_text('---\nparent: "[[B]]"\n---\n', encoding="utf-8")
    (root / "places" / "B.md").write_text('---\nparent: "[[A]]"\n---\n', encoding="utf-8")
    index.refresh()
    assert any(w["code"] == "cycle" for w in index.warnings())


def test_duplicate_names(index, root):
    (root / "places" / "Hammer.md").write_text("", encoding="utf-8")
    index.refresh()
    assert any(w["code"] == "duplicate-name" for w in index.warnings())


def test_imgsize(tmp_path):
    assert imgsize.svg_size('<svg width="10in" height="5in">') == (960, 480)
    assert imgsize.svg_size('<svg viewBox="0 0 30 20" width="100%">') == (30, 20)
    assert imgsize.svg_size('<svg width="300" viewBox="0 0 30 20">') == (300, 200)
    png = (b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + (640).to_bytes(4, "big") + (480).to_bytes(4, "big")
           + b"\x08\x02\x00\x00\x00")
    p = tmp_path / "x.png"
    p.write_bytes(png)
    assert imgsize.size(p) == (640, 480)
