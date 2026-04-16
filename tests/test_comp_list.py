"""Tests for List and ListState."""

from dataclasses import dataclass

from conftest import SnapFn

from ttyz import ListState


@dataclass
class Item:
    key: str
    label: str = ""


def _items(*keys: str) -> list[Item]:
    return [Item(k) for k in keys]


def test_total_reflects_items():
    s = ListState(_items("a", "b", "c"))
    assert s.total == 3


def test_total_before_render():
    s = ListState(_items("a", "b", "c"))
    s.move(1)
    assert s.cursor == 1


def test_total_empty():
    s = ListState[Item]()
    assert s.total == 0


def test_move_clamps():
    s = ListState(_items("a", "b", "c"))
    s.move(100)
    assert s.cursor == 2
    s.move(-100)
    assert s.cursor == 0


def test_move_to():
    s = ListState(_items("a", "b", "c"))
    s.move_to(2)
    assert s.cursor == 2
    assert s.current == Item("c")


def test_set_items_preserves_cursor_by_key():
    s = ListState(_items("a", "b", "c"))
    s.move_to(1)  # cursor on "b"
    s.set_items(_items("x", "b", "c"))
    assert s.cursor == 1
    assert s.current == Item("b")


def test_set_items_preserves_when_item_moves():
    s = ListState(_items("a", "b", "c"))
    s.move_to(1)  # cursor on "b"
    s.set_items(_items("c", "a", "b"))
    assert s.cursor == 2
    assert s.current == Item("b")


def test_set_items_clamps_when_item_removed():
    s = ListState(_items("a", "b", "c"))
    s.move_to(2)  # cursor on "c"
    s.set_items(_items("a", "b"))
    assert s.cursor == 1  # clamped to last


def test_set_items_from_empty():
    s = ListState[Item]()
    s.set_items(_items("a", "b"))
    assert s.cursor == 0


def test_set_items_to_empty():
    s = ListState(_items("a", "b"))
    s.move_to(1)
    s.set_items([])
    assert s.cursor == 0
    assert s.current is None


def test_set_items_updates_render(snap: SnapFn):
    from ttyz import list, text
    from ttyz.components.base import Node

    @dataclass
    class LabelItem:
        key: str
        label: str

    state = ListState([LabelItem("a", "original")])

    def render_fn(item: LabelItem, selected: bool) -> Node:
        return text(item.label)

    snap(list(state, render_fn), 80, 5, name="list_original")

    state.set_items([LabelItem("a", "UPDATED")])
    snap(list(state, render_fn), 80, 5, name="list_updated")
