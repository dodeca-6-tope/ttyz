"""Tests for ZStack component."""

from helpers import vis

from terminal import box, cond, text, vstack, zstack
from terminal.components.base import Renderable
from terminal.components.scroll import ScrollState
from terminal.measure import display_width


def _block(char: str, w: int, h: int) -> Renderable:
    def render(width: int, height: int | None = None) -> list[str]:
        return [char * w] * h

    return Renderable(render, flex_basis=w)


def _grower(char: str = "X") -> Renderable:
    def render(width: int, height: int | None = None) -> list[str]:
        return [char * width] * (height or 1)

    return Renderable(render, grow=1)


# ── Canvas sizing ─────────────────────────────────────────────────


def test_canvas_height_from_first_child():
    base = vstack(text("a"), text("b"), text("c"))  # 3 lines
    overlay = vstack(*[text(str(i)) for i in range(10)])  # 10 lines
    assert len(zstack(base, overlay).render(20)) == 3


def test_canvas_height_uses_h():
    assert len(zstack(_grower(), text("overlay")).render(20, 10)) == 10


def test_canvas_height_uses_h_even_without_grower():
    assert len(zstack(_block(".", 10, 3)).render(10, 7)) == 7


def test_canvas_width_uses_w():
    lines = vis(zstack(_block(".", 5, 2)).render(20))
    assert all(len(l) == 20 for l in lines)


def test_default_alignment_is_top_left():
    assert vis(zstack(_block("X", 3, 2)).render(10, 5)) == [
        "XXX·······",
        "XXX·······",
        "··········",
        "··········",
        "··········",
    ]


def test_alignment_uses_declared_width():
    child = vstack(text("very long content"), width="8", height="1")
    lines = vis(zstack(child, justify_content="center").render(30, 1))
    pos = lines[0].index("v")
    assert pos == 11  # centered: (30-8)//2


def test_alignment_uses_rendered_width_without_declared():
    child = text("hello")  # 5 chars
    lines = vis(zstack(child, justify_content="center").render(30, 1))
    pos = lines[0].index("h")
    assert pos == 12  # centered: (30-5)//2


def test_all_children_render_within_canvas():
    lines = vis(zstack(_block(".", 10, 3), _block("X", 5, 1)).render(10, 5))
    assert len(lines) == 5
    assert all(len(l) <= 10 for l in lines)


# ── Alignment ────────────────────────────────────────────────────


def test_all_9_alignments_distinct():
    canvas_w, canvas_h = 20, 7
    overlay = _block("X", 3, 3)
    positions: set[tuple[int, int]] = set()
    combos = [
        ("start", "start"),
        ("center", "start"),
        ("end", "start"),
        ("start", "center"),
        ("center", "center"),
        ("end", "center"),
        ("start", "end"),
        ("center", "end"),
        ("end", "end"),
    ]
    for jc, ai in combos:
        lines = vis(
            zstack(overlay, justify_content=jc, align_items=ai).render(
                canvas_w, canvas_h
            )
        )
        row = next(r for r, l in enumerate(lines) if "X" in l)
        col = lines[row].index("X")
        positions.add((row, col))
    assert len(positions) == 9


def test_top_center():
    overlay = _block("X", 4, 2)
    lines = vis(
        zstack(overlay, justify_content="center", align_items="start").render(20, 10)
    )
    assert lines[0].index("X") == 8  # (20-4)//2
    assert "X" not in lines[2]


def test_center_left():
    overlay = _block("X", 4, 2)
    lines = vis(zstack(overlay, align_items="center").render(20, 10))
    row = next(r for r, l in enumerate(lines) if "X" in l)
    assert row == 4  # (10-2)//2
    assert lines[row].index("X") == 0


# ── Overlay alignment ────────────────────────────────────────────


def test_center_alignment():
    base = vstack(text("." * 20), text("." * 20), text("." * 20))
    lines = vis(
        zstack(base, text("HI"), justify_content="center", align_items="center").render(20)
    )
    assert lines[1].index("H") == 9  # (20-2)//2


def test_bottom_right_alignment():
    assert vis(
        zstack(_block(".", 10, 3), text("X"), justify_content="end", align_items="end").render(10)
    ) == [
        "..........",
        "..........",
        ".........X",
    ]


def test_top_left_default():
    assert vis(zstack(text("." * 10), text("AB")).render(10)) == ["AB........"]


# ── Overlay clipping ─────────────────────────────────────────────


def test_overlay_clips_vertically():
    assert len(zstack(_block("X", 10, 10)).render(10, 3)) == 3


def test_overlay_clips_when_offset():
    lines = vis(
        zstack(_block(".", 10, 5), _block("X", 3, 4), justify_content="center", align_items="end").render(10)
    )
    assert len(lines) == 5
    assert "X" in lines[4]


def test_overlay_clips_width():
    lines = vis(zstack(_block("X", 15, 1)).render(7, 3))
    assert lines == [
        "XXXXXXX",
        "·······",
        "·······",
    ]


def test_overlay_clips_width_when_offset():
    lines = vis(zstack(_block(".", 10, 3), _block("X", 6, 1), justify_content="end").render(10))
    assert len(lines[0]) == 10
    assert lines[0].count("X") == 6


def test_overlay_larger_than_base_clips_both_axes():
    lines = vis(
        zstack(_block("X", 12, 10), justify_content="center", align_items="center").render(7, 5)
    )
    assert len(lines) == 5
    assert all(len(l) == 7 for l in lines)


# ── Height pass-through ──────────────────────────────────────────


