"""Perf tests — each timing test guards one specific optimisation.

If a test fails, its docstring names the exact optimisation that regressed.

Budgets are ~2× measured median on Apple M-series (~3× for sub-ms
measurements where variance is highest).
"""

import time
from dataclasses import dataclass

from terminal import (
    ListState,
    Renderable,
    hstack,
    text,
    vstack,
)
from terminal.buffer import Buffer, parse_line, render_diff
from terminal.components.list import list as tlist
from terminal.measure import display_width
from terminal.screen import clip_and_pad


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


# ── clip_and_pad ──────────────────────────────────────────────────


def test_clip_and_pad_ascii():
    """Guard: clip_and_pad ASCII fast path — direct slice vs _clip_scan.

    Optimisation in screen.py: `"\\033" not in line and line.isascii()`
    bypasses the character-by-character ANSI scan.  ~177× impact.
    """
    lines = ["x" * WIDTH] * 10_000
    elapsed = _timed(lambda: [clip_and_pad(l, WIDTH) for l in lines])
    assert elapsed < 0.002, f"clip_and_pad ASCII 10k took {elapsed:.3f}s"


def test_clip_and_pad_ansi():
    """Regression guard: _clip_scan ANSI parse performance.

    Python _escape_end is the minimal implementation (no bolt-on to disable).
    Disabling C skip_escape has no effect — this path is pure Python.
    """
    lines = [f"\033[1m{'a' * 196}\033[0m"] * 10_000
    elapsed = _timed(lambda: [clip_and_pad(l, WIDTH) for l in lines])
    assert elapsed < 0.28, f"clip_and_pad ANSI 10k took {elapsed:.3f}s"


# ── display_width ─────────────────────────────────────────────────


def test_display_width_lru_cache():
    """Guard: LRU cache for repeated non-ASCII display_width calls.

    Optimisation in measure.py: lru_cache(4096) wrapping c_display_width
    for strings < 512 chars.  ~11× impact for repeated wide/ANSI strings.
    """
    strings = [f"\033[31m{'你好' * 20}abc\033[0m"] * 10_000
    elapsed = _timed(lambda: [display_width(s) for s in strings])
    assert elapsed < 0.0015, f"display_width cache 10k took {elapsed:.3f}s"


# ── cell buffer: parse_line ───────────────────────────────────────


def test_parse_line_c_ascii():
    """Guard: parse_line C ASCII fast path — direct cell fill.

    Optimisation in cbuf.c: is_plain_ascii() gates a loop that copies
    ASCII bytes directly into cells, skipping the ANSI state machine.
    """
    buf = Buffer(WIDTH, HEIGHT)
    lines = ["x" * WIDTH] * HEIGHT

    def run():
        for i, l in enumerate(lines):
            parse_line(buf, i, l)

    elapsed = _timed(run, iterations=1000)
    assert elapsed < 0.008, f"parse ASCII 1k frames took {elapsed:.3f}s"


def test_parse_line_c_ansi():
    """Regression guard: parse_line C ANSI SGR parsing performance.

    Disabling cwidth ASCII shortcut only adds ~20% — not enough to
    blow budget without flaking.  Guards overall ANSI parse speed.
    """
    buf = Buffer(WIDTH, HEIGHT)
    lines = [f"\033[1m{'a' * 196}\033[0m"] * HEIGHT

    def run():
        for i, l in enumerate(lines):
            parse_line(buf, i, l)

    elapsed = _timed(run, iterations=1000)
    assert elapsed < 0.03, f"parse ANSI 1k frames took {elapsed:.3f}s"


# ── cell buffer: render_diff ──────────────────────────────────────


def test_diff_full_frame():
    """Regression guard: render_diff dirty-run coalescing.

    Guards cbuf.c run grouping for changed frames.  Cannot disable from Python.
    """
    old = Buffer(WIDTH, HEIGHT)
    new = Buffer(WIDTH, HEIGHT)
    for i in range(HEIGHT):
        parse_line(old, i, "a" * WIDTH)
        parse_line(new, i, "b" * WIDTH)
    elapsed = _timed(lambda: render_diff(new, old), iterations=100)
    assert elapsed < 0.008, f"diff changed 100 took {elapsed:.3f}s"


# ── cell buffer: output size (correctness) ────────────────────────


def test_diff_identical_emits_nothing():
    """Identical frames must produce zero output bytes."""
    a = Buffer(WIDTH, HEIGHT)
    b = Buffer(WIDTH, HEIGHT)
    for i in range(HEIGHT):
        parse_line(a, i, "x" * WIDTH)
        parse_line(b, i, "x" * WIDTH)
    assert render_diff(a, b) == ""


def test_diff_single_cell_output_small():
    """Changing one cell should emit far less than a full line."""
    a = Buffer(WIDTH, HEIGHT)
    b = Buffer(WIDTH, HEIGHT)
    for i in range(HEIGHT):
        parse_line(a, i, "x" * WIDTH)
        parse_line(b, i, "x" * WIDTH)
    parse_line(b, 0, "y" + "x" * (WIDTH - 1))
    out = render_diff(b, a)
    assert len(out) < 20, f"single cell diff was {len(out)} bytes"


