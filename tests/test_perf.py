"""Stress tests — ensure hot paths stay fast at scale.

Budgets are ~5x measured times: tight enough to catch regressions,
loose enough to not flake on CI.
"""

import time
from dataclasses import dataclass

from terminal import (
    ListState,
    ScrollState,
    box,
    hstack,
    scroll,
    table,
    table_row,
    text,
    vstack,
    zstack,
)
from terminal.buffer import Buffer, parse_line, render_diff
from terminal.components.list import list as tlist
from terminal.measure import display_width
from terminal.screen import clip, clip_and_pad, pad


@dataclass
class _N:
    key: int


def _timed(fn: object, iterations: int = 1) -> float:
    """Run fn and return elapsed seconds."""
    assert callable(fn)
    start = time.perf_counter()
    for _ in range(iterations):
        fn()
    return time.perf_counter() - start


WIDTH = 200
HEIGHT = 50


# ── clip / pad ──────────────────────────────────────────────────────


def test_clip_throughput():
    """clip() on 10k lines with ANSI + wide chars."""
    lines = [f"\033[1m{'あ' * 100}hello world\033[0m"] * 10_000
    elapsed = _timed(lambda: [clip(l, WIDTH) for l in lines])
    assert elapsed < 0.5, f"clip wide 10k took {elapsed:.3f}s"


def test_pad_throughput():
    """pad() on 10k ASCII lines."""
    lines = ["hello world"] * 10_000
    elapsed = _timed(lambda: [pad(l, WIDTH) for l in lines])
    assert elapsed < 0.01, f"pad ASCII 10k took {elapsed:.3f}s"


# ── clip_and_pad (main render loop) ────────────────────────────────


def test_clip_and_pad_ascii_already_fit():
    """Lines already at target width — should be near-instant."""
    lines = ["x" * WIDTH] * 10_000
    elapsed = _timed(lambda: [clip_and_pad(l, WIDTH) for l in lines])
    assert elapsed < 0.01, f"clip_and_pad exact-fit 10k took {elapsed:.3f}s"


def test_clip_and_pad_ansi_already_fit():
    """ANSI lines already at target width — single scan, no double pass."""
    lines = [f"\033[1m{'a' * 196}\033[0m"] * 10_000
    elapsed = _timed(lambda: [clip_and_pad(l, WIDTH) for l in lines])
    assert elapsed < 0.5, f"clip_and_pad ANSI fit 10k took {elapsed:.3f}s"


def test_clip_and_pad_needs_clip():
    """Lines wider than target — must clip."""
    lines = ["x" * 400] * 10_000
    elapsed = _timed(lambda: [clip_and_pad(l, WIDTH) for l in lines])
    assert elapsed < 0.01, f"clip_and_pad needs-clip 10k took {elapsed:.3f}s"


def test_clip_and_pad_needs_pad():
    """Short lines that need padding."""
    lines = ["hello"] * 10_000
    elapsed = _timed(lambda: [clip_and_pad(l, WIDTH) for l in lines])
    assert elapsed < 0.01, f"clip_and_pad needs-pad 10k took {elapsed:.3f}s"


# ── display_width ───────────────────────────────────────────────────


def test_display_width_wide_throughput():
    """display_width on 10k strings with ANSI + wide chars."""
    strings = [f"\033[31m{'你好' * 20}abc\033[0m"] * 10_000
    elapsed = _timed(lambda: [display_width(s) for s in strings])
    assert elapsed < 0.5, f"display_width wide 10k took {elapsed:.3f}s"


def test_display_width_ascii_throughput():
    """display_width on 100k ASCII strings — fast path."""
    strings = ["hello world this is a normal line"] * 100_000
    elapsed = _timed(lambda: [display_width(s) for s in strings])
    assert elapsed < 0.04, f"display_width ASCII 100k took {elapsed:.3f}s"


# ── render_diff ─────────────────────────────────────────────────────


def test_diff_identical_frames():
    """Diffing two identical cell buffers should be fast."""
    a = Buffer(WIDTH, HEIGHT)
    b = Buffer(WIDTH, HEIGHT)
    for i in range(HEIGHT):
        parse_line(a, i, "x" * WIDTH)
        parse_line(b, i, "x" * WIDTH)
    elapsed = _timed(lambda: render_diff(a, b), iterations=1000)
    assert elapsed < 1.0, f"diff identical 1k took {elapsed:.3f}s"


def test_diff_fully_changed():
    """Diffing two completely different cell buffers."""
    old = Buffer(WIDTH, HEIGHT)
    new = Buffer(WIDTH, HEIGHT)
    for i in range(HEIGHT):
        parse_line(old, i, "a" * WIDTH)
        parse_line(new, i, "b" * WIDTH)
    elapsed = _timed(lambda: render_diff(new, old), iterations=100)
    assert elapsed < 1.0, f"diff changed 100 took {elapsed:.3f}s"


