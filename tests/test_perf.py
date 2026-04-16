"""Perf tests — guard the C render pipeline performance.

Each test guards a specific workload through the public contract:
render_to_buffer + Buffer.diff.

Budgets are ~2× measured median on Apple M-series.
"""

import time
from dataclasses import dataclass

from ttyz import (
    Buffer,
    ListState,
    Node,
    hstack,
    render_to_buffer,
    text,
    vstack,
)
from ttyz import (
    list as tlist,
)


@dataclass
class _N:
    key: int


def _timed(fn: object, iterations: int = 1) -> float:
    assert callable(fn)
    start = time.perf_counter()
    for _ in range(iterations):
        fn()
    return time.perf_counter() - start


WIDTH = 200
HEIGHT = 50


# ── cell buffer: parse_line ───────────────────────────────────────


def test_parse_line_c_ascii():
    """Guard: parse_line C ASCII fast path — direct cell fill."""
    buf = Buffer(WIDTH, HEIGHT)
    lines = ["x" * WIDTH] * HEIGHT

    def run():
        for i, l in enumerate(lines):
            buf.parse_line(i, l)

    elapsed = _timed(run, iterations=1000)
    assert elapsed < 0.02, f"parse ASCII 1k frames took {elapsed:.3f}s"


def test_parse_line_c_ansi():
    """Guard: parse_line C ANSI SGR parsing performance."""
    buf = Buffer(WIDTH, HEIGHT)
    lines = [f"\033[1m{'a' * 196}\033[0m"] * HEIGHT

    def run():
        for i, l in enumerate(lines):
            buf.parse_line(i, l)

    elapsed = _timed(run, iterations=1000)
    assert elapsed < 0.03, f"parse ANSI 1k frames took {elapsed:.3f}s"


# ── Buffer.diff ──────────────────────────────────────────────────────


def test_diff_full_frame():
    """Guard: diff performance on fully changed frames."""
    old = Buffer(WIDTH, HEIGHT)
    new = Buffer(WIDTH, HEIGHT)
    for i in range(HEIGHT):
        old.parse_line(i, "a" * WIDTH)
        new.parse_line(i, "b" * WIDTH)
    elapsed = _timed(lambda: new.diff(old), iterations=100)
    assert elapsed < 0.008, f"diff changed 100 took {elapsed:.3f}s"


def test_diff_identical_emits_nothing():
    """Identical frames must produce zero output bytes."""
    a = Buffer(WIDTH, HEIGHT)
    b = Buffer(WIDTH, HEIGHT)
    for i in range(HEIGHT):
        a.parse_line(i, "x" * WIDTH)
        b.parse_line(i, "x" * WIDTH)
    assert a.diff(b) == ""


def test_diff_single_cell_output_small():
    """Changing one cell should emit far less than a full line."""
    a = Buffer(WIDTH, HEIGHT)
    b = Buffer(WIDTH, HEIGHT)
    for i in range(HEIGHT):
        a.parse_line(i, "x" * WIDTH)
        b.parse_line(i, "x" * WIDTH)
    b.parse_line(0, "y" + "x" * (WIDTH - 1))
    out = b.diff(a)
    assert len(out) < 20, f"single cell diff was {len(out)} bytes"


def test_diff_one_line_output_bounded():
    """Changing one full line should emit roughly one line of output."""
    a = Buffer(WIDTH, HEIGHT)
    b = Buffer(WIDTH, HEIGHT)
    for i in range(HEIGHT):
        a.parse_line(i, "x" * WIDTH)
        b.parse_line(i, "x" * WIDTH)
    b.parse_line(0, "z" * WIDTH)
    out = b.diff(a)
    assert len(out) < WIDTH + 50, f"one-line diff was {len(out)} bytes"


# ── render_to_buffer ─────────────────────────────────────────────────


