"""list() / ListState is lazy — render_fn runs only for visible rows."""

from __future__ import annotations

import builtins
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import overload

from conftest import render

import ttyz as t
from ttyz import ListState
from ttyz import list as tlist
from ttyz.components.base import Node


@dataclass
class Item:
    key: str


class LazyItems(Sequence[Item]):
    """Sequence that produces Items on demand and tracks __getitem__ hits."""

    def __init__(self, n: int, counter: builtins.list[int]) -> None:
        self._n = n
        self._counter = counter

    def __len__(self) -> int:
        return self._n

    @overload
    def __getitem__(self, i: int) -> Item: ...
    @overload
    def __getitem__(self, i: slice) -> Sequence[Item]: ...
    def __getitem__(self, i: int | slice) -> Item | Sequence[Item]:
        if isinstance(i, slice):
            raise TypeError
        self._counter[0] += 1
        return Item(key=f"k{i}")


def _counting_render_fn() -> tuple[Callable[[Item, bool], Node], builtins.list[int]]:
    counter = [0]

    def fn(item: Item, selected: bool) -> Node:
        counter[0] += 1
        mark = "*" if selected else " "
        return t.text(f"{mark}{item.key}")

    return fn, counter


def test_construction_does_not_call_render_fn() -> None:
    """Building list() constructs no item nodes up front."""
    items = [Item(f"k{i}") for i in range(1000)]
    fn, counter = _counting_render_fn()
    tlist(ListState(items), fn)
    assert counter[0] == 0


def test_only_visible_items_render_fn_is_called() -> None:
    """Inside a bounded viewport, render_fn runs exactly for the visible rows."""
    items = [Item(f"k{i}") for i in range(1_000_000)]
    fn, counter = _counting_render_fn()
    render(tlist(ListState(items), fn, height="7"), 20, 7)
    assert counter[0] == 7


def test_liststate_accepts_lazy_sequence() -> None:
    """ListState doesn't force-materialize — a lazy Sequence is held by reference."""
    items_hits = [0]
    items = LazyItems(1_000_000, items_hits)
    state = ListState(items)
    # Constructing ListState must not iterate items.
    assert items_hits[0] == 0
    # .total reads len — O(1) for our Sequence.
    assert state.total == 1_000_000
    assert items_hits[0] == 0


def test_liststate_current_only_touches_cursor_item() -> None:
    """state.current indexes once at the cursor, not across the sequence."""
    items_hits = [0]
    items = LazyItems(1_000_000, items_hits)
    state = ListState(items)
    state.move_to(42)
    _ = state.current
    assert items_hits[0] == 1


def test_cursor_highlight_flows_through_lazy_path() -> None:
    """The selected row sees selected=True in render_fn."""
    items = [Item(f"k{i}") for i in range(5)]
    state = ListState(items)
    state.move_to(2)

    def fn(item: Item, selected: bool) -> Node:
        return t.text(f"{'>' if selected else ' '}{item.key}")

    out = render(tlist(state, fn, height="5"), 10, 5)
    assert out == [" k0", " k1", ">k2", " k3", " k4"]


def test_items_list_is_not_copied() -> None:
    """Mutations to the items list show up on the next render (no defensive copy)."""
    items: builtins.list[Item] = [Item("a"), Item("b")]
    state = ListState(items)
    assert state.total == 2
    items.append(Item("c"))
    assert state.total == 3
