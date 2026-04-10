"""Tests for Terminal.readkey() with real pty input.

Writes raw byte sequences to a pty (simulating a real terminal emulator)
and asserts the key names that readkey() produces.
"""

from __future__ import annotations

import os
import pty
import sys
from collections.abc import Generator

import pytest

from terminal import TTY as Terminal
from terminal.term import Paste

# ── TTY.render ────────────────────────────────────────────────────


def test_draw_writes_content() -> None:
    """TTY.draw() should write the given lines to the terminal."""
    from os import terminal_size
    from unittest.mock import patch

    from terminal.screen import Screen

    chunks: list[str] = []
    screen = Screen(write=lambda data: chunks.append(data.decode()), flush=lambda: None)
    t = Terminal(screen=screen)
    size = terminal_size((40, 10))
    with patch("terminal.screen.os.get_terminal_size", return_value=size):
        t.draw(["hello", "world"])
    output = "".join(chunks)
    assert "hello" in output
    assert "world" in output


@pytest.fixture
def term() -> Generator[tuple[Terminal, int], None, None]:
    master, slave = pty.openpty()
    old_stdin = sys.stdin
    with open(slave, closefd=False) as f:
        sys.stdin = f
        t = Terminal()
        with t:
            yield t, master
    sys.stdin = old_stdin
    os.close(master)
    os.close(slave)


def send(term_and_master: tuple[Terminal, int], data: bytes) -> str | Paste | None:
    t, master = term_and_master
    os.write(master, data)
    return t.readkey()


# ── Cmd+arrow → home/end ────────────────────────────────────────────


def test_cmd_left(term: tuple[Terminal, int]) -> None:
    assert send(term, b"\x01") == "home"


def test_cmd_right(term: tuple[Terminal, int]) -> None:
    assert send(term, b"\x05") == "end"


# ── Option+arrow → word jump ────────────────────────────────────────


def test_option_left_double_escape(term: tuple[Terminal, int]) -> None:
    assert send(term, b"\x1b\x1b[D") == "word-left"


def test_option_right_double_escape(term: tuple[Terminal, int]) -> None:
    assert send(term, b"\x1b\x1b[C") == "word-right"


def test_option_left_modifier(term: tuple[Terminal, int]) -> None:
    assert send(term, b"\x1b[1;3D") == "word-left"


def test_option_right_modifier(term: tuple[Terminal, int]) -> None:
    assert send(term, b"\x1b[1;3C") == "word-right"


def test_option_left_esc_b(term: tuple[Terminal, int]) -> None:
    assert send(term, b"\x1bb") == "word-left"


def test_option_right_esc_f(term: tuple[Terminal, int]) -> None:
    assert send(term, b"\x1bf") == "word-right"


# ── Mouse scroll (SGR mode) ─────────────────────────────────────────


def test_scroll_up_mouse(term: tuple[Terminal, int]) -> None:
    assert send(term, b"\x1b[<64;10;20M") == "scroll-up"


def test_scroll_down_mouse(term: tuple[Terminal, int]) -> None:
    assert send(term, b"\x1b[<65;10;20M") == "scroll-down"


def test_mouse_click_ignored(term: tuple[Terminal, int]) -> None:
    """Regular mouse click (button 0) should return None."""
    assert send(term, b"\x1b[<0;10;20M") is None


def test_mouse_release_ignored(term: tuple[Terminal, int]) -> None:
    """Mouse release (lowercase m) should return None for non-scroll."""
    assert send(term, b"\x1b[<0;10;20m") is None


# ── Basic keys ───────────────────────────────────────────────────────


def test_arrow_up(term: tuple[Terminal, int]) -> None:
    assert send(term, b"\x1b[A") == "up"


def test_arrow_down(term: tuple[Terminal, int]) -> None:
    assert send(term, b"\x1b[B") == "down"


def test_arrow_right(term: tuple[Terminal, int]) -> None:
    assert send(term, b"\x1b[C") == "right"


def test_arrow_left(term: tuple[Terminal, int]) -> None:
    assert send(term, b"\x1b[D") == "left"


def test_enter(term: tuple[Terminal, int]) -> None:
    assert send(term, b"\r") == "enter"


def test_tab(term: tuple[Terminal, int]) -> None:
    assert send(term, b"\t") == "tab"


def test_shift_tab(term: tuple[Terminal, int]) -> None:
    assert send(term, b"\x1b[Z") == "shift-tab"


def test_backspace(term: tuple[Terminal, int]) -> None:
    assert send(term, b"\x7f") == "backspace"


def test_delete(term: tuple[Terminal, int]) -> None:
    assert send(term, b"\x1b[3~") == "delete"


def test_page_up(term: tuple[Terminal, int]) -> None:
    assert send(term, b"\x1b[5~") == "page-up"


def test_page_down(term: tuple[Terminal, int]) -> None:
    assert send(term, b"\x1b[6~") == "page-down"


def test_home(term: tuple[Terminal, int]) -> None:
    assert send(term, b"\x1b[H") == "home"


def test_end(term: tuple[Terminal, int]) -> None:
    assert send(term, b"\x1b[F") == "end"


def test_printable_char(term: tuple[Terminal, int]) -> None:
    assert send(term, b"a") == "a"


def test_space(term: tuple[Terminal, int]) -> None:
    assert send(term, b" ") == "space"


def test_ctrl_q(term: tuple[Terminal, int]) -> None:
    assert send(term, b"\x11") == "ctrl-q"


def test_delete_word(term: tuple[Terminal, int]) -> None:
    assert send(term, b"\x17") == "delete-word"


def test_clear_line(term: tuple[Terminal, int]) -> None:
    assert send(term, b"\x15") == "clear-line"


def test_esc(term: tuple[Terminal, int]) -> None:
    assert send(term, b"\x1b") == "esc"


def test_focus(term: tuple[Terminal, int]) -> None:
    assert send(term, b"\x1b[I") == "focus"


def test_focus_lost(term: tuple[Terminal, int]) -> None:
    assert send(term, b"\x1b[O") is None


# ── active / suspend / resume ──────────────────────────────────────


def test_active_inside_context() -> None:
    master, slave = pty.openpty()
    old_stdin = sys.stdin
    with open(slave, closefd=False) as f:
        sys.stdin = f
        t = Terminal()
        assert not t.active
        with t:
            assert t.active
        assert not t.active
    sys.stdin = old_stdin
    os.close(master)
    os.close(slave)


def test_suspend_resume(term: tuple[Terminal, int]) -> None:
    t, _ = term
    assert t.active
    t.suspend()
    t.resume()
    assert t.active


# ── resource cleanup ───────────────────────────────────────────────


def _count_fds() -> int:
    """Count open file descriptors for the current process."""
    count = 0
    for fd in range(256):
        try:
            os.fstat(fd)
            count += 1
        except OSError:
            pass
    return count


def test_no_fd_leak_after_exit() -> None:
    """Entering and exiting TTY should not leak file descriptors."""
    master, slave = pty.openpty()
    old_stdin = sys.stdin
    with open(slave, closefd=False) as f:
        sys.stdin = f
        before = _count_fds()
        t = Terminal()
        with t:
            pass
        after = _count_fds()
    sys.stdin = old_stdin
    os.close(master)
    os.close(slave)
    assert after == before