def test_parse_line_ascii_throughput():
    """parse_line on plain ASCII lines, 1000 frames."""
    buf = Buffer(WIDTH, HEIGHT)
    lines = ["x" * WIDTH] * HEIGHT

    def run():
        for i, l in enumerate(lines):
            parse_line(buf, i, l)

    elapsed = _timed(run, iterations=1000)
    assert elapsed < 2.0, f"parse ASCII 1k frames took {elapsed:.3f}s"


def test_parse_line_ansi_throughput():
    """parse_line on ANSI-styled lines, 1000 frames."""
    buf = Buffer(WIDTH, HEIGHT)
    lines = [f"\033[1m{'a' * 196}\033[0m"] * HEIGHT

    def run():
        for i, l in enumerate(lines):
            parse_line(buf, i, l)

    elapsed = _timed(run, iterations=1000)
    assert elapsed < 5.0, f"parse ANSI 1k frames took {elapsed:.3f}s"


# ── Full component render ──────────────────────────────────────────


def test_large_vstack():
    """VStack with 1000 children, 100 renders."""
    children = [text(f"line {i}") for i in range(1000)]
    tree = vstack(*children)
    elapsed = _timed(lambda: tree.render(WIDTH, HEIGHT), iterations=100)
    assert elapsed < 0.2, f"vstack 1000 x100 took {elapsed:.3f}s"


def test_large_list():
    """List with 10k items, 10 renders."""
    state = ListState([_N(i) for i in range(10_000)])
    elapsed = _timed(
        lambda: tlist(state, lambda item, sel: text(f"item {item.key}")).render(
            WIDTH, HEIGHT
        ),
        iterations=10,
    )
    assert elapsed < 0.5, f"list 10k x10 took {elapsed:.3f}s"


def test_wide_table():
    """Table with 500 rows x 5 columns, 50 renders."""
    rows = [
        table_row(
            text(f"id-{i}"),
            text(f"name-{i}", grow=1),
            text("active" if i % 2 else "inactive"),
            text(str(i * 100)),
            text("details..."),
        )
        for i in range(500)
    ]
    tree = table(*rows)
    elapsed = _timed(lambda: tree.render(WIDTH), iterations=50)
    assert elapsed < 0.3, f"table 500x5 x50 took {elapsed:.3f}s"


def test_nested_hstack():
    """Deeply nested HStacks: 5^5 = 3125 leaf nodes, 10 renders."""

    def build(depth: int):
        if depth == 0:
            return text("leaf")
        return hstack(*[build(depth - 1) for _ in range(5)], spacing=1)

    tree = build(5)
    elapsed = _timed(lambda: tree.render(WIDTH), iterations=10)
    assert elapsed < 0.5, f"nested hstack x10 took {elapsed:.3f}s"


# ── ZStack ──────────────────────────────────────────────────────────


def test_zstack_large_overlay():
    """ZStack: full-screen ASCII base + centered overlay, 100 renders."""
    base = vstack(*[text("." * WIDTH) for _ in range(HEIGHT)])
    overlay = box(text("Alert! " * 10), padding=1)
    tree = zstack(base, overlay, justify_content="center", align_items="center")
    elapsed = _timed(lambda: tree.render(WIDTH, HEIGHT), iterations=100)
    assert elapsed < 0.06, f"zstack overlay x100 took {elapsed:.3f}s"


def test_zstack_wide_chars():
    """ZStack: wide-char base + overlay, 100 renders."""
    base = vstack(*[text("你好世界" * 25) for _ in range(HEIGHT)])
    overlay = text("ALERT")
    tree = zstack(base, overlay, justify_content="center", align_items="center")
    elapsed = _timed(lambda: tree.render(WIDTH, HEIGHT), iterations=100)
    assert elapsed < 0.5, f"zstack wide x100 took {elapsed:.3f}s"


# ── Scroll ──────────────────────────────────────────────────────────


def test_scroll_large_content():
    """Scroll: 10k children at offset 5000, viewport 50, 100 renders."""
    state = ScrollState()
    state.offset = 5000
    children = [text(f"line {i}") for i in range(10_000)]
    tree = scroll(*children, state=state)
    elapsed = _timed(lambda: tree.render(WIDTH, HEIGHT), iterations=100)
    assert elapsed < 0.01, f"scroll 10k x100 took {elapsed:.3f}s"


# ── Realistic full app frame ────────────────────────────────────────


def test_realistic_frame():
    """Full app frame: header + 1000-item list + footer, 100 renders."""
    items = ListState([_N(i) for i in range(1000)])

    def build():
        header = hstack(
            text("\033[1m✦ APP\033[0m"),
            text("\033[2m100/1000\033[0m"),
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

    elapsed = _timed(lambda: build().render(WIDTH, HEIGHT), iterations=100)
    assert elapsed < 0.5, f"realistic frame x100 took {elapsed:.3f}s"
