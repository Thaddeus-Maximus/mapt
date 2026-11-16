"""YAML frontmatter: safe reads, ruamel round-trip writes that keep the rest of the file."""
from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.error import YAMLError
from ruamel.yaml.scalarstring import DoubleQuotedScalarString

from .paths import atomic_write

_LINK = re.compile(r"^\s*!?\[\[([^\]]+)\]\]\s*$")


@dataclass
class Split:
    yaml: str | None     # frontmatter text without the --- fences, or None
    body: str
    body_line: int       # 1-based line number of the body's first line


def split(text: str) -> Split:
    lines = text.split("\n")
    if lines and lines[0].rstrip("\r") == "---":
        for i in range(1, len(lines)):
            if lines[i].rstrip("\r") in ("---", "..."):
                return Split("\n".join(lines[1:i]), "\n".join(lines[i + 1:]), i + 2)
    return Split(None, text, 1)


def load(text: str) -> tuple[dict, Split, str | None]:
    """→ (fields, split, error). Unparseable YAML gives {} and an error message."""
    sp = split(text)
    if sp.yaml is None or not sp.yaml.strip():
        return {}, sp, None
    try:
        data = YAML(typ="safe").load(sp.yaml)
    except YAMLError as e:
        return {}, sp, str(e).splitlines()[0] if str(e) else "invalid YAML"
    if data is None:
        return {}, sp, None
    if not isinstance(data, dict):
        return {}, sp, "frontmatter is not a mapping"
    return {str(k): v for k, v in data.items()}, sp, None


def link_target(inner: str) -> str:
    """The file name a `[[inner]]` points at: no `|alias`, `#heading`, folders or `.md`."""
    t = inner.split("|", 1)[0].split("#", 1)[0].strip().replace("\\", "/").rsplit("/", 1)[-1]
    return t[:-3] if t.lower().endswith(".md") else t


def link_value(v) -> str | None:
    """`"[[Red Toolbox]]"` (or a bare `Red Toolbox`) → `Red Toolbox`."""
    if v is None:
        return None
    if isinstance(v, list):
        # Obsidian sometimes writes a single link property as a one-item list
        if len(v) != 1:
            return None
        v = v[0]
    s = str(v).strip()
    if not s:
        return None
    m = _LINK.match(s)
    if m:
        return link_target(m.group(1)) or None
    return s.split("|", 1)[0].strip() or None


def _rt() -> YAML:
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096
    y.indent(mapping=2, sequence=4, offset=2)
    return y


def _flow(v):
    """Short lists (`pos: [0.4, 0.6]`, `tags: [tool]`) are written on one line, and links
    in double quotes the way Obsidian writes them."""
    if isinstance(v, str) and v.startswith("[[") and type(v) is str:
        return DoubleQuotedScalarString(v)
    if isinstance(v, list) and not isinstance(v, CommentedSeq):
        s = CommentedSeq(v)
        s.fa.set_flow_style()
        return s
    return v


def _text(data, body: str) -> str:
    buf = io.StringIO()
    if len(data):
        _rt().dump(data, buf)
    fm = buf.getvalue()
    return f"---\n{fm}---\n{body}" if fm else body


def update(path: Path, changes: dict, remove: tuple[str, ...] = (), body: str | None = None) -> None:
    """Re-read the file and rewrite its frontmatter; the body is kept unless one is given."""
    text = path.read_text(encoding="utf-8-sig") if path.exists() else ""
    sp = split(text)
    data = _rt().load(sp.yaml) if sp.yaml and sp.yaml.strip() else None
    if not isinstance(data, CommentedMap):
        data = CommentedMap()
    for k, v in changes.items():
        data[k] = _flow(v)
    for k in remove:
        data.pop(k, None)
    if body is None:
        body = sp.body if sp.yaml is not None else text
    atomic_write(path, _text(data, body))


def dump(fields: dict, body: str = "") -> str:
    """A new file's text."""
    data = CommentedMap()
    for k, v in fields.items():
        data[k] = _flow(v)
    return _text(data, body)
