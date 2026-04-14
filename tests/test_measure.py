"""Tests for display_width, strip_ansi, char_width, and slice_at_width."""

from ttyz.measure import (
    char_width,
    display_width,
    distribute,
    slice_at_width,
    strip_ansi,
    truncate,
)


def test_plain_ascii():
    assert display_width("hello") == 5


def test_ansi_codes_ignored():
    assert display_width("\033[1mhello\033[0m") == 5


def test_wide_chars():
    assert display_width("你好") == 4


def test_mixed_ansi_and_wide():
    assert display_width("\033[31m你好\033[0m world") == 10


def test_strip_ansi():
    assert strip_ansi("\033[1;31mhello\033[0m") == "hello"


def test_strip_ansi_no_codes():
    assert strip_ansi("hello") == "hello"


def test_strip_ansi_non_sgr_csi():
    assert strip_ansi("AB\033[1;1HCD") == "ABCD"


def test_display_width_non_sgr_csi():
    assert display_width("AB\033[1;1HCD") == 4


def test_empty():
    assert display_width("") == 0
    assert strip_ansi("") == ""


# ── char_width ──────────────────────────────────────────────────────


def test_char_width_ascii():
    assert char_width("a") == 1


def test_char_width_wide():
    assert char_width("你") == 2


# ── slice_at_width ──────────────────────────────────────────────────


def test_slice_at_width_ascii():
    assert slice_at_width("hello world", 5) == "hello"


def test_slice_at_width_wide_chars():
    assert slice_at_width("你好世界", 4) == "你好"


def test_slice_at_width_wide_chars_odd_budget():
    # 你=2 cols, so budget=3 can only fit 1 wide char
    assert slice_at_width("你好", 3) == "你"


def test_slice_at_width_fits():
    assert slice_at_width("hi", 10) == "hi"


def test_slice_at_width_empty():
    assert slice_at_width("", 5) == ""


def test_slice_at_width_mixed():
    assert slice_at_width("a你b", 3) == "a你"
    assert slice_at_width("a你b", 2) == "a"


# ── display_width: long strings (bypass cache) ────────────────────


def test_display_width_long_ascii():
    s = "a" * 1000
    assert display_width(s) == 1000


def test_display_width_long_wide():
    s = "你" * 500
    assert display_width(s) == 1000


def test_display_width_long_ansi():
    s = "\033[31m" + "x" * 600 + "\033[0m"
    assert display_width(s) == 600


# ── slice_at_width edge cases ──────────────────────────────────────


def test_slice_at_width_negative():
    assert slice_at_width("hello", -1) == ""


def test_slice_at_width_zero():
    assert slice_at_width("hello", 0) == ""


# ── truncate edge cases ────────────────────────────────────────────


def test_truncate_zero_width():
    assert truncate("title", 0) == ""
    assert truncate("title", 0, ellipsis=True) == ""


def test_truncate_negative_width():
    assert truncate("hello", -1) == ""


# ── distribute edge cases ──────────────────────────────────────────


def test_distribute_all_zero_weights():
    assert distribute(100, [0, 0]) == [0, 0]


def test_distribute_zero_total():
    assert distribute(0, [1, 2, 3]) == [0, 0, 0]


def test_distribute_empty_weights():
    assert distribute(100, []) == []


# ── OSC handling in strip_ansi ────────────────────────────────────────

OSC_LINK_BEL = "\x1b]8;;https://example.com\x07click\x1b]8;;\x07"
OSC_LINK_ST = "\x1b]8;;https://example.com\x1b\\click\x1b]8;;\x1b\\"


def test_strip_ansi_osc_bel():
    assert strip_ansi(OSC_LINK_BEL) == "click"


def test_strip_ansi_osc_st():
    assert strip_ansi(OSC_LINK_ST) == "click"


def test_strip_ansi_osc_plus_csi():
    s = "\x1b[1m\x1b]8;;url\x07hi\x1b]8;;\x07\x1b[0m"
    assert strip_ansi(s) == "hi"


def test_strip_ansi_multiple_osc():
    s = "\x1b]8;;a\x07A\x1b]8;;\x07\x1b]8;;b\x07B\x1b]8;;\x07"
    assert strip_ansi(s) == "AB"


# ── OSC handling in display_width ─────────────────────────────────────


def test_display_width_osc_bel():
    assert display_width(OSC_LINK_BEL) == 5


def test_display_width_osc_st():
    assert display_width(OSC_LINK_ST) == 5


# ── OSC handling in truncate ──────────────────────────────────────────


def test_truncate_osc_preserves_visible():
    result = truncate(OSC_LINK_BEL, 3)
    assert strip_ansi(result) == "cli"


def test_truncate_osc_fits():
    result = truncate(OSC_LINK_BEL, 5)
    assert strip_ansi(result) == "click"


def test_truncate_osc_with_ellipsis():
    result = truncate(OSC_LINK_BEL, 3, ellipsis=True)
    stripped = strip_ansi(result)
    assert len(stripped) <= 3
