"""Tests for Screen rendering — clip, diff, full render."""

from os import terminal_size
from unittest.mock import patch

from terminal.screen import Screen, clip, render_diff, render_full


def _make_screen():
    """Create a Screen that captures output as a string."""
    chunks: list[str] = []
    s = Screen(write=lambda data: chunks.append(data.decode()), flush=lambda: None)
    return s, chunks


def _last_frame(chunks: list[str]) -> list[str]:
    """Extract visible lines from the last rendered output."""
    raw = chunks[-1]
    # Strip synchronized update markers
    raw = raw.replace("\033[?2026h", "").replace("\033[?2026l", "")
    # Full render starts with \033[H; diff has \033[row;1H per line
    raw = raw.replace("\033[H", "")
    # Split on \n for full render, or on cursor-move sequences for diff
    if "\n" in raw:
        return raw.split("\n")
    import re
    parts = re.split(r"\033\[\d+;1H", raw)
    return [p for p in parts if p]

# ── clip ────────────────────────────────────────────────────────────


def test_clip_leaves_short_text():
    assert clip("hello", 10) == "hello"


def test_clip_truncates_at_width():
    result = clip("hello world", 5)
    # Should contain exactly 5 visible chars + ANSI reset
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


def test_pad_wide_chars():
    from terminal.screen import pad

    assert pad("你好", 6) == "你好  "  # 4 cols + 2 spaces


# ── render_full ────────────────────────────────────────────────────


def test_full_render_starts_at_home():
    result = render_full(["a", "b"])
    assert result.startswith("\033[H")


def test_full_render_joins_lines():
    result = render_full(["a", "b", "c"])
    assert "a\nb\nc" in result


def test_full_render_contains_all_content():
    result = render_full(["hello", "world"])
    assert "hello" in result
    assert "world" in result


# ── render_diff ────────────────────────────────────────────────────


def test_diff_skips_unchanged_lines():
    result = render_diff(["same", "same"], ["same", "same"])
    assert result == ""


def test_diff_updates_only_changed_lines():
    result = render_diff(["same", "new"], ["same", "old"])
    assert "same" not in result
    assert "new" in result


def test_diff_updates_line_that_became_empty():
    result = render_diff(["hello", ""], ["hello", "world"])
    assert "world" not in result
    assert "\033[2;1H" in result  # cursor moved to write empty line


def test_diff_adds_new_lines_beyond_previous():
    result = render_diff(["a", "b", "c"], ["a", "b"])
    assert "c" in result
    assert "a" not in result


# ── _pad ──────────────────────────────────────────────────────────────


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


def test_render_full_no_erase_codes():
    """Full render uses padding, not \\033[K], to clear line remainders."""
    result = render_full(["hello", "world"])
    assert "\033[K" not in result


def test_render_diff_no_erase_codes():
    """Diff render uses padding, not \\033[K], to clear line remainders."""
    result = render_diff(["new"], ["old"])
    assert "\033[K" not in result


# ── clip edge cases ──────────────────────────────────────────────────


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
    # ANSI-styled content should include reset
    result = clip("\033[1mhello\033[0m", 0)
    assert "\033[0m" in result
    assert display_width(strip_ansi(result)) == 0


# ── Screen.render ───────────────────────────────────────────────────


def test_screen_resize_clears_stale_lines():
    """After resize, all terminal rows should be written (clearing stale content)."""
    s, chunks = _make_screen()
    size = terminal_size((20, 5))
    with patch("terminal.screen.os.get_terminal_size", return_value=size):
        s.render(["line1", "line2", "line3", "line4", "line5"])
    # Now resize to 10 rows but only render 2 lines of content
    big = terminal_size((20, 10))
    with patch("terminal.screen.os.get_terminal_size", return_value=big):
        s.render(["line1", "line2"])
    frame = _last_frame(chunks)
    assert len(frame) == 10
    assert frame[0].startswith("line1")
    assert frame[1].startswith("line2")
    # Rows 3-10 should be blank (spaces only)
    for row in frame[2:]:
        assert row.strip() == ""


def test_screen_shrinking_content_clears_old_rows():
    """Rendering fewer lines than before should blank the leftover rows."""
    s, chunks = _make_screen()
    size = terminal_size((20, 10))
    with patch("terminal.screen.os.get_terminal_size", return_value=size):
        s.render(["a", "b", "c", "d", "e"])
        s.render(["a", "b"])
    # The diff render should include blank lines for rows 3-5
    frame = _last_frame(chunks)
    for line in frame:
        assert "c" not in line
        assert "d" not in line
        assert "e" not in line
