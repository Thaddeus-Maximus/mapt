"""Width and height of a map image, read from its header (no imaging library)."""
from __future__ import annotations

import re
import struct
from pathlib import Path

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp")

_UNITS = {"": 1.0, "px": 1.0, "pt": 96 / 72, "pc": 16.0, "mm": 96 / 25.4, "cm": 96 / 2.54, "in": 96.0}
_LEN = re.compile(r"^\s*([\d.]+(?:e[-+]?\d+)?)\s*([a-z]*)\s*$", re.I)


def _svg_len(v: str | None) -> float | None:
    if not v:
        return None
    m = _LEN.match(v)
    if not m or m.group(2).lower() not in _UNITS:
        return None   # `100%`, `auto`: fall back to the viewBox
    return float(m.group(1)) * _UNITS[m.group(2).lower()]


def svg_size(text: str) -> tuple[float, float] | None:
    m = re.search(r"<svg\b([^>]*)>", text, re.S)
    if not m:
        return None
    attrs = dict(re.findall(r'([\w:-]+)\s*=\s*["\']([^"\']*)["\']', m.group(1)))
    w, h = _svg_len(attrs.get("width")), _svg_len(attrs.get("height"))
    vb = [float(x) for x in re.split(r"[\s,]+", attrs.get("viewBox", "").strip()) if x] or None
    if w and h:
        return w, h
    if vb and len(vb) == 4 and vb[2] > 0 and vb[3] > 0:
        if w:
            return w, w * vb[3] / vb[2]
        if h:
            return h * vb[2] / vb[3], h
        return vb[2], vb[3]
    return None


def _jpeg(data: bytes) -> tuple[int, int] | None:
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        seg = struct.unpack(">H", data[i + 2:i + 4])[0]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        i += 2 + seg
    return None


def size(path: Path) -> tuple[float, float] | None:
    """→ (width, height) in pixels (SVG lengths in CSS pixels), or None if unreadable."""
    try:
        if path.suffix.lower() == ".svg":
            with open(path, encoding="utf-8", errors="replace") as f:
                return svg_size(f.read(64 * 1024))
        data = path.read_bytes()
    except OSError:
        return None
    try:
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            return struct.unpack(">II", data[16:24])
        if data[:6] in (b"GIF87a", b"GIF89a"):
            return struct.unpack("<HH", data[6:10])
        if data[:2] == b"\xff\xd8":
            return _jpeg(data)
        if data[:2] == b"BM":
            w, h = struct.unpack("<ii", data[18:26])
            return w, abs(h)
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            kind = data[12:16]
            if kind == b"VP8 ":
                w, h = struct.unpack("<HH", data[26:30])
                return w & 0x3FFF, h & 0x3FFF
            if kind == b"VP8L":
                b = data[21:25]
                w = 1 + (((b[1] & 0x3F) << 8) | b[0])
                h = 1 + (((b[3] & 0xF) << 10) | (b[2] << 2) | ((b[1] & 0xC0) >> 6))
                return w, h
            if kind == b"VP8X":
                w = 1 + int.from_bytes(data[24:27], "little")
                h = 1 + int.from_bytes(data[27:30], "little")
                return w, h
    except struct.error:
        return None
    return None
