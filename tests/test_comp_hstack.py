"""Tests for HStack component."""

from helpers import vis

from ttyz import cond, hstack, scroll, text, vstack
from ttyz.components.scroll import ScrollState

# ── Fixed layout ─────────────────────────────────────────────────────


def test_side_by_side():
    assert vis(hstack(text("a"), text("b"), spacing=1).render(20)) == ["a·b"]


def test_spacing():
    assert vis(hstack(text("a"), text("b"), spacing=3).render(20)) == ["a···b"]


def test_percentage_width_reserves_column_space():
    assert vis(hstack(text("A", width="50%"), text("B"), spacing=1).render(20)) == [
        "A··········B",
    ]


def test_cond_false_invisible():
    assert vis(hstack(cond(False, text("gone")), text("here")).render(80)) == ["here"]


def test_empty():
    assert vis(hstack().render(80)) == [""]


def test_multiline_children():
    assert vis(
        hstack(vstack(text("a"), text("b")), text("c"), spacing=1).render(20)
    ) == [
        "a·c",
        "b··",
    ]


# ── Justify ──────────────────────────────────────────────────────────


def test_justify_between():
    assert vis(hstack(text("L"), text("R"), justify_content="between").render(20)) == [
        "L··················R",
    ]


def test_justify_end():
    assert vis(hstack(text("hi"), justify_content="end").render(20)) == [
        "··················hi",
    ]


def test_justify_center():
    assert vis(hstack(text("hi"), justify_content="center").render(20)) == [
        "·········hi",
    ]


def test_justify_between_single_child():
    assert vis(hstack(text("only"), justify_content="between").render(20)) == ["only"]


def test_justify_between_nested():
    inner = hstack(text("L"), text("R"), justify_content="between", grow=1)
    assert vis(hstack(inner).render(20)) == [
        "L··················R",
    ]


# ── Wrap ─────────────────────────────────────────────────────────────


def test_wrap_fits_one_line():
    assert vis(hstack(text("aa"), text("bb"), wrap=True, spacing=1).render(10)) == [
        "aa·bb",
    ]


def test_wrap_breaks_to_next_line():
    assert vis(hstack(text("aa"), text("bb"), wrap=True, spacing=1).render(4)) == [
        "aa",
        "bb",
    ]


def test_wrap_empty():
    assert vis(hstack(wrap=True).render(80)) == [""]


def test_wrap_many_chunks():
    chunks = [text("[a] one"), text("[b] two"), text("[c] three"), text("[d] four")]
    assert vis(hstack(*chunks, wrap=True, spacing=1).render(24)) == [
        "[a]·one·[b]·two",
        "[c]·three·[d]·four",
    ]


def test_wrap_boundary():
    #                     3 + 1 + 3 = 7 → fits exactly
    assert vis(hstack(text("aaa"), text("bbb"), wrap=True, spacing=1).render(7)) == [
        "aaa·bbb",
    ]
    #                     one short → wraps
    assert vis(hstack(text("aaa"), text("bbb"), wrap=True, spacing=1).render(6)) == [
        "aaa",
        "bbb",
    ]


def test_wrap_respects_spacing():
    assert vis(hstack(text("aaa"), text("bbb"), wrap=True, spacing=3).render(9)) == [
        "aaa···bbb",
    ]
    assert vis(hstack(text("aaa"), text("bbb"), wrap=True, spacing=3).render(8)) == [
        "aaa",
        "bbb",
    ]


def test_wrap_preserves_ansi():
    green, rst = "\033[32m", "\033[0m"
    chunks = [text(f"{green}[⏎]{rst} select"), text("[esc] back")]
    assert vis(hstack(*chunks, wrap=True, spacing=1).render(25)) == [
        "[⏎]·select·[esc]·back",
    ]


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


def test_height_passed_to_scroll_child():
    s = ScrollState()
    view = vstack(
        hstack(
            scroll(*[text(str(i)) for i in range(20)], state=s),
            text("R"),
            grow=1,
        ),
    )
    view.render(20, 10)
    assert s.height == 10


def test_height_not_passed_to_fixed_child():
    s = ScrollState()
    view = vstack(
        hstack(
            scroll(*[text(str(i)) for i in range(20)], state=s),
            text("side"),
            grow=1,
        ),
    )
    lines = view.render(40, 8)
    assert len(lines) == 8
    assert s.height == 8


def test_grow_not_propagated():
    s = ScrollState()
    assert not hstack(scroll(text("a"), state=s), text("b")).grow


def test_hstack_in_vstack_scroll_gets_remaining_height():
    s = ScrollState()
    view = vstack(
        text("header"),
        hstack(
            scroll(*[text(str(i)) for i in range(50)], state=s),
            grow=1,
        ),
        text("footer"),
    )
    lines = view.render(20, 12)
    assert len(lines) == 12
    assert s.height == 10
    assert vis([lines[0]]) == ["header"]
    assert vis([lines[11]]) == ["footer"]


def test_bg_fills_flex_allocated_height():
    from helpers import clean

    from ttyz import spacer

    v = vstack(
        hstack(text(""), grow=1, bg=1),
        spacer(),
        bg=2,
    )
    assert len(clean(v.render(10, 10))) == 10


# ── Nested flat path offsets ────────────────────────────────────────


def test_nested_hstack_flat_offsets():
    inner = hstack(text("ab"), text("cd"), spacing=1)
    outer = hstack(inner, text("X"), spacing=1)
    assert vis(outer.render(20)) == ["ab·cd·X"]


def test_nested_hstack_flat_offsets_deep():
    a = hstack(text("AAA"), text("BBB"), spacing=1)
    b = hstack(a, text("CCC"), spacing=1)
    c = hstack(b, text("DDD"), spacing=1)
    assert vis(c.render(30)) == ["AAA·BBB·CCC·DDD"]


def test_nested_hstack_flat_total_width():
    from ttyz.measure import display_width, strip_ansi

    inner = hstack(text("hello"), text("world"), spacing=1)
    outer = hstack(inner, text("!"), spacing=1)
    lines = outer.render(30)
    assert display_width(strip_ansi(lines[0])) >= len("hello world !")


def test_all_hidden_cond_children():
    h = hstack(cond(False, text("a")), cond(False, text("b")))
    lines = h.render(80)
    assert lines == [""]
