"""Tests for Scroll component."""

from conftest import SnapFn

from ttyz import box, hstack, scroll, scrollbar, scrollbar_default, text, vstack
from ttyz.components.scroll import ScrollState


def _state(offset: int = 0) -> ScrollState:
    s = ScrollState()
    s.offset = offset
    return s


# ── Basic rendering ──────────────────────────────────────────────────


def test_shows_slice_at_offset(snap: SnapFn):
    s = _state(1)
    snap(scroll(text("a"), text("b"), text("c"), text("d"), text("e"), state=s), 80, 3)


def test_offset_zero(snap: SnapFn):
    s = _state()
    snap(scroll(text("a"), text("b"), text("c"), text("d"), state=s), 80, 2)


def test_single_child(snap: SnapFn):
    s = _state()
    snap(scroll(text("only"), state=s), 80, 1)


def test_pads_when_content_shorter_than_height(snap: SnapFn):
    s = _state()
    snap(scroll(text("a"), state=s), 80, 3)


def test_exact_fit(snap: SnapFn):
    s = _state()
    snap(scroll(text("a"), text("b"), text("c"), state=s), 80, 3)


def test_empty_no_children(snap: SnapFn):
    s = _state()
    snap(scroll(state=s), 80, 3)


def test_height_one(snap: SnapFn):
    s = _state(2)
    snap(scroll(text("a"), text("b"), text("c"), state=s), 80, 1)


# ── Offset clamping ─────────────────────────────────────────────────


def test_clamps_offset_over_max(snap: SnapFn):
    s = _state(10)
    snap(scroll(text("a"), text("b"), text("c"), state=s), 80, 2)
    assert s.offset == 1


def test_offset_negative_clamps_to_zero(snap: SnapFn):
    s = _state(-5)
    snap(scroll(text("a"), text("b"), text("c"), state=s), 80, 2)
    assert s.offset == 0


def test_offset_exactly_at_max(snap: SnapFn):
    s = _state(2)
    snap(scroll(text("a"), text("b"), text("c"), text("d"), state=s), 80, 2)
    assert s.offset == 2


def test_offset_clamps_when_content_fits(snap: SnapFn):
    s = _state(5)
    snap(scroll(text("a"), text("b"), state=s), 80, 5)
    assert s.offset == 0


# ── Multiline children ──────────────────────────────────────────────


def test_multiline_child(snap: SnapFn):
    s = _state()
    child = vstack(text("x"), text("y"))
    snap(scroll(child, text("z"), state=s), 80, 2)


def test_multiline_child_partial_clip(snap: SnapFn):
    s = _state()
    child = vstack(text("x"), text("y"), text("z"))
    snap(scroll(child, text("after"), state=s), 80, 2)


def test_multiline_child_at_offset(snap: SnapFn):
    s = _state(1)
    child1 = vstack(text("a"), text("b"))
    child2 = vstack(text("c"), text("d"))
    child3 = vstack(text("e"), text("f"))
    snap(scroll(child1, child2, child3, state=s), 80, 2)


def test_mixed_single_and_multiline(snap: SnapFn):
    s = _state()
    child = vstack(text("x"), text("y"))
    snap(scroll(text("header"), child, text("footer"), state=s), 80, 4)


# ── Flex delegation ─────────────────────────────────────────────────


def test_renders_children_at_natural_width(snap: SnapFn):
    """Scroll renders children at their natural width."""
    s = _state()
    snap(scroll(text("hi"), text("hello"), state=s), 20, 5)


def test_flex_grow_when_child_grows():
    s = _state()
    assert scroll(text("x", grow=1), state=s).grow


def test_flex_grow_fill():
    s = _state()
    assert scroll(text("a"), state=s).grow


# ── height="fill" ───────────────────────────────────────────────────


def test_fill_uses_parent_height(snap: SnapFn):
    s = _state()
    snap(scroll(text("a"), text("b"), text("c"), text("d"), text("e"), state=s), 80, 3)


def test_fill_with_offset(snap: SnapFn):
    s = _state(2)
    snap(scroll(text("a"), text("b"), text("c"), text("d"), state=s), 80, 2)


