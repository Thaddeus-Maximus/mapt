"""The SQLite index: derived and disposable, rebuilt from the files whenever they change.

Two kinds of file make up the library:

- `places/<Name>.md`: somewhere things are. `parent:` links the place it's inside,
  `map:` embeds a floor plan image, and `pos:` is where it sits on its parent's map.
  Map and pos are both optional. On a map, everything inside a place shows as that place's pin.
- `things/<Name>.md`: `place:` links where it is and `pos:` where on that place's map;
  `qty:`, `unit:`, `reorder:`, `owner:`, `tags:` and `added:` are optional.

`pos: [x, y]` is a fraction of the map's width and height from its top-left corner, so it
survives the image being re-exported at another size.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from . import config as config_mod
from . import imgsize, stock
from .frontmatter import link_value, load as load_fm
from .paths import iter_markdown, rel, state_dir

SCHEMA = 1

DDL = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE items (
  id TEXT PRIMARY KEY COLLATE NOCASE, kind TEXT, path TEXT, parent TEXT, x REAL, y REAL,
  map TEXT, map_w REAL, map_h REAL, qty REAL, unit TEXT, reorder REAL, added TEXT, owner TEXT,
  tags TEXT, fields TEXT, body TEXT, body_line INTEGER, chain TEXT, map_place TEXT, pin TEXT,
  things INTEGER, children INTEGER, search TEXT,
  last_bought TEXT, per_day REAL, days_left REAL, low INTEGER);
CREATE TABLE stock (item TEXT COLLATE NOCASE, ts TEXT, kind TEXT, n REAL, before REAL, after REAL, line INTEGER);
CREATE TABLE warnings (path TEXT, line INTEGER, code TEXT, severity TEXT, message TEXT);
CREATE VIRTUAL TABLE fts USING fts5(id, text);
CREATE INDEX items_parent ON items(parent COLLATE NOCASE);
CREATE INDEX stock_item ON stock(item, ts);
"""

# frontmatter keys the edit form owns; anything else is shown as an extra property
KNOWN = {"place", "parent", "pos", "map", "qty", "unit", "reorder", "owner", "tags", "added"}


@dataclass
class Warning:
    path: str
    line: int
    code: str
    message: str
    severity: str = "warning"     # error | warning | info


@dataclass
class Item:
    id: str
    kind: str                     # place | thing
    path: str
    fields: dict
    body: str
    body_line: int
    parent: str | None = None     # link target as written
    pos: tuple[float, float] | None = None
    map: str | None = None        # image name as written
    qty: float | None = None
    unit: str | None = None
    reorder: float | None = None
    added: str | None = None
    owner: str | None = None
    tags: list[str] = field(default_factory=list)
    events: list[stock.Event] = field(default_factory=list)
    warnings: list[Warning] = field(default_factory=list)


def _number(it: Item, key: str):
    v = it.fields.get(key)
    if v is None or v == "":
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        try:
            return float(str(v).strip())
        except ValueError:
            it.warnings.append(Warning(it.path, 1, f"bad-{key}", f"{key}: {v!r} isn't a number"))
            return None
    return float(v)


