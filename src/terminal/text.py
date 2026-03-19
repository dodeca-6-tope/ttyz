"""ANSI-aware text — a string that knows its visible width."""

from terminal.measure import display_width, strip_ansi


class Text:
    """A string that measures and manipulates by visible width, ignoring ANSI escapes."""

    __slots__ = ("_raw", "_visible")

    def __init__(self, value=""):
        self._raw = str(value)
        self._visible = display_width(self._raw)

    def __len__(self):
        return self._visible

    def __str__(self):
        return self._raw

    def __repr__(self):
        return f"Text({self._raw!r})"

    def __add__(self, other):
        if isinstance(other, Text):
            return Text(self._raw + other._raw)
        return Text(self._raw + str(other))

    def __radd__(self, other):
        return Text(str(other) + self._raw)

    def __format__(self, format_spec):
        return self._raw.__format__(format_spec)

    def truncate(self, max_len: int = 30) -> "Text":
        if self._visible <= max_len:
            return self
        raw = strip_ansi(self._raw)
        return Text(raw[:max_len - 1] + "…")

    def pad(self, width: int, align: str = "left") -> "Text":
        gap = width - self._visible
        if gap <= 0:
            return self
        spaces = " " * gap
        if align == "left":
            return Text(self._raw + spaces)
        return Text(spaces + self._raw)
