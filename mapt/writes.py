"""Web-UI write actions. Each is a plain file edit, written atomically."""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

from . import frontmatter, stock
from .frontmatter import link_target, load as load_fm
from .paths import atomic_write, iter_markdown

_BAD_NAME = re.compile(r'[\\/:*?"<>|#^\[\]]')


class WriteError(ValueError):
    pass


def safe_name(name: str) -> str:
    name = " ".join((name or "").split()).strip(". ")
    if not name or _BAD_NAME.search(name):
        raise WriteError(f"{name!r} can't be a file name (avoid \\ / : * ? \" < > | # ^ [ ])")
    return name


def under(root: Path, relpath: str) -> Path:
    """`relpath` inside the data root, or WriteError."""
    p = (root / relpath).resolve()
    if p != root and root not in p.parents:
        raise WriteError("path is outside the data root")
    return p


def link(name: str) -> str:
    return f"[[{name}]]"


def new_item(root: Path, folder: str, name: str, fields: dict, body: str = "") -> str:
    """Write `<folder>/<name>.md`; → its root-relative path."""
    name = safe_name(name)
    path = root / folder / f"{name}.md"
    if path.exists():
        raise WriteError(f"{folder}/{name}.md already exists")
    body = body.replace("\r\n", "\n").strip("\n")
    atomic_write(path, frontmatter.dump({k: v for k, v in fields.items() if v not in (None, "", [])},
                                        body + "\n" if body else ""))
    return path.relative_to(root).as_posix()


def set_pos(path: Path, pos: tuple[float, float] | None) -> None:
    if pos is None:
        frontmatter.update(path, {}, ("pos",))
    else:
        x, y = (round(min(max(float(v), 0.0), 1.0), 4) for v in pos)
        frontmatter.update(path, {"pos": [x, y]})


def number(text) -> float | int | None:
    t = str(text if text is not None else "").strip()
    if not t:
        return None
    try:
        return stock.num(float(t))
    except ValueError:
        raise WriteError(f"{t!r} isn't a number")


def record(path: Path, kind: str, n, now: datetime | None = None) -> None:
    """A stock change: update `qty:` and add a dated line under `## Stock`."""
    if kind not in stock.WRITE_VERB:
        raise WriteError(f"unknown stock change {kind!r}")
    n = number(n)
    if n is None or n < 0:
        raise WriteError("how many?")
    text = path.read_text(encoding="utf-8-sig")
    fields, sp, err = load_fm(text)
    if err:
        raise WriteError(f"{path.name}: {err}")
    before = fields.get("qty")
    before = float(before) if isinstance(before, (int, float)) and not isinstance(before, bool) else None
    after = stock.apply(before, kind, float(n))
    body = stock.append(sp.body, stock.line(kind, n, before, after, now or datetime.now()))
    frontmatter.update(path, {"qty": stock.num(after)} if after is not None else {}, body=body)


def edit_item(path: Path, changes: dict, remove: list[str], body: str | None) -> None:
    frontmatter.update(path, changes, tuple(remove),
                       body=None if body is None else body.replace("\r\n", "\n"))


def save_raw(path: Path, text: str) -> None:
    atomic_write(path, text.replace("\r\n", "\n"))


_WIKILINK = re.compile(r"\[\[([^\]\n]+)\]\]")


def relink(text: str, old: str, new: str) -> tuple[str, int]:
    """Point every `[[link]]` to `old` at `new`, keeping `#heading` and `|alias`."""
    n = 0

    def sub(m):
        nonlocal n
        inner = m.group(1)
        if link_target(inner).casefold() != old.casefold():
            return m.group(0)
        n += 1
        cut = min((i for i in (inner.find("#"), inner.find("|")) if i >= 0), default=len(inner))
        return f"[[{new}{inner[cut:]}]]"

    return _WIKILINK.sub(sub, text), n


def rename(root: Path, path: str, new: str, other_paths: set[str]) -> tuple[str, int]:
    """Rename the file at `path` to `new` and rewrite links to it everywhere.
    `other_paths` are files that already use the new name. → (new path, files changed)."""
    new = safe_name(new)
    src = under(root, path)
    old = src.stem
    dst = src.with_name(f"{new}.md")
    if (dst.exists() and not dst.samefile(src)) or other_paths:
        raise WriteError(f"something called {new!r} already exists")
    files = 0
    for p in iter_markdown(root):
        text = p.read_text(encoding="utf-8-sig")
        out, n = relink(text, old, new)
        if n:
            atomic_write(p, out)
            files += 1
    if dst != src:
        src.rename(dst)   # also a case-only rename on Windows
    return dst.relative_to(root).as_posix(), files


def trash(root: Path, path: str) -> str:
    """Move a file into `.trash/` under the root, keeping its folders. → new path."""
    src = under(root, path)
    dst = root / ".trash" / path
    n = 2
    while dst.exists():
        dst = root / ".trash" / Path(path).with_name(f"{Path(path).stem} {n}{Path(path).suffix}")
        n += 1
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dst)
    return dst.relative_to(root).as_posix()


IMAGE_UPLOAD = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".heic")


def save_upload(root: Path, folder: str, filename: str, data: bytes, now: datetime | None = None) -> str:
    """Save an image to the attachments folder; → the file name to embed as ![[name]]."""
    now = now or datetime.now()
    ext = Path(filename or "").suffix.lower() or ".png"
    if ext not in IMAGE_UPLOAD:
        raise WriteError(f"not an image: {filename}")
    if not data:
        raise WriteError("the file is empty")
    stem = Path(filename).stem if filename and Path(filename).stem not in ("image", "blob") else \
        f"Pasted image {now:%Y%m%d%H%M%S}"
    stem = _BAD_NAME.sub("-", stem).strip() or "image"
    d = root / folder
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{stem}{ext}"
    n = 2
    while path.exists():
        path = d / f"{stem} {n}{ext}"
        n += 1
    path.write_bytes(data)
    return path.name


def today() -> date:
    return date.today()