def tag_list(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        v = v.replace(",", " ").split()
    return [str(t).strip().lstrip("#") for t in v if str(t).strip().lstrip("#")]


def build(stem: str, kind: str, path: str, fields: dict, body: str, body_line: int) -> Item:
    it = Item(stem, kind, path, fields, body, body_line)
    place, parent = link_value(fields.get("place")), link_value(fields.get("parent"))
    if place and parent and place.casefold() != parent.casefold():
        it.warnings.append(Warning(path, 1, "two-parents",
                                   f"both place: [[{place}]] and parent: [[{parent}]]; using {place}"))
    it.parent = place or parent
    pos = fields.get("pos")
    if pos is not None:
        try:
            x, y = (float(v) for v in pos)
            if not (-0.001 <= x <= 1.001 and -0.001 <= y <= 1.001):
                raise ValueError
            it.pos = (min(max(x, 0.0), 1.0), min(max(y, 0.0), 1.0))
        except (TypeError, ValueError):
            it.warnings.append(Warning(path, 1, "bad-pos",
                                       f"pos: {pos!r} should be [x, y], each from 0 to 1 across the map"))
    it.map = link_value(fields.get("map"))
    it.qty = _number(it, "qty")
    it.reorder = _number(it, "reorder")
    it.unit = str(fields["unit"]).strip() if fields.get("unit") not in (None, "") else None
    it.owner = link_value(fields.get("owner"))
    it.tags = tag_list(fields.get("tags"))
    if fields.get("added") not in (None, ""):
        it.added = str(fields["added"])
    it.events = stock.parse(body, body_line)
    return it


@dataclass
class _Cached:
    mtime: float
    size: int
    item: Item | None


class Index:
    def __init__(self, root: Path, db_path: Path | None = None):
        self.root = root
        self.db_path = db_path or state_dir(root) / "index.sqlite"
        self.lock = threading.RLock()
        self.cache: dict[str, _Cached] = {}
        self.sizes: dict[str, tuple[float, tuple | None]] = {}   # image path → (mtime, size)
        self.config = None
        self._config_mtime = None
        self.conflicts: list[str] = []
        self.generation = 0
        self.images: dict[str, str] = {}
        self.db = self._open()
        self.refresh(force=True)

    # --- database --------------------------------------------------------
    def _open(self) -> sqlite3.Connection:
        if self.db_path.exists():
            try:
                db = sqlite3.connect(self.db_path, check_same_thread=False)
                v = db.execute("SELECT value FROM meta WHERE key='schema'").fetchone()
                if v and int(v[0]) == SCHEMA:
                    db.row_factory = sqlite3.Row
                    return db
                db.close()
            except sqlite3.DatabaseError:
                pass
            try:
                self.db_path.unlink()
            except PermissionError:
                # Windows: another mapt has it open. Empty it in place.
                db = sqlite3.connect(self.db_path, check_same_thread=False)
                for (n,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' "
                                       "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'fts_%'").fetchall():
                    db.execute(f'DROP TABLE IF EXISTS "{n}"')
                db.commit()
                db.close()
        db = sqlite3.connect(self.db_path, check_same_thread=False)
        db.executescript(DDL)
        db.execute("INSERT INTO meta VALUES ('schema', ?)", (str(SCHEMA),))
        db.commit()
        db.row_factory = sqlite3.Row
        return db

    def q(self, sql: str, *args) -> list[sqlite3.Row]:
        with self.lock:
            return self.db.execute(sql, args).fetchall()

    def q1(self, sql: str, *args):
        with self.lock:
            return self.db.execute(sql, args).fetchone()

    # --- scanning --------------------------------------------------------
    def refresh(self, force: bool = False) -> bool:
        """Re-parse changed files and rebuild if anything changed. → changed?"""
        with self.lock:
            cpath = self.root / config_mod.CONFIG_NAME
            cm = cpath.stat().st_mtime if cpath.exists() else None
            if self.config is None or cm != self._config_mtime:
                self.config = config_mod.load(self.root)
                self._config_mtime = cm
                self.cache.clear()
                force = True
            seen = set()
            changed = force
            conflicts: list[Path] = []
            for p in iter_markdown(self.root, conflicts):
                r = rel(self.root, p)
                seen.add(r)
                try:
                    s = p.stat()
                except OSError:
                    continue
                c = self.cache.get(r)
                if c and c.mtime == s.st_mtime and c.size == s.st_size:
                    continue
                self.cache[r] = _Cached(s.st_mtime, s.st_size, self._parse(r, p))
                changed = True
            for gone in set(self.cache) - seen:
                del self.cache[gone]
                changed = True
            conflicts_rel = sorted(rel(self.root, p) for p in conflicts)
            if conflicts_rel != self.conflicts:
                changed = True
            self.conflicts = conflicts_rel
            images = self._image_lookup()
            if images != self.images:
                changed = True
            self.images = images
            if changed:
                self._rebuild()
                self.generation += 1
            return changed

    def _parse(self, r: str, p: Path) -> Item | None:
        if "/" not in r:
            return None
        kind = self.config.kind_for_folder(r.split("/", 1)[0])
        if kind is None:
            return None            # other notes are left alone
        stem = r.rsplit("/", 1)[-1][:-3]
        try:
            text = p.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            it = Item(stem, kind, r, {}, "", 1)
            it.warnings.append(Warning(r, 1, "unreadable", f"can't read file: {exc}", "error"))
            return it
        fields, sp, err = load_fm(text)
        it = build(stem, kind, r, fields, sp.body, sp.body_line)
        if err:
            it.warnings.append(Warning(r, 1, "bad-frontmatter", err, "error"))
        return it

    def _image_lookup(self) -> dict[str, str]:
        """File name (casefolded) → root-relative path: attachments first, then anywhere."""
        found: dict[str, str] = {}
        dirs = [self.root / str(self.config["attachments_dir"]), self.root]
        for d in dirs:
            if not d.is_dir():
                continue
            for dirpath, dirnames, filenames in os.walk(d):
                dirnames[:] = [x for x in dirnames if not x.startswith(".")]
                for f in filenames:
                    if f.lower().endswith(imgsize.IMAGE_EXT):
                        found.setdefault(f.casefold(), rel(self.root, Path(dirpath) / f))
        return found

    def find_image(self, name: str) -> str | None:
        """An embed name (`shop.svg`, `attachments/shop.svg`) → root-relative path."""
        name = name.replace("\\", "/").strip()
        if "/" in name and (self.root / name).is_file():
            return name
        return self.images.get(name.rsplit("/", 1)[-1].casefold())

    def _size(self, relpath: str):
        p = self.root / relpath
        try:
            m = p.stat().st_mtime
        except OSError:
            return None
        c = self.sizes.get(relpath)
        if c and c[0] == m:
            return c[1]
        s = imgsize.size(p)
        self.sizes[relpath] = (m, s)
        return s

    # --- rebuild ---------------------------------------------------------
    def _rebuild(self):
        warnings: list[Warning] = [
            Warning(c, 1, "sync-conflict", "a sync tool's conflict copy: merge what's new in it into the "
                    "original, then delete it (mapt ignores it until then)", "error")
            for c in self.conflicts]
        items: dict[str, Item] = {}           # casefolded id → item
        for r in sorted(self.cache, key=str.casefold):
            it = self.cache[r].item
            if it is None:
                continue
            warnings.extend(it.warnings)
            k = it.id.casefold()
            if k in items:
                warnings.append(Warning(r, 1, "duplicate-name",
                                        f"{items[k].path} has the same name; links can't tell them apart, "
                                        f"so this one is ignored", "error"))
                continue
            items[k] = it

        def get(name):
            return items.get(name.casefold()) if name else None

        # parents
        parent: dict[str, str | None] = {}
        for k, it in items.items():
            p = get(it.parent)
            if it.parent and p is None:
                warnings.append(Warning(it.path, 1, "unresolved",
                                        f"[[{it.parent}]] doesn't match any place", "warning"))
            elif p is it:
                warnings.append(Warning(it.path, 1, "self-parent", "it can't be inside itself", "error"))
                p = None
            elif p is not None and p.kind == "thing":
                warnings.append(Warning(it.path, 1, "in-thing",
                                        f"[[{p.id}]] is a thing; to hold things, it could be a place "
                                        f"(move it to {self.config['places_dir']}/)", "info"))
            parent[k] = p.id.casefold() if p else None

        # cycles: cut the link that closes the loop
        for k in items:
            seen = [k]
            cur = parent[k]
            while cur is not None:
                if cur in seen:
                    last = seen[-1]
                    warnings.append(Warning(items[last].path, 1, "cycle",
                                            "places inside each other in a loop: "
                                            + " → ".join(items[s].id for s in seen[seen.index(cur):] + [cur]),
                                            "error"))
                    parent[last] = None
                    break
                seen.append(cur)
                cur = parent[cur]

        children: dict[str, list[str]] = {k: [] for k in items}
        for k, p in parent.items():
            if p is not None:
                children[p].append(k)

        # maps
        maps: dict[str, tuple[str, float, float]] = {}
        for k, it in items.items():
            if not it.map:
                continue
            path = self.find_image(it.map)
            if path is None:
                warnings.append(Warning(it.path, 1, "missing-map", f"map image not found: {it.map}", "error"))
                continue
            sz = self._size(path)
            if not sz or not sz[0] or not sz[1]:
                warnings.append(Warning(it.path, 1, "map-size",
                                        f"can't tell how big {it.map} is; use a PNG, JPEG or SVG with a width "
                                        f"and height or viewBox", "error"))
                continue
            if it.kind == "thing":
                warnings.append(Warning(it.path, 1, "thing-map", "only places have maps", "info"))
            maps[k] = (path, float(sz[0]), float(sz[1]))

        def chain(k):
            out = []
            cur = parent[k]
            while cur is not None:
                out.append(cur)
                cur = parent[cur]
            return out[::-1]

        def descendants(k):
            out, todo = [], list(children[k])
            while todo:
                c = todo.pop()
                out.append(c)
                todo.extend(children[c])
            return out

        today = date.today()
        item_rows, stock_rows, fts_rows = [], [], []
        for k, it in items.items():
            ch = chain(k)
            map_place = next((a for a in reversed(ch) if a in maps), None)
            pin = None
            if map_place is not None:
                path_down = ch[ch.index(map_place) + 1:] + [k]
                pin = items[path_down[0]].id
            pos = it.pos
            p = parent[k]
            if pos is not None and (p is None or p not in maps):
                warnings.append(Warning(it.path, 1, "pos-unused",
                                        f"pos: is ignored because {'it has no place' if p is None else items[p].id + ' has no map'}",
                                        "info"))
                pos = None
            desc = descendants(k)
            st = stock.stats(it.events, it.qty, today) if it.kind == "thing" else {}
            mp = maps.get(k)
            search = " ".join([it.id, *it.tags] + [items[d].id for d in desc]).casefold()
            item_rows.append((
                it.id, it.kind, it.path, items[p].id if p else None,
                pos[0] if pos else None, pos[1] if pos else None,
                mp[0] if mp else None, mp[1] if mp else None, mp[2] if mp else None,
                it.qty, it.unit, it.reorder, it.added, it.owner,
                json.dumps(it.tags), json.dumps(it.fields, default=str), it.body, it.body_line,
                json.dumps([items[a].id for a in ch]),
                items[map_place].id if map_place else None, pin,
                sum(1 for d in desc if items[d].kind == "thing"), len(children[k]), search,
                st.get("last_bought"), st.get("per_day"), st.get("days_left"),
                int(it.qty is not None and it.reorder is not None and it.qty <= it.reorder)))
            for e in it.events:
                stock_rows.append((it.id, e.ts, e.kind, e.n, e.before, e.after, e.line))
            extra = " ".join(f"{fk} {fv}" for fk, fv in it.fields.items() if fk not in ("pos", "map"))
            fts_rows.append((it.id, f"{' '.join(it.tags)} {it.owner or ''} {extra}\n{it.body}"))

        db = self.db
        db.execute("BEGIN")
        for name, rows in (("items", item_rows), ("stock", stock_rows), (
                "warnings", [(w.path, w.line, w.code, w.severity, w.message) for w in warnings])):
            db.execute(f"DELETE FROM {name}")
            if rows:
                db.executemany(f"INSERT INTO {name} VALUES ({','.join('?' * len(rows[0]))})", rows)
        db.execute("DELETE FROM fts")
        db.executemany("INSERT INTO fts (id, text) VALUES (?, ?)", fts_rows)
        db.execute("INSERT OR REPLACE INTO meta VALUES ('built', ?)",
                   (datetime.now().isoformat(timespec="seconds"),))
        db.commit()

    # --- queries -----------------------------------------------------------
    def item(self, name: str):
        return self.q1("SELECT * FROM items WHERE id = ?", name) if name else None

    def children(self, name: str):
        return self.q("SELECT * FROM items WHERE parent = ? COLLATE NOCASE "
                      "ORDER BY kind, id COLLATE NOCASE", name)

    def pins(self, map_id: str):
        return self.q("SELECT * FROM items WHERE parent = ? COLLATE NOCASE AND x IS NOT NULL "
                      "ORDER BY id COLLATE NOCASE", map_id)

    def unplaced(self, map_id: str):
        return self.q("SELECT * FROM items WHERE parent = ? COLLATE NOCASE AND x IS NULL "
                      "ORDER BY kind, id COLLATE NOCASE", map_id)

    def homes(self):
        """Top-level places with maps: where browsing starts."""
        return self.q("SELECT * FROM items WHERE map IS NOT NULL AND map_place IS NULL "
                      "ORDER BY parent IS NOT NULL, id COLLATE NOCASE")

    def names(self, kind: str | None = None) -> list[str]:
        if kind:
            return [r[0] for r in self.q("SELECT id FROM items WHERE kind=? ORDER BY id COLLATE NOCASE", kind)]
        return [r[0] for r in self.q("SELECT id FROM items ORDER BY id COLLATE NOCASE")]

    def stock_events(self, name: str):
        return self.q("SELECT * FROM stock WHERE item = ? ORDER BY ts DESC, line DESC", name)

    def warnings(self, include_info: bool = False):
        sql = "SELECT * FROM warnings"
        if not include_info:
            sql += " WHERE severity != 'info'"
        return self.q(sql + " ORDER BY path COLLATE NOCASE, line")

    def search(self, text: str, limit: int = 100):
        """Names first (contains), then full text. → rows with a `snippet` column."""
        text = text.strip()
        if not text:
            return []
        like = f"%{text.replace('%', '').replace('_', '')}%"
        rows = list(self.q("SELECT *, '' AS snippet FROM items WHERE id LIKE ? "
                           "ORDER BY id NOT LIKE ?, length(id), id COLLATE NOCASE LIMIT ?",
                           like, text.replace("%", "") + "%", limit))
        seen = {r["id"].casefold() for r in rows}
        terms = [t for t in "".join(c if c.isalnum() else " " for c in text).split() if t]
        if terms:
            match = " ".join(f'"{t}"*' for t in terms)
            try:
                hits = self.q("SELECT i.*, snippet(fts, 1, '[[[', ']]]', '…', 12) AS snippet FROM fts "
                              "JOIN items i ON i.id = fts.id WHERE fts MATCH ? ORDER BY rank LIMIT ?",
                              match, limit)
            except sqlite3.OperationalError:
                hits = []
            rows += [h for h in hits if h["id"].casefold() not in seen]
        return rows[:limit]

    def summary_text(self) -> str:
        n = self.q1("SELECT sum(kind='place'), sum(kind='thing'), sum(map IS NOT NULL) FROM items")
        w = self.q1("SELECT count(*) FROM warnings WHERE severity != 'info'")[0]
        return (f"{n[0] or 0} places ({n[2] or 0} with maps), {n[1] or 0} things"
                + (f", {w} warning{'s' if w != 1 else ''}" if w else ""))
