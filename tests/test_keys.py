"""Tests for terminal.keys — KeyReader.read() contract.

All tests go through the public API: KeyReader.read().
Internal parse functions are not tested directly.
"""

import os

from ttyz.keys import Event, Focus, Key, KeyReader, Mouse, Paste


def _read_all(data: bytes) -> list[Event]:
    """Feed data into a KeyReader and collect all events."""
    r, w = os.pipe()
    os.write(w, data)
    os.close(w)
    kr = KeyReader(r)
    events: list[Event] = []
    while (e := kr.read(0)) is not None:
        events.append(e)
    os.close(r)
    return events


def _read_one(data: bytes) -> Event | None:
    r, w = os.pipe()
    os.write(w, data)
    os.close(w)
    kr = KeyReader(r)
    result = kr.read(0)
    os.close(r)
    return result


# ── Printable characters ─────────────────────────────────────────────


def test_printable_chars():
    assert _read_all(b"abc") == ["a", "b", "c"]


def test_empty_returns_none():
    assert _read_one(b"") is None


# ── Special keys ─────────────────────────────────────────────────────


def test_enter():
    assert _read_one(b"\r") == "enter"


def test_tab():
    assert _read_one(b"\t") == "tab"


def test_backspace():
    assert _read_one(b"\x7f") == "backspace"


def test_space():
    assert _read_one(b" ") == "space"


def test_escape():
    assert _read_one(b"\x1b") == "esc"


# ── Arrow keys ───────────────────────────────────────────────────────


def test_arrows():
    events = _read_all(b"\x1b[A\x1b[B\x1b[C\x1b[D")
    assert events == ["up", "down", "right", "left"]


def test_home_end():
    events = _read_all(b"\x1b[H\x1b[F")
    assert events == ["home", "end"]


def test_page_keys():
    events = _read_all(b"\x1b[5~\x1b[6~")
    assert events == ["page-up", "page-down"]


def test_delete():
    assert _read_one(b"\x1b[3~") == "delete"


def test_shift_tab():
    assert _read_one(b"\x1b[Z") == "shift-tab"


# ── Modifier keys ────────────────────────────────────────────────────


def test_option_arrows():
    events = _read_all(b"\x1b[1;3C\x1b[1;3D")
    assert events == ["word-right", "word-left"]


def test_alt_keys():
    events = _read_all(b"\x1b\x7f\x1bb\x1bf")
    assert events == ["delete-word", "word-left", "word-right"]


def test_double_escape_arrows():
    events = _read_all(b"\x1b\x1b[C\x1b\x1b[D")
    assert events == ["word-right", "word-left"]


# ── Mouse ────────────────────────────────────────────────────────────


def test_scroll_events():
    events = _read_all(b"\x1b[<64;10;20M\x1b[<65;10;20M")
    assert len(events) == 2
    assert all(isinstance(e, Mouse) for e in events)


def test_many_scroll_events():
    events = _read_all(b"\x1b[<64;10;20M" * 50)
    assert len(events) == 50
    assert all(isinstance(e, Mouse) for e in events)


def test_click_ignored():
    assert _read_one(b"\x1b[<0;10;20M") is None


# ── Focus ────────────────────────────────────────────────────────────


def test_focus_gained():
    assert _read_one(b"\x1b[I") == Focus(gained=True)


def test_focus_lost():
    assert _read_one(b"\x1b[O") == Focus(gained=False)


# ── Paste ────────────────────────────────────────────────────────────


def test_paste():
    result = _read_one(b"\x1b[200~hello world\x1b[201~")
    assert isinstance(result, Paste)
    assert result.text == "hello world"


def test_paste_converts_cr():
    result = _read_one(b"\x1b[200~line1\rline2\x1b[201~")
    assert isinstance(result, Paste)
    assert result.text == "line1\nline2"


def test_paste_split_across_reads():
    """End marker arrives in a separate read — must not busy-loop."""
    import threading
    import time

    r, w = os.pipe()
    kr = KeyReader(r)

    def delayed_write():
        # First chunk: start marker + content (no end marker)
        os.write(w, b"\x1b[200~hello ")
        time.sleep(0.02)
        # Second chunk: rest of content + end marker
        os.write(w, b"world\x1b[201~")

    t = threading.Thread(target=delayed_write)
    t.start()
    result = kr.read(timeout=1.0)
    t.join()
    os.close(r)
    os.close(w)

    assert isinstance(result, Paste)
    assert result.text == "hello world"


# ── Kitty keyboard protocol ─────────────────────────────────────────


def test_kitty_unmodified():
    """CSI u without modifiers returns a plain Key."""
    assert _read_one(b"\x1b[97u") == "a"
    assert _read_one(b"\x1b[13u") == "enter"
    assert _read_one(b"\x1b[9u") == "tab"


