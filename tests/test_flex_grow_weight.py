"""Tests for weighted flex_grow distribution."""

from conftest import SnapFn

from ttyz import hstack, text, vstack
from ttyz.components.base import Custom, Node
from ttyz.components.table import table, table_row


def weighted(label: str, grow: int = 0) -> Node:
    def render_fn(width: int, height: int | None = None) -> list[str]:
        lines = [label[:width].ljust(width)]
        if height is not None:
            while len(lines) < height:
                lines.append(" " * width)
        return lines

    return Custom(render_fn, grow=grow)


# ── HStack weighted ────────────────────────────────────────────────


def test_hstack_equal_weights(snap: SnapFn):
    snap(hstack(weighted("A", 1), weighted("B", 1)), 20)


def test_hstack_2_to_1_weight(snap: SnapFn):
    snap(hstack(weighted("A", 2), weighted("B", 1)), 30)


def test_hstack_3_to_1_weight(snap: SnapFn):
    snap(hstack(weighted("A", 3), weighted("B", 1)), 40)


def test_hstack_uneven_remainder(snap: SnapFn):
    snap(hstack(weighted("A", 1), weighted("B", 1), weighted("C", 1)), 20)


def test_hstack_mixed_fixed_and_weighted(snap: SnapFn):
    snap(hstack(text("XX"), weighted("A", 1), weighted("B", 2)), 32)


def test_hstack_weight_with_spacing(snap: SnapFn):
    snap(hstack(weighted("A", 1), weighted("B", 1), spacing=2), 22)


# ── VStack weighted ────────────────────────────────────────────────


def test_vstack_equal_height_weights(snap: SnapFn):
    snap(vstack(weighted("A", 1), weighted("B", 1)), 10, 20)


def test_vstack_2_to_1_height(snap: SnapFn):
    snap(vstack(weighted("A", 2), weighted("B", 1)), 10, 30)


def test_vstack_mixed_fixed_and_weighted(snap: SnapFn):
    snap(vstack(text("HEAD"), weighted("A", 1), weighted("B", 2)), 10, 31)


def test_vstack_uneven_height_remainder(snap: SnapFn):
    snap(vstack(weighted("A", 1), weighted("B", 1), weighted("C", 1)), 5, 20)


# ── Table weighted ─────────────────────────────────────────────────


def test_table_weighted_columns(snap: SnapFn):
    snap(table(table_row(weighted("A", 2), weighted("B", 1)), spacing=0), 30)


def test_table_weighted_with_fixed(snap: SnapFn):
    snap(
        table(table_row(text("XX"), weighted("A", 1), weighted("B", 3)), spacing=0),
        30,
    )


# ── Protocol ───────────────────────────────────────────────────────


def test_default_flex_grow_is_zero():
    assert text("").grow == 0


def test_weighted_component_returns_weight():
    assert weighted("x", grow=3).grow == 3
