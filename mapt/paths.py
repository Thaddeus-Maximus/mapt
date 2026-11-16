"""The data root is the current directory; files are keyed by root-relative paths."""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

STATE_DIR = ".mapt"


def data_root(path: str | Path | None = None) -> Path:
    return Path(path or os.getcwd()).resolve()


def state_dir(root: Path) -> Path:
    d = root / STATE_DIR
    d.mkdir(exist_ok=True)
    gi = d / ".gitignore"
    if not gi.exists():
        gi.write_text("*\n", encoding="utf-8")
    return d


def rel(root: Path, path: Path) -> str:
    """Root-relative path with forward slashes; this is a file's key everywhere."""
    return path.relative_to(root).as_posix()


# a sync tool's copy of a file both sides changed (Syncthing, Dropbox, OneDrive)
CONFLICT = re.compile(r"\.sync-conflict-\d{8}-\d{6}|\(conflicted copy|\.conflict\.md$", re.I)


def iter_markdown(root: Path, conflicts: list[Path] | None = None):
    """Every .md file under the root, skipping dot-folders (.mapt, .obsidian, .trash) and
    sync conflict copies (those go in `conflicts`)."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for name in sorted(filenames):
            if name.lower().endswith(".md"):
                if CONFLICT.search(name):
                    if conflicts is not None:
                        conflicts.append(Path(dirpath) / name)
                    continue
                yield Path(dirpath) / name


def atomic_write(path: Path, text: str) -> None:
    """Write to a temp file in the same folder, then rename over the target."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".mapt-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
