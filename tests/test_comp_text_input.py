"""Tests for InputBuffer."""

from terminal import InputBuffer, PasteRange, display_text
from terminal.keys import Key, Paste

# ── Basic typing ─────────────────────────────────────────────────────


def test_empty_initial():
    ti = InputBuffer()
    assert ti.value == ""
    assert ti.cursor == 0


def test_initial_value():
    ti = InputBuffer("hello")
    assert ti.value == "hello"
    assert ti.cursor == 5


def test_type_characters():
    ti = InputBuffer()
    ti.handle_key(Key("a"))
    ti.handle_key(Key("b"))
    ti.handle_key(Key("c"))
    assert ti.value == "abc"
    assert ti.cursor == 3


def test_type_space():
    ti = InputBuffer("ab")
    ti.handle_key(Key("space"))
    ti.handle_key(Key("c"))
    assert ti.value == "ab c"


def test_type_char_returns_true_and_preserves():
    ti = InputBuffer()
    assert ti.handle_key(Key("x")) is True
    ti2 = InputBuffer("hello")
    ti2.cursor = 5
    ti2.handle_key(Key("!"))
    assert ti2.value == "hello!"


def test_type_unicode():
    ti = InputBuffer()
    ti.handle_key(Key("é"))
    ti.handle_key(Key("ñ"))
    assert ti.value == "éñ"
    assert ti.cursor == 2


def test_non_printable_returns_false():
    ti = InputBuffer()
    assert ti.handle_key(Key("\x01")) is False
    assert ti.value == ""


# ── Cursor navigation ───────────────────────────────────────────────


def test_left_right():
    ti = InputBuffer("abc")
    ti.handle_key(Key("left"))
    assert ti.cursor == 2
    ti.handle_key(Key("left"))
    assert ti.cursor == 1
    ti.handle_key(Key("right"))
    assert ti.cursor == 2


def test_left_at_start():
    ti = InputBuffer("abc")
    ti.cursor = 0
    ti.handle_key(Key("left"))
    assert ti.cursor == 0


def test_right_at_end():
    ti = InputBuffer("abc")
    ti.handle_key(Key("right"))
    assert ti.cursor == 3


def test_home_end():
    ti = InputBuffer("hello world")
    ti.handle_key(Key("home"))
    assert ti.cursor == 0
    ti.handle_key(Key("end"))
    assert ti.cursor == 11


def test_home_end_on_empty():
    ti = InputBuffer()
    ti.handle_key(Key("home"))
    assert ti.cursor == 0
    ti.handle_key(Key("end"))
    assert ti.cursor == 0


def test_word_left():
    ti = InputBuffer("hello world foo")
    ti.handle_key(Key("word-left"))
    assert ti.cursor == 12  # on 'f' of "foo"
    ti.handle_key(Key("word-left"))
    assert ti.cursor == 6  # on 'w' of "world"
    ti.handle_key(Key("word-left"))
    assert ti.cursor == 0  # on 'h' of "hello"
    ti.handle_key(Key("word-left"))
    assert ti.cursor == 0  # stays at start


def test_word_right():
    ti = InputBuffer("hello world foo")
    ti.cursor = 0
    ti.handle_key(Key("word-right"))
    assert ti.cursor == 5  # end of "hello"
    ti.handle_key(Key("word-right"))
    assert ti.cursor == 11  # end of "world"
    ti.handle_key(Key("word-right"))
    assert ti.cursor == 15  # end of "foo"
    ti.handle_key(Key("word-right"))
    assert ti.cursor == 15  # stays at end


def test_word_nav_single_word():
    ti = InputBuffer("hello")
    ti.handle_key(Key("word-left"))
    assert ti.cursor == 0
    ti.handle_key(Key("word-right"))
    assert ti.cursor == 5


def test_word_left_multiple_spaces():
    ti = InputBuffer("hello   world")
    ti.handle_key(Key("word-left"))
    assert ti.cursor == 8  # on 'w' of "world"
    ti.handle_key(Key("word-left"))
    assert ti.cursor == 0


