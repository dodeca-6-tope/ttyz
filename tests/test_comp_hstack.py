"""Tests for HStack component."""

from conftest import SnapFn

from ttyz import cond, hstack, scroll, text, vstack
from ttyz.components.scroll import ScrollState

# ── Fixed layout ─────────────────────────────────────────────────────


def test_side_by_side(snap: SnapFn):
    snap(hstack(text("a"), text("b"), spacing=1), 20)


def test_spacing(snap: SnapFn):
    snap(hstack(text("a"), text("b"), spacing=3), 20)


def test_percentage_width_reserves_column_space(snap: SnapFn):
    snap(hstack(text("A", width="50%"), text("B"), spacing=1), 20)


def test_cond_false_invisible(snap: SnapFn):
    snap(hstack(cond(False, text("gone")), text("here")), 80)


def test_empty(snap: SnapFn):
    snap(hstack(), 80)


def test_multiline_children(snap: SnapFn):
    snap(hstack(vstack(text("a"), text("b")), text("c"), spacing=1), 20)


# ── Justify ──────────────────────────────────────────────────────────


def test_justify_between(snap: SnapFn):
    snap(hstack(text("L"), text("R"), justify_content="between"), 20)


def test_justify_end(snap: SnapFn):
    snap(hstack(text("hi"), justify_content="end"), 20)


def test_justify_center(snap: SnapFn):
    snap(hstack(text("hi"), justify_content="center"), 20)


def test_justify_between_single_child(snap: SnapFn):
    snap(hstack(text("only"), justify_content="between"), 20)


def test_justify_between_nested(snap: SnapFn):
    inner = hstack(text("L"), text("R"), justify_content="between", grow=1)
    snap(hstack(inner), 20)


# ── Wrap ─────────────────────────────────────────────────────────────


def test_wrap_fits_one_line(snap: SnapFn):
    snap(hstack(text("aa"), text("bb"), wrap=True, spacing=1), 10)


def test_wrap_breaks_to_next_line(snap: SnapFn):
    snap(hstack(text("aa"), text("bb"), wrap=True, spacing=1), 4)


def test_wrap_empty(snap: SnapFn):
    snap(hstack(wrap=True), 80)


def test_wrap_many_chunks(snap: SnapFn):
    chunks = [text("[a] one"), text("[b] two"), text("[c] three"), text("[d] four")]
    snap(hstack(*chunks, wrap=True, spacing=1), 24)


def test_wrap_boundary(snap: SnapFn):
    snap(
        hstack(text("aaa"), text("bbb"), wrap=True, spacing=1),
        7,
        name="wrap_boundary_fits",
    )
    snap(
        hstack(text("aaa"), text("bbb"), wrap=True, spacing=1),
        6,
        name="wrap_boundary_wraps",
    )


def test_wrap_respects_spacing(snap: SnapFn):
    snap(
        hstack(text("aaa"), text("bbb"), wrap=True, spacing=3),
        9,
        name="wrap_spacing_fits",
    )
    snap(
        hstack(text("aaa"), text("bbb"), wrap=True, spacing=3),
        8,
        name="wrap_spacing_wraps",
    )


def test_wrap_preserves_ansi(snap: SnapFn):
    green, rst = "\033[32m", "\033[0m"
    chunks = [text(f"{green}[⏎]{rst} select"), text("[esc] back")]
    snap(hstack(*chunks, wrap=True, spacing=1), 25)


# ── flex_grow propagation ───────────────────────────────────────────


def test_grow_not_propagated_from_child():
    assert not hstack(text("a"), text("b", grow=1)).grow


def test_flex_grow_false_without_growers():
    assert not hstack(text("a"), text("b")).grow


def test_justify_does_not_imply_grow():
    assert not hstack(text("a"), justify_content="center").grow
    assert not hstack(text("a"), justify_content="between").grow


# ── Validation ──────────────────────────────────────────────────────


def test_invalid_justify_content_raises():
    import pytest

    with pytest.raises(ValueError, match="unknown justify_content"):
        hstack(text("x"), justify_content="spread")


# ── Height propagation ─────────────────────────────────────────────


def test_height_passed_to_scroll_child(snap: SnapFn):
    s = ScrollState()
    view = vstack(
        hstack(
            scroll(*[text(str(i)) for i in range(20)], state=s),
            text("R"),
            grow=1,
        ),
    )
    snap(view, 20, 10)
    assert s.height == 10


def test_height_not_passed_to_fixed_child(snap: SnapFn):
    s = ScrollState()
    view = vstack(
        hstack(
            scroll(*[text(str(i)) for i in range(20)], state=s),
            text("side"),
            grow=1,
        ),
    )
    snap(view, 40, 8)
    assert s.height == 8


def test_grow_not_propagated():
    s = ScrollState()
    assert not hstack(scroll(text("a"), state=s), text("b")).grow


def test_hstack_in_vstack_scroll_gets_remaining_height(snap: SnapFn):
    s = ScrollState()
    view = vstack(
        text("header"),
        hstack(
            scroll(*[text(str(i)) for i in range(50)], state=s),
            grow=1,
        ),
        text("footer"),
    )
    snap(view, 20, 12)
    assert s.height == 10


def test_bg_fills_flex_allocated_height(snap: SnapFn):
    from ttyz import spacer

    v = vstack(
        hstack(text(""), grow=1, bg=1),
        spacer(),
        bg=2,
    )
    snap(v, 10, 10)


# ── Nested flat path offsets ────────────────────────────────────────


def test_nested_hstack_flat_offsets(snap: SnapFn):
    inner = hstack(text("ab"), text("cd"), spacing=1)
    outer = hstack(inner, text("X"), spacing=1)
    snap(outer, 20)


def test_nested_hstack_flat_offsets_deep(snap: SnapFn):
    a = hstack(text("AAA"), text("BBB"), spacing=1)
    b = hstack(a, text("CCC"), spacing=1)
    c = hstack(b, text("DDD"), spacing=1)
    snap(c, 30)


def test_nested_hstack_flat_total_width(snap: SnapFn):
    inner = hstack(text("hello"), text("world"), spacing=1)
    outer = hstack(inner, text("!"), spacing=1)
    snap(outer, 30)


def test_all_hidden_cond_children(snap: SnapFn):
    snap(hstack(cond(False, text("a")), cond(False, text("b"))), 80)


# ── Grow column width stability ──────────────────────────────────────


def test_grow_column_does_not_overflow(snap: SnapFn):
    """A grow column's content must not inflate the hstack beyond w."""
    snap(hstack(text("SIDE"), text("x" * 200, grow=1)), 40, name="grow_overflow")


def test_grow_column_gets_remaining_space(snap: SnapFn):
    """Grow column fills remaining space after fixed columns."""
    snap(hstack(text("AB"), text("X", grow=1), text("YZ")), 10)


def test_nested_grow_content_does_not_inflate_parent(snap: SnapFn):
    """Growing content inside box+vstack+hstack must not widen the layout."""
    from ttyz import box

    sidebar = text("SIDE", width="6")
    content = vstack(text("x" * 200, truncation="end"), grow=1)
    main = box(content, grow=1, padding=1)
    snap(hstack(sidebar, main, spacing=1), 40)
