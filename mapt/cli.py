"""`mapt <command>`, run from inside the data root."""
from __future__ import annotations

import argparse
import sys

from . import __version__
from .paths import data_root


def _index(args):
    from .index import Index
    return Index(data_root(args.root))


def cmd_index(args):
    idx = _index(args)
    print(idx.summary_text())
    if idx.warnings():
        print("run `mapt lint` for details")
    return 0


def cmd_lint(args):
    rows = _index(args).warnings(include_info=args.all)
    for w in rows:
        print(f"{w['path']}:{w['line']} {w['code']} {w['message']}")
    return 1 if any(w["severity"] == "error" for w in rows) else 0


def cmd_find(args):
    idx = _index(args)
    import json
    rows = idx.search(" ".join(args.text), limit=args.limit)
    for r in rows:
        where = " › ".join(json.loads(r["chain"])) or "(nowhere)"
        qty = f"  ×{r['qty']:g}" if r["qty"] is not None else ""
        print(f"{r['id']}{qty}  —  {where}")
    return 0 if rows else 1


def cmd_server(args):
    from .server import run
    run(data_root(args.root), host=args.host, port=args.port, readonly=args.read_only)
    return 0


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(prog="mapt", description="Where everything is, in Markdown.")
    ap.add_argument("--version", action="version", version=f"mapt {__version__}")
    ap.add_argument("--root", help="data root (default: current directory)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("server", help="index, then run the web UI")
    p.add_argument("--port", type=int, default=8715)
    p.add_argument("--host", default="127.0.0.1", help="0.0.0.0 to serve your network")
    p.add_argument("--read-only", action="store_true", help="browse and search only (a lobby screen)")
    p.set_defaults(fn=cmd_server)
    sub.add_parser("index", help="rebuild the index and summarize warnings").set_defaults(fn=cmd_index)
    p = sub.add_parser("lint", help="print problems as file:line code message")
    p.add_argument("--all", action="store_true", help="include informational notes")
    p.set_defaults(fn=cmd_lint)
    p = sub.add_parser("find", help="where is it? search names and notes")
    p.add_argument("text", nargs="+")
    p.add_argument("-n", "--limit", type=int, default=20)
    p.set_defaults(fn=cmd_find)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
