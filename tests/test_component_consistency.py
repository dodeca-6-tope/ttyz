"""Cross-component consistency tests.

Verifies that components sharing the same concept (flex delegation, height
pass-through, private children, empty render) follow identical rules.
"""

from conftest import SnapFn

from ttyz import Node, cond, foreach, hstack, scroll, text, vstack, zstack
from ttyz.components.scroll import ScrollState

# ── grow delegation ───────────────────────────────────────────────────


def test_cond_delegates_grow_true():
    assert cond(True, text("x", grow=1)).grow


def test_cond_delegates_grow_false():
    assert cond(False, text("x", grow=1)).grow == 0


def test_foreach_grow_not_propagated():
    fe = foreach(["a"], lambda item, i: text(str(item), grow=1))
    assert not fe.grow

    fe = foreach(["a"], lambda item, i: text(str(item)))
    assert fe.grow == 0

    fe = foreach([], lambda item, i: text(str(item)))
    assert fe.grow == 0

    s = ScrollState()
    fe = foreach(["a"], lambda item, i: scroll(text(item), state=s))
    assert not fe.grow


# ── Height pass-through: only growers receive height ──────────────────


def _make_scroll(n: int = 20) -> tuple[ScrollState, list[Node]]:
    s = ScrollState()
    items: list[Node] = [text(str(i)) for i in range(n)]
    return s, items


def test_hstack_passes_height_only_to_growers(snap: SnapFn):
    s, items = _make_scroll()
    snap(hstack(scroll(*items, state=s), text("fixed")), 40, 5)
    assert s.height == 5


def test_zstack_passes_height_only_to_growers(snap: SnapFn):
    s, items = _make_scroll()
    snap(zstack(scroll(*items, state=s), text("overlay")), 40, 5)
    assert s.height == 5


def test_zstack_passes_height_to_children(snap: SnapFn):
    s = ScrollState()
    snap(zstack(text("base"), scroll(text("a"), state=s)), 40, 5)
    assert s.height == 5


def test_foreach_passes_height_to_children(snap: SnapFn):
    s = ScrollState()
    snap(foreach(["a"], lambda item, i: scroll(text(item), state=s)), 40, 5)
    assert s.height == 5


# ── Weighted flex grow consistency ────────────────────────────────────


def test_cond_propagates_flex_grow_weight():
    s1 = ScrollState()
    inner = scroll(text("a"), state=s1)
    assert cond(True, inner).grow == inner.grow


def test_foreach_no_propagation():
    s = ScrollState()
    fe = foreach(
        ["a", "b"],
        lambda item, i: scroll(text(item), state=s) if i == 0 else text(item),
    )
    assert not fe.grow


# ── All containers: flex methods match on empty ───────────────────────


def test_empty_intrinsic_width(snap: SnapFn):
    """Empty containers have zero intrinsic width."""
    for name, container in [
        ("hstack", hstack()),
        ("vstack", vstack()),
        ("zstack", zstack()),
        ("foreach", foreach([], lambda item, i: text(str(item)))),
    ]:
        snap(hstack(container, text("|")), 20, name=f"empty_{name}")


def test_empty_grow():
    assert hstack().grow == 0
    assert vstack().grow == 0
    assert zstack().grow == 0
    assert foreach([], lambda item, i: text(str(item))).grow == 0


# ── Cond in HStack flex grow ──────────────────────────────────────────


def test_cond_fill_text_grows_in_hstack(snap: SnapFn):
    snap(hstack(text("L"), cond(True, text("R", grow=1))), 20)


def test_cond_false_fill_text_no_grow_in_hstack(snap: SnapFn):
    snap(hstack(text("L"), cond(False, text("R", grow=1))), 20)


# ── Frame bg respects width constraint ───────────────────────────────


def test_bg_respects_fixed_width(snap: SnapFn):
    snap(text("hi", width="10", bg=1), 40)


def test_bg_respects_percentage_width(snap: SnapFn):
    snap(vstack(text("hi"), width="50%", bg=1), 40)


def test_bg_without_width_uses_full_parent(snap: SnapFn):
    snap(vstack(text("hi"), bg=1), 40)
