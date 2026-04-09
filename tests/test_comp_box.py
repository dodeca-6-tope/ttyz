"""Tests for Box component."""

from helpers import vis

from terminal import bold, box, scroll, text, vstack
from terminal.components.scroll import ScrollState

# ── Border styles ────────────────────────────────────────────────────


def test_basic_rounded():
    assert vis(box(text("hello")).render(20)) == [
        "╭─────╮",
        "│hello│",
        "╰─────╯",
    ]


def test_basic_normal():
    assert vis(box(text("hi"), style="normal").render(20)) == [
        "┌──┐",
        "│hi│",
        "└──┘",
    ]


def test_basic_double():
    assert vis(box(text("hi"), style="double").render(20)) == [
        "╔══╗",
        "║hi║",
        "╚══╝",
    ]


def test_basic_heavy():
    assert vis(box(text("hi"), style="heavy").render(20)) == [
        "┏━━┓",
        "┃hi┃",
        "┗━━┛",
    ]


# ── Title ────────────────────────────────────────────────────────────


def test_title():
    assert vis(box(text("body"), title="Title").render(20)) == [
        "╭·Title·╮",
        "│body···│",
        "╰───────╯",
    ]


def test_title_truncated():
    lines = vis(box(text("x"), title="A Very Long Title That Overflows").render(15))
    assert lines == [
        "╭·A·Very·Lon…·╮",
        "│x············│",
        "╰─────────────╯",
    ]


def test_title_starts_after_corner():
    #              ╭ T ─╮   (no leading dash before title)
    assert vis(box(text("body"), title="T").render(20)) == [
        "╭·T·─╮",
        "│body│",
        "╰────╯",
    ]


# ── Content ──────────────────────────────────────────────────────────


def test_multiline_child():
    child = vstack(text("one"), text("two"), text("three"))
    assert vis(box(child).render(20)) == [
        "╭─────╮",
        "│one··│",
        "│two··│",
        "│three│",
        "╰─────╯",
    ]


def test_content_padded_to_width():
    lines = vis(box(text("hi")).render(20))
    widths = {len(l) for l in lines}
    assert len(widths) == 1


def test_empty_child():
    assert vis(box(text("")).render(10)) == [
        "╭╮",
        "││",
        "╰╯",
    ]


def test_narrow_width():
    """Box at minimum width (just borders) shouldn't crash."""
    assert vis(box(text("hello")).render(2)) == [
        "╭╮",
        "││",
        "╰╯",
    ]


def test_content_clipped_to_inner_width():
    assert vis(box(text("a long line of text")).render(10)) == [
        "╭────────╮",
        "│a·long·l│",
        "╰────────╯",
    ]


def test_content_clip_preserves_ansi():
    raw = box(text(bold("a long line"))).render(10)
    content_line = raw[1]
    assert "\033[1m" in content_line


# ── Height ───────────────────────────────────────────────────────────


def test_height_passed_to_child():
    s = ScrollState()
    b = box(scroll(text("a"), text("b"), text("c"), text("d"), state=s))
    assert vis(b.render(20, 5)) == [
        "╭──────────────────╮",
        "│a·················│",
        "│b·················│",
        "│c·················│",
        "╰──────────────────╯",
    ]


def test_height_none_unconstrained():
    assert vis(box(text("hi")).render(20)) == [
        "╭──╮",
        "│hi│",
        "╰──╯",
    ]


# ── Flex properties ──────────────────────────────────────────────────


def test_flex_basis():
    assert box(text("hello")).flex_basis == 7  # 5 + 2 borders
    assert box(text("hello"), padding=1).flex_basis == 9  # 5 + 2 borders + 2 padding


def test_flex_basis_accounts_for_title():
    b = box(text("x"), title="Long Title Here")
    assert b.flex_basis >= len("Long Title Here") + 4


def test_flex_grow_passthrough():
    assert box(text("hi"), grow=1).grow == 1
    assert not box(text("hi")).grow


def test_flex_grow_delegates():
    s = ScrollState()
    assert box(scroll(text("a"), state=s)).grow
    assert not box(text("a")).grow


# ── Validation ───────────────────────────────────────────────────────


def test_invalid_style_raises():
    import pytest

    with pytest.raises(ValueError, match="unknown border style"):
        box(text("x"), style="fancy")
