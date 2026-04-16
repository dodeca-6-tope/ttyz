"""Tests for ZStack component."""

from conftest import SnapFn

from ttyz import box, cond, text, vstack, zstack
from ttyz.components.base import Custom
from ttyz.components.scroll import ScrollState


def _block(char: str, w: int, h: int) -> Custom:
    def render_fn(width: int, height: int | None = None) -> list[str]:
        return [char * w] * h

    return Custom(render_fn, width=str(w))


def _grower(char: str = "X") -> Custom:
    def render_fn(width: int, height: int | None = None) -> list[str]:
        return [char * width] * (height or 1)

    return Custom(render_fn, grow=1)


# ── Canvas sizing ─────────────────────────────────────────────────


def test_canvas_height_from_first_child(snap: SnapFn):
    base = vstack(text("a"), text("b"), text("c"))
    overlay = vstack(*[text(str(i)) for i in range(10)])
    snap(zstack(base, overlay), 20)


def test_canvas_height_uses_h(snap: SnapFn):
    snap(zstack(_grower(), text("overlay")), 20, 10)


def test_canvas_height_uses_h_even_without_grower(snap: SnapFn):
    snap(zstack(_block(".", 10, 3)), 10, 7)


def test_canvas_width_uses_w(snap: SnapFn):
    snap(zstack(_block(".", 5, 2)), 20)


def test_default_alignment_is_top_left(snap: SnapFn):
    snap(zstack(_block("X", 3, 2)), 10, 5)


def test_alignment_uses_declared_width(snap: SnapFn):
    child = vstack(text("very long content"), width="8", height="1")
    snap(zstack(child, justify_content="center"), 30, 1)


def test_alignment_uses_rendered_width_without_declared(snap: SnapFn):
    snap(zstack(text("hello"), justify_content="center"), 30, 1)


def test_all_children_render_within_canvas(snap: SnapFn):
    snap(zstack(_block(".", 10, 3), _block("X", 5, 1)), 10, 5)


# ── Alignment ────────────────────────────────────────────────────


def test_all_9_alignments(snap: SnapFn):
    canvas_w, canvas_h = 20, 7
    overlay = _block("X", 3, 3)
    for jc, ai in [
        ("start", "start"),
        ("center", "start"),
        ("end", "start"),
        ("start", "center"),
        ("center", "center"),
        ("end", "center"),
        ("start", "end"),
        ("center", "end"),
        ("end", "end"),
    ]:
        snap(
            zstack(overlay, justify_content=jc, align_items=ai),
            canvas_w,
            canvas_h,
            name=f"align_{jc}_{ai}",
        )


def test_top_center(snap: SnapFn):
    snap(
        zstack(_block("X", 4, 2), justify_content="center", align_items="start"), 20, 10
    )


def test_center_left(snap: SnapFn):
    snap(zstack(_block("X", 4, 2), align_items="center"), 20, 10)


# ── Overlay alignment ────────────────────────────────────────────


def test_center_alignment(snap: SnapFn):
    base = vstack(text("." * 20), text("." * 20), text("." * 20))
    snap(
        zstack(base, text("HI"), justify_content="center", align_items="center"),
        20,
    )


def test_bottom_right_alignment(snap: SnapFn):
    snap(
        zstack(_block(".", 10, 3), text("X"), justify_content="end", align_items="end"),
        10,
    )


def test_top_left_default(snap: SnapFn):
    snap(zstack(text("." * 10), text("AB")), 10)


# ── Overlay clipping ─────────────────────────────────────────────


def test_overlay_clips_vertically(snap: SnapFn):
    snap(zstack(_block("X", 10, 10)), 10, 3)


def test_overlay_clips_when_offset(snap: SnapFn):
    snap(
        zstack(
            _block(".", 10, 5),
            _block("X", 3, 4),
            justify_content="center",
            align_items="end",
        ),
        10,
    )


def test_overlay_clips_width(snap: SnapFn):
    snap(zstack(_block("X", 15, 1)), 7, 3)


def test_overlay_clips_width_when_offset(snap: SnapFn):
    snap(
        zstack(_block(".", 10, 3), _block("X", 6, 1), justify_content="end"),
        10,
    )


def test_overlay_larger_than_base_clips_both_axes(snap: SnapFn):
    snap(
        zstack(_block("X", 12, 10), justify_content="center", align_items="center"),
        7,
        5,
    )


# ── Height pass-through ──────────────────────────────────────────


def test_height_passed_to_growers(snap: SnapFn):
    from ttyz import scroll

    s = ScrollState()
    items = [text(str(i)) for i in range(20)]
    snap(zstack(scroll(*items, state=s), text("HI")), 10, 5)
    assert s.height == 5


# ── Nested ZStacks ───────────────────────────────────────────────


def test_nested_zstack_preserves_inner_width(snap: SnapFn):
    inner = zstack(_block("X", 4, 1), justify_content="center", align_items="center")
    snap(inner, 40, 3)


def test_nested_zstack_positions_correctly(snap: SnapFn):
    inner = zstack(
        _block("B", 10, 3),
        _block("X", 2, 1),
        justify_content="center",
        align_items="center",
    )
    snap(zstack(inner, justify_content="center", align_items="center"), 30, 9)


