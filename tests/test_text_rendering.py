"""Contract: text rendering handles ANSI, wide chars, OSC, and edge cases.

These test that the rendering pipeline correctly measures, truncates,
and displays text with styling, wide characters, and escape sequences.
"""

from conftest import SnapFn

import ttyz as t

# ── Plain text fills correct width ──────────────────────────────────


def test_plain_ascii_width(snap: SnapFn):
    snap(t.text("hello"), 10)


def test_empty_text(snap: SnapFn):
    snap(t.text(""), 5)


# ── ANSI styled text ────────────────────────────────────────────────


def test_ansi_bold_renders_content(snap: SnapFn):
    snap(t.text(t.bold("hello")), 10)


def test_ansi_does_not_consume_width(snap: SnapFn):
    """Styled text should occupy the same columns as unstyled."""
    snap(t.hstack(t.text(t.bold("hello")), t.text("X")), 10)


# ── Wide characters ──────────────────────────────────────────────────


def test_wide_char_text(snap: SnapFn):
    snap(t.text("你好"), 10)


def test_wide_chars_in_hstack(snap: SnapFn):
    """Wide chars should get 2 columns each in layout."""
    snap(t.hstack(t.text("你好"), t.text("X")), 10)


def test_wide_char_with_ansi(snap: SnapFn):
    snap(t.text(t.bold("你好")), 10)


# ── OSC sequences (hyperlinks) ──────────────────────────────────────

OSC_BEL = "\x1b]8;;https://example.com\x07click\x1b]8;;\x07"
OSC_ST = "\x1b]8;;https://example.com\x1b\\click\x1b]8;;\x1b\\"


def test_osc_bel_renders_visible_text(snap: SnapFn):
    snap(t.text(OSC_BEL), 10)


def test_osc_st_renders_visible_text(snap: SnapFn):
    snap(t.text(OSC_ST), 10)


def test_osc_does_not_consume_width(snap: SnapFn):
    """OSC hyperlink markup should not affect column layout."""
    snap(t.hstack(t.text(OSC_BEL), t.text("X")), 10)


def test_multiple_osc_links(snap: SnapFn):
    s = "\x1b]8;;a\x07A\x1b]8;;\x07\x1b]8;;b\x07B\x1b]8;;\x07"
    snap(t.text(s), 10)


# ── Mixed ANSI + wide chars ──────────────────────────────────────────


def test_ansi_wide_mixed_layout(snap: SnapFn):
    """ANSI styling + wide chars: layout should account for both."""
    snap(t.hstack(t.text(t.bold("你好")), t.text("end")), 20)


def test_long_ansi_text(snap: SnapFn):
    s = "\033[31m" + "x" * 600 + "\033[0m"
    snap(t.text(s), 600)


# ── Truncation ───────────────────────────────────────────────────────


def test_truncate_tail(snap: SnapFn):
    snap(t.text("hello world", truncation="tail"), 8)


def test_truncate_with_wide_chars(snap: SnapFn):
    snap(t.text("你好世界end", truncation="tail"), 6)


def test_truncate_zero_width(snap: SnapFn):
    snap(t.text("title", truncation="tail"), 1, 1)


def test_truncate_osc_preserves_visible(snap: SnapFn):
    snap(t.text(OSC_BEL, truncation="tail"), 5)


def test_truncate_osc_clips(snap: SnapFn):
    snap(t.text(OSC_BEL, truncation="tail"), 4)


def test_truncate_osc_with_ellipsis(snap: SnapFn):
    snap(t.text(OSC_BEL, truncation="tail"), 4)


def test_osc_plus_csi_renders(snap: SnapFn):
    """Mixed CSI styling + OSC hyperlink should render visible text."""
    s = "\x1b[1m\x1b]8;;url\x07hi\x1b]8;;\x07\x1b[0m"
    snap(t.text(s), 10)


# ── Text wrap ────────────────────────────────────────────────────────


def test_wrap_splits_long_text(snap: SnapFn):
    snap(t.text("hello world foo", wrap=True), 10, 3)


# ── Edge cases ───────────────────────────────────────────────────────


def test_long_ascii_text(snap: SnapFn):
    snap(t.text("a" * 200), 200)


def test_long_wide_text(snap: SnapFn):
    snap(t.text("你" * 100), 200)


def test_non_sgr_csi_in_text(snap: SnapFn):
    """Non-SGR CSI (like cursor move) should not corrupt cell content."""
    snap(t.text("AB\033[1;1HCD"), 10)


def test_non_sgr_csi_preserves_style(snap: SnapFn):
    """Non-SGR CSI must not reset active foreground color."""
    snap(t.text("\033[31mA\033[10;20HB"), 10, 1)


def test_non_sgr_csi_in_render(snap: SnapFn):
    """Buffer rendering must skip non-SGR CSI without corrupting style."""
    snap(t.text("\033[32mOK\033[2Jafter"), 20, 1)


# ── Flex distribute (via VStack grow) ────────────────────────────────


def test_flex_distribute_equal_weights(snap: SnapFn):
    """Two equal-grow children should split the space evenly."""
    snap(t.vstack(t.text("A", grow=1), t.text("B", grow=1)), 10, 10)


def test_flex_distribute_unequal_weights(snap: SnapFn):
    """grow=2 should get twice as much space as grow=1."""
    snap(t.vstack(t.text("A", grow=2, bg=1), t.text("B", grow=1, bg=2)), 10, 9)
