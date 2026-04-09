"""Tests for Scroll component."""

from helpers import clean, vis

from terminal import box, hstack, scroll, scrollbar, scrollbar_default, text, vstack
from terminal.components.scroll import ScrollState
from terminal.measure import display_width, strip_ansi


def _state(offset: int = 0) -> ScrollState:
    s = ScrollState()
    s.offset = offset
    return s


# ── Basic rendering ──────────────────────────────────────────────────


def test_shows_slice_at_offset():
    s = _state(1)
    assert clean(
        scroll(text("a"), text("b"), text("c"), text("d"), text("e"), state=s).render(
            80, 3
        )
    ) == ["b", "c", "d"]


def test_offset_zero():
    s = _state()
    assert clean(
        scroll(text("a"), text("b"), text("c"), text("d"), state=s).render(80, 2)
    ) == ["a", "b"]


def test_single_child():
    s = _state()
    assert clean(scroll(text("only"), state=s).render(80, 1)) == ["only"]


def test_pads_when_content_shorter_than_height():
    s = _state()
    assert clean(scroll(text("a"), state=s).render(80, 3)) == ["a", "", ""]


def test_exact_fit():
    s = _state()
    assert clean(scroll(text("a"), text("b"), text("c"), state=s).render(80, 3)) == [
        "a",
        "b",
        "c",
    ]


def test_empty_no_children():
    s = _state()
    assert clean(scroll(state=s).render(80, 3)) == ["", "", ""]


def test_height_one():
    s = _state(2)
    assert clean(scroll(text("a"), text("b"), text("c"), state=s).render(80, 1)) == [
        "c"
    ]


# ── Offset clamping ─────────────────────────────────────────────────


def test_clamps_offset_over_max():
    s = _state(10)
    assert clean(scroll(text("a"), text("b"), text("c"), state=s).render(80, 2)) == [
        "b",
        "c",
    ]
    assert s.offset == 1


def test_offset_negative_clamps_to_zero():
    s = _state(-5)
    assert clean(scroll(text("a"), text("b"), text("c"), state=s).render(80, 2)) == [
        "a",
        "b",
    ]
    assert s.offset == 0


def test_offset_exactly_at_max():
    s = _state(2)
    assert clean(
        scroll(text("a"), text("b"), text("c"), text("d"), state=s).render(80, 2)
    ) == ["c", "d"]
    assert s.offset == 2


def test_offset_clamps_when_content_fits():
    s = _state(5)
    assert clean(scroll(text("a"), text("b"), state=s).render(80, 5)) == [
        "a",
        "b",
        "",
        "",
        "",
    ]
    assert s.offset == 0


# ── Multiline children ──────────────────────────────────────────────


def test_multiline_child():
    s = _state()
    child = vstack(text("x"), text("y"))
    assert clean(scroll(child, text("z"), state=s).render(80, 2)) == ["x", "y"]


def test_multiline_child_partial_clip():
    s = _state()
    child = vstack(text("x"), text("y"), text("z"))
    assert clean(scroll(child, text("after"), state=s).render(80, 2)) == ["x", "y"]


def test_multiline_child_at_offset():
    s = _state(1)
    child1 = vstack(text("a"), text("b"))
    child2 = vstack(text("c"), text("d"))
    child3 = vstack(text("e"), text("f"))
    assert clean(scroll(child1, child2, child3, state=s).render(80, 2)) == ["c", "d"]


def test_mixed_single_and_multiline():
    s = _state()
    child = vstack(text("x"), text("y"))
    assert clean(
        scroll(text("header"), child, text("footer"), state=s).render(80, 4)
    ) == ["header", "x", "y", "footer"]


# ── Flex delegation ─────────────────────────────────────────────────


def test_flex_basis_uses_max():
    s = _state()
    assert scroll(text("hi"), text("hello"), state=s).flex_basis == 5


def test_flex_basis_empty():
    s = _state()
    assert scroll(state=s).flex_basis == 0


def test_flex_grow_when_child_grows():
    s = _state()
    assert scroll(text("x", grow=1), state=s).grow


def test_flex_grow_fill():
    s = _state()
    assert scroll(text("a"), state=s).grow


# ── height="fill" ───────────────────────────────────────────────────


def test_fill_uses_parent_height():
    s = _state()
    assert clean(
        scroll(text("a"), text("b"), text("c"), text("d"), text("e"), state=s).render(
            80, 3
        )
    ) == ["a", "b", "c"]


def test_fill_with_offset():
    s = _state(2)
    assert clean(scroll(text("a"), text("b"), text("c"), text("d"), state=s).render(80, 2)) == [
        "c",
        "d",
    ]


def test_fill_in_vstack():
    s = _state()
    v = vstack(
        text("header"), scroll(text("a"), text("b"), text("c"), text("d"), state=s)
    )
    assert clean(v.render(80, 4)) == ["header", "a", "b", "c"]


