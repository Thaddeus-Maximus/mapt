"""Every page renders, and every write action writes a plain file edit."""
import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from mapt.server import App, make_handler


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def serve(index, readonly=False):
    app = App(index, readonly=readonly)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    opener = urllib.request.build_opener(NoRedirect)

    def call(path, data=None, raw=None, ctype=None, headers=None):
        body = raw if raw is not None else (
            urllib.parse.urlencode(data, doseq=True).encode() if data is not None else None)
        req = urllib.request.Request(base + path, data=body, headers=headers or {})
        if ctype:
            req.add_header("Content-Type", ctype)
        try:
            with opener.open(req) as r:
                return r.status, r.headers, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.headers, e.read().decode("utf-8", "replace")

    return httpd, call


@pytest.fixture
def web(index):
    httpd, call = serve(index)
    yield call
    httpd.shutdown()


@pytest.mark.parametrize("path", [
    "/m/Shop", "/m/Shop?sel=Socket%20Set", "/m/Paint%20Room", "/d/Lost%20Thing", "/pane/Shop?map=Shop",
    "/pane/Shop%20Towels?map=Shop", "/pane/Hammer", "/new", "/new?place=Shop&x=0.1&y=0.2",
    "/new?kind=place", "/edit/Hammer", "/edit/Shop", "/raw/things/Hammer.md", "/things", "/things?tag=tool",
    "/places", "/stock", "/search?q=towel", "/search?q=claw", "/search?q=", "/lint", "/lint?all=1",
    "/img?name=shop.svg", "/api/names", "/api/pins/Shop", "/form/new?place=Shop&x=0.1&y=0.2",
    "/form/edit/Hammer", "/form/edit/Shop", "/static/app.js", "/static/vendor/leaflet/leaflet.js",
    "/manifest.webmanifest",
])
def test_pages(web, path):
    status, _, body = web(path)
    assert status == 200, body[:2000]


@pytest.mark.parametrize("path,to", [
    ("/", "/m/Shop"),
    ("/i/Shop", "/m/Shop"),
    ("/i/Socket%20Set", "/m/Shop?sel=Socket%20Set"),
    ("/i/paint%20room", "/m/Paint%20Room"),
    ("/i/Spray%20Paint", "/m/Paint%20Room?sel=Spray%20Paint"),
    ("/i/Lost%20Thing", "/m/Shop?sel=Lost%20Thing"),
    ("/i/Drill", "/m/Shop?sel=Drill"),
    ("/m/Red%20Toolbox", "/i/Red%20Toolbox"),
    ("/search?q=hammer&go=1", "/i/Hammer"),
])
def test_redirects(web, path, to):
    status, headers, _ = web(path)
    assert status == 303 and headers["Location"] == to


def test_map_page_data(web):
    _, _, body = web("/m/Shop?sel=Hammer")
    assert '"pin": "Red Toolbox"' in body and '"sel": "Hammer"' in body
    assert "Hammer" in body and "On the map: " in body
    _, _, body = web("/m/Shop")
    assert "Not on the map yet" in body and "Drill" in body


def test_new_thing_on_map(web, root):
    status, headers, body = web("/new", {"kind": "thing", "name": "Tape Measure", "where": "shop",
                                         "x": "0.3", "y": "0.4", "qty": "", "tags": "tool, measuring"})
    assert status == 303, body
    assert headers["Location"] == "/i/Tape%20Measure"
    text = (root / "things" / "Tape Measure.md").read_text(encoding="utf-8")
    assert 'place: "[[Shop]]"' in text and "pos: [0.3, 0.4]" in text and "tags: [tool, measuring]" in text
    assert "added:" in text and "qty" not in text
    status, _, body = web("/new", {"kind": "thing", "name": "hammer", "where": "Shop"})
    assert status == 400 and "already exists" in body
    status, _, body = web("/new", {"kind": "thing", "name": "X", "where": "Narnia"})
    assert status == 400 and "no place called" in body


def test_new_place_without_map(web, root):
    status, _, _ = web("/new", {"kind": "place", "name": "Shelf A", "where": "Shop", "x": "0.9", "y": "0.9"})
    assert status == 303
    assert (root / "places" / "Shelf A.md").read_text(encoding="utf-8").startswith('---\nparent: "[[Shop]]"')


