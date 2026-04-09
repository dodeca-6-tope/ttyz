"""Tests for cell buffer — parsing, diffing, rendering."""

import pytest

from terminal.buffer import Buffer, parse_line, render_diff, render_full


def _buf(lines: list[str], w: int = 10) -> Buffer:
    buf = Buffer(w, len(lines))
    for i, line in enumerate(lines):
        parse_line(buf, i, line)
    return buf


# ── parse_line ────────────────────────────────────────────────────────


def test_parse_line_ascii():
    buf = Buffer(10, 1)
    parse_line(buf, 0, "hello")
    assert buf.row_text(0) == "hello     "


def test_parse_line_styled():
    buf = Buffer(10, 1)
    parse_line(buf, 0, "\033[1mhi\033[0m")
    assert buf.row_text(0).startswith("hi")


def test_parse_line_wide_chars():
    buf = Buffer(10, 1)
    parse_line(buf, 0, "你好")
    assert buf.row_text(0).startswith("你好")


def test_parse_line_clips_at_width():
    buf = Buffer(5, 1)
    parse_line(buf, 0, "hello world")
    assert buf.row_text(0) == "hello"


def test_parse_line_fg_color():
    """Foreground color should be preserved through diff."""
    a = Buffer(5, 1)
    b = Buffer(5, 1)
    parse_line(a, 0, "\033[38;5;196mhi\033[0m")
    parse_line(b, 0, "hi")
    result = render_diff(a, b)
    assert "38;5;196" in result


def test_parse_line_bg_color():
    """Background color should be preserved through diff."""
    a = Buffer(5, 1)
    b = Buffer(5, 1)
    parse_line(a, 0, "\033[48;5;22mhi\033[0m")
    parse_line(b, 0, "hi")
    result = render_diff(a, b)
    assert "48;5;22" in result


# ── render_full ───────────────────────────────────────────────────────


def test_full_render_contains_all_content():
    buf = _buf(["hello", "world"])
    result = render_full(buf)
    assert "hello" in result
    assert "world" in result


def test_full_render_no_erase_codes():
    buf = _buf(["hello", "world"])
    assert "\033[K" not in render_full(buf)


# ── render_diff ───────────────────────────────────────────────────────


def test_diff_skips_unchanged_cells():
    a = _buf(["same", "same"])
    b = _buf(["same", "same"])
    assert render_diff(a, b) == ""


def test_diff_updates_only_changed_cells():
    old = _buf(["same", "old"])
    new = _buf(["same", "new"])
    result = render_diff(new, old)
    assert "same" not in result
    assert "new" in result


def test_diff_updates_cells_that_became_blank():
    old = _buf(["hello", "world"])
    new = _buf(["hello", ""])
    result = render_diff(new, old)
    assert "world" not in result
    assert len(result) > 0


def test_diff_new_content_in_blank_rows():
    old = Buffer(10, 3)
    parse_line(old, 0, "a")
    parse_line(old, 1, "b")
    new = Buffer(10, 3)
    parse_line(new, 0, "a")
    parse_line(new, 1, "b")
    parse_line(new, 2, "c")
    result = render_diff(new, old)
    assert "c" in result
    assert "a" not in result


def test_diff_no_erase_codes():
    old = _buf(["old"])
    new = _buf(["new"])
    assert "\033[K" not in render_diff(new, old)


def test_diff_detects_style_only_change():
    """Same text, different style — must produce output."""
    a = _buf(["hello"])
    b = _buf(["\033[1mhello\033[0m"])
    result = render_diff(b, a)
    assert "hello" in result
    assert len(result) > 0


def test_diff_mismatched_dimensions():
    a = Buffer(10, 2)
    b = Buffer(20, 2)
    with pytest.raises(ValueError):
        render_diff(a, b)


# ── Buffer init ───────────────────────────────────────────────────────


def test_buffer_dimensions():
    buf = Buffer(80, 24)
    assert buf.width == 80
    assert buf.height == 24


def test_buffer_blank_fill():
    buf = Buffer(5, 1)
    assert buf.row_text(0) == "     "


def test_buffer_invalid_dimensions():
    with pytest.raises(ValueError):
        Buffer(0, 10)
    with pytest.raises(ValueError):
        Buffer(10, -1)


def test_buffer_row_text_out_of_range():
    buf = Buffer(5, 2)
    with pytest.raises(IndexError):
        buf.row_text(5)


# ── parse_line edge cases ─────────────────────────────────────────────


def test_parse_line_empty_string():
    buf = Buffer(10, 1)
    parse_line(buf, 0, "")
    assert buf.row_text(0) == "          "


def test_parse_line_combined_sgr():
    """Combined SGR like \\033[1;38;5;196m should parse bold + fg color."""
    a = Buffer(5, 1)
    b = Buffer(5, 1)
    parse_line(a, 0, "\033[1;38;5;196mhi\033[0m")
    parse_line(b, 0, "hi")
    result = render_diff(a, b)
    assert "38;5;196" in result
    assert ";1" in result


def test_parse_line_reset_mid_line():
    """Reset mid-line should clear style for subsequent characters."""
    a = Buffer(10, 1)
    b = Buffer(10, 1)
    parse_line(a, 0, "\033[1mA\033[0mB")
    parse_line(b, 0, "AB")
    result = render_diff(a, b)
    # "A" should be styled, "B" should match plain — only "A" in diff
    assert "A" in result


def test_parse_line_row_out_of_range():
    buf = Buffer(10, 2)
    with pytest.raises(IndexError):
        parse_line(buf, 5, "hello")


def test_parse_line_wide_char_at_boundary():
    """Wide char that doesn't fit in last column should be skipped."""
    buf = Buffer(5, 1)
    parse_line(buf, 0, "abcd你")  # 'abcd' = 4 cols, '你' needs 2 — won't fit
    assert buf.row_text(0) == "abcd "


# ── render_full ───────────────────────────────────────────────────────


def test_full_render_styled_roundtrip():
    """Full render of styled content should include style codes."""
    buf = Buffer(10, 1)
    parse_line(buf, 0, "\033[1mhello\033[0m")
    result = render_full(buf)
    assert "hello" in result
    assert ";1" in result  # bold attribute present