def test_fill_in_vstack(snap: SnapFn):
    s = _state()
    v = vstack(
        text("header"), scroll(text("a"), text("b"), text("c"), text("d"), state=s)
    )
    snap(v, 80, 4)


def test_fill_in_vstack_with_multiple_fixed(snap: SnapFn):
    s = _state()
    v = vstack(
        text("top"), scroll(text("a"), text("b"), text("c"), state=s), text("bottom")
    )
    snap(v, 80, 5)


def test_fill_in_vstack_with_spacing(snap: SnapFn):
    s = _state()
    v = vstack(
        text("top"),
        scroll(text("a"), text("b"), text("c"), text("d"), state=s),
        spacing=1,
    )
    snap(v, 80, 5)


def test_fill_returns_empty_without_parent_height(snap: SnapFn):
    s = _state()
    snap(scroll(text("a"), state=s), 80)


def test_fill_clamps_offset(snap: SnapFn):
    s = _state(100)
    snap(scroll(text("a"), text("b"), text("c"), state=s), 80, 2)
    assert s.offset == 1


def test_fill_inside_box(snap: SnapFn):
    s = _state()
    snap(box(scroll(text("a"), text("b"), text("c"), text("d"), state=s)), 10, 5)


# ── Render feeds back dimensions ────────────────────────────────────


def test_render_feeds_back_fixed_height(snap: SnapFn):
    s = _state()
    snap(scroll(text("a"), text("b"), text("c"), state=s), 80, 2)
    assert s.height == 2
    assert s.total == 3


def test_render_feeds_back_fill_height(snap: SnapFn):
    s = _state()
    snap(scroll(text("a"), text("b"), state=s), 80, 10)
    assert s.height == 10
    assert s.total == 2


def test_dimensions_update_on_rerender(snap: SnapFn):
    s = _state()
    snap(scroll(text("a"), text("b"), state=s), 80, 5, name="dimensions_first")
    assert s.total == 2
    assert s.height == 5
    snap(
        scroll(text("a"), text("b"), text("c"), text("d"), state=s),
        80,
        3,
        name="dimensions_second",
    )
    assert s.total == 4
    assert s.height == 3


# ── Shared state across renders ─────────────────────────────────────


def test_state_persists_offset_across_renders(snap: SnapFn):
    s = _state()
    s.height = 3
    s.total = 10
    s.scroll_down(5)
    snap(scroll(*[text(str(i)) for i in range(10)], state=s), 80, 3)


def test_scroll_down_then_render(snap: SnapFn):
    s = _state()
    snap(
        scroll(text("a"), text("b"), text("c"), text("d"), state=s),
        80,
        2,
        name="scroll_down_before",
    )
    s.scroll_down()
    snap(
        scroll(text("a"), text("b"), text("c"), text("d"), state=s),
        80,
        2,
        name="scroll_down_after",
    )


def test_page_down_then_render(snap: SnapFn):
    s = _state()
    snap(
        scroll(*[text(str(i)) for i in range(20)], state=s),
        80,
        5,
        name="page_down_before",
    )
    s.page_down()
    snap(
        scroll(*[text(str(i)) for i in range(20)], state=s),
        80,
        5,
        name="page_down_after",
    )


def test_page_up_from_middle(snap: SnapFn):
    s = _state()
    snap(
        scroll(*[text(str(i)) for i in range(20)], state=s),
        80,
        5,
        name="page_up_initial",
    )
    s.scroll_down(10)
    s.page_up()
    snap(
        scroll(*[text(str(i)) for i in range(20)], state=s), 80, 5, name="page_up_after"
    )


def test_scroll_to_bottom_then_render(snap: SnapFn):
    s = _state()
    snap(
        scroll(*[text(str(i)) for i in range(10)], state=s),
        80,
        3,
        name="to_bottom_before",
    )
    s.scroll_to_bottom()
    snap(
        scroll(*[text(str(i)) for i in range(10)], state=s),
        80,
        3,
        name="to_bottom_after",
    )


def test_scroll_to_top_then_render(snap: SnapFn):
    s = _state(5)
    snap(
        scroll(*[text(str(i)) for i in range(10)], state=s), 80, 3, name="to_top_before"
    )
    s.scroll_to_top()
    snap(
        scroll(*[text(str(i)) for i in range(10)], state=s), 80, 3, name="to_top_after"
    )


