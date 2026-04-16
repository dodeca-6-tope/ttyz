"""Edge case tests for render_to_buffer."""

from conftest import SnapFn

import ttyz as t

# ── Flex distribute edge cases ─────────────────────────────────────


def test_flex_distribute_all_zero_grows(snap: SnapFn):
    """Children with grow=0 should only take their natural height."""
    snap(t.vstack(t.text("A"), t.text("B")), 60, 10)


def test_flex_distribute_zero_remaining(snap: SnapFn):
    """When children exactly fill available space, grow gets nothing extra."""
    snap(t.vstack(t.text("A"), t.text("B"), t.text("C", grow=1)), 60, 3)


def test_flex_distribute_empty_vstack(snap: SnapFn):
    """A vstack with no children should render as blank."""
    snap(t.vstack(), 60, 5)


# ── Edge cases: zero/tiny width ─────────────────────────────────────


def test_hstack_at_minimal_width(snap: SnapFn):
    """Rendering an hstack into a 1-col buffer must not crash."""
    snap(t.hstack(t.text("a"), t.text("b"), t.text("c")), 1, 1)


def test_hstack_at_width_one(snap: SnapFn):
    """An hstack squeezed to 1 col should not crash or corrupt memory."""
    snap(t.hstack(t.text("hello"), t.text("world"), spacing=1), 1, 1)


def test_hstack_children_exceed_width(snap: SnapFn):
    """Children wider than the buffer should clip, not overflow."""
    snap(t.hstack(t.text("aaaa"), t.text("bbbb"), t.text("cccc"), spacing=1), 5, 1)


# ── Clipping and padding (buffer-level) ──────────────────────────────


def test_text_clips_at_buffer_width(snap: SnapFn):
    """Text wider than buffer is clipped at the column boundary."""
    snap(t.text("hello world"), 5)


def test_wide_chars_clip_at_boundary(snap: SnapFn):
    """Wide CJK characters don't split across the buffer edge."""
    snap(t.text("你好世界"), 5)


def test_ansi_preserved_after_clip(snap: SnapFn):
    """Styling is preserved when content is clipped to buffer width."""
    snap(t.text(t.bold("hello world")), 5)


def test_short_text_padded_in_hstack(snap: SnapFn):
    """Short text in an hstack column is padded with spaces."""
    snap(t.hstack(t.text("hi"), t.text("|")), 10)


def test_pad_with_wide_chars(snap: SnapFn):
    """Wide chars are accounted for when padding in hstack layout."""
    snap(t.hstack(t.text("你好"), t.text("|")), 10)
