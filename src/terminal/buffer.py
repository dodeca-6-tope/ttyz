"""Sole Python gateway to the C extension (terminal.cbuf).

All other modules import C functions through here, keeping a single
point of coupling to the native layer.
"""

from terminal.cbuf import (
    Buffer,
    Renderable,
    c_make_text,
    char_width,
    hstack_join_row,
    parse_line,
    render_diff,
    render_flat_line,
    render_full,
    resolve_col_widths,
    set_text_render_fallback,
)
from terminal.cbuf import (
    display_width as c_display_width,
)

__all__ = [
    "Buffer",
    "Renderable",
    "c_display_width",
    "c_make_text",
    "char_width",
    "hstack_join_row",
    "parse_line",
    "render_diff",
    "render_flat_line",
    "render_full",
    "resolve_col_widths",
    "set_text_render_fallback",
]