# ── ScrollState edge cases ──────────────────────────────────────────


def test_scroll_state_initial():
    s = ScrollState()
    assert s.offset == 0
    assert s.height == 0
    assert s.total == 0
    assert s.max_offset == 0


def test_scroll_state_scroll_down():
    s = ScrollState()
    s.height = 5
    s.total = 20
    s.scroll_down(3)
    assert s.offset == 3


def test_scroll_state_scroll_down_clamps():
    s = ScrollState()
    s.height = 5
    s.total = 10
    s.scroll_down(100)
    assert s.offset == 5


def test_scroll_state_scroll_up():
    s = ScrollState()
    s.offset = 5
    s.scroll_up(3)
    assert s.offset == 2


def test_scroll_state_scroll_up_clamps():
    s = ScrollState()
    s.offset = 2
    s.scroll_up(10)
    assert s.offset == 0


def test_scroll_state_scroll_up_from_zero():
    s = ScrollState()
    s.scroll_up()
    assert s.offset == 0


def test_scroll_state_scroll_down_when_content_fits():
    s = ScrollState()
    s.height = 10
    s.total = 5
    s.scroll_down()
    assert s.offset == 0


def test_scroll_state_page_down():
    s = ScrollState()
    s.height = 10
    s.total = 50
    s.page_down()
    assert s.offset == 10


def test_scroll_state_page_down_clamps():
    s = ScrollState()
    s.height = 10
    s.total = 15
    s.page_down()
    assert s.offset == 5


def test_scroll_state_page_up():
    s = ScrollState()
    s.height = 10
    s.total = 50
    s.offset = 20
    s.page_up()
    assert s.offset == 10


def test_scroll_state_page_up_clamps():
    s = ScrollState()
    s.height = 10
    s.total = 50
    s.offset = 5
    s.page_up()
    assert s.offset == 0


def test_scroll_state_page_down_then_up_roundtrip():
    s = ScrollState()
    s.height = 10
    s.total = 100
    s.page_down()
    s.page_down()
    s.page_up()
    assert s.offset == 10


def test_scroll_state_to_top():
    s = ScrollState()
    s.offset = 15
    s.scroll_to_top()
    assert s.offset == 0


def test_scroll_state_to_bottom():
    s = ScrollState()
    s.height = 5
    s.total = 20
    s.scroll_to_bottom()
    assert s.offset == 15


def test_scroll_state_to_bottom_when_content_fits():
    s = ScrollState()
    s.height = 10
    s.total = 3
    s.scroll_to_bottom()
    assert s.offset == 0


def test_scroll_state_max_offset():
    s = ScrollState()
    s.height = 5
    s.total = 20
    assert s.max_offset == 15


def test_scroll_state_max_offset_content_fits():
    s = ScrollState()
    s.height = 10
    s.total = 3
    assert s.max_offset == 0


def test_scroll_state_max_offset_exact():
    s = ScrollState()
    s.height = 5
    s.total = 5
    assert s.max_offset == 0


def test_scroll_state_scroll_n_steps():
    s = ScrollState()
    s.height = 5
    s.total = 100
    s.scroll_down(50)
    assert s.offset == 50
    s.scroll_up(20)
    assert s.offset == 30


def test_scroll_state_before_first_render():
    s = ScrollState()
    s.scroll_down()
    assert s.offset == 0
    s.page_down()
    assert s.offset == 0
    s.scroll_to_bottom()
    assert s.offset == 0


def test_scroll_to_visible_above():
    s = ScrollState()
    s.height = 5
    s.total = 20
    s.offset = 10
    s.scroll_to_visible(7)
    assert s.offset == 7


def test_scroll_to_visible_below():
    s = ScrollState()
    s.height = 5
    s.total = 20
    s.offset = 0
    s.scroll_to_visible(8)
    assert s.offset == 4


def test_scroll_to_visible_already_visible():
    s = ScrollState()
    s.height = 5
    s.total = 20
    s.offset = 5
    s.scroll_to_visible(7)
    assert s.offset == 5


def test_scroll_to_visible_at_top_edge():
    s = ScrollState()
    s.height = 5
    s.total = 20
    s.offset = 5
    s.scroll_to_visible(5)
    assert s.offset == 5


