"""ANSI styling helpers — thin wrappers that produce escape codes."""


def bold(s: str) -> str:
    return f"\033[1m{s}\033[0m"


def dim(s: str) -> str:
    return f"\033[2m{s}\033[0m"


def italic(s: str) -> str:
    return f"\033[3m{s}\033[0m"


def underline(s: str) -> str:
    return f"\033[4m{s}\033[0m"


def blink(s: str) -> str:
    return f"\033[5m{s}\033[0m"


def reverse(s: str) -> str:
    return f"\033[7m{s}\033[0m"


def invisible(s: str) -> str:
    return f"\033[8m{s}\033[0m"


def strikethrough(s: str) -> str:
    return f"\033[9m{s}\033[0m"


def overline(s: str) -> str:
    return f"\033[53m{s}\033[0m"


def color(c: int, s: str) -> str:
    """Apply 256-color foreground."""
    return f"\033[38;5;{c}m{s}\033[0m"


def bg(c: int, s: str) -> str:
    """Apply 256-color background."""
    return f"\033[48;5;{c}m{s}\033[0m"


def rgb(r: int, g: int, b: int, s: str) -> str:
    """Apply 24-bit true-color foreground."""
    return f"\033[38;2;{r};{g};{b}m{s}\033[0m"


def bg_rgb(r: int, g: int, b: int, s: str) -> str:
    """Apply 24-bit true-color background."""
    return f"\033[48;2;{r};{g};{b}m{s}\033[0m"
