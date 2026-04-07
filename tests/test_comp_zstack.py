"""Tests for ZStack component."""

from terminal import box, text, vstack, zstack
from terminal.components.base import Component
from terminal.components.scroll import ScrollState
from terminal.components.zstack import _offsets
from terminal.measure import display_width, strip_ansi


def clean(lines: list[str]) -> list[str]:
    return [strip_ansi(l) for l in lines]


class _Block(Component):
    """Fixed-size block for testing."""

    def __init__(self, char: str, w: int, h: int) -> None:
        self._char = char
        self._w = w
        self._h = h

    def flex_basis(self) -> int:
        return self._w

    def render(self, width: int, height: int | None = None) -> list[str]:
        return [self._char * self._w] * self._h


class _Grower(Component):
    """Component that grows to fill available space."""

    def __init__(self, char: str = "X") -> None:
        self._char = char

    def flex_grow_width(self) -> int:
        return 1

    def flex_grow_height(self) -> int:
        return 1

    def render(self, width: int, height: int | None = None) -> list[str]:
        return [self._char * width] * (height or 1)


# ── Canvas sizing ─────────────────────────────────────────────────


def test_canvas_height_is_first_child():
    base = vstack(text("a"), text("b"), text("c"))  # 3 lines
    overlay = vstack(*[text(str(i)) for i in range(10)])  # 10 lines
    lines = zstack(base, overlay).render(20)
    assert len(lines) == 3


def test_canvas_height_ignores_parent_height_when_no_grower():
    """A non-growing ZStack ignores parent height for canvas sizing."""
    base = vstack(text("a"), text("b"))  # 2 lines
    z = zstack(base, text("X"))
    lines = z.render(20, 50)
    assert len(lines) == 2


def test_canvas_height_uses_grower():
    """When the first child grows, it receives height and defines the canvas."""
    z = zstack(_Grower(), text("overlay"))
    lines = z.render(20, 10)
    assert len(lines) == 10


def test_canvas_width_matches_first_child_when_no_grower():
    base = _Block(".", 15, 3)
    overlay = _Block("X", 5, 1)
    lines = clean(zstack(base, overlay).render(40))
    assert all(display_width(l) == 15 for l in lines)


def test_canvas_width_uses_parent_when_grower():
    z = zstack(_Grower("."), text("X"))
    lines = clean(z.render(30, 3))
    assert all(display_width(l) == 30 for l in lines)


# ── First child positioning ───────────────────────────────────────


def test_first_child_always_top_left():
    """First child is placed at top-left regardless of alignment."""
    base = _Block("B", 10, 3)
    overlay = _Block("O", 3, 1)
    lines = clean(zstack(base, overlay, align="bottom-right").render(20))
    # Base starts at row 0, col 0
    assert lines[0].startswith("B")
    assert lines[2].startswith("B")


# ── Overlay alignment ────────────────────────────────────────────


def test_all_9_alignments_distinct():
    """Every alignment produces a unique (row, col) offset."""
    aligns = [
        "top-left", "top", "top-right",
        "left", "center", "right",
        "bottom-left", "bottom", "bottom-right",
    ]
    positions = set()
    for align in aligns:
        pos = _offsets(align, (20, 7), (3, 3))
        positions.add(pos)
    assert len(positions) == 9


def test_single_axis_centers_other():
    """'top' centers horizontally, 'left' centers vertically."""
    top = _offsets("top", (20, 10), (4, 2))
    top_left = _offsets("top-left", (20, 10), (4, 2))
    assert top[0] == 0  # top row
    assert top[1] == 8  # centered horizontally: (20-4)//2
    assert top_left[1] == 0  # left

    left = _offsets("left", (20, 10), (4, 2))
    assert left[0] == 4  # centered vertically: (10-2)//2
    assert left[1] == 0  # left


def test_overlay_aligns_within_first_child_bounds():
    """Overlay centers within the first child, not the parent width."""
    base = _Block(".", 20, 7)
    overlay = _Block("X", 4, 1)
    lines = clean(zstack(base, overlay, align="center").render(60))
    mid = lines[3]
    x_pos = mid.index("XXXX")
    assert x_pos == 8  # (20-4)//2