def test_word_right_multiple_spaces():
    ti = InputBuffer("hello   world")
    ti.cursor = 0
    ti.handle_key(Key("word-right"))
    assert ti.cursor == 5  # end of "hello"


def test_word_left_from_middle_of_word():
    ti = InputBuffer("hello world")
    ti.cursor = 8  # on 'r' of "world"
    ti.handle_key(Key("word-left"))
    assert ti.cursor == 6  # on 'w' of "world"


def test_word_right_from_middle_of_word():
    ti = InputBuffer("hello world")
    ti.cursor = 2  # on 'l' of "hello"
    ti.handle_key(Key("word-right"))
    assert ti.cursor == 5  # end of "hello"


# ── Backspace ────────────────────────────────────────────────────────


def test_backspace():
    ti = InputBuffer("abc")
    ti.handle_key(Key("backspace"))
    assert ti.value == "ab"
    assert ti.cursor == 2


def test_backspace_at_start():
    ti = InputBuffer("abc")
    ti.cursor = 0
    ti.handle_key(Key("backspace"))
    assert ti.value == "abc"
    assert ti.cursor == 0


def test_backspace_middle():
    ti = InputBuffer("abc")
    ti.cursor = 2
    ti.handle_key(Key("backspace"))
    assert ti.value == "ac"
    assert ti.cursor == 1


def test_backspace_all_and_empty():
    ti = InputBuffer("ab")
    ti.handle_key(Key("backspace"))
    ti.handle_key(Key("backspace"))
    assert ti.value == ""
    assert ti.cursor == 0
    ti.handle_key(Key("backspace"))
    assert ti.value == ""
    assert ti.cursor == 0


# ── Clear line / delete word ─────────────────────────────────────────


def test_clear_line():
    ti = InputBuffer("hello world")
    ti.cursor = 6
    ti.handle_key(Key("clear-line"))
    assert ti.value == "world"
    assert ti.cursor == 0


def test_clear_line_boundaries():
    ti = InputBuffer("hello")
    ti.cursor = 0
    ti.handle_key(Key("clear-line"))
    assert ti.value == "hello"
    assert ti.cursor == 0
    ti.cursor = 5
    ti.handle_key(Key("clear-line"))
    assert ti.value == ""
    assert ti.cursor == 0


def test_delete_word():
    ti = InputBuffer("hello world")
    ti.handle_key(Key("delete-word"))
    assert ti.value == "hello "
    assert ti.cursor == 6


def test_delete_word_boundaries():
    ti = InputBuffer("hello")
    ti.cursor = 0
    ti.handle_key(Key("delete-word"))
    assert ti.value == "hello"
    assert ti.cursor == 0
    ti.cursor = 5
    ti.handle_key(Key("delete-word"))
    assert ti.value == ""
    assert ti.cursor == 0


def test_delete_word_with_trailing_spaces():
    ti = InputBuffer("hello   ")
    ti.handle_key(Key("delete-word"))
    assert ti.value == ""
    assert ti.cursor == 0


def test_delete_word_at_word_boundary():
    """delete-word when cursor is right after a space."""
    ti = InputBuffer("hello world")
    ti.cursor = 6  # right after the space, on 'w'
    ti.handle_key(Key("delete-word"))
    assert ti.value == "world"
    assert ti.cursor == 0


def test_delete_word_multiple_times():
    ti = InputBuffer("one two three")
    ti.handle_key(Key("delete-word"))
    assert ti.value == "one two "
    ti.handle_key(Key("delete-word"))
    assert ti.value == "one "
    ti.handle_key(Key("delete-word"))
    assert ti.value == ""


# ── Insert in middle ────────────────────────────────────────────────


def test_insert_middle():
    ti = InputBuffer("ac")
    ti.cursor = 1
    ti.handle_key(Key("b"))
    assert ti.value == "abc"
    assert ti.cursor == 2


def test_insert_at_start():
    ti = InputBuffer("bc")
    ti.cursor = 0
    ti.handle_key(Key("a"))
    assert ti.value == "abc"
    assert ti.cursor == 1