def test_height_passed_to_growers():
    from terminal import scroll

    s = ScrollState()
    items = [text(str(i)) for i in range(20)]
    lines = zstack(scroll(*items, state=s), text("HI")).render(10, 5)
    assert len(lines) == 5
    assert s.height == 5


# ── Nested ZStacks ───────────────────────────────────────────────


def test_nested_zstack_preserves_inner_width():
    inner = zstack(_block("X", 4, 1), justify_content="center", align_items="center")
    inner_lines = inner.render(40, 3)
    for line in inner_lines:
        assert display_width(line) == 40


def test_nested_zstack_positions_correctly():
    inner = zstack(
        _block("B", 10, 3),
        _block("X", 2, 1),
        justify_content="center",
        align_items="center",
    )
    lines = vis(
        zstack(inner, justify_content="center", align_items="center").render(30, 9)
    )
    assert "B" in lines[3]
    assert lines[3].index("B") == 10


def test_block_positioned_at_all_9_spots():
    outer_w, outer_h = 30, 9
    block = _block("B", 6, 3)

    expected = {
        ("start", "start"): (0, 0),
        ("center", "start"): (0, 12),
        ("end", "start"): (0, 24),
        ("start", "center"): (3, 0),
        ("center", "center"): (3, 12),
        ("end", "center"): (3, 24),
        ("start", "end"): (6, 0),
        ("center", "end"): (6, 12),
        ("end", "end"): (6, 24),
    }
    for (jc, ai), (exp_row, exp_col) in expected.items():
        lines = vis(
            zstack(block, justify_content=jc, align_items=ai).render(outer_w, outer_h)
        )
        assert lines[exp_row].index("B") == exp_col, (
            f"jc={jc},ai={ai}: expected col {exp_col}, got {lines[exp_row].index('B')}"
        )
        assert "B" not in lines[exp_row - 1] if exp_row > 0 else True


def test_nested_zstack_at_all_9_spots():
    outer_w, outer_h = 30, 9
    inner_base = _block("B", 6, 3)
    inner_overlay = _block("X", 2, 1)

    combos = [
        ("start", "start"),
        ("center", "start"),
        ("end", "start"),
        ("start", "center"),
        ("center", "center"),
        ("end", "center"),
        ("start", "end"),
        ("center", "end"),
        ("end", "end"),
    ]

    for jc, ai in combos:
        combo = zstack(
            inner_base,
            inner_overlay,
            justify_content="center",
            align_items="center",
        )
        lines = vis(
            zstack(combo, justify_content=jc, align_items=ai).render(outer_w, outer_h)
        )
        assert len(lines) == outer_h
        assert any("B" in l for l in lines), f"jc={jc},ai={ai}: inner base not visible"
        assert any("X" in l for l in lines), f"jc={jc},ai={ai}: inner overlay not visible"


# ── Flex properties ──────────────────────────────────────────────


def test_flex_basis_is_max():
    assert zstack(text("short"), text("longer text")).flex_basis == 11


def test_grow_not_propagated():
    from terminal import scroll

    assert not zstack(text("hi"), text("fill", grow=1)).grow
    assert not zstack(text("hi"), text("no")).grow

    s = ScrollState()
    assert not zstack(scroll(text("a"), state=s)).grow


# ── Edge cases ───────────────────────────────────────────────────


def test_empty():
    assert vis(zstack().render(10)) == [""]


def test_single_child():
    lines = vis(zstack(text("hello")).render(20))
    assert lines[0].startswith("hello")


def test_top_layer_overwrites():
    assert vis(zstack(text("aaaa"), text("bb")).render(10)) == ["bbaa······"]


def test_empty_overlay_preserves_base():
    lines = vis(zstack(text("visible"), cond(False, text("hidden"))).render(20))
    assert "visible" in lines[0]


def test_box_overlay_centered():
    base = vstack(*[text("." * 30) for _ in range(5)])
    overlay = box(text("Alert!"), style="normal", padding=1)
    assert vis(
        zstack(base, overlay, justify_content="center", align_items="center").render(30)
    ) == [
        "..............................",
        "..........┌────────┐..........",
        "..........│·Alert!·│..........",
        "..........└────────┘..........",
        "..............................",
    ]


# ── ANSI / styling preservation ──────────────────────────────────


def test_overlay_preserves_base_styling():
    from terminal import bold

    base = text(bold("hello world"))
    overlay = text("XX")
    lines = zstack(base, overlay).render(20)
    raw = lines[0]
    after_overlay = raw.split("XX", 1)[1]
    assert "\033[1m" in after_overlay


def test_overlay_preserves_base_color():
    from terminal import color

    base = text(color(1, "aaabbbccc"))
    overlay = text("XX")
    lines = zstack(base, overlay).render(20)
    raw = lines[0]
    after_overlay = raw.split("XX", 1)[1]
    assert "\033[38;5;1m" in after_overlay


# ── Wide character handling ──────────────────────────────────────


def test_split_at_col_wide_chars():
    lines = vis(zstack(text("你好世界xxxx"), text("AB")).render(20))
    assert lines[0].startswith("AB")
    assert "好" in lines[0]


def test_overlay_on_wide_char_base():
    lines = vis(
        zstack(text("你好世界"), text("AB"), justify_content="center", align_items="center").render(8)
    )
    assert "AB" in lines[0]


# ── Validation ───────────────────────────────────────────────────


def test_invalid_justify_content_raises():
    import pytest

    with pytest.raises(ValueError, match="unknown justify_content"):
        zstack(text("x"), justify_content="middle")


def test_invalid_align_items_raises():
    import pytest

    with pytest.raises(ValueError, match="unknown align_items"):
        zstack(text("x"), align_items="middle")