def test_kitty_ctrl():
    result = _read_one(b"\x1b[97;5u")
    assert isinstance(result, Key)
    assert result.name == "a"
    assert result.ctrl


def test_kitty_shift():
    result = _read_one(b"\x1b[97;2u")
    assert isinstance(result, Key)
    assert result.shift


def test_kitty_alt():
    result = _read_one(b"\x1b[97;3u")
    assert isinstance(result, Key)
    assert result.alt


def test_kitty_super():
    result = _read_one(b"\x1b[97;9u")
    assert isinstance(result, Key)
    assert result.super


def test_kitty_ctrl_shift():
    result = _read_one(b"\x1b[97;6u")
    assert isinstance(result, Key)
    assert result.ctrl and result.shift


def test_kitty_modified_tilde():
    """Ctrl+Delete via Kitty protocol."""
    result = _read_one(b"\x1b[3;5~")
    assert isinstance(result, Key)
    assert result.name == "delete"
    assert result.ctrl


def test_kitty_modified_arrow():
    """Ctrl+Up via Kitty protocol."""
    result = _read_one(b"\x1b[1;5A")
    assert isinstance(result, Key)
    assert result.name == "up"
    assert result.ctrl


# ── Sequence boundaries ──────────────────────────────────────────────


def test_sequences_dont_bleed():
    """Each sequence is self-contained — no byte bleeding."""
    events = _read_all(
        b"\x1b[A"  # up
        b"\x1b[<64;1;1M"  # mouse
        b"\x1b[5~"  # page-up
        b"\x1b[1;3D"  # word-left
        b"x"  # char
        b"\x1b[200~hi\x1b[201~"  # paste
        b"\x1b[97;5u"  # kitty ctrl+a
    )
    assert events[0] == "up"
    assert isinstance(events[1], Mouse)
    assert events[2] == "page-up"
    assert events[3] == "word-left"
    assert events[4] == "x"
    assert isinstance(events[5], Paste)
    assert isinstance(events[6], Key) and events[6].ctrl


# ── Key equality ─────────────────────────────────────────────────────


def test_key_equals_string():
    assert Key("q") == "q"
    assert Key("tab") == "tab"


def test_key_not_equal_wrong_string():
    assert Key("q") != "x"


# ── UTF-8 ────────────────────────────────────────────────────────────


def test_utf8_chars():
    events = _read_all("é你".encode())
    assert events == ["é", "你"]


# ── Ctrl keys ────────────────────────────────────────────────────────


def test_ctrl_keys():
    assert _read_one(b"\x02") == "ctrl-b"
    assert _read_one(b"\x04") == "ctrl-d"
    assert _read_one(b"\x11") == "ctrl-q"


def test_ctrl_c_legacy():
    assert _read_one(b"\x03") == "ctrl-c"


def test_kitty_ctrl_c():
    result = _read_one(b"\x1b[99;5u")
    assert isinstance(result, Key)
    assert result.name == "c"
    assert result.ctrl


# ── Mouse fields ─────────────────────────────────────────────────────


def test_mouse_scroll_fields():
    result = _read_one(b"\x1b[<64;42;99M")
    assert isinstance(result, Mouse)
    assert result.action == "scroll-up"
    assert result.x == 42
    assert result.y == 99


# ── Kitty modified f-key ─────────────────────────────────────────────


def test_kitty_modified_fkey():
    result = _read_one(b"\x1b[15;3~")  # Alt+F5
    assert isinstance(result, Key)
    assert result.name == "f5"
    assert result.alt


# ── Key equality ────────────────────────────────────────────────────


def test_key_equality_between_key_objects():
    k1 = Key("enter")
    k2 = Key("enter")
    assert k1 is not k2
    assert k1 == k2


def test_key_equality_with_modifiers():
    k1 = Key("a", ctrl=True)
    k2 = Key("a", ctrl=True)
    assert k1 is not k2
    assert k1 == k2


def test_key_inequality_different_modifiers():
    assert Key("a") != Key("a", ctrl=True)
    assert Key("a", shift=True) != Key("a", alt=True)


def test_key_hash_consistent_with_equality():
    k = Key("enter")
    assert k == "enter"
    assert hash(k) == hash("enter")


def test_key_dict_lookup_by_string():
    d: dict[Key | str, str] = {Key("enter"): "found"}
    assert d.get("enter") == "found"


def test_key_set_membership_by_string():
    s = {Key("enter")}
    assert "enter" in s


def test_key_with_modifiers_not_equal_to_string():
    assert Key("a", ctrl=True) != "a"
    assert Key("enter", shift=True) != "enter"
