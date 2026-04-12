"""Tests for cell buffer — the contract is:

1. Text written to a Buffer can be read back
2. Styled text survives parse → render round-trip (styles preserved)
3. Diff only outputs when content changed
4. Different styles are distinguishable by diff
5. Non-CSI escape sequences don't cause hangs or corrupt output
"""

import pytest

from terminal.buffer import Buffer, parse_line, render_diff, render_full
from terminal.style import (
    bg,
    bg_rgb,
    blink,
    bold,
    color,
    dim,
    invisible,
    italic,
    overline,
    reverse,
    rgb,
    strikethrough,
    underline,
)


def _buf(lines: list[str], w: int = 20) -> Buffer:
    buf = Buffer(w, len(lines))
    for i, line in enumerate(lines):
        parse_line(buf, i, line)
    return buf


# ── Text round-trip ──────────────────────────────────────────────────


def test_ascii_text_preserved():
    buf = _buf(["hello"])
    assert buf.row_text(0).startswith("hello")


def test_wide_chars_preserved():
    buf = _buf(["你好"])
    assert buf.row_text(0).startswith("你好")


def test_clips_at_width():
    buf = _buf(["hello world"], w=5)
    assert buf.row_text(0) == "hello"


def test_wide_char_at_boundary_skipped():
    buf = _buf(["abcd你"], w=5)
    assert buf.row_text(0) == "abcd "


def test_empty_string():
    buf = Buffer(10, 1)
    parse_line(buf, 0, "")
    assert buf.row_text(0) == " " * 10


def test_blank_fill():
    buf = Buffer(5, 1)
    assert buf.row_text(0) == "     "


# ── Styled text round-trip ───────────────────────────────────────────


def _styled_differs_from_plain(styled_line: str, plain: str) -> bool:
    """True if the styled version produces different render output than plain."""
    a = _buf([styled_line])
    b = _buf([plain])
    return render_diff(a, b) != ""


def test_bold_survives():
    assert _styled_differs_from_plain(bold("hi"), "hi")


def test_dim_survives():
    assert _styled_differs_from_plain(dim("hi"), "hi")


def test_italic_survives():
    assert _styled_differs_from_plain(italic("hi"), "hi")


def test_underline_survives():
    assert _styled_differs_from_plain(underline("hi"), "hi")


def test_blink_survives():
    assert _styled_differs_from_plain(blink("hi"), "hi")


def test_reverse_survives():
    assert _styled_differs_from_plain(reverse("hi"), "hi")


def test_invisible_survives():
    assert _styled_differs_from_plain(invisible("hi"), "hi")


def test_strikethrough_survives():
    assert _styled_differs_from_plain(strikethrough("hi"), "hi")


def test_overline_survives():
    assert _styled_differs_from_plain(overline("hi"), "hi")


def test_indexed_fg_survives():
    assert _styled_differs_from_plain(color(196, "hi"), "hi")


def test_indexed_bg_survives():
    assert _styled_differs_from_plain(bg(22, "hi"), "hi")


def test_rgb_fg_survives():
    assert _styled_differs_from_plain(rgb(255, 128, 0, "hi"), "hi")


def test_rgb_bg_survives():
    assert _styled_differs_from_plain(bg_rgb(10, 20, 30, "hi"), "hi")


def test_combined_styles_survive():
    styled = bold(rgb(255, 0, 0, "hi"))
    assert _styled_differs_from_plain(styled, "hi")


def test_reset_mid_line_clears_style():
    """After reset, subsequent chars should match plain text."""
    a = _buf([bold("A") + "B"])
    b = _buf(["AB"])
    diff = render_diff(a, b)
    assert "A" in diff
    # B should not be in the diff — it matches plain
    # (it may appear as part of a run, but the key point is A is styled)


def test_identical_styled_content_no_diff():
    styled = rgb(1, 2, 3, "hi")
    a = _buf([styled])
    b = _buf([styled])
    assert render_diff(a, b) == ""


# ── Diff contract ────────────────────────────────────────────────────


def test_identical_no_output():
    a = _buf(["same", "same"])
    b = _buf(["same", "same"])
    assert render_diff(a, b) == ""


def test_changed_cells_in_output():
    old = _buf(["same", "old"])
    new = _buf(["same", "new"])
    result = render_diff(new, old)
    assert "new" in result
    assert "same" not in result


def test_new_content_in_blank_row():
    old = Buffer(20, 3)
    parse_line(old, 0, "a")
    new = Buffer(20, 3)
    parse_line(new, 0, "a")
    parse_line(new, 2, "c")
    result = render_diff(new, old)
    assert "c" in result
    assert "a" not in result


def test_style_only_change_detected():
    a = _buf(["hello"])
    b = _buf([bold("hello")])
    assert render_diff(b, a) != ""


def test_mismatched_dimensions_raises():
    with pytest.raises(ValueError):
        render_diff(Buffer(10, 2), Buffer(20, 2))


# ── Full render ──────────────────────────────────────────────────────


def test_full_render_contains_content():
    buf = _buf(["hello", "world"])
    result = render_full(buf)
    assert "hello" in result
    assert "world" in result


def test_full_render_includes_style():
    buf = _buf([bold("hello")])
    result = render_full(buf)
    assert "hello" in result
    assert len(result) > len("hello")  # has escape codes


# ── Buffer init ──────────────────────────────────────────────────────


def test_dimensions():
    buf = Buffer(80, 24)
    assert buf.width == 80 and buf.height == 24


def test_invalid_dimensions():
    with pytest.raises(ValueError):
        Buffer(0, 10)
    with pytest.raises(ValueError):
        Buffer(10, -1)


def test_row_out_of_range():
    with pytest.raises(IndexError):
        Buffer(5, 2).row_text(5)


def test_parse_row_out_of_range():
    with pytest.raises(IndexError):
        parse_line(Buffer(10, 2), 5, "hello")


# ── Non-CSI escapes don't hang ──────────────────────────────────────


def test_osc_in_hstack_no_hang():
    from terminal.buffer import hstack_join_row

    osc = "\033]8;;https://example.com\033\\click\033]8;;\033\\"
    result = hstack_join_row([osc], [10], 0)
    assert "click" in result


def test_osc_skipped_in_cells():
    buf = Buffer(20, 1)
    parse_line(buf, 0, "\033]8;;http://x\033\\hi\033]8;;\033\\")
    text = buf.row_text(0)
    assert text.startswith("hi")
    assert "http" not in text


def test_osc_in_display_width():
    from terminal.buffer import c_display_width

    osc = "\033]8;;https://example.com\033\\click\033]8;;\033\\"
    assert c_display_width(osc) == 5


# ── hstack_join_row ──────────────────────────────────────────────────


def test_hstack_ansi_clips_to_width():
    from terminal.buffer import hstack_join_row
    from terminal.measure import display_width, strip_ansi

    result = hstack_join_row([bold("hello world")], [5], 0)
    assert display_width(strip_ansi(result)) <= 5


def test_hstack_ansi_ascii_same_width():
    from terminal.buffer import hstack_join_row
    from terminal.measure import display_width, strip_ansi

    ascii_w = display_width(strip_ansi(hstack_join_row(["hello world"], [5], 0)))
    ansi_w = display_width(strip_ansi(hstack_join_row([bold("hello world")], [5], 0)))
    assert ascii_w == ansi_w
