"""Tests for display_width, strip_ansi, char_width, and slice_at_width."""

from terminal.measure import char_width, display_width, slice_at_width, strip_ansi


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
