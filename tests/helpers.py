"""Shared test helpers."""

from terminal.measure import strip_ansi


def clean(lines: list[str]) -> list[str]:
    return [strip_ansi(l) for l in lines]


def vis(lines: list[str]) -> list[str]:
    """Replace spaces with dots so layouts are visible in assertions."""
    return [l.replace(" ", "·") for l in clean(lines)]
