"""Tests for style helpers — the contract is:

1. Each helper wraps text with styling
2. strip_ansi recovers the original text
3. Helpers compose (nest without breaking)
"""

from terminal import (
    bg,
    bg_rgb,
    blink,
    bold,
    color,
    dim,
    invisible,
    italic,
    overline,
    reverse,
    rgb,
    strikethrough,
    underline,
)
from terminal.measure import strip_ansi


def test_each_helper_wraps_text():
    for fn in [
        bold,
        dim,
        italic,
        underline,
        blink,
        reverse,
        invisible,
        strikethrough,
        overline,
    ]:
        result = fn("hi")
        assert strip_ansi(result) == "hi"
        assert len(result) > len("hi")  # has escape codes


def test_color_wraps_text():
    assert strip_ansi(color(196, "hi")) == "hi"


def test_bg_wraps_text():
    assert strip_ansi(bg(22, "hi")) == "hi"


def test_rgb_wraps_text():
    assert strip_ansi(rgb(255, 128, 0, "hi")) == "hi"


def test_bg_rgb_wraps_text():
    assert strip_ansi(bg_rgb(10, 20, 30, "hi")) == "hi"


def test_compose_two():
    result = bold(color(1, "hi"))
    assert strip_ansi(result) == "hi"


def test_compose_rgb_and_attr():
    result = bold(rgb(255, 0, 0, "hi"))
    assert strip_ansi(result) == "hi"


def test_compose_fg_and_bg():
    result = rgb(255, 0, 0, bg_rgb(0, 0, 255, "hi"))
    assert strip_ansi(result) == "hi"