def test_render_nested_hstack():
    """Guard: deeply nested fixed-width hstacks (3125 leaves)."""

    def build(depth: int) -> Node:
        if depth == 0:
            return text("leaf")
        return hstack(*[build(depth - 1) for _ in range(5)], spacing=1)

    tree = build(5)

    def run():
        buf = Buffer(WIDTH, HEIGHT)
        render_to_buffer(tree, buf)

    elapsed = _timed(run, iterations=10)
    assert elapsed < 0.016, f"nested hstack x10 took {elapsed:.3f}s"


def test_render_hstack_flex():
    """Guard: 200-row × 10-col hstack with flex grow."""
    rows = [
        hstack(
            text(f"c0-{i}"),
            text(f"c1-{i}", grow=1),
            text(f"c2-{i}"),
            text(f"c3-{i}"),
            text(f"c4-{i}", grow=1),
            text(f"c5-{i}"),
            text(f"c6-{i}"),
            text(f"c7-{i}"),
            text(f"c8-{i}"),
            text(f"c9-{i}"),
            spacing=1,
        )
        for i in range(200)
    ]
    tree = vstack(*rows)

    def run():
        buf = Buffer(WIDTH, HEIGHT * 4)
        render_to_buffer(tree, buf)

    elapsed = _timed(run, iterations=50)
    assert elapsed < 0.04, f"hstack flex x50 took {elapsed:.3f}s"


# ── Full pipeline: build → render_to_buffer → diff ───────────────────


def test_pipeline_cold():
    """Guard: cold pipeline — rebuild entire tree each frame."""
    items = ListState([_N(i) for i in range(1000)])

    def build_cold() -> Node:
        header = hstack(
            text("\033[1m✦ APP\033[0m"),
            text(f"\033[2m{items.cursor}/1000\033[0m"),
            justify_content="between",
            spacing=1,
        )
        body = tlist(
            items,
            lambda item, sel: hstack(
                text("▸ " if sel else "  "),
                text(f"Item {item.key}", grow=1, truncation="tail"),
                text("✓" if item.key % 3 == 0 else " "),
            ),
        )
        footer = hstack(
            text("\033[2m[j/k] move\033[0m"),
            text("\033[2m[q] quit\033[0m"),
            spacing=2,
        )
        return vstack(header, body, footer, spacing=1)

    prev = Buffer(WIDTH, HEIGHT)
    render_to_buffer(build_cold(), prev)

    def run():
        nonlocal prev
        for _ in range(100):
            items.move(1)
            buf = Buffer(WIDTH, HEIGHT)
            render_to_buffer(build_cold(), buf)
            buf.diff(prev)
            prev = buf

    elapsed = _timed(run)
    assert elapsed < 0.06, f"cold pipeline 100 took {elapsed:.3f}s"


def test_pipeline_warm():
    """Guard: warm pipeline — persistent list with item cache."""
    items = ListState([_N(i) for i in range(1000)])
    body = tlist(
        items,
        lambda item, sel: hstack(
            text("▸ " if sel else "  "),
            text(f"Item {item.key}", grow=1, truncation="tail"),
            text("✓" if item.key % 3 == 0 else " "),
        ),
    )
    footer = hstack(
        text("\033[2m[j/k] move\033[0m"),
        text("\033[2m[q] quit\033[0m"),
        spacing=2,
    )

    def build_warm() -> Node:
        header = hstack(
            text("\033[1m✦ APP\033[0m"),
            text(f"\033[2m{items.cursor}/1000\033[0m"),
            justify_content="between",
            spacing=1,
        )
        return vstack(header, body, footer, spacing=1)

    prev = Buffer(WIDTH, HEIGHT)
    render_to_buffer(build_warm(), prev)

    def run():
        nonlocal prev
        for _ in range(100):
            items.move(1)
            buf = Buffer(WIDTH, HEIGHT)
            render_to_buffer(build_warm(), buf)
            buf.diff(prev)
            prev = buf

    elapsed = _timed(run)
    assert elapsed < 0.015, f"warm pipeline 100 took {elapsed:.3f}s"
