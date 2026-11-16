"""`mapt server`: stdlib HTTP server + Jinja2 templates."""
from __future__ import annotations

import json
import mimetypes
import re
import traceback
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse

from jinja2 import Environment, PackageLoader, select_autoescape
from markupsafe import Markup, escape

from . import stock, writes
from .index import KNOWN, Index, tag_list
from .render import Renderer, first_image
from .stock import Event, fmt as fmt_num, stats as stock_stats
from .writes import WriteError

STATIC = Path(__file__).parent / "static"
MAX_UPLOAD = 60 * 1024 * 1024


class Redirect(Exception):
    def __init__(self, url: str):
        self.url = url


class NotFound(Exception):
    pass


class ReadOnly(Exception):
    pass


def iurl(name: str) -> str:
    return f"/i/{quote(name)}"


class App:
    def __init__(self, index: Index, readonly: bool = False):
        self.index = index
        self.readonly = readonly
        self.lock = index.lock
        self.env = Environment(loader=PackageLoader("mapt", "templates"),
                               autoescape=select_autoescape(["html"]), trim_blocks=True,
                               lstrip_blocks=True)
        self.env.globals.update(app=self, static=self.static_url, ilink=self.ilink,
                                fields=self.fields, extra=self.extra, now=datetime.now)
        self.env.filters.update(q=lambda s: quote(str(s)), num=fmt_num, iurl=iurl,
                                inline=lambda t: self.renderer().inline(t or ""),
                                day=self.fmt_day, rate=self.fmt_rate, left=self.fmt_left,
                                tags=lambda r: json.loads(r["tags"] or "[]"),
                                chain=lambda r: json.loads(r["chain"] or "[]"))

    @property
    def config(self):
        return self.index.config

    # --- helpers used by templates ----------------------------------------------
    @staticmethod
    def static_url(relpath: str) -> str:
        """`/static/<rel>?v=<mtime>`: a changed file gets a new URL, so browsers never run a stale copy."""
        try:
            v = int((STATIC / relpath).stat().st_mtime)
        except OSError:
            v = 0
        return f"/static/{relpath}?v={v}"

    def ilink(self, name: str, label: str | None = None, cls: str = "") -> Markup:
        """A link to an item. `data-map` lets the map page select it in place when it
        shows on the same map, instead of loading a new page."""
        row = self.index.item(name) if name else None
        if row is None:
            return Markup(f'<span class="link unresolved" title="no such place or thing">{escape(label or name)}</span>')
        return Markup(
            f'<a class="link {row["kind"]}{" " + cls if cls else ""}" href="{iurl(row["id"])}" '
            f'data-id="{escape(row["id"])}" data-map="{escape(row["map_place"] or "")}"'
            f'{" data-hasmap" if row["map"] else ""}>{escape(label or row["id"])}</a>')

    def renderer(self) -> Renderer:
        return Renderer(lambda t, label: str(self.ilink(t, label)), self.image_url)

    @staticmethod
    def image_url(name: str) -> str:
        return f"/img?name={quote(name)}"

    @staticmethod
    def fields(row) -> dict:
        return json.loads(row["fields"] or "{}")

    def extra(self, row) -> dict:
        """Frontmatter the forms don't own, to show as is."""
        return {k: v for k, v in self.fields(row).items() if k not in KNOWN and k != "aliases"}

    @staticmethod
    def fmt_day(v) -> str:
        if not v:
            return ""
        s = str(v)
        try:
            d = datetime.fromisoformat(s) if "T" in s else date.fromisoformat(s[:10])
        except ValueError:
            return s
        out = f"{d.day} {d:%b %Y}"
        return out + (f" {d:%H:%M}" if isinstance(d, datetime) else "")

    @staticmethod
    def fmt_rate(per_day, unit=None) -> str:
        if not per_day:
            return ""
        u = f" {unit}" if unit else ""
        for span, name in ((1, "day"), (7, "week"), (30.4, "month"), (365, "year")):
            v = per_day * span
            if v >= 1 or span == 365:
                return f"{v:.1f}".rstrip("0").rstrip(".") + f"{u} a {name}"
        return ""

    @staticmethod
    def fmt_left(days) -> str:
        if days is None:
            return ""
        if days < 1:
            return "less than a day"
        if days < 14:
            return f"{days:.0f} days"
        if days < 70:
            return f"{days / 7:.0f} weeks"
        return f"{days / 30.4:.0f} months"

    @staticmethod
    def snippet(s: str) -> Markup:
        """An FTS snippet with its `[[[match]]]` markers as <mark>."""
        return Markup(str(escape(s)).replace("[[[", "<mark>").replace("]]]", "</mark>"))

    def warning_count(self) -> int:
        return self.index.q1("SELECT count(*) FROM warnings WHERE severity != 'info'")[0]

    def low_count(self) -> int:
        return self.index.q1("SELECT count(*) FROM items WHERE low = 1")[0]

    def page(self, name: str, **ctx) -> str:
        return self.env.get_template(name).render(**ctx)

    def _item(self, name: str):
        row = self.index.item(name)
        if row is None:
            raise NotFound()
        return row

    def _path(self, row) -> Path:
        return writes.under(self.index.root, row["path"])

    def _write(self):
        if self.readonly:
            raise ReadOnly()

    # --- routing ----------------------------------------------------------------
    ROUTES = [
        ("GET", r"/", "home"),
        ("GET", r"/m/(?P<name>[^/]+)", "map"),
        ("GET", r"/i/(?P<name>[^/]+)", "item"),
        ("GET", r"/d/(?P<name>[^/]+)", "detail"),
        ("GET", r"/pane/(?P<name>[^/]+)", "pane"),
        ("GET", r"/new", "new"),
        ("GET", r"/form/new", "form_new"),
        ("GET", r"/form/edit/(?P<name>[^/]+)", "form_edit"),
        ("POST", r"/new", "new_save"),
        ("GET", r"/edit/(?P<name>[^/]+)", "edit"),
        ("POST", r"/edit/(?P<name>[^/]+)", "edit_save"),
        ("POST", r"/delete/(?P<name>[^/]+)", "delete"),
        ("POST", r"/stock/(?P<name>[^/]+)", "stock_save"),
        ("GET", r"/raw/(?P<path>.+)", "raw"),
        ("POST", r"/raw/(?P<path>.+)", "raw_save"),
        ("GET", r"/things", "things"),
        ("GET", r"/places", "places"),
        ("GET", r"/stock", "stock"),
        ("GET", r"/search", "search"),
        ("GET", r"/lint", "lint"),
        ("GET", r"/img", "img"),
        ("POST", r"/upload", "upload"),
        ("POST", r"/api/pos", "api_pos"),
        ("GET", r"/api/names", "api_names"),
        ("GET", r"/api/pins/(?P<name>[^/]+)", "api_pins"),
        ("GET", r"/manifest\.webmanifest", "manifest"),
    ]

    def dispatch(self, method: str, path: str, query: dict, form: dict, files: dict):
        for m, pattern, name in self.ROUTES:
            if m != method:
                continue
            mt = re.fullmatch(pattern, path)
            if mt:
                if method == "POST":
                    self._write()
                kw = {k: unquote(v) for k, v in mt.groupdict().items()}
                return getattr(self, "r_" + name)(query=query, form=form, files=files, **kw)
        raise NotFound()

    # --- browsing ------------------------------------------------------------
    def r_home(self, **_):
        home = self.config["home"]
        if home and self.index.item(str(home)):
            raise Redirect(iurl(str(home)))
        homes = self.index.homes()
        if len(homes) == 1:
            raise Redirect(f"/m/{quote(homes[0]['id'])}")
        roots = self.index.q("SELECT * FROM items WHERE parent IS NULL AND kind='place' ORDER BY id COLLATE NOCASE")
        return self.page("home.html", homes=homes, roots=roots)

    def default_map(self):
        """The map to show something on when there's no map above it."""
        home = self.index.item(str(self.config["home"])) if self.config["home"] else None
        if home is not None and home["map"]:
            return home
        homes = self.index.homes()
        return homes[0] if homes else None

    def r_item(self, name, **_):
        """Where an item is best seen: a place with a map opens its map; anything else is
        selected on the map it sits on. With no map above it, it's shown in the pane of the
        home map; with no maps at all, on its own page."""
        row = self._item(name)
        if row["map"]:
            raise Redirect(f"/m/{quote(row['id'])}")
        if row["map_place"]:
            raise Redirect(f"/m/{quote(row['map_place'])}?sel={quote(row['id'])}")
        home = self.default_map()
        if home is not None:
            raise Redirect(f"/m/{quote(home['id'])}?sel={quote(row['id'])}")
        raise Redirect(f"/d/{quote(row['id'])}")

    def resolve(self, url: str) -> str:
        """Follow `/i/` redirects to where the item is actually shown."""
        for _ in range(3):
            if not url.startswith("/i/"):
                break
            try:
                self.r_item(unquote(url[3:].split("?")[0]))
            except Redirect as r:
                url = r.url
            except NotFound:
                break
        return url

    def pins(self, place: str) -> list[dict]:
        return [{
            "id": p["id"], "kind": p["kind"], "x": p["x"], "y": p["y"],
            "map": bool(p["map"]), "things": p["things"], "children": p["children"],
            "qty": p["qty"], "low": bool(p["low"]), "search": p["search"],
        } for p in self.index.pins(place)]

    def r_api_pins(self, name, **_):
        row = self._item(name)
        return ("application/json", json.dumps(self.pins(row["id"])).encode())

    def r_map(self, name, query, **_):
        row = self._item(name)
        if not row["map"]:
            raise Redirect(iurl(row["id"]))
        if row["id"] != name:
            raise Redirect(f"/m/{quote(row['id'])}" + (f"?{urlencode(query)}" if query else ""))
        sel = self.index.item(query.get("sel", "")) if query.get("sel") else None
        here = sel is not None and sel["map_place"] == row["id"]
        data = {"id": row["id"], "url": self.image_url(row["map"]), "w": row["map_w"], "h": row["map_h"],
                "pins": self.pins(row["id"]), "sel": sel["id"] if sel else None,
                "pin": sel["pin"] if here else None, "readonly": self.readonly}
        return self.page("map.html", place=row, data=data,
                         pane=self.pane(sel["id"] if sel else row["id"], row["id"]))

    def r_detail(self, name, **_):
        row = self._item(name)
        if row["id"] != name:
            raise Redirect(f"/d/{quote(row['id'])}")
        return self.page("detail.html", e=row, pane=self.pane(row["id"], None))

    def r_pane(self, name, query, **_):
        return self.pane(name, query.get("map") or None)

    def pane(self, name: str, on_map: str | None) -> Markup:
        """The side pane for an item (as seen from map `on_map`, if any)."""
        row = self._item(name)
        st = None
        if row["kind"] == "thing":
            events = self.index.stock_events(row["id"])
            if events or row["qty"] is not None:
                st = stock_stats([Event(r["ts"], r["kind"], r["n"], r["before"], r["after"], r["line"])
                                  for r in events], row["qty"])
                st["history"] = list(reversed(st["history"]))[:12]
        body = row["body"] or ""
        return Markup(self.page(
            "pane.html", e=row, on_map=on_map, is_map=on_map is not None and row["id"] == on_map,
            chain=json.loads(row["chain"] or "[]"), tags=json.loads(row["tags"] or "[]"),
            children=self.index.children(row["id"]), photo=first_image(body),
            unplaced=self.index.unplaced(row["id"]) if row["map"] else [],
            notes=self.renderer().document(body, skip_stock=st is not None), st=st))

    def r_things(self, query, **_):
        rows = self.index.q("SELECT * FROM items WHERE kind='thing' ORDER BY id COLLATE NOCASE")
        tag = query.get("tag")
        if tag:
            rows = [r for r in rows if tag.casefold() in (t.casefold() for t in json.loads(r["tags"] or "[]"))]
        return self.page("list.html", kind="thing", rows=rows, tag=tag)

    def r_places(self, **_):
        rows = self.index.q("SELECT * FROM items WHERE kind='place' ORDER BY id COLLATE NOCASE")
        return self.page("list.html", kind="place", rows=rows, tag=None)

    def r_stock(self, **_):
        rows = self.index.q(
            "SELECT * FROM items WHERE kind='thing' AND (qty IS NOT NULL OR reorder IS NOT NULL "
            "OR id IN (SELECT item FROM stock)) "
            "ORDER BY low DESC, days_left IS NULL, days_left, id COLLATE NOCASE")
        return self.page("stock.html", rows=rows)

    def r_search(self, query, **_):
        q = query.get("q", "").strip()
        rows = self.index.search(q) if q else []
        if q and query.get("go") and rows and rows[0]["id"].casefold() == q.casefold():
            raise Redirect(iurl(rows[0]["id"]))
        return self.page("search.html", q=q, rows=rows)

    def r_lint(self, query, **_):
        return self.page("lint.html", rows=self.index.warnings(include_info=bool(query.get("all"))),
                         all=bool(query.get("all")))

    def r_img(self, query, **_):
        found = self.index.find_image(query.get("name", ""))
        if not found:
            raise NotFound()
        return ("file", writes.under(self.index.root, found))

    def r_api_names(self, **_):
        rows = self.index.q("SELECT id, kind, chain FROM items ORDER BY id COLLATE NOCASE")
        return ("application/json", json.dumps(
            [{"id": r["id"], "kind": r["kind"], "where": " › ".join(json.loads(r["chain"]))} for r in rows]
        ).encode())

    def r_manifest(self, **_):
        return ("application/manifest+json", json.dumps({
            "name": self.config["title"], "short_name": self.config["title"], "start_url": "/",
            "display": "standalone", "background_color": "#f7f7f5", "theme_color": "#3b5bdb",
            "icons": [{"src": "/static/icon.svg", "sizes": "any", "type": "image/svg+xml"}],
        }).encode())

    # --- writing ---------------------------------------------------------------
    def _where(self, text: str, kind: str) -> str | None:
        """A place name from a form → its canonical name; unknown names are an error."""
        text = (text or "").strip()
        if text.startswith("[[") and text.endswith("]]"):
            text = text[2:-2]
        if not text:
            return None
        row = self.index.item(text)
        if row is None:
            raise WriteError(f"there's no place called {text!r} (make it first, or pick one from the list)")
        return row["id"]

    def _map_upload(self, files) -> str | None:
        f = files.get("mapfile")
        if not f or not f[1]:
            return None
        return writes.save_upload(self.index.root, self.config["attachments_dir"], f[0], f[1])

    def r_new(self, query, **_):
        self._write()
        return self.page("new.html", **self._new_ctx(query))

    def _new_ctx(self, query) -> dict:
        where = self.index.item(query.get("place", "")) if query.get("place") else None
        return dict(where=where, kind=query.get("kind", "thing"), x=query.get("x", ""),
                    y=query.get("y", ""), places=self.index.names("place"))

    def r_form_new(self, query, **_):
        """The add form for the map's side pane."""
        self._write()
        ctx = self._new_ctx(query)
        ctx["on_map"] = self._map_name(query)
        return Markup('<div class="pane-item pane-form" data-id="">') + Markup(
            self.page("_new_form.html", in_pane=True, **ctx)) + Markup("</div>")

    def r_form_edit(self, name, query, **_):
        """The edit form for the map's side pane."""
        self._write()
        row = self._item(name)
        return Markup('<div class="pane-item pane-form" data-id="{}">').format(row["id"]) + Markup(
            self.page("_edit_form.html", in_pane=True, on_map=self._map_name(query),
                      **self._edit_ctx(row))) + Markup("</div>")

    def _map_name(self, query) -> str | None:
        """`?map=`: the map the pane is on, when it is one."""
        row = self.index.item(query.get("map", "")) if query.get("map") else None
        return row["id"] if row is not None and row["map"] else None

    def _edit_ctx(self, row) -> dict:
        return dict(e=row, f=self.fields(row), places=self.index.names("place"),
                    tags=", ".join(json.loads(row["tags"] or "[]")), extra=self.extra(row))

    def r_new_save(self, form, files, **_):
        kind = form.get("kind", "thing")
        name = writes.safe_name(form.get("name", ""))
        existing = self.index.item(name)
        if existing is not None:
            where = " › ".join(json.loads(existing["chain"]) + [existing["id"]])
            raise WriteError(f"{existing['id']!r} already exists ({where}). Give this one a name of its "
                             f"own, like '{name} (2)' or '{name} - bench'.")
        where = self._where(form.get("where", ""), kind)
        fields: dict = {}
        key = "parent" if kind == "place" else "place"
        if where:
            fields[key] = writes.link(where)
        if form.get("x") and form.get("y") and where and self.index.item(where)["map"]:
            fields["pos"] = [round(float(form["x"]), 4), round(float(form["y"]), 4)]
        if kind == "place":
            m = self._map_upload(files)
            if m:
                fields["map"] = writes.link(m)
        if kind == "thing":
            for k in ("qty", "reorder"):
                v = writes.number(form.get(k))
                if v is not None:
                    fields[k] = v
            for k in ("unit", "owner"):
                if form.get(k, "").strip():
                    fields[k] = form[k].strip()
            tags = tag_list(form.get("tags", ""))
            if tags:
                fields["tags"] = tags
            fields["added"] = writes.today()
        folder = self.config.folder("place" if kind == "place" else "thing")
        writes.new_item(self.index.root, folder, name, fields, form.get("body", ""))
        self.index.refresh()
        raise Redirect(iurl(name))

    def r_edit(self, name, **_):
        self._write()
        row = self._item(name)
        return self.page("edit.html", **self._edit_ctx(row))

    def r_edit_save(self, name, form, files, **_):
        row = self._item(name)
        path = self._path(row)
        old = self.fields(row)
        changes: dict = {}
        remove: list[str] = []
        body = form.get("body", row["body"] or "").replace("\r\n", "\n")

        key = next((k for k in ("place", "parent") if k in old),
                   "parent" if row["kind"] == "place" else "place")
        where = self._where(form.get("where", ""), row["kind"])
        if where and where.casefold() == row["id"].casefold():
            raise WriteError("it can't be inside itself")
        if (where or "").casefold() != (row["parent"] or "").casefold() or (not where and old.get(key)):
            if where:
                changes[key] = writes.link(where)
            else:
                remove.append(key)
            remove.append("pos")            # the old spot was on another map
        if "x" in form and where and self.index.item(where)["map"]:
            # the pane's spot picker, for a place with a map: a spot, or none
            if form.get("x") and form.get("y"):
                pos = [round(min(1, max(0, float(form[k]))), 4) for k in ("x", "y")]
                if pos != [row["x"], row["y"]] or "pos" in remove:
                    changes["pos"] = pos
                    remove = [k for k in remove if k != "pos"]
            elif "pos" in old:
                remove.append("pos")

        if row["kind"] == "place":
            m = self._map_upload(files)
            if m:
                changes["map"] = writes.link(m)
            elif form.get("remove_map"):
                remove.append("map")
        else:
            qty = writes.number(form.get("qty"))
            before = row["qty"]
            if qty != (stock.num(before) if before is not None else None):
                if qty is None:
                    remove.append("qty")
                else:   # a typed-in amount is a count, and goes in the history like one
                    changes["qty"] = qty
                    body = stock.append(body, stock.line("count", qty, before, qty, datetime.now()))
            for k in ("reorder",):
                v = writes.number(form.get(k))
                if v is None:
                    remove.append(k)
                else:
                    changes[k] = v
            for k in ("unit", "owner"):
                v = form.get(k, "").strip()
                if v:
                    if v != str(old.get(k) or ""):
                        changes[k] = v
                else:
                    remove.append(k)
            tags = tag_list(form.get("tags", ""))
            if tags != tag_list(old.get("tags")):
                if tags:
                    changes["tags"] = tags
                else:
                    remove.append("tags")
        writes.edit_item(path, changes, [k for k in remove if k in old or k == "pos"], body)

        new = form.get("name", "").strip()
        target = row["id"]
        if new and new != row["id"]:
            clash = self.index.item(new)
            others = {clash["path"]} if clash is not None and clash["path"] != row["path"] else set()
            writes.rename(self.index.root, row["path"], new, others)
            target = writes.safe_name(new)
        self.index.refresh()
        raise Redirect(iurl(target))

    def r_delete(self, name, **_):
        row = self._item(name)
        writes.trash(self.index.root, row["path"])
        self.index.refresh()
        raise Redirect(iurl(row["parent"]) if row["parent"] and self.index.item(row["parent"]) else "/")

    def r_stock_save(self, name, form, **_):
        row = self._item(name)
        writes.record(self._path(row), form.get("kind", ""), form.get("n", ""))
        self.index.refresh()
        back = form.get("back") or iurl(row["id"])
        raise Redirect(back if back.startswith("/") and not back.startswith("//") else iurl(row["id"]))

    def r_raw(self, path, **_):
        self._write()
        p = writes.under(self.index.root, path)
        if not p.is_file() or p.suffix.lower() != ".md":
            raise NotFound()
        row = self.index.q1("SELECT * FROM items WHERE path = ?", path)
        return self.page("raw.html", path=path, text=p.read_text(encoding="utf-8-sig"), e=row)

    def r_raw_save(self, path, form, **_):
        p = writes.under(self.index.root, path)
        if not p.is_file() or p.suffix.lower() != ".md":
            raise NotFound()
        writes.save_raw(p, form.get("text", ""))
        self.index.refresh()
        row = self.index.q1("SELECT * FROM items WHERE path = ?", path)
        raise Redirect(iurl(row["id"]) if row else "/lint")

    def r_upload(self, files, **_):
        f = files.get("file")
        if not f:
            raise WriteError("no file")
        name = writes.save_upload(self.index.root, self.config["attachments_dir"], f[0], f[1])
        self.index.refresh()
        return ("application/json", json.dumps({"name": name}).encode())

    def r_api_pos(self, form, **_):
        row = self._item(form.get("id", ""))
        if form.get("clear"):
            writes.set_pos(self._path(row), None)
        else:
            parent = self.index.item(row["parent"]) if row["parent"] else None
            if parent is None or not parent["map"]:
                raise WriteError(f"{row['id']} isn't in a place with a map")
            writes.set_pos(self._path(row), (float(form["x"]), float(form["y"])))
        self.index.refresh()
        return ("application/json", json.dumps({"ok": True}).encode())