def test_scroll_to_visible_at_bottom_edge():
    s = ScrollState()
    s.height = 5
    s.total = 20
    s.offset = 5
    s.scroll_to_visible(9)
    assert s.offset == 5


# ── Follow mode ────────────────────────────────────────────────────


def test_follow_disabled_by_default():
    s = ScrollState()
    assert s.follow is False


def test_follow_sticks_to_bottom(snap: SnapFn):
    s = ScrollState(follow=True)
    items = [text(str(i)) for i in range(10)]
    snap(scroll(*items, state=s), 80, 3, name="follow_sticks_10")
    assert s.offset == 7
    items.extend(text(str(i)) for i in range(10, 20))
    snap(scroll(*items, state=s), 80, 3, name="follow_sticks_20")
    assert s.offset == 17


def test_scroll_up_disables_follow(snap: SnapFn):
    s = ScrollState(follow=True)
    snap(
        scroll(*[text(str(i)) for i in range(10)], state=s),
        80,
        3,
        name="follow_up_before",
    )
    s.scroll_up(2)
    assert s.follow is False
    assert s.offset == 5
    snap(
        scroll(*[text(str(i)) for i in range(10)], state=s),
        80,
        3,
        name="follow_up_after",
    )
    assert s.offset == 5


def test_follow_reengages_at_bottom(snap: SnapFn):
    s = ScrollState(follow=True)
    snap(
        scroll(*[text(str(i)) for i in range(10)], state=s),
        80,
        3,
        name="follow_reengage_before",
    )
    s.scroll_up(2)
    assert s.follow is False
    s.scroll_down(2)
    snap(
        scroll(*[text(str(i)) for i in range(10)], state=s),
        80,
        3,
        name="follow_reengage_after",
    )
    assert s.follow is True


def test_follow_with_growing_content(snap: SnapFn):
    s = ScrollState(follow=True)
    items = [text(str(i)) for i in range(5)]
    snap(scroll(*items, state=s), 80, 3, name="follow_grow_initial")
    assert s.offset == 2
    s.scroll_up(1)
    assert s.follow is False
    items.extend([text(str(i)) for i in range(5, 10)])
    snap(scroll(*items, state=s), 80, 3, name="follow_grow_after")
    assert s.offset == 1


def test_page_up_disables_follow():
    s = ScrollState()
    s.height = 5
    s.total = 20
    s.offset = 15
    s.page_up()
    assert s.follow is False


def test_scroll_down_does_not_disable_follow():
    s = ScrollState()
    s.follow = True
    s.height = 5
    s.total = 20
    s.scroll_down(3)
    assert s.follow is True


# ── Scrollbar component ────────────────────────────────────────────


def test_scrollbar_returns_one_char_wide(snap: SnapFn):
    s = _state()
    snap(
        scroll(*[text(str(i)) for i in range(20)], state=s),
        80,
        5,
        name="scrollbar_wide_scroll",
    )
    snap(scrollbar(state=s), 1, 5, name="scrollbar_wide_bar")


def test_scrollbar_empty_when_content_fits(snap: SnapFn):
    s = _state()
    snap(scroll(text("a"), text("b"), state=s), 80, 5, name="scrollbar_empty_scroll")
    snap(scrollbar(state=s), 1, 5, name="scrollbar_empty_bar")


def test_scrollbar_thumb_moves_with_offset(snap: SnapFn):
    items = [text(str(i)) for i in range(100)]
    s1 = _state(0)
    snap(scroll(*items, state=s1), 80, 10, name="scrollbar_thumb_top_scroll")
    snap(scrollbar(state=s1), 1, 10, name="scrollbar_thumb_top")
    s2 = _state(90)
    snap(scroll(*items, state=s2), 80, 10, name="scrollbar_thumb_bottom_scroll")
    snap(scrollbar(state=s2), 1, 10, name="scrollbar_thumb_bottom")


def test_scrollbar_composes_with_hstack(snap: SnapFn):
    s = _state()
    view = vstack(
        hstack(
            scroll(*[text(str(i)) for i in range(20)], state=s),
            scrollbar(state=s),
            grow=1,
        ),
    )
    snap(view, 20, 5)


