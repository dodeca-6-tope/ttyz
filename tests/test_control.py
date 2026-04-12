"""Tests for terminal control commands."""

from terminal import (
    CursorBack,
    CursorDown,
    CursorForward,
    CursorShape,
    CursorUp,
    DeleteChars,
    DeleteLines,
    EraseChars,
    EraseDisplay,
    EraseLine,
    HideCursor,
    InsertChars,
    InsertLines,
    MoveTo,
    ResetScrollRegion,
    RestoreCursor,
    SaveCursor,
    ScrollDown,
    ScrollUp,
    SetClipboard,
    SetScrollRegion,
    SetTitle,
    ShowCursor,
)


def test_cursor_shape():
    assert CursorShape(2).sequence() == "\033[2 q"
    assert CursorShape(6).sequence() == "\033[6 q"


def test_show_hide_cursor():
    assert ShowCursor().sequence() == "\033[?25h"
    assert HideCursor().sequence() == "\033[?25l"


def test_move_to():
    assert MoveTo(10, 20).sequence() == "\033[10;20H"


def test_cursor_movement():
    assert CursorUp(3).sequence() == "\033[3A"
    assert CursorDown().sequence() == "\033[1B"
    assert CursorForward(5).sequence() == "\033[5C"
    assert CursorBack(2).sequence() == "\033[2D"


def test_save_restore_cursor():
    assert SaveCursor().sequence() == "\033[s"
    assert RestoreCursor().sequence() == "\033[u"


def test_erase():
    assert EraseDisplay(0).sequence() == "\033[0J"
    assert EraseDisplay(2).sequence() == "\033[2J"
    assert EraseLine(0).sequence() == "\033[0K"
    assert EraseLine(2).sequence() == "\033[2K"
    assert EraseChars(5).sequence() == "\033[5X"


def test_scroll_region():
    assert SetScrollRegion(5, 20).sequence() == "\033[5;20r"
    assert ResetScrollRegion().sequence() == "\033[r"


def test_scroll():
    assert ScrollUp(3).sequence() == "\033[3S"
    assert ScrollDown(1).sequence() == "\033[1T"


def test_insert_delete():
    assert InsertLines(2).sequence() == "\033[2L"
    assert DeleteLines(3).sequence() == "\033[3M"
    assert InsertChars(1).sequence() == "\033[1@"
    assert DeleteChars(4).sequence() == "\033[4P"


def test_set_title():
    assert SetTitle("my app").sequence() == "\033]2;my app\033\\"


def test_set_clipboard():
    import base64

    result = SetClipboard("hello").sequence()
    assert result.startswith("\033]52;c;")
    assert result.endswith("\033\\")
    encoded = result[len("\033]52;c;") : -len("\033\\")]
    assert base64.b64decode(encoded).decode() == "hello"
