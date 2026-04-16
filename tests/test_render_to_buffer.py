"""Edge case tests for render_to_buffer."""

import ttyz as t
from ttyz import Buffer, render_to_buffer

W, H = 60, 12


# ── Flex distribute edge cases ─────────────────────────────────────


def test_flex_distribute_all_zero_grows():
    """Children with grow=0 should only take their natural height."""
    buf = Buffer(W, 10)
    render_to_buffer(t.vstack(t.text("A"), t.text("B")), buf)
    assert buf.row_text(0).strip() == "A"
    assert buf.row_text(1).strip() == "B"
    assert buf.row_text(2).strip() == ""


def test_flex_distribute_zero_remaining():
    """When children exactly fill available space, grow gets nothing extra."""
    buf = Buffer(W, 3)
    render_to_buffer(
        t.vstack(t.text("A"), t.text("B"), t.text("C", grow=1)),
        buf,
    )
    assert buf.row_text(0).strip() == "A"
    assert buf.row_text(1).strip() == "B"
    assert buf.row_text(2).strip() == "C"


def test_flex_distribute_empty_vstack():
    """A vstack with no children should render as blank."""
    buf = Buffer(W, 5)
    render_to_buffer(t.vstack(), buf)
    for row in range(5):
        assert buf.row_text(row).strip() == ""


# ── Edge cases: zero/tiny width ─────────────────────────────────────


def test_hstack_at_minimal_width():
    """Rendering an hstack into a 1-col buffer must not crash."""
    buf = Buffer(1, 1)
    render_to_buffer(t.hstack(t.text("a"), t.text("b"), t.text("c")), buf)


def test_hstack_at_width_one():
    """An hstack squeezed to 1 col should not crash or corrupt memory."""
    buf = Buffer(1, 1)
    render_to_buffer(t.hstack(t.text("hello"), t.text("world"), spacing=1), buf)
    assert len(buf.row_text(0)) <= 1


def test_hstack_children_exceed_width():
    """Children wider than the buffer should clip, not overflow."""
    buf = Buffer(5, 1)
    render_to_buffer(
        t.hstack(t.text("aaaa"), t.text("bbbb"), t.text("cccc"), spacing=1),
        buf,
    )
    row = buf.row_text(0)
    assert len(row) == 5


# ── Clipping and padding (buffer-level) ──────────────────────────────


def test_text_clips_at_buffer_width():
    """Text wider than buffer is clipped at the column boundary."""
    buf = Buffer(5, 1)
    render_to_buffer(t.text("hello world"), buf)
    assert buf.row_text(0)[:5] == "hello"


def test_wide_chars_clip_at_boundary():
    """Wide CJK characters don't split across the buffer edge."""
    buf = Buffer(5, 1)
    render_to_buffer(t.text("你好世界"), buf)
    row = buf.row_text(0)
    assert "你好" in row
    assert "世" not in row


def test_ansi_preserved_after_clip():
    """Styling is preserved when content is clipped to buffer width."""
    buf = Buffer(5, 1)
    render_to_buffer(t.text(t.bold("hello world")), buf)
    styled = buf.row_styled(0)
    assert "\033[" in styled
    assert "hello" in styled


def test_short_text_padded_in_hstack():
    """Short text in an hstack column is padded with spaces."""
    buf = Buffer(10, 1)
    render_to_buffer(t.hstack(t.text("hi"), t.text("|")), buf)
    assert buf.row_text(0).startswith("hi|")


def test_pad_with_wide_chars():
    """Wide chars are accounted for when padding in hstack layout."""
    buf = Buffer(10, 1)
    render_to_buffer(t.hstack(t.text("你好"), t.text("|")), buf)
    # "你好" is 4 columns wide
    assert buf.row_text(0).startswith("你好|")
