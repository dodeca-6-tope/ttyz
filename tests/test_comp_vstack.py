"""Tests for VStack component."""

from conftest import SnapFn

from ttyz import scroll, text, vstack
from ttyz.components.scroll import ScrollState


def test_stacks_children(snap: SnapFn):
    snap(vstack(text("a"), text("b")), 80)


def test_spacing(snap: SnapFn):
    snap(vstack(text("a"), text("b"), spacing=1), 80)


def test_empty(snap: SnapFn):
    snap(vstack(), 80)


def test_intrinsic_width(snap: SnapFn):
    from ttyz import hstack

    snap(hstack(vstack(text("hello"), text("hi")), text("|")), 20)


# ── Height-constrained rendering ─────────────────────────────────────


def test_unconstrained_when_no_height(snap: SnapFn):
    v = vstack(text("a"), text("b"), text("c"))
    snap(v, 80, name="unconstrained_no_h")
    snap(v, 80, None, name="unconstrained_none_h")


def test_constrained_no_growers_ignores_height(snap: SnapFn):
    snap(vstack(text("a"), text("b")), 80, 10)


def test_constrained_distributes_to_grower(snap: SnapFn):
    s = ScrollState()
    v = vstack(text("header"), scroll(text("a"), text("b"), text("c"), state=s))
    snap(v, 80, 4)


def test_constrained_multiple_fixed_children(snap: SnapFn):
    s = ScrollState()
    v = vstack(
        text("top"), scroll(text("a"), text("b"), text("c"), state=s), text("bottom")
    )
    snap(v, 80, 5)


def test_constrained_with_spacing(snap: SnapFn):
    s = ScrollState()
    v = vstack(
        text("top"),
        scroll(text("a"), text("b"), text("c"), text("d"), state=s),
        spacing=1,
    )
    snap(v, 80, 5)


def test_constrained_two_growers(snap: SnapFn):
    s1 = ScrollState()
    s2 = ScrollState()
    v = vstack(
        scroll(*[text(str(i)) for i in range(10)], state=s1),
        scroll(*[text(str(i + 10)) for i in range(10)], state=s2),
    )
    snap(v, 80, 6)


def test_constrained_grower_gets_zero_when_fixed_fills(snap: SnapFn):
    s = ScrollState()
    v = vstack(
        text("a"),
        text("b"),
        text("c"),
        scroll(text("x"), text("y"), state=s),
    )
    snap(v, 80, 3)


# ── flex_grow propagation ───────────────────────────────────────────


def test_grow_not_propagated_from_children():
    assert not vstack(text("a"), text("b", grow=1)).grow


def test_flex_grow_false_without_growers():
    assert not vstack(text("a"), text("b")).grow


# ── bg fills parent-allocated height ───────────────────────────────


def test_bg_fills_flex_allocated_height(snap: SnapFn):
    from ttyz import spacer

    v = vstack(
        vstack(text(""), grow=1, bg=1),
        spacer(),
        bg=2,
    )
    snap(v, 10, 10)


def test_height_child_with_height_spec(snap: SnapFn):
    """A child with height='2' is clipped to 2 lines even when parent has more."""
    child = text("content", height="2")
    snap(vstack(child), 80, 10)
