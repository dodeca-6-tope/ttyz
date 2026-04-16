"""Tests for Text component."""

from conftest import SnapFn

from ttyz import bold, box, color, hstack, text

# ── Render ───────────────────────────────────────────────────────────


def test_renders_content(snap: SnapFn):
    snap(text("hello"), 80)


def test_empty(snap: SnapFn):
    snap(text(), 80)


def test_ansi_passthrough(snap: SnapFn):
    snap(text("\033[1mhi\033[0m"), 80)


def test_ansi_color_passthrough(snap: SnapFn):
    snap(text("\033[38;5;1mhi\033[0m"), 80)


# ── Padding ──────────────────────────────────────────────────────────


def test_padding(snap: SnapFn):
    snap(text("hi", padding=2), 80)


def test_padding_left_right(snap: SnapFn):
    snap(text("hi", padding_left=1, padding_right=3), 80)


def test_padding_left_only(snap: SnapFn):
    snap(text("hi", padding_left=2), 80)


def test_padding_right_only(snap: SnapFn):
    snap(text("hi", padding_right=2), 80)


def test_padding_exceeds_width(snap: SnapFn):
    snap(text("hi", padding=10), 5)


# ── Width / overflow ─────────────────────────────────────────────────


def test_width_truncates_with_overflow_hidden(snap: SnapFn):
    snap(text("hello world", width="8", overflow="hidden"), 80)


def test_width_no_truncate_when_fits(snap: SnapFn):
    snap(text("hi", width="10", overflow="hidden"), 80)


def test_width_100pct_truncates_to_budget(snap: SnapFn):
    snap(text("a" * 100, width="100%", overflow="hidden"), 20)


def test_width_100pct_no_truncate_when_fits(snap: SnapFn):
    snap(text("short", width="100%"), 80)


# ── Multiline ───────────────────────────────────────────────────────


def test_multiline_render(snap: SnapFn):
    snap(text("a\nb\nc"), 80)


def test_multiline_ansi(snap: SnapFn):
    snap(text("\033[1ma\033[0m\n\033[1mb\033[0m"), 80)


def test_multiline_intrinsic_width(snap: SnapFn):
    """Widest line determines column width in hstack layout."""
    snap(hstack(text("short\na longer line"), text("|")), 30)


def test_multiline_crlf(snap: SnapFn):
    snap(text("a\r\nb"), 80)


# ── Wrap ─────────────────────────────────────────────────────────────


def test_wrap_word_boundary(snap: SnapFn):
    snap(text("hello world foo", wrap=True), 11)


def test_wrap_char_fallback(snap: SnapFn):
    snap(text("abcdefgh", wrap=True), 3)


def test_wrap_mixed(snap: SnapFn):
    snap(text("hi abcdefgh bye", wrap=True), 5)


def test_wrap_wide_char_fallback(snap: SnapFn):
    snap(text("你好世界", wrap=True), 4)


def test_wrap_preserves_short_line(snap: SnapFn):
    snap(text("hi", wrap=True), 80)


def test_wrap_with_newlines(snap: SnapFn):
    snap(text("hello world\nfoo bar", wrap=True), 7)


# ── Truncation mode ──────────────────────────────────────────────────


def test_truncation_tail(snap: SnapFn):
    snap(text("hello world", truncation="tail"), 8)


def test_truncation_head(snap: SnapFn):
    snap(text("hello world", truncation="head"), 8)


def test_truncation_middle(snap: SnapFn):
    snap(text("hello world", truncation="middle"), 8)


def test_truncation_no_op_when_fits(snap: SnapFn):
    snap(text("hi", truncation="tail"), 80)


def test_truncation_inside_box(snap: SnapFn):
    snap(box(text("a long line of text", truncation="tail")), 10)


# ── Flex layout ──────────────────────────────────────────────────────


def test_intrinsic_width(snap: SnapFn):
    """Text intrinsic width drives hstack column sizing."""
    snap(hstack(text("hello"), text("|")), 20, name="intrinsic_width_basic")
    snap(hstack(text("hi", padding=1), text("|")), 20, name="intrinsic_width_padded")


def test_flex_grow_with_100pct_width():
    assert text("hello", grow=1).grow
    assert not text("hello").grow


# ── Tail truncation + padding ────────────────────────────────────────


def test_tail_truncation_with_padding(snap: SnapFn):
    snap(text("hello world", truncation="tail", padding=2), 15)


def test_tail_truncation_with_padding_truncates(snap: SnapFn):
    snap(text("hello world!!!!", truncation="tail", padding=2), 15)


def test_tail_truncation_padding_c_matches_python(snap: SnapFn):
    snap(
        text("こんにちは世界テスト", truncation="tail", padding=2),
        20,
        name="tail_trunc_padding_wide",
    )
    snap(
        text("hello world test!!", truncation="tail", padding=2),
        20,
        name="tail_trunc_padding_ascii",
    )


def test_head_truncation_wide_chars_at_boundary(snap: SnapFn):
    snap(text("x你好世界", truncation="head"), 6)


def test_truncation_content_correct(snap: SnapFn):
    """Tail truncation produces correct visible content regardless of ANSI input."""
    snap(text(bold("hello world"), truncation="tail"), 8)


def test_wrap_at_zero_inner_width(snap: SnapFn):
    # padding == width → inner width 0, must not hang
    snap(text("hello", wrap=True, padding_left=5), 5)


def test_head_truncation_strips_ansi(snap: SnapFn):
    """Known limitation: head truncation operates on stripped text."""
    snap(text(color(1, "hello world here"), truncation="head"), 10)


def test_middle_truncation_strips_ansi(snap: SnapFn):
    """Known limitation: middle truncation operates on stripped text."""
    snap(text(bold("hello world here"), truncation="middle"), 10)


def test_non_string_value(snap: SnapFn):
    snap(text(42), 80, name="non_string_int")
    snap(text(None), 80, name="non_string_none")
    snap(text([1, 2, 3]), 80, name="non_string_list")
