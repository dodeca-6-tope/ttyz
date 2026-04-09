"""Tests for Text component."""

from helpers import vis

from terminal import Text, box, text
from terminal.components.text import truncate
from terminal.measure import strip_ansi


# ── Render ───────────────────────────────────────────────────────────


def test_renders_content():
    assert vis(text("hello").render(80)) == ["hello"]


def test_empty():
    assert vis(text().render(80)) == [""]


def test_ansi_passthrough():
    lines = text("\033[1mhi\033[0m").render(80)
    assert "\033[1m" in lines[0]
    assert "hi" in strip_ansi(lines[0])


def test_ansi_color_passthrough():
    lines = text("\033[38;5;1mhi\033[0m").render(80)
    assert "\033[38;5;1m" in lines[0]


# ── Padding ──────────────────────────────────────────────────────────


def test_padding():
    assert vis(text("hi", padding=2).render(80)) == ["··hi··"]


def test_padding_left_right():
    assert vis(text("hi", padding_left=1, padding_right=3).render(80)) == ["·hi···"]


def test_padding_exceeds_width():
    result = vis(text("hi", padding=10).render(5))
    assert len(result) == 1


# ── Width / overflow ─────────────────────────────────────────────────


def test_width_truncates_with_overflow_hidden():
    assert vis(text("hello world", width="8", overflow="hidden").render(80)) == [
        "hello·wo",
    ]


def test_width_no_truncate_when_fits():
    assert vis(text("hi", width="10", overflow="hidden").render(80)) == [
        "hi········",
    ]


def test_width_100pct_truncates_to_budget():
    #                  20 a's clipped to width 20
    assert vis(text("a" * 100, width="100%", overflow="hidden").render(20)) == [
        "a" * 20,
    ]


def test_width_100pct_no_truncate_when_fits():
    assert vis(text("short", width="100%").render(80)) == ["short"]


# ── Multiline ───────────────────────────────────────────────────────


def test_multiline_render():
    assert vis(text("a\nb\nc").render(80)) == ["a", "b", "c"]


def test_multiline_ansi():
    lines = text("\033[1ma\033[0m\n\033[1mb\033[0m").render(80)
    assert strip_ansi(lines[0]) == "a"
    assert strip_ansi(lines[1]) == "b"
    assert all("\033[1m" in l for l in lines)


def test_multiline_flex_basis_uses_widest():
    assert text("short\na longer line").flex_basis == 13


def test_multiline_crlf():
    assert vis(text("a\r\nb").render(80)) == ["a", "b"]


# ── Wrap ─────────────────────────────────────────────────────────────


def test_wrap_word_boundary():
    assert vis(text("hello world foo", wrap=True).render(11)) == [
        "hello·world",
        "foo",
    ]


def test_wrap_char_fallback():
    assert vis(text("abcdefgh", wrap=True).render(3)) == [
        "abc",
        "def",
        "gh",
    ]


def test_wrap_mixed():
    assert vis(text("hi abcdefgh bye", wrap=True).render(5)) == [
        "hi",
        "abcde",
        "fgh",
        "bye",
    ]


def test_wrap_wide_char_fallback():
    assert vis(text("你好世界", wrap=True).render(4)) == ["你好", "世界"]


def test_wrap_preserves_short_line():
    assert vis(text("hi", wrap=True).render(80)) == ["hi"]


def test_wrap_with_newlines():
    assert vis(text("hello world\nfoo bar", wrap=True).render(7)) == [
        "hello",
        "world",
        "foo·bar",
    ]


# ── Truncation mode ──────────────────────────────────────────────────


def test_truncation_tail():
    assert vis(text("hello world", truncation="tail").render(8)) == ["hello·w…"]


def test_truncation_head():
    assert vis(text("hello world", truncation="head").render(8)) == ["…o·world"]


def test_truncation_middle():
    assert vis(text("hello world", truncation="middle").render(8)) == ["hel…orld"]


def test_truncation_no_op_when_fits():
    assert vis(text("hi", truncation="tail").render(80)) == ["hi"]


def test_truncation_inside_box():
    assert vis(box(text("a long line of text", truncation="tail")).render(10)) == [
        "╭────────╮",
        "│a·long·…│",
        "╰────────╯",
    ]


# ── Flex layout ──────────────────────────────────────────────────────


def test_flex_basis():
    assert text("hello").flex_basis == 5
    assert text("hi", padding=1).flex_basis == 4


def test_flex_basis_with_100pct_width():
    assert text("hello", width="100%").flex_basis == 5


def test_flex_grow_with_100pct_width():
    assert text("hello", grow=1).grow
    assert not text("hello").grow


# ── Display width ────────────────────────────────────────────────────


def test_display_width():
    assert len(Text("hello")) == 5
    assert len(Text("\033[1mhello\033[0m")) == 5
    assert len(Text("")) == 0
    assert len(Text("日本")) == 4


# ── Pad ──────────────────────────────────────────────────────────────


def test_pad():
    assert str(Text("hi").pad(5)) == "hi   "
    assert str(Text("hi").pad(5, align="right")) == "   hi"
    t = Text("hello")
    assert t.pad(3) is t


def test_pad_ansi():
    padded = Text("\033[1mhi\033[0m").pad(5)
    assert len(padded) == 5
    assert str(padded) == "\033[1mhi\033[0m   "


# ── Truncate (standalone function) ───────────────────────────────────


def test_truncate():
    assert truncate("short", 10) == "short"
    assert truncate("hello world", 8) == "hello wo"


def test_truncate_ellipsis():
    assert truncate("hello world", 8, ellipsis=True) == "hello w…"


def test_truncate_strips_ansi():
    assert truncate("\033[1mhello world\033[0m", 8) == "hello wo"


def test_truncate_no_op_when_fits():
    assert truncate("hi", 10) == "hi"


def test_truncate_wide_chars():
    assert truncate("你好世界", 4) == "你好"


def test_truncate_wide_chars_ellipsis():
    assert truncate("你好世界", 5, ellipsis=True) == "你好…"


def test_truncate_wide_chars_no_op():
    assert truncate("你好", 4) == "你好"


# ── Concatenation ────────────────────────────────────────────────────


def test_concatenation():
    result = Text("hello") + Text(" world")
    assert str(result) == "hello world"
    assert len(result) == 11
    assert str(Text("hello") + " world") == "hello world"
    assert str("hello " + Text("world")) == "hello world"


def test_str_representation():
    raw = "\033[32mgreen\033[0m"
    assert str(Text(raw)) == raw
    assert f"[{Text('hi').pad(5)}]" == "[hi   ]"


def test_chaining():
    result = Text(truncate("a very long name here", 10)).pad(15)
    assert len(result) == 15
    assert str(result) == "a very lon     "
