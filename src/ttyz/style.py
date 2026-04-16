"""ANSI styling helpers — thin wrappers that produce escape codes."""


def _wrap(on: str, off: str, s: str) -> str:
    return f"\033[{on}m{s}\033[{off}m"


def bold(s: str) -> str:
    return _wrap("1", "22", s)


def dim(s: str) -> str:
    return _wrap("2", "22", s)


def italic(s: str) -> str:
    return _wrap("3", "23", s)


def underline(s: str) -> str:
    return _wrap("4", "24", s)


def blink(s: str) -> str:
    return _wrap("5", "25", s)


def reverse(s: str) -> str:
    return _wrap("7", "27", s)


def invisible(s: str) -> str:
    return _wrap("8", "28", s)


def strikethrough(s: str) -> str:
    return _wrap("9", "29", s)


def overline(s: str) -> str:
    return _wrap("53", "55", s)


def color(c: int, s: str) -> str:
    """Apply 256-color foreground."""
    return _wrap(f"38;5;{c}", "39", s)


def bg(c: int, s: str) -> str:
    """Apply 256-color background."""
    return _wrap(f"48;5;{c}", "49", s)


def rgb(r: int, g: int, b: int, s: str) -> str:
    """Apply 24-bit true-color foreground."""
    return _wrap(f"38;2;{r};{g};{b}", "39", s)


def bg_rgb(r: int, g: int, b: int, s: str) -> str:
    """Apply 24-bit true-color background."""
    return _wrap(f"48;2;{r};{g};{b}", "49", s)
