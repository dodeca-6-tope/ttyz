"""Tests for Screen rendering — clip, pad, Screen.render."""

from os import terminal_size
from unittest.mock import patch

from terminal.screen import Screen, clip


def _make_screen():
    """Create a Screen that captures output as a string."""
    chunks: list[str] = []
    s = Screen(write=lambda data: chunks.append(data.decode()), flush=lambda: None)
    return s, chunks


# ── clip ────────────────────────────────────────────────────────────


def test_clip_leaves_short_text():
    assert clip("hello", 10) == "hello"


def test_clip_truncates_at_width():
    result = clip("hello world", 5)
    assert "hello" in result
    assert "world" not in result


def test_clip_preserves_ansi_before_cutoff():
    result = clip("\033[1mhello world\033[0m", 5)
    assert "\033[1m" in result
    assert "hello" in result
    assert "world" not in result


def test_clip_ansi_codes_dont_consume_width():
    """A line with ANSI codes that fits visually should not be clipped."""
    line = "\033[31mhi\033[0m"  # 2 visible chars
    assert clip(line, 2) == line
    assert clip(line, 10) == line


def test_clip_wide_chars():
    result = clip("你好世界", 4)
    assert "你好" in result
    assert "世界" not in result


def test_clip_wide_chars_with_ansi():
    """Wide chars inside ANSI styling should still clip at the right column."""
    line = "\033[31m你好世界\033[0m"
    result = clip(line, 4)
    assert "你好" in result
    assert "世界" not in result


def test_clip_exact_width():
    assert clip("hello", 5) == "hello"


def test_clip_zero_width():
    from terminal.measure import display_width, strip_ansi

    assert clip("hello", 0) == ""
    result = clip("\033[1mhello\033[0m", 0)
    assert "\033[0m" in result
    assert display_width(strip_ansi(result)) == 0


# ── pad ──────────────────────────────────────────────────────────────


def test_pad_short_line():
    from terminal.screen import pad

    assert pad("hi", 5) == "hi   "


def test_pad_full_width_line():
    from terminal.screen import pad

    assert pad("hello", 5) == "hello"


def test_pad_with_ansi():
    from terminal.screen import pad

    line = "\033[1mhi\033[0m"
    padded = pad(line, 5)
    assert padded == line + "   "


def test_pad_wide_chars():
    from terminal.screen import pad

    assert pad("你好", 6) == "你好  "  # 4 cols + 2 spaces


# ── Screen.render ───────────────────────────────────────────────────


def test_screen_resize_writes_all_rows():
    """After resize, output should contain all content and blank remaining rows."""
    s, chunks = _make_screen()
    size = terminal_size((20, 5))
    with patch("terminal.screen.os.get_terminal_size", return_value=size):
        s.render(["line1", "line2", "line3", "line4", "line5"])
    big = terminal_size((20, 10))
    with patch("terminal.screen.os.get_terminal_size", return_value=big):
        s.render(["line1", "line2"])
    output = chunks[-1]
    assert "line1" in output
    assert "line2" in output
    assert "line3" not in output
    assert "line4" not in output
    assert "line5" not in output


def test_screen_shrinking_content_clears_old_rows():
    """Rendering fewer lines than before should blank the leftover rows."""
    s, chunks = _make_screen()
    size = terminal_size((20, 10))
    with patch("terminal.screen.os.get_terminal_size", return_value=size):
        s.render(["a", "b", "c", "d", "e"])
        s.render(["a", "b"])
    output = chunks[-1]
    assert "c" not in output
    assert "d" not in output
    assert "e" not in output


def test_clip_non_sgr_csi_preserves_visible_text():
    """Non-SGR CSI sequences (like cursor-move) should not eat visible text."""
    from terminal.measure import strip_ansi

    result = clip("AB\033[1;1HCD", 4)
    assert strip_ansi(result) == "ABCD"
