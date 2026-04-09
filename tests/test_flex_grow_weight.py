"""Tests for weighted flex_grow distribution."""

from helpers import vis

from terminal import hstack, text, vstack
from terminal.components.base import Renderable
from terminal.components.table import table, table_row


def weighted(label: str, grow: int = 0) -> Renderable:
    def render(width: int, height: int | None = None) -> list[str]:
        lines = [label[:width].ljust(width)]
        if height is not None:
            while len(lines) < height:
                lines.append(" " * width)
        return lines

    return Renderable(render, grow=grow)


# ── HStack weighted ────────────────────────────────────────────────


def test_hstack_equal_weights():
    assert vis(hstack(weighted("A", 1), weighted("B", 1)).render(20)) == [
        "A·········B·········",
    ]


def test_hstack_2_to_1_weight():
    assert vis(hstack(weighted("A", 2), weighted("B", 1)).render(30)) == [
        "A···················B·········",
    ]


def test_hstack_3_to_1_weight():
    assert vis(hstack(weighted("A", 3), weighted("B", 1)).render(40)) == [
        "A·····························B·········",
    ]


def test_hstack_uneven_remainder():
    #          A=6         B=7          C=7
    assert vis(hstack(weighted("A", 1), weighted("B", 1), weighted("C", 1)).render(20)) == [
        "A·····B······C······",
    ]


def test_hstack_mixed_fixed_and_weighted():
    #          XX  A=10             B=20
    assert vis(hstack(text("XX"), weighted("A", 1), weighted("B", 2)).render(32)) == [
        "XXA·········B···················",
    ]


def test_hstack_weight_with_spacing():
    assert vis(hstack(weighted("A", 1), weighted("B", 1), spacing=2).render(22)) == [
        "A···········B·········",
    ]


# ── VStack weighted ────────────────────────────────────────────────


def test_vstack_equal_height_weights():
    lines = vis(vstack(weighted("A", 1), weighted("B", 1)).render(10, 20))
    assert len(lines) == 20
    assert lines[0].startswith("A")
    assert lines[10].startswith("B")


def test_vstack_2_to_1_height():
    lines = vis(vstack(weighted("A", 2), weighted("B", 1)).render(10, 30))
    assert len(lines) == 30
    assert lines[0].startswith("A")
    assert lines[20].startswith("B")


def test_vstack_mixed_fixed_and_weighted():
    lines = vis(vstack(text("HEAD"), weighted("A", 1), weighted("B", 2)).render(10, 31))
    assert len(lines) == 31
    assert lines[0] == "HEAD"
    assert lines[1].startswith("A")
    assert lines[11].startswith("B")


def test_vstack_uneven_height_remainder():
    lines = vis(vstack(weighted("A", 1), weighted("B", 1), weighted("C", 1)).render(5, 20))
    assert len(lines) == 20
    assert lines[0].startswith("A")
    assert lines[6].startswith("B")
    assert lines[13].startswith("C")


# ── Table weighted ─────────────────────────────────────────────────


def test_table_weighted_columns():
    assert vis(table(table_row(weighted("A", 2), weighted("B", 1)), spacing=0).render(30)) == [
        "A···················B·········",
    ]


def test_table_weighted_with_fixed():
    assert vis(table(table_row(text("XX"), weighted("A", 1), weighted("B", 3)), spacing=0).render(30)) == [
        "XXA······B····················",
    ]


# ── Protocol ───────────────────────────────────────────────────────


def test_default_flex_grow_is_zero():
    assert text("").grow == 0


def test_weighted_component_returns_weight():
    assert weighted("x", grow=3).grow == 3