def test_center_alignment():
    base = vstack(text("." * 20), text("." * 20), text("." * 20))
    overlay = text("HI")
    lines = clean(zstack(base, overlay, align="center").render(20))
    mid = lines[1]
    hi_pos = mid.index("H")
    assert hi_pos == 9  # (20 - 2) // 2


def test_bottom_right_alignment():
    base = _Block(".", 10, 3)
    overlay = text("X")
    lines = clean(zstack(base, overlay, align="bottom-right").render(10))
    assert lines[2].rstrip().endswith("X")


def test_top_left_default():
    lines = clean(zstack(text("." * 10), text("AB")).render(10))
    assert lines[0].startswith("AB")


# ── Overlay clipping ─────────────────────────────────────────────


def test_overlay_clips_vertically():
    """Overlay taller than base is clipped to base height."""
    base = _Block(".", 10, 3)
    overlay = _Block("X", 10, 10)
    lines = zstack(base, overlay).render(10)
    assert len(lines) == 3


def test_overlay_clips_when_offset():
    """Overlay at bottom that would exceed base is clipped."""
    base = _Block(".", 10, 5)
    overlay = _Block("X", 3, 4)
    lines = clean(zstack(base, overlay, align="bottom").render(10))
    assert len(lines) == 5
    # Overlay should appear on the bottom rows, partially clipped
    assert "X" in lines[4]


def test_overlay_clips_width():
    """Overlay wider than base is clipped to base width."""
    base = _Block(".", 7, 3)
    overlay = _Block("X", 15, 1)
    lines = clean(zstack(base, overlay).render(7))
    assert all(display_width(l) == 7 for l in lines)
    assert "X" * 7 == lines[0]


def test_overlay_clips_width_when_offset():
    """Overlay at right edge that would exceed base is clipped."""
    base = _Block(".", 10, 3)
    overlay = _Block("X", 6, 1)
    lines = clean(zstack(base, overlay, align="right").render(10))
    # Overlay at col 4, width 6 — should clip to 6 (fits: 4+6=10)
    assert display_width(lines[1]) == 10
    assert lines[1].count("X") == 6


def test_overlay_larger_than_base_clips_both_axes():
    """Overlay larger than base in both dimensions clips to base bounds."""
    base = _Block(".", 7, 5)
    overlay = _Block("X", 12, 10)
    lines = clean(zstack(base, overlay, align="center").render(7))
    assert len(lines) == 5
    assert all(display_width(l) == 7 for l in lines)


# ── Height pass-through ──────────────────────────────────────────


def test_height_passed_to_growers():
    from terminal import scroll

    s = ScrollState()
    items = [text(str(i)) for i in range(20)]
    base = scroll(*items, state=s)
    overlay = text("HI")
    lines = zstack(base, overlay).render(10, 5)
    assert len(lines) == 5
    assert s.height == 5


def test_height_not_passed_to_non_growers():
    """Non-growing children render at natural size regardless of height."""
    base = _Block(".", 10, 3)
    overlay = _Block("X", 5, 1)
    # Even though height=20 is passed, canvas = base = 3 lines
    lines = zstack(base, overlay).render(10, 20)
    assert len(lines) == 3


# ── Nested ZStacks ───────────────────────────────────────────────


def test_nested_zstack_preserves_inner_width():
    """Inner ZStack output width = first child width, not parent width."""
    inner_base = _Block("B", 10, 3)
    inner_overlay = _Block("X", 4, 1)
    inner = zstack(inner_base, inner_overlay, align="center")

    inner_lines = inner.render(40)
    # Inner should be 10 wide, not 40
    for line in inner_lines:
        assert display_width(line) == 10


def test_nested_zstack_positions_correctly():
    """Inner ZStack can be positioned within an outer ZStack."""
    inner = zstack(_Block("B", 10, 3), _Block("X", 2, 1), align="center")
    outer_base = _Block(" ", 30, 9)
    lines = clean(zstack(outer_base, inner, align="center").render(30))

    # Inner block (10 wide) centered in outer (30 wide) -> col 10
    # Inner block (3 tall) centered in outer (9 tall) -> row 3
    assert "B" in lines[3]
    b_pos = lines[3].index("B")
    assert b_pos == 10