def test_insert_space_middle():
    ti = InputBuffer("helloworld")
    ti.cursor = 5
    ti.handle_key(Key("space"))
    assert ti.value == "hello world"
    assert ti.cursor == 6


# ── Paste ────────────────────────────────────────────────────────────


def test_paste():
    ti = InputBuffer()
    ti.handle_key(Paste(text="hello world this is a long prompt"))
    assert ti.value == "hello world this is a long prompt"
    assert ti.cursor == 33


def test_paste_display_shows_placeholder():
    ti = InputBuffer()
    ti.handle_key(Paste(text="hello world this is pasted text"))
    display = display_text(ti)
    assert "[Pasted +" in display
    assert "hello world" not in display


def test_paste_backspace_deletes_whole_paste():
    ti = InputBuffer()
    ti.handle_key(Paste(text="some long pasted text here"))
    assert ti.value == "some long pasted text here"
    ti.handle_key(Key("backspace"))
    assert ti.value == ""
    assert ti.cursor == 0


def test_paste_then_type_then_backspace():
    ti = InputBuffer()
    ti.handle_key(Paste(text="pasted text"))
    ti.handle_key(Key("x"))
    assert ti.value == "pasted textx"
    ti.handle_key(Key("backspace"))  # deletes 'x'
    assert ti.value == "pasted text"
    ti.handle_key(Key("backspace"))  # deletes entire paste
    assert ti.value == ""


def test_paste_preserves_control_chars():
    ti = InputBuffer()
    ti.handle_key(Paste(text="line one\nline two\tline three"))
    assert ti.value == "line one\nline two\tline three"
    ti2 = InputBuffer()
    ti2.handle_key(Paste(text="line one\r\nline two"))
    assert ti2.value == "line one\r\nline two"


def test_display_sanitizes_control_chars():
    ti = InputBuffer("line one\nline two")
    assert "↵" in display_text(ti)
    assert "\n" not in display_text(ti)
    assert "\t" not in display_text(InputBuffer("col1\tcol2"))
    ti2 = InputBuffer("line one\r\nline two")
    assert "\r" not in display_text(ti2)
    assert "\n" not in display_text(ti2)


def test_paste_with_newlines_display_cursor_correct():
    """Cursor should still work after pasting content with newlines."""
    ti = InputBuffer()
    ti.handle_key(Paste(text="a\nb\nc"))
    assert ti.cursor == 5
    assert ti.value == "a\nb\nc"
    # Display should have paste placeholder, not raw content
    display = display_text(ti)
    assert "\n" not in display


def test_type_then_paste():
    ti = InputBuffer()
    ti.handle_key(Key("a"))
    ti.handle_key(Key("b"))
    ti.handle_key(Paste(text="pasted stuff"))
    assert ti.value == "abpasted stuff"
    ti.handle_key(Key("backspace"))  # deletes paste
    assert ti.value == "ab"


def test_paste_in_middle():
    ti = InputBuffer("ac")
    ti.cursor = 1
    ti.handle_key(Paste(text="pasted text"))
    assert ti.value == "apasted textc"
    assert ti.cursor == 12


def test_paste_in_middle_backspace():
    ti = InputBuffer("ac")
    ti.cursor = 1
    ti.handle_key(Paste(text="pasted text"))
    assert ti.value == "apasted textc"
    ti.handle_key(Key("backspace"))
    assert ti.value == "ac"
    assert ti.cursor == 1


def test_multiple_pastes():
    ti = InputBuffer()
    ti.handle_key(Paste(text="first paste"))
    ti.handle_key(Key(" "))
    ti.handle_key(Paste(text="second paste"))
    assert ti.value == "first paste second paste"
    ti.handle_key(Key("backspace"))  # deletes second paste
    assert ti.value == "first paste "
    ti.handle_key(Key("backspace"))  # deletes space
    assert ti.value == "first paste"
    ti.handle_key(Key("backspace"))  # deletes first paste
    assert ti.value == ""