def test_fill_in_vstack_with_multiple_fixed():
    s = _state()
    v = vstack(
        text("top"), scroll(text("a"), text("b"), text("c"), state=s), text("bottom")
    )
    assert clean(v.render(80, 5)) == ["top", "a", "b", "c", "bottom"]


def test_fill_in_vstack_with_spacing():
    s = _state()
    v = vstack(
        text("top"),
        scroll(text("a"), text("b"), text("c"), text("d"), state=s),
        spacing=1,
    )
    assert clean(v.render(80, 5)) == ["top", "", "a", "b", "c"]


def test_fill_returns_empty_without_parent_height():
    s = _state()
    assert clean(scroll(text("a"), state=s).render(80)) == []


def test_fill_clamps_offset():
    s = _state(100)
    assert clean(scroll(text("a"), text("b"), text("c"), state=s).render(80, 2)) == [
        "b",
        "c",
    ]
    assert s.offset == 1


def test_fill_inside_box():
    s = _state()
    b = box(scroll(text("a"), text("b"), text("c"), text("d"), state=s))
    lines = vis(b.render(10, 5))
    assert lines == [
        "╭────────╮",
        "│a·······│",
        "│b·······│",
        "│c·······│",
        "╰────────╯",
    ]


# ── Render feeds back dimensions ────────────────────────────────────


def test_render_feeds_back_fixed_height():
    s = _state()
    scroll(text("a"), text("b"), text("c"), state=s).render(80, 2)
    assert s.height == 2
    assert s.total == 3


def test_render_feeds_back_fill_height():
    s = _state()
    scroll(text("a"), text("b"), state=s).render(80, 10)
    assert s.height == 10
    assert s.total == 2


def test_dimensions_update_on_rerender():
    s = _state()
    scroll(text("a"), text("b"), state=s).render(80, 5)
    assert s.total == 2
    assert s.height == 5
    scroll(text("a"), text("b"), text("c"), text("d"), state=s).render(80, 3)
    assert s.total == 4
    assert s.height == 3


# ── Shared state across renders ─────────────────────────────────────


def test_state_persists_offset_across_renders():
    s = _state()
    s.height = 3
    s.total = 10
    s.scroll_down(5)
    assert clean(scroll(*[text(str(i)) for i in range(10)], state=s).render(80, 3)) == [
        "5",
        "6",
        "7",
    ]


def test_scroll_down_then_render():
    s = _state()
    scroll(text("a"), text("b"), text("c"), text("d"), state=s).render(80, 2)
    s.scroll_down()
    assert clean(
        scroll(text("a"), text("b"), text("c"), text("d"), state=s).render(80, 2)
    ) == ["b", "c"]


def test_page_down_then_render():
    s = _state()
    scroll(*[text(str(i)) for i in range(20)], state=s).render(80, 5)
    s.page_down()
    assert clean(scroll(*[text(str(i)) for i in range(20)], state=s).render(80, 5)) == [
        "5",
        "6",
        "7",
        "8",
        "9",
    ]


def test_page_up_from_middle():
    s = _state()
    scroll(*[text(str(i)) for i in range(20)], state=s).render(80, 5)
    s.scroll_down(10)
    s.page_up()
    assert clean(scroll(*[text(str(i)) for i in range(20)], state=s).render(80, 5)) == [
        "5",
        "6",
        "7",
        "8",
        "9",
    ]


def test_scroll_to_bottom_then_render():
    s = _state()
    scroll(*[text(str(i)) for i in range(10)], state=s).render(80, 3)
    s.scroll_to_bottom()
    assert clean(scroll(*[text(str(i)) for i in range(10)], state=s).render(80, 3)) == [
        "7",
        "8",
        "9",
    ]


def test_scroll_to_top_then_render():
    s = _state(5)
    scroll(*[text(str(i)) for i in range(10)], state=s).render(80, 3)
    s.scroll_to_top()
    assert clean(scroll(*[text(str(i)) for i in range(10)], state=s).render(80, 3)) == [
        "0",
        "1",
        "2",
    ]


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


def test_follow_sticks_to_bottom():
    s = ScrollState(follow=True)
    items = [text(str(i)) for i in range(10)]
    scroll(*items, state=s).render(80, 3)
    assert s.offset == 7

    items.extend(text(str(i)) for i in range(10, 20))
    scroll(*items, state=s).render(80, 3)
    assert s.offset == 17


def test_scroll_up_disables_follow():
    s = ScrollState(follow=True)
    scroll(*[text(str(i)) for i in range(10)], state=s).render(80, 3)
    s.scroll_up(2)
    assert s.follow is False
    assert s.offset == 5

    scroll(*[text(str(i)) for i in range(10)], state=s).render(80, 3)
    assert s.offset == 5