def test_block_positioned_at_all_9_spots():
    """A small block placed at each alignment lands at the expected offset."""
    outer_w, outer_h = 30, 9
    block_w, block_h = 6, 3
    outer_base = _Block(" ", outer_w, outer_h)
    block = _Block("B", block_w, block_h)

    expected = {
        "top-left": (0, 0),
        "top": (0, 12),
        "top-right": (0, 24),
        "left": (3, 0),
        "center": (3, 12),
        "right": (3, 24),
        "bottom-left": (6, 0),
        "bottom": (6, 12),
        "bottom-right": (6, 24),
    }
    for align, (exp_row, exp_col) in expected.items():
        lines = clean(zstack(outer_base, block, align=align).render(outer_w))
        # Find where the block content starts
        b_pos = lines[exp_row].index("B")
        assert b_pos == exp_col, f"{align}: expected col {exp_col}, got {b_pos}"
        assert "B" not in lines[exp_row - 1] if exp_row > 0 else True


def test_nested_zstack_at_all_9_spots():
    """Nested ZStack (block + overlay) positioned at all 9 spots."""
    outer_w, outer_h = 30, 9
    inner_base = _Block("B", 6, 3)
    inner_overlay = _Block("X", 2, 1)
    outer_base = _Block(" ", outer_w, outer_h)

    for align in [
        "top-left", "top", "top-right",
        "left", "center", "right",
        "bottom-left", "bottom", "bottom-right",
    ]:
        combo = zstack(inner_base, inner_overlay, align="center")
        lines = clean(zstack(outer_base, combo, align=align).render(outer_w))
        assert len(lines) == outer_h
        # The inner block content should appear somewhere
        has_b = any("B" in l for l in lines)
        has_x = any("X" in l for l in lines)
        assert has_b, f"{align}: inner base not visible"
        assert has_x, f"{align}: inner overlay not visible"


# ── Flex properties ──────────────────────────────────────────────


def test_flex_basis_is_max():
    assert zstack(text("short"), text("longer text")).flex_basis() == 11


def test_flex_grow_width_if_any_child_grows():
    assert zstack(text("hi"), text("fill", max_width="fill")).flex_grow_width()
    assert not zstack(text("hi"), text("no")).flex_grow_width()


def test_flex_grow_height_propagates():
    from terminal import scroll

    s = ScrollState()
    z = zstack(scroll(text("a"), state=s))
    assert z.flex_grow_height()
    assert not zstack(text("a")).flex_grow_height()


# ── Edge cases ───────────────────────────────────────────────────


def test_empty():
    assert clean(zstack().render(10)) == [""]


def test_single_child():
    lines = clean(zstack(text("hello")).render(20))
    assert "hello" in lines[0]


def test_top_layer_overwrites():
    lines = clean(zstack(text("aaaa"), text("bb")).render(10))
    assert lines[0].startswith("bb")


def test_empty_overlay_preserves_base():
    from terminal import cond

    base = text("visible")
    overlay = cond(False, text("hidden"))
    lines = clean(zstack(base, overlay).render(20))
    assert "visible" in lines[0]


def test_box_overlay_centered():
    base = vstack(*[text("." * 30) for _ in range(5)])
    overlay = box(text("Alert!"), style="normal", padding=1)
    lines = clean(zstack(base, overlay, align="center").render(30))
    assert any("Alert!" in l for l in lines)
    assert lines[0].startswith(".")
    assert lines[4].startswith(".")


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
    lines = zstack(base, overlay, align="top-left").render(20)
    raw = lines[0]
    after_overlay = raw.split("XX", 1)[1]
    assert "\033[38;5;1m" in after_overlay


# ── Wide character handling ──────────────────────────────────────


def test_split_at_col_wide_chars():
    z = zstack(text("你好世界xxxx"), text("AB"), align="top-left")
    lines = clean(z.render(20))
    assert lines[0].startswith("AB")
    assert "好" in lines[0]


def test_overlay_on_wide_char_base():
    base = text("你好世界")
    overlay = text("AB")
    lines = clean(zstack(base, overlay, align="center").render(8))
    assert "AB" in lines[0]


# ── Validation ───────────────────────────────────────────────────


def test_invalid_align_raises():
    import pytest

    with pytest.raises(ValueError, match="unknown align"):
        zstack(text("x"), align="middle")