def test_paste_edge_cases():
    ti = InputBuffer("hello")
    ti.handle_key(Paste(text=""))
    assert ti.value == "hello"
    assert ti.cursor == 5
    ti2 = InputBuffer()
    ti2.handle_key(Paste(text="x"))
    assert ti2.value == "x"
    assert len(ti2.pastes) == 1


def test_paste_preserves_value_after_clear():
    ti = InputBuffer()
    ti.handle_key(Paste(text="pasted"))
    ti.handle_key(Key("clear-line"))
    assert ti.value == ""
    assert ti.pastes == []


# ── Display ──────────────────────────────────────────────────────────


def test_display_no_paste():
    ti = InputBuffer("abc")
    assert display_text(ti) == "abc"


def test_display_empty():
    ti = InputBuffer()
    assert display_text(ti) == ""


def test_display_paste_placeholder_length():
    ti = InputBuffer()
    ti.handle_key(Paste(text="x" * 100))
    display = display_text(ti)
    assert "[Pasted +100 chars]" in display
    assert len(display) < 100  # much shorter than raw value


def test_display_typed_around_paste():
    ti = InputBuffer()
    ti.handle_key(Key("a"))
    ti.handle_key(Key("b"))
    ti.handle_key(Paste(text="long pasted content"))
    ti.handle_key(Key("c"))
    display = display_text(ti)
    assert display.startswith("ab")
    assert "[Pasted +" in display


# ── Unknown keys ─────────────────────────────────────────────────────


def test_unknown_keys():
    ti = InputBuffer()
    for key in ["up", "down", "tab", "esc", "enter", "ctrl-r", "focus", "shift-tab"]:
        assert ti.handle_key(Key(key)) is False
    ti2 = InputBuffer("hello")
    for key in ["up", "down", "tab"]:
        ti2.handle_key(Key(key))
    assert ti2.value == "hello"
    assert ti2.cursor == 5


# ── Paste navigation ────────────────────────────────────────────────


def test_type_at_paste_start():
    """Typing at start of paste inserts before it."""
    ti = InputBuffer()
    ti.handle_key(Paste(text="hello world pasted"))
    ti.handle_key(Key("home"))
    assert ti.cursor == 0
    ti.handle_key(Key("x"))
    assert ti.value == "xhello world pasted"
    assert ti.cursor == 1
    assert ti.pastes == [PasteRange(1, 19)]


def test_paste_at_cursor_between_typed_text():
    ti = InputBuffer()
    ti.handle_key(Key("a"))
    ti.handle_key(Key("b"))
    ti.cursor = 1
    ti.handle_key(Paste(text="pasted text here"))
    assert ti.value == "apasted text hereb"
    assert ti.cursor == 17
    ti.handle_key(Key("backspace"))
    assert ti.value == "ab"
    assert ti.cursor == 1


def test_backspace_at_paste_start():
    """word-left to paste start, then backspace — does nothing."""
    ti = InputBuffer()
    text = "hello world pasted text here"
    ti.handle_key(Paste(text=text))
    ti.handle_key(Key("word-left"))
    assert ti.cursor == 0
    ti.handle_key(Key("backspace"))
    assert ti.value == text


def test_backspace_right_after_paste():
    """Cursor right at end of paste, backspace deletes it."""
    ti = InputBuffer()
    ti.handle_key(Paste(text="hello world here"))
    assert ti.cursor == 16
    ti.handle_key(Key("backspace"))
    assert ti.value == ""
    assert ti.pastes == []


def test_delete_word_after_paste_does_not_eat_paste():
    ti = InputBuffer("hello world pasted x", cursor=20, pastes=[PasteRange(0, 18)])
    ti.handle_key(Key("delete-word"))
    assert ti.value == "hello world pasted "
    assert ti.cursor == 19
    ti.handle_key(Key("delete-word"))
    assert ti.value == "hello world pasted"
    assert ti.cursor == 18
    assert ti.pastes == [PasteRange(0, 18)]


def test_delete_word_at_paste_end():
    """delete-word at end of paste deletes entire paste."""
    ti = InputBuffer()
    ti.handle_key(Paste(text="hello world pasted"))
    ti.handle_key(Key("delete-word"))
    assert ti.value == ""
    assert ti.pastes == []


