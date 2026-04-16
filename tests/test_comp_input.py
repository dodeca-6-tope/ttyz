"""Tests for Input component."""

from conftest import SnapFn

from ttyz import input
from ttyz.components.input import InputBuffer, display_text
from ttyz.keys import Paste


def test_renders_value(snap: SnapFn):
    snap(input(InputBuffer("hello")), 80)


def test_placeholder_when_empty_and_inactive(snap: SnapFn):
    snap(input(InputBuffer(), placeholder="type here", active=False), 80)


def test_cursor_when_active(snap: SnapFn):
    snap(input(InputBuffer("abc"), active=True), 80)


def test_no_cursor_when_inactive(snap: SnapFn):
    snap(input(InputBuffer("abc"), active=False), 80)


def test_wraps_long_content(snap: SnapFn):
    snap(input(InputBuffer("a" * 100)), 40)


def test_paste_display():
    ti = InputBuffer()
    ti.handle_key(Paste(text="long pasted text here"))
    assert "[Pasted +" in display_text(ti)


def test_intrinsic_width(snap: SnapFn):
    from ttyz import hstack, text

    snap(
        hstack(input(InputBuffer("hello")), text("|")),
        20,
        name="intrinsic_width_with_content",
    )
    snap(
        hstack(input(InputBuffer(), active=False), text("|")),
        20,
        name="intrinsic_width_empty",
    )


def test_empty_paste_no_degenerate_range():
    ti = InputBuffer("hello")
    ti.handle_key(Paste(text=""))
    assert ti.pastes == []