def test_diff_one_line_output_bounded():
    """Changing one full line should emit roughly one line of output."""
    a = Buffer(WIDTH, HEIGHT)
    b = Buffer(WIDTH, HEIGHT)
    for i in range(HEIGHT):
        parse_line(a, i, "x" * WIDTH)
        parse_line(b, i, "x" * WIDTH)
    parse_line(b, 0, "z" * WIDTH)
    out = render_diff(b, a)
    assert len(out) < WIDTH + 50, f"one-line diff was {len(out)} bytes"


# ── hstack ────────────────────────────────────────────────────────


def test_hstack_flat_collapse():
    """Guard: hstack Tier 1 flat path — _try_flatten + C render_flat_line.

    Optimisation in hstack.py + cbuf.c: nested fixed-width hstacks are
    collapsed into flat offset arrays and rendered with ASCII memcpy.
    ~29× impact at depth 5.  Validated by monkeypatching _try_flatten
    to return None.
    """

    def build(depth: int):
        if depth == 0:
            return text("leaf")
        return hstack(*[build(depth - 1) for _ in range(5)], spacing=1)

    tree = build(5)
    elapsed = _timed(lambda: tree.render(WIDTH), iterations=10)
    assert elapsed < 0.001, f"nested hstack x10 took {elapsed:.3f}s"


def test_hstack_c_flex():
    """Regression guard: hstack flex render pipeline.

    Disabling C ASCII memcpy in hstack_join_row adds ~24%, disabling
    C resolve_col_widths adds ~41% — neither enough to blow budget
    without flaking.  Guards overall flex hstack speed.
    """
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
    elapsed = _timed(lambda: tree.render(WIDTH, HEIGHT * 4), iterations=50)
    assert elapsed < 0.03, f"hstack grow 200x10 x50 took {elapsed:.3f}s"


# ── list component ────────────────────────────────────────────────


def test_list_item_cache():
    """Guard: list component per-item render cache.

    Optimisation in list.py: dict cache keyed by item.key → (sel, width,
    rendered lines).  Unchanged items return cached output.  ~12× impact.
    """
    state = ListState([_N(i) for i in range(1000)])

    def render_item(item: _N, sel: bool) -> Renderable:
        return hstack(
            text("▸ " if sel else "  "),
            text(f"Item {item.key}", grow=1, truncation="tail"),
            text("✓" if item.key % 3 == 0 else " "),
        )

    body = tlist(state, render_item)
    body.render(WIDTH, HEIGHT)  # prime

    def scroll_run():
        for _ in range(100):
            state.move(1)
            body.render(WIDTH, HEIGHT)

    elapsed = _timed(scroll_run)
    assert elapsed < 0.004, f"list scroll cached 100 took {elapsed:.3f}s"


# ── full pipeline (build → render → parse → diff) ────────────────
#
# Integration tests — guard the combined effect of all optimisations
# through the real render loop.  Cold = rebuild every frame.
# Warm = persistent list body so item cache stays hot.


def _make_pipeline_app(items: ListState[_N]) -> tuple[Renderable, Renderable]:
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
    return body, footer


def test_pipeline_cold():
    """Guard: overall cold pipeline — rebuild everything each frame."""
    items = ListState([_N(i) for i in range(1000)])

    def build_cold() -> list[str]:
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
            text("\033[2m[j/k] move\033[0m"), text("\033[2m[q] quit\033[0m"), spacing=2
        )
        return vstack(header, body, footer, spacing=1).render(WIDTH, HEIGHT)

    prev = Buffer(WIDTH, HEIGHT)
    for i, l in enumerate(build_cold()[:HEIGHT]):
        parse_line(prev, i, l)

    def run():
        nonlocal prev
        for _ in range(100):
            items.move(1)
            lines = build_cold()
            buf = Buffer(WIDTH, HEIGHT)
            for i, l in enumerate(lines[:HEIGHT]):
                parse_line(buf, i, l)
            render_diff(buf, prev)
            prev = buf

    elapsed = _timed(run)
    assert elapsed < 0.04, f"cold pipeline 100 took {elapsed:.3f}s"


def test_pipeline_warm():
    """Guard: warm pipeline — persistent list body with item cache."""
    items = ListState([_N(i) for i in range(1000)])
    body, footer = _make_pipeline_app(items)

    def build_warm() -> list[str]:
        header = hstack(
            text("\033[1m✦ APP\033[0m"),
            text(f"\033[2m{items.cursor}/1000\033[0m"),
            justify_content="between",
            spacing=1,
        )
        return vstack(header, body, footer, spacing=1).render(WIDTH, HEIGHT)

    build_warm()  # prime cache
    prev = Buffer(WIDTH, HEIGHT)
    for i, l in enumerate(build_warm()[:HEIGHT]):
        parse_line(prev, i, l)

    def run():
        nonlocal prev
        for _ in range(100):
            items.move(1)
            lines = build_warm()
            buf = Buffer(WIDTH, HEIGHT)
            for i, l in enumerate(lines[:HEIGHT]):
                parse_line(buf, i, l)
            render_diff(buf, prev)
            prev = buf

    elapsed = _timed(run)
    assert elapsed < 0.008, f"warm pipeline 100 took {elapsed:.3f}s"
