# Decisions

Made 2026-11-16, starting the Python rewrite (the earlier Firebase version is in git history).

- **D-1** Two folders, `places/` and `things/`, with flat names. The folder says what a file is; frontmatter links say where it is. Moving something is a one-line edit, not a file move, and Obsidian links keep working.
- **D-2** There is no container or "virtual place" kind. A place's `map` and `pos` are both optional: a toolbox is a place without a map, and giving it a map just makes it a place you can open. (Revised 2026-11-16; an earlier draft had a separate container kind in the UI.)
- **D-3** A thing's place is `place:`; a place's is `parent:`. Either key is read on either kind, so a hand-edited file isn't wrong for using the other one.
- **D-4** `pos: [x, y]` is a share (0–1) of the map's width and height from its top-left corner, not pixels, so a re-exported or higher-resolution floor plan keeps its pins.
- **D-5** Something inside a place (however deeply) shows on a map as the outermost place between it and that map. Its own `pos` is ignored there, with an info note.
- **D-6** Names are unique across places and things, compared without case, because a `[[link]]` names a file. A second file with the same name is ignored with an error, and the UI refuses to make one.
- **D-7** Stock history is dated list lines under `## Stock` in the thing's own file, not a separate log. `qty:` stays the amount on hand; the lines are the evidence. Typing a new amount in the edit form is recorded as a count.
- **D-8** Use rate = `used` amounts plus any shortfall a count finds, over the last 365 days, divided by the days since the first event in that window (at least 7).
- **D-9** No login (grazr's model): local or tailnet use. `--read-only` covers the lobby screen. Cross-site posts are refused.
- **D-10** Moving something to another place in the edit form drops its `pos`, because the old spot was on another map.
- **D-11** The index is refreshed on every request (a stat of each file; only changed files are re-read), so edits made in Obsidian show up on the next page load.
- **D-12** The map and pane are the main view: adding and editing happen in the pane, which posts with `X-Mapt: pane` and gets back `{"go": url}` (or `{"error"}`) instead of a redirect, so the map keeps its zoom and only the pins are re-fetched. `/new` and `/edit/<name>` still work as pages without JavaScript. Items with no map above them open in the home map's pane rather than a page of their own.
