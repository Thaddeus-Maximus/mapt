from datetime import datetime

import pytest

from mapt import writes


def read(root, rel):
    return (root / rel).read_text(encoding="utf-8")


def test_set_pos_keeps_body_and_writes_flow_list(root):
    writes.set_pos(root / "places" / "Red Toolbox.md", (0.123456, 1.4))
    text = read(root, "places/Red Toolbox.md")
    assert "pos: [0.1235, 1.0]" in text
    assert 'parent: "[[Shop]]"' in text
    assert text.endswith("Craftsman, by the bench.\n")
    writes.set_pos(root / "places" / "Red Toolbox.md", None)
    assert "pos" not in read(root, "places/Red Toolbox.md")


def test_record_stock(root):
    writes.record(root / "things" / "Shop Towels.md", "buy", "6", now=datetime(2026, 11, 16, 8, 0))
    text = read(root, "things/Shop Towels.md")
    assert "qty: 9\n" in text
    assert text.rstrip().endswith("- 2026-10-20 counted 3\n- 2026-11-16 08:00 bought 6 (3 → 9)")
    writes.record(root / "things" / "Hammer.md", "use", "1", now=datetime(2026, 11, 16, 8, 0))
    assert "## Stock\n- 2026-11-16 08:00 used 1\n" in read(root, "things/Hammer.md")
    with pytest.raises(writes.WriteError):
        writes.record(root / "things" / "Hammer.md", "eat", "1")


def test_rename_relinks(root):
    new, files = writes.rename(root, "places/Red Toolbox.md", "Blue Toolbox", set())
    assert new == "places/Blue Toolbox.md"
    assert files == 2
    assert 'place: "[[Blue Toolbox]]"' in read(root, "things/Hammer.md")
    assert 'parent: "[[Blue Toolbox]]"' in read(root, "places/Drawer 2.md")
    assert not (root / "places" / "Red Toolbox.md").exists()


def test_relink_keeps_alias_and_heading():
    out, n = writes.relink("[[Red Toolbox|the box]] and [[red toolbox#Top]] not [[Red]]", "Red Toolbox", "Blue")
    assert out == "[[Blue|the box]] and [[Blue#Top]] not [[Red]]" and n == 2


def test_new_item_and_names(root):
    p = writes.new_item(root, "things", "Tape Measure", {"place": "[[Shop]]", "pos": [0.1, 0.2], "qty": None})
    assert read(root, p) == '---\nplace: "[[Shop]]"\npos: [0.1, 0.2]\n---\n'
    with pytest.raises(writes.WriteError):
        writes.new_item(root, "things", "Tape Measure", {})
    with pytest.raises(writes.WriteError):
        writes.new_item(root, "things", "a/b", {})


def test_trash(root):
    assert writes.trash(root, "things/Drill.md") == ".trash/things/Drill.md"
    assert not (root / "things" / "Drill.md").exists()
