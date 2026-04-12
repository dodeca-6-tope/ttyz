"""Tests for Input component."""

from terminal import input
from terminal.components.input import InputBuffer, display_text
from terminal.keys import Paste
from terminal.measure import strip_ansi


def test_renders_value():
    ti = InputBuffer("hello")
    assert "hello" in strip_ansi(input(ti).render(80)[0])


def test_placeholder_when_empty_and_inactive():
    ti = InputBuffer()
    lines = input(ti, placeholder="type here", active=False).render(80)
    assert "type here" in strip_ansi(lines[0])


def test_cursor_when_active():
    ti = InputBuffer("abc")
    lines = input(ti, active=True).render(80)
    assert "\033[7m" in lines[0]


def test_no_cursor_when_inactive():
    ti = InputBuffer("abc")
    lines = input(ti, active=False).render(80)
    assert "\033[7m" not in lines[0]


def test_wraps_long_content():
    ti = InputBuffer("a" * 100)
    assert len(input(ti).render(40)) > 1


def test_paste_display():
    ti = InputBuffer()
    ti.handle_key(Paste(text="long pasted text here"))
    assert "[Pasted +" in display_text(ti)


def test_flex_basis():
    assert input(InputBuffer("hello")).flex_basis > 0
    assert input(InputBuffer()).flex_basis == 0