def test_type_after_paste_via_word_nav():
    """word-left jumps to paste start, typing inserts before paste."""
    ti = InputBuffer()
    text = "hello world pasted text here"
    ti.handle_key(Paste(text=text))
    ti.handle_key(Key("word-left"))
    assert ti.cursor == 0
    ti.handle_key(Key("x"))
    assert ti.value == "x" + text
    assert ti.cursor == 1


# ── Arrow navigation with paste ──────────────────────────────────────


def test_left_arrow_skips_paste():
    """Left arrow at end of paste should jump to start of paste."""
    ti = InputBuffer("ab")
    ti.cursor = 2
    ti.handle_key(Paste(text="cd hello world"))
    ti.handle_key(Key("e"))
    ti.handle_key(Key("f"))
    assert ti.cursor == 18
    ti.handle_key(Key("left"))  # f→e
    assert ti.cursor == 17
    ti.handle_key(Key("left"))  # e→end of paste
    assert ti.cursor == 16
    ti.handle_key(Key("left"))  # skip paste → 2
    assert ti.cursor == 2
    ti.handle_key(Key("left"))  # b
    assert ti.cursor == 1


def test_right_arrow_skips_paste():
    """Right arrow at start of paste should jump to end of paste."""
    ti = InputBuffer("ahello world pastedb", cursor=0, pastes=[PasteRange(1, 19)])
    ti.handle_key(Key("right"))  # a
    assert ti.cursor == 1
    ti.handle_key(Key("right"))  # skip paste → 19
    assert ti.cursor == 19
    ti.handle_key(Key("right"))  # b
    assert ti.cursor == 20


def test_word_left_skips_paste():
    """option+left should treat paste as one unit."""
    ti = InputBuffer()
    for c in "hello":
        ti.handle_key(Key(c))
    ti.handle_key(Key("space"))
    ti.handle_key(Paste(text="big pasted block"))
    ti.handle_key(Key("space"))
    for c in "world":
        ti.handle_key(Key(c))
    assert ti.value == "hello big pasted block world"
    assert ti.cursor == 28
    ti.handle_key(Key("word-left"))  # on 'w' of "world"
    assert ti.cursor == 23
    ti.handle_key(Key("word-left"))  # skips paste → 6
    assert ti.cursor == 6
    ti.handle_key(Key("word-left"))  # on 'h' of "hello"
    assert ti.cursor == 0


def test_word_right_skips_paste():
    """option+right should treat paste as one unit."""
    ti = InputBuffer()
    for c in "hi":
        ti.handle_key(Key(c))
    ti.handle_key(Key("space"))
    ti.handle_key(Paste(text="pasted content here"))
    ti.handle_key(Key("space"))
    for c in "bye":
        ti.handle_key(Key(c))
    assert ti.value == "hi pasted content here bye"
    ti.cursor = 0
    ti.handle_key(Key("word-right"))  # end of "hi"
    assert ti.cursor == 2
    ti.handle_key(Key("word-right"))  # skip paste → end of paste
    assert ti.cursor == 22
    ti.handle_key(Key("word-right"))  # end of "bye"
    assert ti.cursor == 26


def test_word_right_paste_at_start():
    """word-right from pos 0 when paste starts at 0 should stop at paste end."""
    ti = InputBuffer()
    ti.handle_key(Paste(text="hello"))
    for c in " world":
        ti.handle_key(Key(c))
    ti.cursor = 0
    ti.handle_key(Key("word-right"))
    assert ti.cursor == 5  # end of paste, not 11
    ti.handle_key(Key("word-right"))
    assert ti.cursor == 11  # end of "world"


def test_word_right_doesnt_stick_at_paste_end():
    """After landing at paste.end, next word-right must advance past the space."""
    ti = InputBuffer()
    for c in "a ":
        ti.handle_key(Key(c))
    ti.handle_key(Paste(text="bb"))
    for c in " c":
        ti.handle_key(Key(c))
    # value = "a bb c", paste = [2,4)
    ti.cursor = 0
    ti.handle_key(Key("word-right"))
    assert ti.cursor == 1  # end of "a"
    ti.handle_key(Key("word-right"))
    assert ti.cursor == 4  # end of paste
    ti.handle_key(Key("word-right"))
    assert ti.cursor == 6  # end of "c"


