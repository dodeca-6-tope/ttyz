"""Container factories (vstack/hstack/zstack) accept a Sequence positional.

Single non-Node positional → treat as the Sequence backing; varargs of
Nodes behave as before.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import overload

from conftest import render

import ttyz as t
from ttyz.components.base import Node


class LazySeq(Sequence[Node]):
    def __init__(self, n: int, counter: list[int]) -> None:
        self._n = n
        self._counter = counter

    def __len__(self) -> int:
        return self._n

    @overload
    def __getitem__(self, i: int) -> Node: ...
    @overload
    def __getitem__(self, i: slice) -> Sequence[Node]: ...
    def __getitem__(self, i: int | slice) -> Node | Sequence[Node]:
        if isinstance(i, slice):
            raise TypeError
        self._counter[0] += 1
        return t.text(f"r{i}")


# ── vstack ──────────────────────────────────────────────────────────


def test_vstack_varargs_unchanged():
    assert render(t.vstack(t.text("a"), t.text("b")), 10, 2) == ["a", "b"]


def test_vstack_list_as_backing():
    nodes = [t.text("x"), t.text("y"), t.text("z")]
    node = t.vstack(nodes)
    assert node.children is nodes
    assert render(node, 10, 3) == ["x", "y", "z"]


def test_vstack_sequence_is_non_flex_to_enable_short_circuit():
    """Sequence backing forces has_flex=False so the render loop can break."""
    counter = [0]
    # Height constraint forces non-flex vstack to stop after filling h.
    # (non-flex vstack doesn't propagate h to children, so the OUTER h
    # bounds the iteration.)
    t.render_to_buffer(
        t.vstack(LazySeq(1_000_000, counter), height="5"), t.Buffer(10, 5), 5
    )
    assert counter[0] == 5
    # Confirm the stack wasn't accidentally put in flex mode.
    node = t.vstack(LazySeq(1_000_000, [0]))
    assert node.has_flex is False


def test_vstack_tuple_varargs_still_probes_has_flex():
    flex = t.vstack(t.text("a"), t.text("b", grow=1))
    assert flex.has_flex is True
    non_flex = t.vstack(t.text("a"), t.text("b"))
    assert non_flex.has_flex is False


# ── hstack ──────────────────────────────────────────────────────────


def test_hstack_varargs_unchanged():
    assert render(t.hstack(t.text("a"), t.text("b"), spacing=1), 5, 1) == ["a b"]


def test_hstack_list_as_backing():
    assert render(t.hstack([t.text("a"), t.text("b")], spacing=1), 5, 1) == ["a b"]


def test_hstack_sequence_renders():
    counter = [0]
    # HStack measures active children; this forces every item to be
    # measured at least once — laziness is limited for HStack, but the
    # API contract is that it accepts a Sequence without erroring.
    out = render(t.hstack(LazySeq(3, counter), spacing=1), 10, 1)
    assert out == ["r0 r1 r2"]


# ── zstack ──────────────────────────────────────────────────────────


def test_zstack_varargs_unchanged():
    baseline = render(t.zstack(t.text("a"), t.text("b")), 5, 1)
    # Top layer wins at column 0 regardless of exact padding semantics.
    assert baseline[0].startswith("b")


def test_zstack_list_as_backing():
    out = render(t.zstack([t.text("a"), t.text("b")]), 5, 1)
    baseline = render(t.zstack(t.text("a"), t.text("b")), 5, 1)
    assert out == baseline


# ── Single-Node argument is still one child, not a sequence ────────


def test_single_node_positional_is_still_one_child():
    """A lone Node is treated as varargs, not misread as 'sequence of one'."""
    v = t.vstack(t.text("solo"))
    assert isinstance(v.children, tuple)
    assert len(v.children) == 1

    h = t.hstack(t.text("solo"))
    assert isinstance(h.children, tuple)
    assert len(h.children) == 1

    z = t.zstack(t.text("solo"))
    assert isinstance(z.children, tuple)
    assert len(z.children) == 1