def test_block_positioned_at_all_9_spots(snap: SnapFn):
    outer_w, outer_h = 30, 9
    block = _block("B", 6, 3)
    for jc, ai in [
        ("start", "start"),
        ("center", "start"),
        ("end", "start"),
        ("start", "center"),
        ("center", "center"),
        ("end", "center"),
        ("start", "end"),
        ("center", "end"),
        ("end", "end"),
    ]:
        snap(
            zstack(block, justify_content=jc, align_items=ai),
            outer_w,
            outer_h,
            name=f"block_9_{jc}_{ai}",
        )


def test_nested_zstack_at_all_9_spots(snap: SnapFn):
    outer_w, outer_h = 30, 9
    inner_base = _block("B", 6, 3)
    inner_overlay = _block("X", 2, 1)
    for jc, ai in [
        ("start", "start"),
        ("center", "start"),
        ("end", "start"),
        ("start", "center"),
        ("center", "center"),
        ("end", "center"),
        ("start", "end"),
        ("center", "end"),
        ("end", "end"),
    ]:
        combo = zstack(
            inner_base,
            inner_overlay,
            justify_content="center",
            align_items="center",
        )
        snap(
            zstack(combo, justify_content=jc, align_items=ai),
            outer_w,
            outer_h,
            name=f"nested_9_{jc}_{ai}",
        )


# ── Flex properties ──────────────────────────────────────────────


def test_intrinsic_width(snap: SnapFn):
    """ZStack intrinsic width is max of children."""
    from ttyz import hstack

    snap(hstack(zstack(text("short"), text("longer text")), text("|")), 20)


def test_grow_not_propagated():
    from ttyz import scroll

    assert not zstack(text("hi"), text("fill", grow=1)).grow
    assert not zstack(text("hi"), text("no")).grow

    s = ScrollState()
    assert not zstack(scroll(text("a"), state=s)).grow


# ── Edge cases ───────────────────────────────────────────────────


def test_empty(snap: SnapFn):
    snap(zstack(), 10)


def test_single_child(snap: SnapFn):
    snap(zstack(text("hello")), 20)


def test_top_layer_overwrites(snap: SnapFn):
    snap(zstack(text("aaaa"), text("bb")), 10)


def test_empty_overlay_preserves_base(snap: SnapFn):
    snap(zstack(text("visible"), cond(False, text("hidden"))), 20)


def test_box_overlay_centered(snap: SnapFn):
    base = vstack(*[text("." * 30) for _ in range(5)])
    overlay = box(text("Alert!"), style="normal", padding=1)
    snap(
        zstack(base, overlay, justify_content="center", align_items="center"),
        30,
    )


# ── ANSI / styling preservation ──────────────────────────────────


def test_overlay_preserves_base_styling(snap: SnapFn):
    from ttyz import bold

    snap(zstack(text(bold("hello world")), text("XX")), 20)


def test_overlay_preserves_base_color(snap: SnapFn):
    from ttyz import color

    snap(zstack(text(color(1, "aaabbbccc")), text("XX")), 20)


# ── Wide character handling ──────────────────────────────────────


def test_split_at_col_wide_chars(snap: SnapFn):
    snap(zstack(text("你好世界xxxx"), text("AB")), 20)


def test_overlay_on_wide_char_base(snap: SnapFn):
    snap(
        zstack(
            text("你好世界"),
            text("AB"),
            justify_content="center",
            align_items="center",
        ),
        8,
    )


# ── Validation ───────────────────────────────────────────────────


def test_invalid_justify_content_raises():
    import pytest

    with pytest.raises(ValueError, match="unknown justify_content"):
        zstack(text("x"), justify_content="middle")


def test_invalid_align_items_raises():
    import pytest

    with pytest.raises(ValueError, match="unknown align_items"):
        zstack(text("x"), align_items="middle")


# ── ANSI handling ───────────────────────────────────────────────────


def test_non_sgr_csi_not_treated_as_style(snap: SnapFn):
    """Non-SGR CSI (cursor move) in base must not corrupt overlay output."""
    from ttyz.components.base import Custom

    def base_render(w: int, h: int | None = None) -> list[str]:
        return ["\033[31mA\033[10;20H" + "B" * (w - 2) + "\033[0m"]

    def overlay_render(w: int, h: int | None = None) -> list[str]:
        return ["X"]

    base = Custom(base_render, width="10")
    overlay = Custom(overlay_render, width="1")
    snap(zstack(base, overlay), 10, 1)


def test_non_sgr_csi_split_preserves_visible_text(snap: SnapFn):
    """Non-SGR CSI in base must not eat visible characters during overlay stamp."""
    from ttyz.components.base import Custom

    def base_render(w: int, h: int | None = None) -> list[str]:
        return ["A\033[3JBC" + " " * (w - 4)]

    def overlay_render(w: int, h: int | None = None) -> list[str]:
        return ["X"]

    base = Custom(base_render, width="10")
    overlay = Custom(overlay_render, width="1")
    snap(zstack(base, overlay), 10, 1)


def test_empty_string_overlay_preserves_base(snap: SnapFn):
    """An empty-string overlay should not corrupt the base layer."""
    snap(zstack(text("hello world"), text("")), 20, 1)