def test_new_place_with_map_upload(web, root):
    boundary = "XyZ"
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="40" height="30"></svg>'
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="kind"\r\n\r\nplace\r\n'.encode(),
        f'--{boundary}\r\nContent-Disposition: form-data; name="name"\r\n\r\nGarage\r\n'.encode(),
        f'--{boundary}\r\nContent-Disposition: form-data; name="where"\r\n\r\n\r\n'.encode(),
        f'--{boundary}\r\nContent-Disposition: form-data; name="mapfile"; filename="garage.svg"\r\n'
        f'Content-Type: image/svg+xml\r\n\r\n'.encode() + svg + b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    status, headers, body = web("/new", raw=b"".join(parts), ctype=f"multipart/form-data; boundary={boundary}")
    assert status == 303, body
    assert (root / "attachments" / "garage.svg").exists()
    assert 'map: "[[garage.svg]]"' in (root / "places" / "Garage.md").read_text(encoding="utf-8")
    status, headers, _ = web("/i/Garage")
    assert headers["Location"] == "/m/Garage"


def test_api_pos(web, root):
    status, _, body = web("/api/pos", {"id": "Drill", "x": "0.7", "y": "0.25"})
    assert status == 200, body
    assert "pos: [0.7, 0.25]" in (root / "things" / "Drill.md").read_text(encoding="utf-8")
    status, _, body = web("/api/pos", {"id": "Hammer", "x": "0.7", "y": "0.25"})
    assert status == 400 and "isn't in a place with a map" in json.loads(body)["error"]
    status, _, _ = web("/api/pos", {"id": "Drill", "clear": "1"})
    assert "pos" not in (root / "things" / "Drill.md").read_text(encoding="utf-8")


def test_stock_buttons(web, root):
    status, headers, _ = web("/stock/Shop%20Towels", {"kind": "use", "n": "1"})
    assert status == 303 and headers["Location"] == "/i/Shop%20Towels"
    text = (root / "things" / "Shop Towels.md").read_text(encoding="utf-8")
    assert "qty: 2\n" in text and "used 1 (3 → 2)" in text


def test_edit(web, root):
    status, headers, body = web("/edit/Hammer", {
        "name": "Claw Hammer", "where": "Shop", "qty": "", "unit": "", "reorder": "", "owner": "Thad",
        "tags": "tool", "body": "16 oz.\r\nSee also [[Socket Set]].\r\n"})
    assert status == 303, body
    assert headers["Location"] == "/i/Claw%20Hammer"
    text = (root / "things" / "Claw Hammer.md").read_text(encoding="utf-8")
    assert 'place: "[[Shop]]"' in text and "\r" not in text and "16 oz." in text
    assert "added: 2026-01-05" in text                     # fields the form doesn't own are kept


def test_edit_qty_is_a_count(web, root):
    web("/edit/Spray%20Paint", {"name": "Spray Paint", "where": "Paint Room", "qty": "4", "unit": "cans",
                                 "reorder": "", "owner": "", "tags": "", "body": ""})
    text = (root / "things" / "Spray Paint.md").read_text(encoding="utf-8")
    assert "qty: 4\n" in text and "counted 4 (6 → 4)" in text
    assert "pos: [0.5, 0.5]" in text                       # same place: the pin stays


def test_edit_move_clears_pos(web, root):
    web("/edit/Shop%20Towels", {"name": "Shop Towels", "where": "Red Toolbox", "qty": "3", "unit": "rolls",
                                 "reorder": "4", "owner": "", "tags": "consumable", "body": "x\n"})
    text = (root / "things" / "Shop Towels.md").read_text(encoding="utf-8")
    assert 'place: "[[Red Toolbox]]"' in text and "pos:" not in text


def test_delete(web, root):
    status, headers, _ = web("/delete/Drill", {})
    assert status == 303 and headers["Location"] == "/i/Shop"
    assert (root / ".trash" / "things" / "Drill.md").exists()


def test_raw_save(web, root):
    status, _, _ = web("/raw/things/Drill.md", {"text": "---\nplace: \"[[Paint Room]]\"\n---\nmoved\r\n"})
    assert status == 303
    assert (root / "things" / "Drill.md").read_text(encoding="utf-8").endswith("moved\n")
    status, _, _ = web("/raw/../outside.md", {"text": "x"})
    assert status in (400, 404)


