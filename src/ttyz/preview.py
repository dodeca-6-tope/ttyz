"""Render a ttyz node tree to stdout — a quick iteration tool.

    python -m ttyz.preview "vstack(text('hi'), box(text('world')))"
    python -m ttyz.preview "text('long' * 10)" --width 20
    python -m ttyz.preview -  # expression from stdin (may span lines)

Every `ttyz` public symbol is in scope, plus `t` and `ttyz` as module
aliases.  The input must be a single Python expression that evaluates
to a Node — line breaks are fine inside brackets.
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback

import ttyz
from ttyz import Buffer, render_to_buffer


def main() -> int:
    p = argparse.ArgumentParser(
        prog="python -m ttyz.preview",
        description="Render a ttyz node tree to stdout.",
    )
    p.add_argument(
        "expr", help="Python expression evaluating to a Node ('-' reads stdin)"
    )
    p.add_argument("--width", "-w", type=int, help="default: terminal width, fallback 80")
    p.add_argument("--height", type=int, help="default: content's natural height")
    args = p.parse_args()

    code = sys.stdin.read() if args.expr == "-" else args.expr
    try:
        width = args.width or os.get_terminal_size().columns
    except OSError:
        width = 80

    ns = {n: getattr(ttyz, n) for n in ttyz.__all__} | {"t": ttyz, "ttyz": ttyz}

    try:
        node = eval(code, ns)
    except Exception:
        traceback.print_exc()
        return 1

    buf = Buffer(width, args.height or 1000)
    rows = render_to_buffer(node, buf, args.height or -1)
    sys.stdout.write("\n".join(buf.dump().split("\n")[:rows]) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