def test_left_into_paste_end():
    """Left arrow from just past paste.end should jump to paste.start."""
    ti = InputBuffer("xPASTEDy", cursor=7, pastes=[PasteRange(1, 7)])
    ti.handle_key(Key("left"))  # from 7 (paste end) → 1 (paste start)
    assert ti.cursor == 1


def test_left_right_no_paste():
    """Normal left/right should work as before without pastes."""
    ti = InputBuffer("abc")
    ti.handle_key(Key("left"))
    assert ti.cursor == 2
    ti.handle_key(Key("right"))
    assert ti.cursor == 3


def test_word_nav_with_paste():
    ti = InputBuffer("before ")
    ti.handle_key(Paste(text="pasted words here"))
    ti.handle_key(Key(" "))
    for c in "after":
        ti.handle_key(Key(c))
    assert ti.value == "before pasted words here after"
    ti.handle_key(Key("word-left"))
    assert ti.cursor == 25  # on 'a' of "after"
    ti.handle_key(Key("word-left"))
    assert ti.cursor == 7  # on start of paste


# ── Typed text adjacent to paste ─────────────────────────────────────


def test_word_left_stops_at_paste_typed_boundary():
    """word-left from typed text adjacent to paste should not jump through paste."""
    ti = InputBuffer()
    ti.handle_key(Paste(text="pasted"))
    for c in "dsa":
        ti.handle_key(Key(c))
    # value = "pasteddsa", paste = [0,6), typed = "dsa"
    assert ti.cursor == 9
    ti.handle_key(Key("word-left"))  # should stop at start of "dsa" (pos 6)
    assert ti.cursor == 6
    ti.handle_key(Key("word-left"))  # should jump over paste to 0
    assert ti.cursor == 0


def test_word_right_stops_at_typed_paste_boundary():
    """word-right from typed text adjacent to paste should not jump through paste."""
    ti = InputBuffer()
    for c in "dsa":
        ti.handle_key(Key(c))
    ti.handle_key(Paste(text="pasted"))
    # value = "dsapasted", paste = [3,9), typed = "dsa"
    ti.cursor = 0
    ti.handle_key(Key("word-right"))  # should stop at end of "dsa" (pos 3)
    assert ti.cursor == 3
    ti.handle_key(Key("word-right"))  # should jump over paste to 9
    assert ti.cursor == 9


def test_word_nav_two_pastes_then_typed():
    """Two consecutive pastes followed by typed text should be three word stops."""
    ti = InputBuffer()
    ti.handle_key(Paste(text="aaaa"))
    ti.handle_key(Paste(text="bbbb"))
    for c in "dsa":
        ti.handle_key(Key(c))
    # value = "aaaabbbbdsa", paste1=[0,4), paste2=[4,8), typed="dsa"
    assert ti.cursor == 11
    ti.handle_key(Key("word-left"))  # stop at start of "dsa" (pos 8)
    assert ti.cursor == 8
    ti.handle_key(Key("word-left"))  # skip paste2 → pos 4
    assert ti.cursor == 4
    ti.handle_key(Key("word-left"))  # skip paste1 → pos 0
    assert ti.cursor == 0
    # Now go right
    ti.handle_key(Key("word-right"))  # skip paste1 → pos 4
    assert ti.cursor == 4
    ti.handle_key(Key("word-right"))  # skip paste2 → pos 8
    assert ti.cursor == 8
    ti.handle_key(Key("word-right"))  # end of "dsa" → pos 11
    assert ti.cursor == 11


# ── Edge cases ───────────────────────────────────────────────────────


def test_rapid_backspace_on_empty():
    ti = InputBuffer()
    for _ in range(10):
        ti.handle_key(Key("backspace"))
    assert ti.value == ""
    assert ti.cursor == 0


