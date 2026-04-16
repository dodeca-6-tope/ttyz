"""Tests for Box component."""

from conftest import SnapFn

from ttyz import (
    bold,
    box,
    scroll,
    text,
    vstack,
    zstack,
)
from ttyz.components.scroll import ScrollState

# ── Border styles ────────────────────────────────────────────────────


def test_basic_rounded(snap: SnapFn):
    snap(box(text("hello")), 20)


def test_basic_normal(snap: SnapFn):
    snap(box(text("hi"), style="normal"), 20)


def test_basic_double(snap: SnapFn):
    snap(box(text("hi"), style="double"), 20)


def test_basic_heavy(snap: SnapFn):
    snap(box(text("hi"), style="heavy"), 20)


# ── Title ────────────────────────────────────────────────────────────


def test_title(snap: SnapFn):
    snap(box(text("body"), title="Title"), 20)


def test_title_truncated(snap: SnapFn):
    snap(box(text("x"), title="A Very Long Title That Overflows"), 15)


def test_title_starts_after_corner(snap: SnapFn):
    snap(box(text("body"), title="T"), 20)


# ── Content ──────────────────────────────────────────────────────────


def test_multiline_child(snap: SnapFn):
    child = vstack(text("one"), text("two"), text("three"))
    snap(box(child), 20)


def test_content_padded_to_width(snap: SnapFn):
    snap(box(text("hi")), 20)


def test_empty_child(snap: SnapFn):
    snap(box(text("")), 10)


def test_narrow_width(snap: SnapFn):
    """Box at minimum width (just borders) shouldn't crash."""
    snap(box(text("hello")), 2)


def test_content_clipped_to_inner_width(snap: SnapFn):
    snap(box(text("a long line of text")), 10)


def test_content_clip_preserves_ansi(snap: SnapFn):
    snap(box(text(bold("a long line"))), 10)


# ── Height ───────────────────────────────────────────────────────────


def test_height_passed_to_child(snap: SnapFn):
    s = ScrollState()
    b = box(scroll(text("a"), text("b"), text("c"), text("d"), state=s))
    snap(b, 20, 5)


def test_height_none_unconstrained(snap: SnapFn):
    snap(box(text("hi")), 20)


# ── Flex properties ──────────────────────────────────────────────────


def test_intrinsic_width(snap: SnapFn):
    from ttyz import hstack

    snap(hstack(box(text("hello")), text("M")), 20, name="intrinsic_width_basic")
    snap(
        hstack(box(text("hello"), padding=1), text("M")),
        20,
        name="intrinsic_width_padded",
    )


def test_intrinsic_width_accounts_for_title(snap: SnapFn):
    from ttyz import hstack

    snap(hstack(box(text("x"), title="Long Title Here"), text("M")), 40)


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


def test_narrow_box_title_does_not_overflow(snap: SnapFn):
    snap(box(text(""), title="title"), 4)


def test_box_interior_opaque_over_content(snap: SnapFn):
    """Box must overwrite background content — interior is not transparent."""
    snap(zstack(text("X" * 20), box(text("hi"))), 20, 5)