class Form(dict):
    """Single values by key; all values with getlist()."""

    def __init__(self, multi: dict[str, list[str]]):
        super().__init__({k: v[-1] for k, v in multi.items()})
        self.multi = multi

    def getlist(self, key):
        return self.multi.get(key, [])


def parse_multipart(body: bytes, content_type: str):
    """→ (Form, {name: (filename, bytes)}). Small and strict; `cgi` is gone in 3.13."""
    m = re.search(r'boundary="?([^";]+)"?', content_type)
    if not m:
        raise WriteError("bad upload")
    boundary = b"--" + m.group(1).encode()
    fields_: dict[str, list[str]] = {}
    files: dict[str, tuple[str, bytes]] = {}
    for part in body.split(boundary)[1:]:
        if part.startswith(b"--"):
            break
        head, _, data = part.lstrip(b"\r\n").partition(b"\r\n\r\n")
        data = data[:-2] if data.endswith(b"\r\n") else data
        disp = re.search(rb'name="([^"]*)"(?:; filename="([^"]*)")?', head)
        if not disp:
            continue
        name = disp.group(1).decode()
        if disp.group(2) is not None:
            files[name] = (disp.group(2).decode("utf-8", "replace"), data)
        else:
            fields_.setdefault(name, []).append(data.decode("utf-8", "replace"))
    return Form(fields_), files


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        server_version = "mapt"

        def log_message(self, fmt, *args):
            pass

        def _send(self, status, body: bytes, ctype="text/html; charset=utf-8", headers=None):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _file(self, p: Path, cache=False):
            ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
            if p.suffix.lower() == ".svg":
                ctype = "image/svg+xml"
            elif p.suffix.lower() == ".js":
                ctype = "text/javascript"
            headers = {"Cache-Control": "max-age=86400" if cache else "no-cache"}
            if ctype == "image/svg+xml":
                headers["Content-Security-Policy"] = "script-src 'none'"   # an uploaded SVG can't run code
            self._send(200, p.read_bytes(), ctype, headers)

        def do_GET(self):
            self._handle("GET")

        def do_POST(self):
            self._handle("POST")

        def _pane(self) -> bool:
            return self.headers.get("X-Mapt") == "pane"

        def _same_origin(self) -> bool:
            """Refuse cross-site form posts: any web page could target 127.0.0.1."""
            origin = self.headers.get("Origin") or self.headers.get("Referer")
            if not origin:
                return True
            host = urlparse(origin).netloc
            return host in (self.headers.get("Host"), self.headers.get("X-Forwarded-Host"))

        def _handle(self, method):
            url = urlparse(self.path)
            path = url.path
            query = {k: v[-1] for k, v in parse_qs(url.query, keep_blank_values=True).items()}
            try:
                if method == "GET" and path.startswith("/static/"):
                    p = (STATIC / unquote(path[8:])).resolve()
                    if STATIC.resolve() not in p.parents or not p.is_file():
                        raise NotFound()
                    return self._file(p, cache="v=" in url.query)
                form, files = Form({}), {}
                if method == "POST":
                    if not self._same_origin():
                        return self._send(403, b"cross-site request refused", "text/plain")
                    n = int(self.headers.get("Content-Length") or 0)
                    if n > MAX_UPLOAD:
                        return self._send(413, b"too large", "text/plain")
                    body = self.rfile.read(n)
                    ctype = self.headers.get("Content-Type", "")
                    if ctype.startswith("multipart/form-data"):
                        form, files = parse_multipart(body, ctype)
                    else:
                        form = Form(parse_qs(body.decode("utf-8"), keep_blank_values=True))
                with app.lock:
                    app.index.refresh()
                    out = app.dispatch(method, path, query, form, files)
                if isinstance(out, tuple) and out[0] == "file":
                    return self._file(out[1])
                if isinstance(out, tuple):
                    return self._send(200, out[1], out[0])
                return self._send(200, str(out).encode("utf-8"))
            except Redirect as r:
                if self._pane():   # a form posted from the map's pane: say where it went, as JSON
                    with app.lock:
                        go = app.resolve(r.url)
                    return self._send(200, json.dumps({"go": go}).encode(), "application/json")
                self._send(303, b"", headers={"Location": r.url})
            except NotFound:
                self._send(404, app.page("error.html", title="Not found",
                                         message=f"Nothing at {unquote(path)}").encode("utf-8"))
            except ReadOnly:
                self._send(403, app.page("error.html", title="Read-only",
                                         message="This mapt is read-only.").encode("utf-8"))
            except (WriteError, KeyError, ValueError) as e:
                msg = str(e) if isinstance(e, WriteError) else f"{type(e).__name__}: {e}"
                if path.startswith(("/upload", "/api/")) or self._pane():
                    return self._send(400, json.dumps({"error": msg}).encode(), "application/json")
                self._send(400, app.page("error.html", title="Couldn't save", message=msg).encode("utf-8"))
            except Exception:
                tb = traceback.format_exc()
                print(tb)
                self._send(500, app.page("error.html", title="Error", message=tb).encode("utf-8"))

        do_HEAD = do_GET

    return Handler


def run(root: Path, host: str = "127.0.0.1", port: int = 8715, readonly: bool = False):
    print(f"indexing {root} …", flush=True)
    index = Index(root)
    print(index.summary_text())
    if index.warnings():
        print("see the Problems page, or run `mapt lint`")
    app = App(index, readonly=readonly)
    httpd = ThreadingHTTPServer((host, port), make_handler(app))
    print(f"mapt serving {root} at http://{host}:{port}" + (" (read-only)" if readonly else "")
          + "  (Ctrl+C to stop)", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