def test_cross_site_post_refused(web, root):
    status, _, _ = web("/api/pos", {"id": "Drill", "x": "0.1", "y": "0.1"}, headers={"Origin": "http://evil.example"})
    assert status == 403
    assert "pos" not in (root / "things" / "Drill.md").read_text(encoding="utf-8")


def test_read_only(index, root):
    httpd, call = serve(index, readonly=True)
    try:
        status, _, body = call("/m/Shop")
        assert status == 200 and "+ Add" not in body
        status, _, _ = call("/stock/Shop%20Towels", {"kind": "use", "n": "1"})
        assert status == 403
        status, _, _ = call("/edit/Hammer")
        assert status == 403
        assert "qty: 3" in (root / "things" / "Shop Towels.md").read_text(encoding="utf-8")
    finally:
        httpd.shutdown()


PANE = {"X-Mapt": "pane"}


def test_pane_forms_answer_json(web, root):
    status, _, body = web("/form/edit/Hammer")
    assert status == 200 and body.startswith('<div class="pane-item pane-form" data-id="Hammer">')
    assert 'action="/edit/Hammer"' in body and "<html" not in body and 'data-act="cancel"' in body
    # saved: where it ended up, resolved past /i/
    status, _, body = web("/new", {"kind": "thing", "name": "Level", "where": "Shop", "x": "0.5", "y": "0.5"},
                          headers=PANE)
    assert status == 200 and json.loads(body) == {"go": "/m/Shop?sel=Level"}
    assert any(p["id"] == "Level" for p in json.loads(web("/api/pins/Shop")[2]))
    # not saved: the reason, as JSON
    status, _, body = web("/new", {"kind": "thing", "name": "level"}, headers=PANE)
    assert status == 400 and "already exists" in json.loads(body)["error"]
    status, _, body = web("/stock/Shop%20Towels", {"kind": "use", "n": "1"}, headers=PANE)
    assert json.loads(body) == {"go": "/m/Shop?sel=Shop%20Towels"}


def test_unmapped_item_shows_in_home_pane(web):
    status, _, body = web("/m/Shop?sel=Lost%20Thing")
    assert status == 200 and '"sel": "Lost Thing"' in body and '"pin": null' in body


def test_pane_forms_have_a_spot_picker(web):
    _, _, body = web("/form/new?place=Shop&map=Shop&x=0.25&y=0.5")
    assert 'class="spot" data-map="Shop" data-picked' in body and 'name="x" value="0.25"' in body
    _, _, body = web("/form/new?place=Shop")                       # no map: no picker
    assert 'class="spot"' not in body
    _, _, body = web("/form/edit/Red%20Toolbox?map=Shop")
    assert 'class="spot" data-map="Shop"' in body and "data-picked" not in body and "Change" in body
    _, _, body = web("/form/edit/Hammer?map=Shop")                 # in the toolbox: no spot of its own
    assert 'name="x" value=""' in body


def test_spot_from_the_pane(web, root):
    def text(rel):
        return (root / rel).read_text(encoding="utf-8")
    web("/new", {"kind": "place", "name": "Shelf B", "where": "Shop", "x": "0.2", "y": "0.3"}, headers=PANE)
    assert "pos: [0.2, 0.3]" in text("places/Shelf B.md")
    web("/new", {"kind": "thing", "name": "Nail", "where": "Red Toolbox", "x": "0.2", "y": "0.3"}, headers=PANE)
    assert "pos" not in text("things/Nail.md")                       # the toolbox has no map
    form = {"name": "Shelf B", "where": "Shop", "body": ""}
    web("/edit/Shelf%20B", {**form, "x": "0.6", "y": "0.7"}, headers=PANE)
    assert "pos: [0.6, 0.7]" in text("places/Shelf B.md")
    web("/edit/Shelf%20B", form, headers=PANE)                       # no spot fields sent: unchanged
    assert "pos: [0.6, 0.7]" in text("places/Shelf B.md")
    web("/edit/Shelf%20B", {**form, "x": "", "y": ""}, headers=PANE)  # cleared
    assert "pos" not in text("places/Shelf B.md")
    web("/edit/Drill", {"name": "Drill", "where": "Shop", "x": "0.5", "y": "0.5", "body": ""}, headers=PANE)
    assert "pos: [0.5, 0.5]" in text("things/Drill.md")