def test_scrollbar_custom_render_fn(snap: SnapFn):
    def my_bar(h: int, total: int, offset: int) -> list[str]:
        return ["X"] * h

    s = _state()
    snap(
        scroll(*[text(str(i)) for i in range(20)], state=s),
        80,
        3,
        name="scrollbar_custom_scroll",
    )
    snap(scrollbar(state=s, render_fn=my_bar), 1, 3, name="scrollbar_custom_bar")


def test_scrollbar_default_fn_directly():
    col = scrollbar_default(10, 100, 0)
    assert len(col) == 10
    assert any("┃" in c for c in col[:3])


def test_scrollbar_default_at_bottom():
    col = scrollbar_default(10, 100, 90)
    assert len(col) == 10
    assert any("┃" in c for c in col[-3:])


def test_scrollbar_default_content_fits():
    col = scrollbar_default(10, 5, 0)
    assert all(c == "" for c in col)


def test_scrollbar_default_single_row():
    col = scrollbar_default(1, 100, 0)
    assert len(col) == 1
    assert "┃" in col[0]


def test_scrollbar_default_monotonic():
    def thumb_top(offset: int) -> int:
        col = scrollbar_default(20, 200, offset)
        for i, c in enumerate(col):
            if "┃" in c:
                return i
        return 20

    positions = [thumb_top(o) for o in range(0, 181, 10)]
    for i in range(1, len(positions)):
        assert positions[i] >= positions[i - 1]


# ── scroll_to_top / scroll_to_bottom follow interaction ───────────


def test_scroll_to_top_disables_follow():
    s = ScrollState(follow=True)
    s.height = 5
    s.total = 20
    s.offset = 15
    s.scroll_to_top()
    assert s.offset == 0
    assert s.follow is False


def test_scroll_to_bottom_enables_follow():
    s = ScrollState()
    s.height = 5
    s.total = 20
    s.scroll_to_bottom()
    assert s.offset == 15
    assert s.follow is True


def test_scroll_always_grows():
    s = ScrollState()
    assert scroll(text("short"), state=s).grow


# ── Scroll + Scrollbar end-to-end ─────────────────────────────────


def test_scroll_and_scrollbar_share_state(snap: SnapFn):
    s = ScrollState()
    items = [text(str(i)) for i in range(50)]
    snap(scroll(*items, state=s), 80, 10, name="share_state_scroll")
    assert s.height == 10
    assert s.total == 50
    snap(scrollbar(state=s), 1, 10, name="share_state_bar")


def test_follow_tracks_growing_content_end_to_end(snap: SnapFn):
    s = ScrollState(follow=True)
    items = [text(str(i)) for i in range(5)]
    snap(scroll(*items, state=s), 80, 3, name="follow_initial")
    items.extend(text(str(i)) for i in range(5, 15))
    snap(scroll(*items, state=s), 80, 3, name="follow_after_grow")
    s.scroll_up(5)
    snap(scroll(*items, state=s), 80, 3, name="follow_after_scroll_up")
    items.extend(text(str(i)) for i in range(15, 25))
    snap(scroll(*items, state=s), 80, 3, name="follow_disabled_grow")
    s.scroll_to_bottom()
    snap(scroll(*items, state=s), 80, 3, name="follow_reengaged")
    items.extend(text(str(i)) for i in range(25, 30))
    snap(scroll(*items, state=s), 80, 3, name="follow_final")


def test_scroll_follow_stays_off_when_content_fits(snap: SnapFn):
    s = ScrollState(follow=True)
    items = [text("a"), text("b"), text("c")]
    snap(scroll(*items, state=s), 80, 3, name="follow_stays_off_before")
    assert s.follow is True
    s.scroll_up()
    assert s.follow is False
    snap(scroll(*items, state=s), 80, 3, name="follow_stays_off_after")
    assert s.follow is False


def test_scroll_state_zero_total_scroll_down():
    s = ScrollState()
    s.height = 5
    s.total = 0
    s.scroll_down(10)
    assert s.offset == 0


def test_scrollbar_uses_state_height_not_render_h(snap: SnapFn):
    """Scrollbar uses state.height from a prior scroll render, not the h argument."""
    s = ScrollState()
    s.total = 100
    snap(scrollbar(state=s), 1, 10)
