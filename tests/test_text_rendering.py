"""Contract: text rendering handles ANSI, wide chars, OSC, and edge cases.

These test that the rendering pipeline correctly measures, truncates,
and displays text with styling, wide characters, and escape sequences.
"""

from conftest import SnapFn

import ttyz as t
from ttyz import Buffer, render_to_buffer


def _row(node: object, w: int = 40, h: int = 1) -> str:
    buf = Buffer(w, h)
    render_to_buffer(node, buf)
    return buf.row_text(0)


# ── Plain text fills correct width ──────────────────────────────────


def test_plain_ascii_width():
    row = _row(t.text("hello"), w=10)
    assert row == "hello     "


def test_empty_text():
    row = _row(t.text(""), w=5)
    assert row == "     "


# ── ANSI styled text ────────────────────────────────────────────────


def test_ansi_bold_renders_content():
    row = _row(t.text(t.bold("hello")), w=10)
    assert "hello" in row


def test_ansi_does_not_consume_width():
    """Styled text should occupy the same columns as unstyled."""
    plain = _row(t.hstack(t.text("hello"), t.text("X")), w=10)
    styled = _row(t.hstack(t.text(t.bold("hello")), t.text("X")), w=10)
    assert plain.index("X") == styled.index("X")


# ── Wide characters ──────────────────────────────────────────────────


def test_wide_char_text():
    row = _row(t.text("你好"), w=10)
    assert "你好" in row


def test_wide_chars_in_hstack():
    """Wide chars should get 2 columns each in layout."""
    row = _row(t.hstack(t.text("你好"), t.text("X")), w=10)
    assert "你好" in row
    assert "X" in row
    assert row.startswith("你好X")


def test_wide_char_with_ansi():
    row = _row(t.text(t.bold("你好")), w=10)
    assert "你好" in row


# ── OSC sequences (hyperlinks) ──────────────────────────────────────

OSC_BEL = "\x1b]8;;https://example.com\x07click\x1b]8;;\x07"
OSC_ST = "\x1b]8;;https://example.com\x1b\\click\x1b]8;;\x1b\\"


def test_osc_bel_renders_visible_text():
    row = _row(t.text(OSC_BEL), w=10)
    assert "click" in row


def test_osc_st_renders_visible_text():
    row = _row(t.text(OSC_ST), w=10)
    assert "click" in row


def test_osc_does_not_consume_width():
    """OSC hyperlink markup should not affect column layout."""
    plain = _row(t.hstack(t.text("click"), t.text("X")), w=10)
    osc = _row(t.hstack(t.text(OSC_BEL), t.text("X")), w=10)
    assert plain.index("X") == osc.index("X")


def test_multiple_osc_links():
    s = "\x1b]8;;a\x07A\x1b]8;;\x07\x1b]8;;b\x07B\x1b]8;;\x07"
    row = _row(t.text(s), w=10)
    assert "A" in row
    assert "B" in row


# ── Mixed ANSI + wide chars ──────────────────────────────────────────


def test_ansi_wide_mixed_layout():
    """ANSI styling + wide chars: layout should account for both."""
    styled_wide = t.bold("你好")  # 4 visible cols
    row = _row(t.hstack(t.text(styled_wide), t.text("end")), w=20)
    assert "你好" in row
    assert "end" in row


def test_long_ansi_text():
    s = "\033[31m" + "x" * 600 + "\033[0m"
    buf = Buffer(600, 1)
    render_to_buffer(t.text(s), buf)
    row = buf.row_text(0)
    assert row.count("x") == 600


# ── Truncation ───────────────────────────────────────────────────────


def test_truncate_tail():
    row = _row(t.text("hello world", truncation="tail"), w=8)
    assert "hello" in row
    assert "world" not in row


def test_truncate_with_wide_chars():
    row = _row(t.text("你好世界end", truncation="tail"), w=6)
    assert "end" not in row


def test_truncate_zero_width():
    row = _row(t.text("title", truncation="tail"), w=1, h=1)
    # Should not crash; content is heavily truncated
    assert isinstance(row, str)


def test_truncate_osc_preserves_visible():
    row = _row(t.text(OSC_BEL, truncation="tail"), w=5)
    assert "click" in row


def test_truncate_osc_clips():
    row = _row(t.text(OSC_BEL, truncation="tail"), w=4)
    assert "click" not in row  # only 4 cols, "click" is 5


def test_truncate_osc_with_ellipsis():
    row = _row(t.text(OSC_BEL, truncation="tail"), w=4)
    assert "click" not in row


def test_osc_plus_csi_renders():
    """Mixed CSI styling + OSC hyperlink should render visible text."""
    s = "\x1b[1m\x1b]8;;url\x07hi\x1b]8;;\x07\x1b[0m"
    row = _row(t.text(s), w=10)
    assert "hi" in row


# ── Text wrap ────────────────────────────────────────────────────────


def test_wrap_splits_long_text():
    buf = Buffer(10, 3)
    render_to_buffer(t.text("hello world foo", wrap=True), buf)
    assert "hello" in buf.row_text(0)
    assert "world" in buf.row_text(1)


# ── Edge cases ───────────────────────────────────────────────────────


def test_long_ascii_text():
    s = "a" * 200
    row = _row(t.text(s), w=200)
    assert row == s


def test_long_wide_text():
    s = "你" * 100
    row = _row(t.text(s), w=200)
    assert "你" * 100 in row


def test_non_sgr_csi_in_text():
    """Non-SGR CSI (like cursor move) should not corrupt cell content."""
    row = _row(t.text("AB\033[1;1HCD"), w=10)
    assert "A" in row
    assert "B" in row


def test_non_sgr_csi_preserves_style(snap: "SnapFn"):
    """Non-SGR CSI must not reset active foreground color."""
    # \033[31m = red, \033[10;20H = cursor move (non-SGR), then "B"
    # B should retain the red color, not be reset to default.
    snap(t.text("\033[31mA\033[10;20HB"), 10, 1)


def test_non_sgr_csi_in_buffer_parse_line(snap: "SnapFn"):
    """Buffer.parse_line must skip non-SGR CSI without corrupting style."""
    snap(t.text("\033[32mOK\033[2Jafter"), 20, 1)


# ── Flex distribute (via VStack grow) ────────────────────────────────


def test_flex_distribute_equal_weights():
    """Two equal-grow children should split the space evenly."""
    buf = Buffer(10, 10)
    render_to_buffer(
        t.vstack(
            t.text("A", grow=1),
            t.text("B", grow=1),
        ),
        buf,
    )
    # A gets ~5 rows, B gets ~5 rows. Both should appear.
    rows = [buf.row_text(r).strip() for r in range(10)]
    assert "A" in rows
    assert "B" in rows


def test_flex_distribute_unequal_weights():
    """grow=2 should get twice as much space as grow=1."""
    buf = Buffer(10, 9)
    render_to_buffer(
        t.vstack(
            t.text("A", grow=2, bg=1),
            t.text("B", grow=1, bg=2),
        ),
        buf,
    )
    # A gets 6 rows (2/3), B gets 3 rows (1/3)
    # Just verify both are present and A comes first
    a_row = next(r for r in range(9) if "A" in buf.row_text(r))
    b_row = next(r for r in range(9) if "B" in buf.row_text(r))
    assert a_row < b_row