def test_cursor_stays_in_bounds():
    ti = InputBuffer("a")
    ti.cursor = 0
    ti.handle_key(Key("left"))
    ti.handle_key(Key("word-left"))
    ti.handle_key(Key("home"))
    assert ti.cursor == 0
    ti2 = InputBuffer("abc")
    ti2.handle_key(Key("right"))
    ti2.handle_key(Key("right"))
    ti2.handle_key(Key("word-right"))
    ti2.handle_key(Key("end"))
    assert ti2.cursor == 3


def test_paste_then_clear_line_then_type():
    ti = InputBuffer()
    ti.handle_key(Paste(text="big paste"))
    ti.handle_key(Key("clear-line"))
    ti.handle_key(Key("a"))
    assert ti.value == "a"
    assert ti.pastes == []


def test_multiple_operations_sequence():
    """Full editing sequence: type, paste, navigate, delete, type more."""
    ti = InputBuffer()
    for c in "hello":
        ti.handle_key(Key(c))
    ti.handle_key(Key("space"))
    ti.handle_key(Paste(text="pasted world"))
    ti.handle_key(Key("space"))
    for c in "end":
        ti.handle_key(Key(c))
    assert ti.value == "hello pasted world end"
    # Delete "end"
    ti.handle_key(Key("delete-word"))
    assert ti.value == "hello pasted world "
    # Delete space (stops at paste boundary)
    ti.handle_key(Key("delete-word"))
    assert ti.value == "hello pasted world"
    # Delete paste
    ti.handle_key(Key("delete-word"))
    assert ti.value == "hello "
    # Delete "hello "
    ti.handle_key(Key("delete-word"))
    assert ti.value == ""


# ── Init with pastes ────────────────────────────────────────────────


def test_init_with_pastes():
    """Restoring a InputBuffer with paste ranges preserves display behavior."""
    ti = InputBuffer("hello world pasted text", cursor=22, pastes=[PasteRange(12, 22)])
    assert ti.value == "hello world pasted text"
    assert ti.cursor == 22
    assert ti.pastes == [PasteRange(12, 22)]
    display = display_text(ti)
    assert "[Pasted +" in display
    assert "pasted tex" not in display


def test_init_with_pastes_backspace_deletes_paste():
    ti = InputBuffer("abpasted textc", cursor=13, pastes=[PasteRange(2, 13)])
    ti.handle_key(Key("backspace"))
    assert ti.value == "abc"
    assert ti.cursor == 2


def test_init_with_pastes_navigation():
    """Arrow keys skip over restored paste ranges."""
    ti = InputBuffer("apasted textb", cursor=13, pastes=[PasteRange(1, 12)])
    ti.handle_key(Key("left"))  # b → end of paste
    assert ti.cursor == 12
    ti.handle_key(Key("left"))  # skip paste → 1
    assert ti.cursor == 1
    ti.handle_key(Key("left"))  # a
    assert ti.cursor == 0
    ti.handle_key(Key("right"))  # → 1
    assert ti.cursor == 1
    ti.handle_key(Key("right"))  # skip paste → 12
    assert ti.cursor == 12


def test_init_with_cursor():
    ti = InputBuffer("hello", cursor=2)
    assert ti.cursor == 2
    ti.handle_key(Key("x"))
    assert ti.value == "hexllo"
    assert ti.cursor == 3


def test_init_with_multiple_pastes():
    ti = InputBuffer(
        "first paste second paste", pastes=[PasteRange(0, 11), PasteRange(12, 24)]
    )
    display = display_text(ti)
    assert "[Pasted +" in display
    assert "first paste" not in display
    ti.handle_key(Key("backspace"))  # deletes second paste
    assert ti.value == "first paste "
    assert ti.pastes == [PasteRange(0, 11)]


def test_init_pastes_sorted():
    """Pastes provided out of order are sorted."""
    ti = InputBuffer("aabbcc", pastes=[PasteRange(4, 6), PasteRange(0, 2)])
    assert ti.pastes == [PasteRange(0, 2), PasteRange(4, 6)]
