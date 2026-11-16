# mapt

Where everything is. Floor plans with pins on them; click a pin and the side pane
says what it is, what's in it and how many are left. New people can find things,
and you can see how fast the consumables go.

Everything is plain Markdown you can open in Obsidian. The SQLite index in `.mapt/`
is derived and disposable: delete it any time. The files are the truth.

## Use

```
pip install -e .
cd D:/shop/inventory           # the data root (any folder)
mapt server                    # http://127.0.0.1:8715
```

Try it on the demo: `cd examples/shop && mapt server`.

| Command | Does |
|---|---|
| `mapt server [--port] [--host 0.0.0.0] [--read-only]` | Index and run the web UI. `--read-only` is for a lobby screen or kiosk: browse and search only |
| `mapt find <words>` | Where is it? Prints each match with its location |
| `mapt index` | Rebuild the index and summarize |
| `mapt lint [--all]` | Print problems as `file:line code message` |

There's no login. Run it on a trusted network, or behind something like
`tailscale serve`; posts from other sites are refused.

## The web UI

- **Map**: a place's floor plan with its pins. Blue dots are things; green pins are places,
  with how many things are inside (round ones have their own map: double-click to go in).
  Everything inside a place shows up as that place's pin; search or click a thing and its
  place lights up.
- **The pane** shows whatever's selected: where it is, notes and photos, stock, and
  what's inside. **Edit** opens the form right there in the pane; **Move pin** lets you
  drag it (or click where it goes); **Put on map** places something that isn't on the map yet.
- **+ Add** (or `A`), then click the map: the form for a new thing or place opens in the
  pane, with a dashed ring where it'll go. **+ Add inside** adds to the selected place.
  While "Where" is the map you're on, the form has a **Spot** row: **Pick on map** (or
  **Change**) and click where it goes, or **Clear** to leave it off the map.
- You stay on the map: links from the lists and search open the map with that item
  selected. Something with no map above it opens in the home map's pane.
- **Filter this map** dims every pin that doesn't match (places match on what's
  inside them). `/` jumps to it, `Esc` clears the selection.
- **Things / Places**: sortable, filterable lists. **Stock**: everything with an
  amount, low ones first, with how fast it's used and when it'll run out.
- On a phone the map and the pane take turns; the bar at the bottom opens the pane.

## Files

```
mapt.yaml              optional settings
places/Shop.md         a place
places/Red Toolbox.md  a place without a map
things/Hammer.md       a thing
attachments/           floor plans and photos
```

A place:

```markdown
---
parent: "[[Shop]]"          # the place it's in (none: top level)
map: "[[shop floor.svg]]"   # optional: an image to put pins on
pos: [0.42, 0.61]           # optional: where it is on the map above it
---
Free notes. ![[photo of the room.jpg]]
```

A thing:

```markdown
---
place: "[[Red Toolbox]]"
pos: [0.3, 0.7]             # optional: only used when its place has a map
qty: 3
unit: rolls
reorder: 4                  # "time to buy more" at or below this
owner: Thad
tags: [consumable]
added: 2026-11-16
---
Blue shop towels. See also [[Paper Towels]].

## Stock
- 2026-09-01 bought 12 (0 → 12)
- 2026-10-01 14:05 used 4 (12 → 8)
- 2026-10-20 counted 3
```

- A place is a place: a building, a room, a shelf, a drawer. `map` and `pos` are both
  optional, and places nest as deep as you like. On any map, something inside a place
  without a map shows as the pin of the outermost place that is on that map.
- Names are file names, so every place and thing needs a distinct one ("Hammer (red box)").
  Links are `[[Name]]`, Obsidian style. Renaming in the UI updates every link.
- `pos` is a share of the map's width and height from its top-left corner, so pins stay
  put if you re-export the floor plan at another size.
- `qty` is what's on hand now; the `## Stock` lines are its history. The Used / Bought /
  Counted buttons write both. You can write the lines by hand too: a date, then
  `bought`, `used` or `counted` and a number. Usage per month comes from the last year of
  `used` lines plus whatever a count finds missing.
- Any other frontmatter is kept and shown as is.
- Map images can be PNG, JPEG, GIF, WebP or SVG.
- Deleting from the UI moves the file to `.trash/`.

`mapt.yaml`:

```yaml
title: Makerspace          # shown in the header
home: Shop                 # the map that opens first (default: the only top-level map)
places_dir: places
things_dir: things
attachments_dir: attachments
```

## Develop

```
pip install -e ".[dev]"
pytest
```

Same shape as grazr: a stdlib HTTP server with Jinja2 templates, ruamel.yaml for
frontmatter round-trips, and SQLite (FTS5) for the index. Leaflet 1.9.4 (BSD-2) is
bundled in `mapt/static/vendor`. See `docs/DECISIONS.md`.
