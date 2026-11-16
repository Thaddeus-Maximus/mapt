"""Minimal Markdown → HTML for notes: wikilinks, embeds, tags, lists, headings."""
from __future__ import annotations

import re
from html import escape
from urllib.parse import quote

from markupsafe import Markup

from .frontmatter import link_target
from .imgsize import IMAGE_EXT

HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
LIST = re.compile(r"^(\s*)(?:[-*+]|\d+[.)])\s+(?:\[( |x|X)\]\s+)?(.*)$")

_INLINE = re.compile(
    r"(?P<embed>!\[\[(?P<et>[^\]\n]+)\]\])"
    r"|(?P<mdimg>!\[[^\]\n]*\]\((?P<mi>[^)\n]+)\))"
    r"|(?P<link>\[\[(?P<lt>[^\]\n]+)\]\])"
    r"|(?P<mdlink>\[(?P<mlt>[^\]\n]+)\]\((?P<mlu>[^)\s]+)\))"
    r"|(?P<code>`[^`\n]+`)"
    r"|(?P<bold>\*\*[^*\n]+\*\*)"
    r"|(?P<em>(?<![\w*])\*[^*\s][^*\n]*\*(?![\w*]))"
    r"|(?P<url>\bhttps?://[^\s<>\]]+)"
    r"|(?P<tag>(?:(?<=\s)|^)#[^\s#.,;:!?()\[\]{}\"'`]*[^\W\d_][^\s#.,;:!?()\[\]{}\"'`]*)"
)


class Renderer:
    """`link(target, label) → html` renders a wikilink; `image_url(name)` an embed."""

    def __init__(self, link, image_url):
        self.link = link
        self.image_url = image_url

    def inline(self, text: str) -> Markup:
        out = []
        pos = 0
        for m in _INLINE.finditer(text):
            out.append(escape(text[pos:m.start()]))
            pos = m.end()
            if m.group("embed"):
                t = m.group("et").split("|", 1)[0].strip()
                if t.lower().endswith(IMAGE_EXT):
                    u = escape(self.image_url(t))
                    out.append(f'<a href="{u}" target="_blank"><img class="embed" src="{u}" alt="{escape(t)}" loading="lazy"></a>')
                else:
                    out.append(self.link(link_target(t), link_target(t)))
            elif m.group("mdimg"):
                src = m.group("mi").strip("<> ")
                url = src if src.startswith(("http://", "https://")) else self.image_url(src)
                out.append(f'<img class="embed" src="{escape(url)}" alt="" loading="lazy">')
            elif m.group("link"):
                inner = m.group("lt")
                label = inner.split("|", 1)[1] if "|" in inner else link_target(inner)
                out.append(self.link(link_target(inner), label))
            elif m.group("mdlink"):
                u = m.group("mlu")
                if u.lower().startswith("javascript:"):
                    u = "#"
                out.append(f'<a href="{escape(u)}">{escape(m.group("mlt"))}</a>')
            elif m.group("code"):
                out.append(f"<code>{escape(m.group('code')[1:-1])}</code>")
            elif m.group("bold"):
                out.append(f"<strong>{escape(m.group('bold')[2:-2])}</strong>")
            elif m.group("em"):
                out.append(f"<em>{escape(m.group('em')[1:-1])}</em>")
            elif m.group("url"):
                u = m.group("url")
                out.append(f'<a href="{escape(u)}">{escape(u)}</a>')
            elif m.group("tag"):
                t = m.group("tag")[1:]
                out.append(f'<a class="tag" href="/things?tag={quote(t)}">#{escape(t)}</a>')
        out.append(escape(text[pos:]))
        return Markup("".join(out))

    def document(self, text: str, skip_stock: bool = False) -> Markup:
        """Notes as HTML. `skip_stock` leaves out the `## Stock` section (shown as a table)."""
        out = []
        in_code = False
        skipping = 0
        for i, line in enumerate(text.split("\n"), 1):
            line = line.rstrip("\r")
            if line.strip().startswith(("```", "~~~")) and not skipping:
                out.append("</pre>" if in_code else "<pre>")
                in_code = not in_code
                continue
            if in_code:
                out.append(escape(line) + "\n")
                continue
            h = HEADING.match(line)
            if h and skipping and len(h.group(1)) <= skipping:
                skipping = 0
            if skipping:
                continue
            if not line.strip():
                continue
            if h:
                n = len(h.group(1))
                if skip_stock and h.group(2).strip().lower() in ("stock", "stock log", "inventory"):
                    skipping = n
                    continue
                out.append(f'<h{min(n + 2, 6)}>{self.inline(h.group(2))}</h{min(n + 2, 6)}>')
                continue
            lm = LIST.match(line)
            if lm:
                depth = len(lm.group(1).expandtabs(4)) // 2
                box = ""
                if lm.group(2) is not None:
                    box = "☑ " if lm.group(2).lower() == "x" else "☐ "
                out.append(f'<div class="li" style="--depth:{depth}">{box}{self.inline(lm.group(3))}</div>')
            else:
                out.append(f"<p>{self.inline(line.strip())}</p>")
        if in_code:
            out.append("</pre>")
        return Markup("\n".join(out))


def first_image(text: str) -> str | None:
    for m in re.finditer(r"!\[\[([^\]\n|]+)", text or ""):
        t = m.group(1).strip()
        if t.lower().endswith(IMAGE_EXT):
            return t
    return None
