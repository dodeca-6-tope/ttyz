"""Tests for Spacer component."""

from conftest import SnapFn

from ttyz import hstack, spacer, text, vstack, zstack

# ── HStack: expands horizontally, not vertically ───────────────────


def test_hstack_spacer_right(snap: SnapFn):
    snap(hstack(spacer(), text("end")), 15)


def test_hstack_spacer_left(snap: SnapFn):
    snap(hstack(text("start"), spacer()), 15)


def test_hstack_spacer_both_sides(snap: SnapFn):
    snap(hstack(spacer(), text("mid"), spacer()), 15)


def test_hstack_spacer_does_not_add_rows(snap: SnapFn):
    snap(hstack(text("a"), spacer(), text("b")), 10)


# ── VStack: expands vertically, not horizontally ───────────────────


def test_vstack_spacer_pushes_down(snap: SnapFn):
    snap(vstack(spacer(), text("bot")), 3, 4)


def test_vstack_spacer_pushes_up(snap: SnapFn):
    snap(vstack(text("top"), spacer()), 3, 4)


def test_vstack_spacer_between(snap: SnapFn):
    snap(vstack(text("hi"), spacer(), text("lo")), 2, 5)


def test_vstack_spacer_no_height_constraint(snap: SnapFn):
    """Without height, no flex context — spacer is just one empty line."""
    snap(vstack(text("a"), spacer(), text("b")), 1)


# ── ZStack: expands on both axes ───────────────────────────────────


def test_zstack_spacer_fills_canvas(snap: SnapFn):
    snap(zstack(spacer()), 4, 3)


def test_zstack_spacer_behind_content(snap: SnapFn):
    snap(zstack(spacer(), text("hi")), 4, 2)


# ── Flex properties ─────────────────────────────────────────────────


def test_grow_is_one():
    assert spacer().grow == 1


def test_intrinsic_width(snap: SnapFn):
    """Spacer has zero intrinsic width, grows to fill remaining space."""
    snap(hstack(text("A"), spacer(), text("B")), 10)


def test_min_length(snap: SnapFn):
    """Spacer with min_length guarantees minimum space in layout."""
    snap(hstack(spacer(min_length=5), text("|")), 6)


def test_does_not_propagate_grow():
    assert not hstack(text("a"), spacer()).grow
    assert not vstack(text("a"), spacer()).grow


# ── No cross-axis leak ─────────────────────────────────────────────


def test_hstack_with_spacer_does_not_steal_height(snap: SnapFn):
    header = hstack(text("L"), spacer(), text("R"))
    snap(vstack(header, text("scene")), 5, 4)


def test_vstack_with_spacer_does_not_steal_width(snap: SnapFn):
    sidebar = vstack(text("T"), spacer(), text("B"))
    snap(hstack(sidebar, text("scene")), 6, 3)