def test_follow_reengages_at_bottom():
    s = ScrollState(follow=True)
    scroll(*[text(str(i)) for i in range(10)], state=s).render(80, 3)
    s.scroll_up(2)
    assert s.follow is False

    s.scroll_down(2)
    scroll(*[text(str(i)) for i in range(10)], state=s).render(80, 3)
    assert s.follow is True


def test_follow_with_growing_content():
    s = ScrollState(follow=True)
    items = [text(str(i)) for i in range(5)]
    scroll(*items, state=s).render(80, 3)
    assert s.offset == 2

    s.scroll_up(1)
    assert s.follow is False

    items.extend([text(str(i)) for i in range(5, 10)])
    scroll(*items, state=s).render(80, 3)
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


def test_scrollbar_returns_one_char_wide():
    s = _state()
    scroll(*[text(str(i)) for i in range(20)], state=s).render(80, 5)
    lines = scrollbar(state=s).render(1, 5)
    assert len(lines) == 5
    for line in lines:
        assert display_width(line) == 1


def test_scrollbar_empty_when_content_fits():
    s = _state()
    scroll(text("a"), text("b"), state=s).render(80, 5)
    lines = scrollbar(state=s).render(1, 5)
    assert all(line == "" for line in lines)


def test_scrollbar_thumb_moves_with_offset():
    items = [text(str(i)) for i in range(100)]

    s1 = _state(0)
    scroll(*items, state=s1).render(80, 10)
    bar_top = [strip_ansi(l) for l in scrollbar(state=s1).render(1, 10)]

    s2 = _state(90)
    scroll(*items, state=s2).render(80, 10)
    bar_bot = [strip_ansi(l) for l in scrollbar(state=s2).render(1, 10)]

    assert bar_top != bar_bot


def test_scrollbar_composes_with_hstack():
    s = _state()
    view = vstack(
        hstack(
            scroll(*[text(str(i)) for i in range(20)], state=s),
            scrollbar(state=s),
            grow=1,
        ),
    )
    lines = view.render(20, 5)
    assert len(lines) == 5


def test_scrollbar_custom_render_fn():
    def my_bar(h: int, total: int, offset: int) -> list[str]:
        return ["X"] * h

    s = _state()
    scroll(*[text(str(i)) for i in range(20)], state=s).render(80, 3)
    assert scrollbar(state=s, render_fn=my_bar).render(1, 3) == ["X", "X", "X"]


def test_scrollbar_default_fn_directly():
    col = scrollbar_default(10, 100, 0)
    assert len(col) == 10
    assert any(strip_ansi(c) == "┃" for c in col[:3])


def test_scrollbar_default_at_bottom():
    col = scrollbar_default(10, 100, 90)
    assert len(col) == 10
    assert any(strip_ansi(c) == "┃" for c in col[-3:])


def test_scrollbar_default_content_fits():
    col = scrollbar_default(10, 5, 0)
    assert all(c == "" for c in col)


def test_scrollbar_default_single_row():
    col = scrollbar_default(1, 100, 0)
    assert len(col) == 1
    assert strip_ansi(col[0]) == "┃"


def test_scrollbar_default_monotonic():
    def thumb_top(offset: int) -> int:
        col = scrollbar_default(20, 200, offset)
        for i, c in enumerate(col):
            if strip_ansi(c) == "┃":
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


def test_scroll_and_scrollbar_share_state():
    s = ScrollState()
    items = [text(str(i)) for i in range(50)]
    scroll(*items, state=s).render(80, 10)
    assert s.height == 10
    assert s.total == 50
    bar = scrollbar(state=s).render(1, 10)
    assert len(bar) == 10
    assert any(strip_ansi(c) == "┃" for c in bar)


def test_follow_tracks_growing_content_end_to_end():
    s = ScrollState(follow=True)
    items = [text(str(i)) for i in range(5)]
    assert clean(scroll(*items, state=s).render(80, 3)) == ["2", "3", "4"]

    items.extend(text(str(i)) for i in range(5, 15))
    assert clean(scroll(*items, state=s).render(80, 3)) == ["12", "13", "14"]

    s.scroll_up(5)
    assert clean(scroll(*items, state=s).render(80, 3)) == ["7", "8", "9"]

    items.extend(text(str(i)) for i in range(15, 25))
    assert clean(scroll(*items, state=s).render(80, 3)) == ["7", "8", "9"]

    s.scroll_to_bottom()
    assert clean(scroll(*items, state=s).render(80, 3)) == ["22", "23", "24"]

    items.extend(text(str(i)) for i in range(25, 30))
    assert clean(scroll(*items, state=s).render(80, 3)) == ["27", "28", "29"]
