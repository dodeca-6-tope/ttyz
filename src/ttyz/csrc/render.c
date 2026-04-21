/*
 * render.c — Direct node-to-cell tree renderer.
 *
 * Walks Python Node objects and writes directly into BufferObject cells,
 * bypassing intermediate list[str] and ANSI re-parsing.
 *
 * All node types are handled in C: Text, HStack, VStack, ZStack, Box,
 * Scroll, Table, Foreach, Cond, Spacer, Input, Scrollbar, Custom.
 */

/* ── Forward declarations ─────────────────────────────────────────── */

typedef struct RenderCtx RenderCtx;

static int c_render_node(RenderCtx *ctx, PyObject *node,
                         int x, int y, int w, int h, Style bg);
static int c_measure_node(RenderCtx *ctx, PyObject *node);

/* ── Type and attribute caches (lazy-initialized) ─────────────────── */

static int render_types_ready = 0;  /* safe: only mutated under the GIL */

/* Node type pointers — resolved once from Python classes. */
static PyTypeObject *NodeType_;
static PyTypeObject *TextType_;
static PyTypeObject *HStackType_;
static PyTypeObject *VStackType_;
static PyTypeObject *ZStackType_;
static PyTypeObject *BoxType_;
static PyTypeObject *SpacerType_;
static PyTypeObject *CondType_;
static PyTypeObject *ForeachType_;
static PyTypeObject *ScrollType_;
static PyTypeObject *ScrollbarType_;
static PyTypeObject *TableType_;
static PyTypeObject *TableRowType_;
static PyTypeObject *ScrollStateType_;
static PyTypeObject *InputType_;

/* Interned attribute name strings — only those still read via
 * PyObject_GetAttr remain. Slot-backed fields are accessed by offset. */
static PyObject *a_value;
static PyObject *a_render_fn;

/* Interned constant strings. */
static PyObject *s_visible;
static PyObject *s_start;
static PyObject *s_end;
static PyObject *s_center;
static PyObject *s_between;
static PyObject *s_rounded;
static PyObject *s_normal;
static PyObject *s_double;
static PyObject *s_heavy;

/* ── Slot offsets (discovered at init time) ────────────────────────── */
/*
 * CPython stores __slots__ values at fixed offsets inside instances.
 * We discover the offsets once from the member descriptors, then read
 * slot values directly, bypassing the descriptor protocol entirely.
 * This eliminates the dominant per-node cost: PyObject_GetAttr calls
 * that perform MRO lookup + descriptor __get__ on every access.
 */

/* Node base (same offset for every subclass). */
static Py_ssize_t off_children, off_grow, off_width, off_height,
                   off_bg, off_overflow;
/* Text */
static Py_ssize_t off_text_value, off_text_lines, off_text_visible_w,
                   off_text_pl, off_text_pr, off_text_truncation,
                   off_text_wrap;
/* HStack */
static Py_ssize_t off_hstack_spacing, off_hstack_jc, off_hstack_ai,
                   off_hstack_wrap;
/* VStack */
static Py_ssize_t off_vstack_spacing, off_vstack_needs_measure_pass;
/* ZStack */
static Py_ssize_t off_zstack_jc, off_zstack_ai;
/* Box */
static Py_ssize_t off_box_style, off_box_title, off_box_padding;
/* Scroll */
static Py_ssize_t off_scroll_state;
/* Table */
static Py_ssize_t off_table_rows, off_table_spacing;
/* TableRow */
static Py_ssize_t off_trow_cells;
/* ScrollState */
static Py_ssize_t off_ss_offset, off_ss_height, off_ss_total, off_ss_follow;
/* Spacer */
static Py_ssize_t off_spacer_min_length;
/* Input */
static Py_ssize_t off_input_buffer, off_input_active, off_input_placeholder;
/* Scrollbar */
static Py_ssize_t off_scrollbar_state, off_scrollbar_render_fn;

/* Read a slot as a borrowed PyObject* (no DECREF needed). */
#define SLOT(obj, offset)  (*(PyObject **)((char *)(obj) + (offset)))

/* Read a slot that holds a Python int, returning a C int. */
static inline int slot_int(PyObject *obj, Py_ssize_t offset) {
    return (int)PyLong_AsLong(SLOT(obj, offset));
}

/* Read a slot that holds a Python bool, returning a C int. */
static inline int slot_bool(PyObject *obj, Py_ssize_t offset) {
    return SLOT(obj, offset) == Py_True;
}

/* Forward declarations. */
static PyObject *text_get_lines(PyObject *node);
static int text_visible_w(PyObject *node);

/* Python helpers for Input rendering. */
static PyObject *py_display_text;
static PyObject *py_display_cursor;

/* ── init_render_types — lazy one-time setup ──────────────────────── */

/*
 * Discover the memory offset of a __slots__ attribute on a type.
 * Walks the MRO to find the member_descriptor, then reads its offset.
 * Returns -1 on failure (sets a Python exception).
 */
static Py_ssize_t discover_slot_offset(PyTypeObject *tp, const char *name) {
    PyObject *key = PyUnicode_InternFromString(name);
    if (!key) return -1;
    PyObject *mro = tp->tp_mro;
    Py_ssize_t n = PyTuple_GET_SIZE(mro);
    for (Py_ssize_t i = 0; i < n; i++) {
        PyTypeObject *base = (PyTypeObject *)PyTuple_GET_ITEM(mro, i);
        if (!base->tp_dict) continue;
        PyObject *descr = PyDict_GetItem(base->tp_dict, key); /* borrowed */
        if (descr && Py_TYPE(descr) == &PyMemberDescr_Type) {
            Py_DECREF(key);
            return ((PyMemberDescrObject *)descr)->d_member->offset;
        }
    }
    PyErr_Format(PyExc_RuntimeError,
                 "ttyz: slot '%s' not found on type '%s'",
                 name, tp->tp_name);
    Py_DECREF(key);
    return -1;
}

static PyTypeObject *load_type(const char *module, const char *name) {
    PyObject *mod = PyImport_ImportModule(module);
    if (!mod) return NULL;
    PyObject *cls = PyObject_GetAttrString(mod, name);
    Py_DECREF(mod);
    if (!cls) return NULL;
    return (PyTypeObject *)cls;  /* owns ref */
}

static int init_render_types(void) {
    if (render_types_ready) return 0;

#define LOAD(var, mod, name) do {            \
    var = load_type(mod, name);              \
    if (!var) return -1;                     \
} while (0)

    LOAD(NodeType_,        "ttyz.components.base",      "Node");
    LOAD(TextType_,        "ttyz.components.text",      "Text");
    LOAD(HStackType_,      "ttyz.components.hstack",    "HStack");
    LOAD(VStackType_,      "ttyz.components.vstack",    "VStack");
    LOAD(ZStackType_,      "ttyz.components.zstack",    "ZStack");
    LOAD(BoxType_,         "ttyz.components.box",        "Box");
    LOAD(SpacerType_,      "ttyz.components.spacer",    "Spacer");
    LOAD(CondType_,        "ttyz.components.cond",      "Cond");
    LOAD(ForeachType_,     "ttyz.components.foreach",   "Foreach");
    LOAD(ScrollType_,      "ttyz.components.scroll",    "Scroll");
    LOAD(ScrollbarType_,   "ttyz.components.scrollbar",  "Scrollbar");
    LOAD(TableType_,       "ttyz.components.table",     "Table");
    LOAD(TableRowType_,    "ttyz.components.table",     "TableRow");
    LOAD(ScrollStateType_, "ttyz.components.scroll",    "ScrollState");
    LOAD(InputType_,       "ttyz.components.input",     "Input");
#undef LOAD

#define INTERN(var, name) do {                        \
    var = PyUnicode_InternFromString(name);            \
    if (!var) return -1;                               \
} while (0)

    INTERN(a_value,           "value");
    INTERN(a_render_fn,       "render_fn");
    INTERN(s_visible,         "visible");
    INTERN(s_start,           "start");
    INTERN(s_end,             "end");
    INTERN(s_center,          "center");
    INTERN(s_between,         "between");
    INTERN(s_rounded,         "rounded");
    INTERN(s_normal,          "normal");
    INTERN(s_double,          "double");
    INTERN(s_heavy,           "heavy");
#undef INTERN

    PyObject *imod = PyImport_ImportModule("ttyz.components.input");
    if (!imod) return -1;
    py_display_text = PyObject_GetAttrString(imod, "display_text");
    py_display_cursor = PyObject_GetAttrString(imod, "display_cursor");
    Py_DECREF(imod);
    if (!py_display_text || !py_display_cursor) return -1;

    /* ── Discover slot offsets ───────────────────────────────────── */
#define OFF(var, tp, name) do {                   \
    var = discover_slot_offset(tp, name);         \
    if (var < 0) return -1;                       \
} while (0)

    /* Node base — shared by all subclasses. */
    OFF(off_children,   NodeType_,     "children");
    OFF(off_grow,       NodeType_,     "grow");
    OFF(off_width,      NodeType_,     "width");
    OFF(off_height,     NodeType_,     "height");
    OFF(off_bg,         NodeType_,     "bg");
    OFF(off_overflow,   NodeType_,     "overflow");
    /* Text */
    OFF(off_text_value,     TextType_,    "value");
    OFF(off_text_lines,     TextType_,    "_lines");
    OFF(off_text_visible_w, TextType_,    "_visible_w");
    OFF(off_text_pl,        TextType_,    "pl");
    OFF(off_text_pr,        TextType_,    "pr");
    OFF(off_text_truncation,TextType_,    "truncation");
    OFF(off_text_wrap,      TextType_,    "wrap");
    /* HStack */
    OFF(off_hstack_spacing, HStackType_,  "spacing");
    OFF(off_hstack_jc,      HStackType_,  "justify_content");
    OFF(off_hstack_ai,      HStackType_,  "align_items");
    OFF(off_hstack_wrap,    HStackType_,  "wrap");
    /* VStack */
    OFF(off_vstack_spacing,  VStackType_,  "spacing");
    OFF(off_vstack_needs_measure_pass, VStackType_, "needs_measure_pass");
    /* ZStack */
    OFF(off_zstack_jc,      ZStackType_,  "justify_content");
    OFF(off_zstack_ai,      ZStackType_,  "align_items");
    /* Box */
    OFF(off_box_style,      BoxType_,     "style");
    OFF(off_box_title,      BoxType_,     "title");
    OFF(off_box_padding,    BoxType_,     "padding");
    /* Scroll */
    OFF(off_scroll_state,     ScrollType_,  "state");
    /* Table */
    OFF(off_table_rows,       TableType_,   "rows");
    OFF(off_table_spacing,    TableType_,   "spacing");
    /* TableRow */
    OFF(off_trow_cells,       TableRowType_, "cells");
    /* ScrollState */
    OFF(off_ss_offset,        ScrollStateType_, "offset");
    OFF(off_ss_height,        ScrollStateType_, "height");
    OFF(off_ss_total,         ScrollStateType_, "total");
    OFF(off_ss_follow,        ScrollStateType_, "follow");
    /* Spacer */
    OFF(off_spacer_min_length, SpacerType_, "min_length");
    /* Input */
    OFF(off_input_buffer,      InputType_,     "buffer");
    OFF(off_input_active,      InputType_,     "active");
    OFF(off_input_placeholder, InputType_,     "placeholder");
    /* Scrollbar */
    OFF(off_scrollbar_state,     ScrollbarType_, "state");
    OFF(off_scrollbar_render_fn, ScrollbarType_, "render_fn");
#undef OFF

    render_types_ready = 1;
    return 0;
}

/* ── RenderCtx ────────────────────────────────────────────────────── */

#define MAX_RENDER_DEPTH 200

struct RenderCtx {
    BufferObject *buf;
    PyObject     *mcache;   /* dict[node, int] for measure */
    PyObject     *ccache;   /* dict[(children, index)] -> Node for lazy child cache */
    int           depth;
};

/* ── Helpers ──────────────────────────────────────────────────────── */

/* Children accessors.
 *
 * `children` is the object held in a node's `children` slot — a tuple for
 * static nodes, or any Sequence-shaped object for lazy backings.
 *
 * children_item always returns a NEW reference.  Callers must Py_DECREF
 * when done — this unifies ownership across the tuple and Sequence paths.
 *
 * For non-tuple (Sequence) backings the result is cached in ctx->ccache
 * for the duration of the render so a node is produced at most once per
 * index per render pass — keeps measure/render two-pass layouts and the
 * node-identity measure cache consistent when render_fn is lazy.
 *
 * children_len returns -1 with a Python exception set on error. */
static inline Py_ssize_t children_len(PyObject *children) {
    if (PyTuple_CheckExact(children))
        return PyTuple_GET_SIZE(children);
    return PySequence_Size(children);
}

static PyObject *children_item(RenderCtx *ctx, PyObject *children,
                               Py_ssize_t i) {
    if (PyTuple_CheckExact(children)) {
        PyObject *item = PyTuple_GET_ITEM(children, i);
        Py_INCREF(item);
        return item;
    }
    /* Key by (id(children), i) — the children object is alive for the
     * whole render so the pointer is stable, and this lets unhashable
     * sequence types (lists, user-defined) work. */
    PyObject *key = Py_BuildValue("(Nn)", PyLong_FromVoidPtr(children), i);
    if (!key) return NULL;
    PyObject *cached = PyDict_GetItem(ctx->ccache, key);  /* borrowed */
    if (cached) {
        Py_INCREF(cached);
        Py_DECREF(key);
        return cached;
    }
    PyObject *fresh = PySequence_GetItem(children, i);
    if (!fresh) { Py_DECREF(key); return NULL; }
    if (PyDict_SetItem(ctx->ccache, key, fresh) < 0) {
        Py_DECREF(key); Py_DECREF(fresh); return NULL;
    }
    Py_DECREF(key);
    return fresh;
}

static inline void rc_set_cell(BufferObject *buf, int col, int row,
                               Py_UCS4 ch, Style style) {
    if (col >= 0 && col < buf->width && row >= 0 && row < buf->height)
        buf->cells[row * buf->width + col] = (Cell){ch, style};
}

static void rc_fill_region(BufferObject *buf, int x, int y, int w, int h,
                           Style style) {
    int x1 = x + w, y1 = y + h;
    if (x < 0) x = 0;
    if (y < 0) y = 0;
    if (x1 > buf->width)  x1 = buf->width;
    if (y1 > buf->height) y1 = buf->height;
    int rw = x1 - x;
    if (rw <= 0 || y >= y1) return;
    Cell cell = {' ', style};
    /* Fill first row, memcpy to rest. */
    Cell *first = buf->cells + y * buf->width + x;
    for (int c = 0; c < rw; c++) first[c] = cell;
    size_t row_bytes = (size_t)rw * sizeof(Cell);
    for (int r = y + 1; r < y1; r++)
        memcpy(buf->cells + r * buf->width + x, first, row_bytes);
}

/* Fill only UNWRITTEN cells in a region — used after rendering content
   so that gaps get the background without overwriting content. */
static void rc_fill_unwritten(BufferObject *buf, int x, int y, int w, int h,
                               Style style) {
    int x1 = x + w, y1 = y + h;
    if (x < 0) x = 0;
    if (y < 0) y = 0;
    if (x1 > buf->width)  x1 = buf->width;
    if (y1 > buf->height) y1 = buf->height;
    Cell cell = {' ', style};
    for (int r = y; r < y1; r++) {
        Cell *row = buf->cells + r * buf->width;
        for (int c = x; c < x1; c++)
            if (row[c].ch == UNWRITTEN)
                row[c] = cell;
    }
}

/* Resolve a size string ("50%", "28") against parent dimension.
 * Returns resolved size, or -1 if value is None. */
static int rc_resolve_size(PyObject *value, int parent) {
    if (value == Py_None) return -1;
    Py_ssize_t len = PyUnicode_GET_LENGTH(value);
    if (len == 0) return -1;
    int kind = PyUnicode_KIND(value);
    const void *data = PyUnicode_DATA(value);
    if (PyUnicode_READ(kind, data, len - 1) == '%') {
        int pct = 0;
        for (Py_ssize_t i = 0; i < len - 1; i++)
            pct = pct * 10 + (int)(PyUnicode_READ(kind, data, i) - '0');
        return parent > 0 ? parent * pct / 100 : 0;
    }
    int val = 0;
    for (Py_ssize_t i = 0; i < len; i++)
        val = val * 10 + (int)(PyUnicode_READ(kind, data, i) - '0');
    return val;
}

/* Write an int into a slot (replacing the previous PyObject). */
static void ss_set_int(PyObject *obj, Py_ssize_t offset, int val) {
    PyObject *v = PyLong_FromLong(val);
    if (!v) { PyErr_Clear(); return; }
    PyObject **slot = (PyObject **)((char *)obj + offset);
    Py_XDECREF(*slot);
    *slot = v;
}

/* Write a bool into a slot. */
static void ss_set_bool(PyObject *obj, Py_ssize_t offset, int val) {
    PyObject *v = val ? Py_True : Py_False;
    Py_INCREF(v);
    PyObject **slot = (PyObject **)((char *)obj + offset);
    Py_XDECREF(*slot);
    *slot = v;
}

/* Distribute remaining space among flex items proportionally. */
static void distribute_flex(int remaining, int *indices, int *weights,
                            int count, int *out) {
    long tw = 0;
    for (int j = 0; j < count; j++) tw += weights[j];
    if (tw <= 0) return;
    long cum = 0, cs = 0;
    for (int j = 0; j < count; j++) {
        cum += weights[j];
        long tgt = (long)remaining * cum / tw;
        out[indices[j]] = (int)(tgt - cs);
        cs = tgt;
    }
}

/* ── parse_line_into — write an ANSI string into cells ───────────── */
/*
 * Parses a Python string (which may contain ANSI escapes) and writes
 * cells at (x, y) up to max_w columns.  bg_style provides the
 * inherited background — unstyled content and SGR resets inherit it.
 */
static void parse_line_into(BufferObject *buf, int x, int y, int max_w,
                            PyObject *line, Style bg_style) {
    if (y < 0 || y >= buf->height || max_w <= 0) return;
    Py_ssize_t len = PyUnicode_GET_LENGTH(line);
    if (len == 0) return;

    int bw = buf->width;
    Cell *cells = buf->cells + y * bw;
    int col_end = x + max_w;
    if (col_end > bw) col_end = bw;
    if (x >= col_end) return;

    /* ASCII fast path: no escapes, no wide chars. */
    if (is_plain_ascii(line)) {
        const char *src = PyUnicode_AsUTF8(line);
        Py_ssize_t n = len;
        if (x + n > col_end) n = col_end - x;
        for (Py_ssize_t i = 0; i < n; i++)
            cells[x + (int)i] = (Cell){
                (Py_UCS4)(unsigned char)src[i], bg_style};
        return;
    }

    /* ANSI + wide-char path. */
    int kind = PyUnicode_KIND(line);
    const void *data = PyUnicode_DATA(line);
    int col = x;
    Py_ssize_t pos = 0;
    Color fg = COLOR_EMPTY, bg_c = bg_style.bg;
    uint16_t flags = 0;
    Style style = bg_style;

    while (pos < len && col < col_end) {
        Py_UCS4 ch = PyUnicode_READ(kind, data, pos);

        if (ch == 0x1B) {
            if (pos + 1 < len &&
                PyUnicode_READ(kind, data, pos + 1) == '[') {
                /* CSI sequence — find final byte, parse SGR. */
                Py_ssize_t end = pos + 2;
                while (end < len) {
                    Py_UCS4 fb = PyUnicode_READ(kind, data, end);
                    end++;
                    if (fb >= 0x40 && fb <= 0x7E) break;
                }
                /* Only parse SGR (final byte 'm'); skip other CSI. */
                if (PyUnicode_READ(kind, data, end - 1) == 'm') {
                    parse_sgr(data, kind, pos + 2, end - 1,
                              &fg, &bg_c, &flags);
                    /* Inherit parent bg when text has no explicit bg. */
                    if (bg_c.kind == COLOR_NONE &&
                        bg_style.bg.kind != COLOR_NONE)
                        bg_c = bg_style.bg;
                    style = (Style){fg, bg_c, flags, {0, 0}};
                }
                pos = end;
            } else {
                pos = skip_escape(data, kind, pos, len);
            }
            continue;
        }

        int cw = cwidth(ch);
        if (cw <= 0) { pos++; continue; }
        if (cw == 2 && col + 1 >= col_end) { pos++; continue; }

        cells[col] = (Cell){ch, style};
        if (cw == 2) {
            cells[col + 1] = (Cell){WIDE_CHAR, style};
            /* Absorb ZWJ continuation into side table extras. */
            int cell_pos = y * bw + col;
            Py_ssize_t tail_start = pos + 1;
            while (tail_start < len) {
                Py_UCS4 nc = PyUnicode_READ(kind, data, tail_start);
                if (nc == 0xFE0F) {                          /* VS16 */
                    buf_add_extra(buf, cell_pos, nc);
                    tail_start++;
                    continue;
                }
                if (nc == 0x200D && tail_start + 1 < len) {  /* ZWJ + next */
                    Py_UCS4 after = PyUnicode_READ(kind, data, tail_start + 1);
                    if (cwidth(after) >= 1) {
                        buf_add_extra(buf, cell_pos, nc);
                        buf_add_extra(buf, cell_pos, after);
                        tail_start += 2;
                        continue;
                    }
                }
                break;
            }
            pos = tail_start;
            col += 2;
        } else {
            col++;
            pos++;
        }
    }
}

/* Write a padded line: left-pad, content, right-pad. */
static void render_padded_line(BufferObject *buf, int x, int y, int w,
                               int pl, int pr, int max_w,
                               PyObject *line, Style bg) {
    int inner_x = x + pl;
    for (int c = x; c < inner_x && c < x + w; c++)
        rc_set_cell(buf, c, y, ' ', bg);
    parse_line_into(buf, inner_x, y, max_w, line, bg);
    int rp = inner_x + max_w;
    for (int c = rp; c < rp + pr && c < x + w; c++)
        rc_set_cell(buf, c, y, ' ', bg);
}

/* Measure column widths (and optionally grow weights) for a Table. */
static int table_measure_cols(RenderCtx *ctx, PyObject *rows, Py_ssize_t nr,
                              int *col_w, int *grow_w) {
    int num_cols = 0;
    for (Py_ssize_t r = 0; r < nr; r++) {
        PyObject *cells = SLOT(PyList_GET_ITEM(rows, r), off_trow_cells);
        if (!cells) continue;
        int nc = (int)PyList_GET_SIZE(cells);
        if (nc > num_cols) num_cols = nc;
        for (Py_ssize_t ci = 0; ci < nc && ci < 256; ci++) {
            PyObject *cell = PyList_GET_ITEM(cells, ci);
            int m = c_measure_node(ctx, cell);
            if (m < 0) return -1;
            if (m > col_w[ci]) col_w[ci] = m;
            if (grow_w) {
                int g = slot_int(cell, off_grow);
                if (g > grow_w[ci]) grow_w[ci] = g;
            }
        }
    }
    return num_cols;
}

/* ── Measure ──────────────────────────────────────────────────────── */

static int c_measure_node(RenderCtx *ctx, PyObject *node) {
    /* Cache lookup. */
    PyObject *cached = PyDict_GetItem(ctx->mcache, node);  /* borrowed */
    if (cached) return (int)PyLong_AsLong(cached);

    int result = 0;
    PyTypeObject *tp = Py_TYPE(node);

    /* Check explicit non-percentage width first (direct slot). */
    PyObject *node_w = SLOT(node, off_width);
    if (node_w != Py_None) {
        Py_ssize_t wlen = PyUnicode_GET_LENGTH(node_w);
        if (wlen > 0) {
            int kind = PyUnicode_KIND(node_w);
            const void *data = PyUnicode_DATA(node_w);
            if (PyUnicode_READ(kind, data, wlen - 1) != '%') {
                result = 0;
                for (Py_ssize_t i = 0; i < wlen; i++)
                    result = result * 10 +
                             (int)(PyUnicode_READ(kind, data, i) - '0');
                goto cache;
            }
        }
    }

    if (tp == TextType_) {
        result = text_visible_w(node) + slot_int(node, off_text_pl) +
                 slot_int(node, off_text_pr);
    }
    else if (tp == SpacerType_) {
        result = slot_int(node, off_spacer_min_length);
    }
    else if (tp == HStackType_) {
        PyObject *children = SLOT(node, off_children);
        int sp = slot_int(node, off_hstack_spacing);
        Py_ssize_t n = children_len(children);
        if (n < 0) return -1;
        int count = 0;
        for (Py_ssize_t i = 0; i < n; i++) {
            PyObject *c = children_item(ctx, children, i);
            if (!c) return -1;
            int cw = c_measure_node(ctx, c);
            if (cw < 0) { Py_DECREF(c); return -1; }
            int g = slot_int(c, off_grow);
            int has_w = (SLOT(c, off_width) != Py_None);
            if (cw > 0 || g || has_w) { result += cw; count++; }
            Py_DECREF(c);
        }
        if (count > 1) result += sp * (count - 1);
    }
    else if (tp == BoxType_) {
        PyObject *children = SLOT(node, off_children);
        int pad = slot_int(node, off_box_padding);
        Py_ssize_t cn = children_len(children);
        if (cn < 0) return -1;
        if (cn > 0) {
            PyObject *first = children_item(ctx, children, 0);
            if (!first) return -1;
            int cw = c_measure_node(ctx, first);
            Py_DECREF(first);
            if (cw < 0) return -1;
            int content_w = cw + pad * 2;
            int title_w = 0;
            PyObject *title = SLOT(node, off_box_title);
            if (PyUnicode_Check(title) && PyUnicode_GET_LENGTH(title) > 0)
                title_w = str_display_width(title) + 2;
            result = (content_w > title_w ? content_w : title_w) + 2;
        }
    }
    else if (tp == TableType_) {
        PyObject *rows = SLOT(node, off_table_rows);
        if (PyList_Check(rows) && PyList_GET_SIZE(rows) > 0) {
            int spacing = slot_int(node, off_table_spacing);
            Py_ssize_t nr = PyList_GET_SIZE(rows);
            int cw[256] = {0};
            int num_cols = table_measure_cols(ctx, rows, nr, cw, NULL);
            if (num_cols < 0) return -1;
            for (int ci = 0; ci < num_cols && ci < 256; ci++)
                result += cw[ci];
            if (num_cols > 1)
                result += spacing * (num_cols - 1);
        }
    }
    else if (tp == InputType_) {
        PyObject *buf = SLOT(node, off_input_buffer);
        PyObject *val = PyObject_GetAttr(buf, a_value);
        if (val && PyUnicode_Check(val) && PyUnicode_GET_LENGTH(val) > 0) {
            result = str_display_width(val);
            if (slot_bool(node, off_input_active)) result++;
        } else {
            PyObject *ph = SLOT(node, off_input_placeholder);
            result = (ph && PyUnicode_Check(ph))
                     ? (int)PyUnicode_GET_LENGTH(ph) : 0;
        }
        Py_XDECREF(val);
    }
    else if (tp == ScrollbarType_) {
        result = 1;
    }
    else if (tp == CondType_) {
        PyObject *children = SLOT(node, off_children);
        Py_ssize_t cn = children_len(children);
        if (cn < 0) return -1;
        if (cn > 0) {
            PyObject *first = children_item(ctx, children, 0);
            if (!first) return -1;
            result = c_measure_node(ctx, first);
            Py_DECREF(first);
            if (result < 0) return -1;
        }
    }
    else {
        /* VStack, ZStack, Scroll, Foreach, others: max of children. */
        PyObject *children = SLOT(node, off_children);
        Py_ssize_t n = children_len(children);
        if (n < 0) return -1;
        for (Py_ssize_t i = 0; i < n; i++) {
            PyObject *c = children_item(ctx, children, i);
            if (!c) return -1;
            int cw = c_measure_node(ctx, c);
            Py_DECREF(c);
            if (cw < 0) return -1;
            if (cw > result) result = cw;
        }
    }

cache:
    {
        PyObject *val = PyLong_FromLong(result);
        if (val) {
            PyDict_SetItem(ctx->mcache, node, val);
            Py_DECREF(val);
        }
    }
    return result;
}

/* ── Text node helpers ────────────────────────────────────────────── */

/*
 * Get the cached lines list from a Text node, parsing the value string
 * on first access.  Returns a borrowed reference.
 */
static PyObject *text_get_lines(PyObject *node) {
    PyObject *cached = SLOT(node, off_text_lines);
    if (cached && cached != Py_None) {
        Py_INCREF(cached);
        return cached; /* caller must DECREF */
    }

    PyObject *val = SLOT(node, off_text_value);
    Py_INCREF(val);

    Py_ssize_t len = PyUnicode_GET_LENGTH(val);
    PyObject *lines;
    if (PyUnicode_FindChar(val, '\n', 0, len, 1) < 0) {
        lines = PyList_New(1);
        if (!lines) { Py_DECREF(val); return NULL; }
        PyList_SET_ITEM(lines, 0, val); /* steals ref */
    } else {
        lines = PyUnicode_Splitlines(val, 0);
        Py_DECREF(val);
        if (!lines) return NULL;
        if (PyList_GET_SIZE(lines) == 0) {
            Py_DECREF(lines);
            lines = PyList_New(1);
            if (!lines) return NULL;
            PyList_SET_ITEM(lines, 0, PyUnicode_FromString(""));
        }
    }

    /* Compute and cache visible_w. */
    int visible_w = 0;
    Py_ssize_t n = PyList_GET_SIZE(lines);
    for (Py_ssize_t i = 0; i < n; i++) {
        int lw = str_display_width(PyList_GET_ITEM(lines, i));
        if (lw > visible_w) visible_w = lw;
    }
    /* Cache directly into slots — faster than PyObject_SetAttr. */
    PyObject *vw_obj = PyLong_FromLong(visible_w);
    if (vw_obj) {
        PyObject **vw_slot = (PyObject **)((char *)node + off_text_visible_w);
        Py_XDECREF(*vw_slot);
        *vw_slot = vw_obj;
    }
    PyObject **lines_slot = (PyObject **)((char *)node + off_text_lines);
    Py_XDECREF(*lines_slot);
    Py_INCREF(lines);
    *lines_slot = lines;

    return lines; /* caller must DECREF */
}

static int text_visible_w(PyObject *node) {
    PyObject *vw = SLOT(node, off_text_visible_w);
    if (vw && vw != Py_None)
        return (int)PyLong_AsLong(vw);
    /* Force parse to populate cache. */
    PyObject *lines = text_get_lines(node);
    if (!lines) return 0;
    Py_DECREF(lines);
    vw = SLOT(node, off_text_visible_w);
    return vw ? (int)PyLong_AsLong(vw) : 0;
}

/* ── Type-specific renderers ──────────────────────────────────────── */

/* ── Text ─────────────────────────────────────────────────────────── */

static int render_text(RenderCtx *ctx, PyObject *node,
                       int x, int y, int w, int h, Style bg) {
    PyObject *lines = text_get_lines(node);
    if (!lines) return -1;

    int pl = slot_int(node, off_text_pl);
    int pr = slot_int(node, off_text_pr);
    int inner_w = w - pl - pr;
    if (inner_w < 0) inner_w = 0;

    int has_pad = (pl > 0 || pr > 0);

    /* Check wrap / truncation (direct slot). */
    int do_wrap = slot_bool(node, off_text_wrap);
    PyObject *trunc_obj = SLOT(node, off_text_truncation); /* borrowed */
    const char *tmode = (trunc_obj != Py_None)
        ? PyUnicode_AsUTF8(trunc_obj) : NULL;

    int rows = 0;
    Py_ssize_t n = PyList_GET_SIZE(lines);

    for (Py_ssize_t i = 0; i < n && (h < 0 || rows < h); i++) {
        PyObject *line = PyList_GET_ITEM(lines, i);

        if (do_wrap && inner_w > 0) {
            PyObject *wrapped = PyList_New(0);
            if (!wrapped) goto error;
            if (wrap_line_into(line, inner_w, wrapped) < 0) {
                Py_DECREF(wrapped); goto error;
            }
            Py_ssize_t nw = PyList_GET_SIZE(wrapped);
            for (Py_ssize_t j = 0; j < nw && (h < 0 || rows < h); j++) {
                PyObject *wline = PyList_GET_ITEM(wrapped, j);
                if (has_pad)
                    render_padded_line(ctx->buf, x, y + rows, w,
                                      pl, pr, inner_w, wline, bg);
                else
                    parse_line_into(ctx->buf, x, y + rows, w, wline, bg);
                rows++;
            }
            Py_DECREF(wrapped);
        }
        else if (tmode && inner_w > 0) {
            PyObject *trunc = truncate_line(line, inner_w, tmode[0]);
            if (!trunc) goto error;
            if (has_pad)
                render_padded_line(ctx->buf, x, y + rows, w,
                                  pl, pr, inner_w, trunc, bg);
            else
                parse_line_into(ctx->buf, x, y + rows, w, trunc, bg);
            Py_DECREF(trunc);
            rows++;
        }
        else if (has_pad) {
            render_padded_line(ctx->buf, x, y + rows, w,
                              pl, pr, str_display_width(line), line, bg);
            rows++;
        }
        else {
            parse_line_into(ctx->buf, x, y + rows, w, line, bg);
            rows++;
        }
    }

    Py_DECREF(lines);
    return rows;

error:
    Py_DECREF(lines);
    return -1;
}

/* ── VStack ───────────────────────────────────────────────────────── */

static int render_vstack(RenderCtx *ctx, PyObject *node,
                         int x, int y, int w, int h, Style bg) {
    PyObject *children = SLOT(node, off_children); /* borrowed */
    Py_ssize_t n = children_len(children);
    if (n < 0) return -1;
    if (n == 0) return 0;

    int spacing = slot_int(node, off_vstack_spacing);

    int needs_measure_pass = (h >= 0) ? slot_bool(node, off_vstack_needs_measure_pass) : 0;

    if (!needs_measure_pass) {
        /* No flex — render children unconstrained, clip total at h.
         * Children don't receive h (matches Python _fill_rows). */
        int rows = 0;
        for (Py_ssize_t i = 0; i < n; i++) {
            if (h >= 0 && rows >= h) break;
            if (i > 0 && spacing) {
                int remaining = (h >= 0) ? h - rows : -1;
                if (h >= 0 && remaining <= spacing) break;
                rows += spacing;
            }
            PyObject *child = children_item(ctx, children, i);
            if (!child) return -1;
            int cr = c_render_node(ctx, child, x, y + rows, w, -1, bg);
            Py_DECREF(child);
            if (cr < 0) return -1;
            rows += cr;
        }
        return rows;
    }

    /* ── Flex layout: two passes. ────────────────────────────────── */
    int *child_h = (int *)calloc((size_t)n, sizeof(int));
    if (!child_h) return (PyErr_NoMemory(), -1);

    int used = spacing * (int)(n > 1 ? n - 1 : 0);
    int grow_idx[256], grow_wt[256];
    int ng = 0;

    for (Py_ssize_t i = 0; i < n; i++) {
        PyObject *child = children_item(ctx, children, i);
        if (!child) { free(child_h); return -1; }
        int g = slot_int(child, off_grow);
        int has_h = (SLOT(child, off_height) != Py_None);

        if (g && !has_h) {
            child_h[i] = -1;
            if (ng >= 256) {
                PyErr_SetString(PyExc_OverflowError,
                                "VStack: too many grow children (max 256)");
                Py_DECREF(child);
                free(child_h); return -1;
            }
            grow_idx[ng] = (int)i; grow_wt[ng] = g; ng++;
        } else {
            int offscreen = ctx->buf->height;
            int ch = has_h ? h : -1;
            int cr = c_render_node(ctx, child, x, offscreen, w, ch, bg);
            if (cr < 0) { Py_DECREF(child); free(child_h); return -1; }
            child_h[i] = cr;
            used += cr;
        }
        Py_DECREF(child);
    }

    int remaining = h - used;
    if (remaining < 0) remaining = 0;
    if (ng > 0)
        distribute_flex(remaining, grow_idx, grow_wt, ng, child_h);

    /* Pass 2: render all children at computed y positions. */
    int row = 0;
    for (Py_ssize_t i = 0; i < n; i++) {
        if (i > 0 && spacing) row += spacing;
        PyObject *child = children_item(ctx, children, i);
        if (!child) { free(child_h); return -1; }
        int g = slot_int(child, off_grow);
        int has_h = (SLOT(child, off_height) != Py_None);

        if (g && !has_h) {
            int cr = c_render_node(ctx, child, x, y + row, w,
                                   child_h[i], bg);
            Py_DECREF(child);
            if (cr < 0) { free(child_h); return -1; }
            row += child_h[i];
        } else {
            int cr = c_render_node(ctx, child, x, y + row, w,
                                   has_h ? h : -1, bg);
            Py_DECREF(child);
            if (cr < 0) { free(child_h); return -1; }
            row += child_h[i] >= 0 ? child_h[i] : cr;
        }
    }

    free(child_h);
    return row;
}

/* ── Foreach ──────────────────────────────────────────────────────── */

static int render_foreach(RenderCtx *ctx, PyObject *node,
                          int x, int y, int w, int h, Style bg) {
    PyObject *children = SLOT(node, off_children);
    Py_ssize_t n = children_len(children);
    if (n < 0) return -1;

    int rows = 0;
    for (Py_ssize_t i = 0; i < n; i++) {
        if (h >= 0 && rows >= h) break;
        int remaining = (h >= 0) ? h - rows : -1;
        PyObject *child = children_item(ctx, children, i);
        if (!child) return -1;
        int cr = c_render_node(ctx, child, x, y + rows, w, remaining, bg);
        Py_DECREF(child);
        if (cr < 0) return -1;
        rows += cr;
    }

    return rows;
}

/* ── Cond ─────────────────────────────────────────────────────────── */

static int render_cond(RenderCtx *ctx, PyObject *node,
                       int x, int y, int w, int h, Style bg) {
    PyObject *children = SLOT(node, off_children);
    Py_ssize_t cn = children_len(children);
    if (cn < 0) return -1;
    if (cn == 0) return 0;
    PyObject *first = children_item(ctx, children, 0);
    if (!first) return -1;
    int cr = c_render_node(ctx, first, x, y, w, h, bg);
    Py_DECREF(first);
    return cr;
}

/* ── Spacer ───────────────────────────────────────────────────────── */

static int render_spacer(RenderCtx *ctx, PyObject *node,
                         int x, int y, int w, int h, Style bg) {
    (void)ctx; (void)node; (void)x; (void)y; (void)w; (void)bg;
    return (h >= 0) ? h : 1;
}

/* ── HStack ───────────────────────────────────────────────────────── */

/*
 * Inline flex distribution over C arrays.
 * col_widths is filled on return.  Returns leftover space.
 */
static int flex_dist(RenderCtx *ctx, PyObject **act, int n,
                     int *col_widths, int w, int spacing) {
    int grow_idx[256], grow_wt[256];
    int ng = 0;
    int used = spacing * (n > 1 ? n - 1 : 0);

    for (int i = 0; i < n; i++) {
        PyObject *c = act[i];
        PyObject *cwid = SLOT(c, off_width);
        int has_w = (cwid != Py_None);
        if (has_w) {
            col_widths[i] = rc_resolve_size(cwid, w);
        } else {
            col_widths[i] = c_measure_node(ctx, c);
            if (col_widths[i] < 0) return -1;
        }
        int g = slot_int(c, off_grow);
        if (!has_w && g) {
            if (ng >= 256) {
                PyErr_SetString(PyExc_OverflowError,
                                "HStack: too many grow children (max 256)");
                return -1;
            }
            grow_idx[ng] = i;
            grow_wt[ng] = g;
            ng++;
            col_widths[i] = 0;
        }
        used += col_widths[i];
    }

    int remaining = w - used;
    if (remaining < 0) remaining = 0;
    if (ng > 0 && remaining > 0) {
        distribute_flex(remaining, grow_idx, grow_wt, ng, col_widths);
        remaining = 0;
    }
    return remaining;
}

/* ── HStack wrap: measure + pack children into rows ────────────── */

static int render_hstack_wrap(RenderCtx *ctx, PyObject *children,
                              Py_ssize_t nc, int spacing,
                              int x, int y, int w, int h, Style bg) {
    if (nc == 0) return 1;

    int row_off = 0;
    int col = 0;  /* x position after last content (excl. spacing) */
    for (Py_ssize_t i = 0; i < nc; i++) {
        if (h >= 0 && row_off >= h) break;
        PyObject *c = children_item(ctx, children, i);
        if (!c) return -1;
        int cw = c_measure_node(ctx, c);
        if (cw < 0) { Py_DECREF(c); return -1; }
        if (cw == 0) { Py_DECREF(c); continue; }

        int needed = col > 0 ? col + spacing + cw : cw;
        if (needed > w && col > 0) {
            row_off++;
            col = 0;
        }
        if (h >= 0 && row_off >= h) { Py_DECREF(c); break; }
        int cx = col > 0 ? col + spacing : 0;
        c_render_node(ctx, c, x + cx, y + row_off, cw, 1, bg);
        col = cx + cw;
        Py_DECREF(c);
    }
    return row_off + 1;
}

static int render_hstack(RenderCtx *ctx, PyObject *node,
                         int x, int y, int w, int h, Style bg) {
    PyObject *children = SLOT(node, off_children); /* borrowed */
    Py_ssize_t nc = children_len(children);
    if (nc < 0) return -1;

    int spacing = slot_int(node, off_hstack_spacing);

    /* Wrap mode. */
    if (slot_bool(node, off_hstack_wrap))
        return render_hstack_wrap(ctx, children, nc, spacing,
                                  x, y, w, h, bg);

    /* Read justify / align (borrowed). */
    PyObject *jc = SLOT(node, off_hstack_jc);
    PyObject *ai = SLOT(node, off_hstack_ai);

    /* Collect active children — act_arr holds owned refs released in cleanup. */
    PyObject *act_arr[512];
    int n = 0;
    int result = -1;

    for (Py_ssize_t i = 0; i < nc; i++) {
        PyObject *c = children_item(ctx, children, i);
        if (!c) goto cleanup;
        int m = c_measure_node(ctx, c);
        if (m < 0) { Py_DECREF(c); goto cleanup; }
        int g = slot_int(c, off_grow);
        int has_w = (SLOT(c, off_width) != Py_None);
        if (m > 0 || g || has_w) {
            if (n >= 512) {
                PyErr_SetString(PyExc_OverflowError,
                                "HStack: too many active children (max 512)");
                Py_DECREF(c);
                goto cleanup;
            }
            act_arr[n++] = c;  /* ownership transferred */
        } else {
            Py_DECREF(c);
        }
    }

    if (n == 0) {
        result = (h >= 0) ? h : 1;
        goto cleanup;
    }

    /* Flex distribution. */
    int col_widths[512];
    int remaining = flex_dist(ctx, act_arr, n, col_widths, w, spacing);
    if (remaining < 0) goto cleanup;

    /* Compute x offsets based on justify_content. */
    int offsets[512];
    int cx = 0;
    if (jc == s_end) {
        cx = remaining;
    } else if (jc == s_center) {
        cx = remaining / 2;
    }
    /* "between" distributes remaining among n-1 gaps with equal weights. */
    int gap_extras[512] = {0};
    if (jc == s_between && n > 1 && remaining > 0) {
        int idx[512], wt[512];
        for (int i = 0; i < n - 1; i++) { idx[i] = i; wt[i] = 1; }
        distribute_flex(remaining, idx, wt, n - 1, gap_extras);
    }

    for (int i = 0; i < n; i++) {
        offsets[i] = cx;
        cx += col_widths[i];
        if (i < n - 1) {
            cx += spacing;
            if (jc == s_between && n > 1 && remaining > 0)
                cx += gap_extras[i];
        }
    }

    /* Non-start align: measure column heights, compute y offsets. */
    int y_offsets[512];
    int max_rows = 0;

    if (ai != s_start) {
        /* First pass: render offscreen to measure heights. */
        int col_heights[512];
        int offscreen = ctx->buf->height;
        for (int i = 0; i < n; i++) {
            int g = slot_int(act_arr[i], off_grow);
            int ch = g ? h : -1;
            int cr = c_render_node(ctx, act_arr[i],
                                   x + offsets[i], offscreen,
                                   col_widths[i], ch, bg);
            if (cr < 0) goto cleanup;
            col_heights[i] = cr;
            if (cr > max_rows) max_rows = cr;
        }

        for (int i = 0; i < n; i++) {
            int diff = max_rows - col_heights[i];
            if (ai == s_end)
                y_offsets[i] = diff;
            else if (ai == s_center)
                y_offsets[i] = diff / 2;
            else
                y_offsets[i] = 0;
        }
    } else {
        for (int i = 0; i < n; i++) y_offsets[i] = 0;
    }

    /* Render each child into its column. */
    for (int i = 0; i < n; i++) {
        int g = slot_int(act_arr[i], off_grow);
        if (g)
            rc_fill_region(ctx->buf, x + offsets[i], y + y_offsets[i],
                           col_widths[i], 1, bg);
        int ch = g ? h : -1;
        int cr = c_render_node(ctx, act_arr[i],
                               x + offsets[i], y + y_offsets[i],
                               col_widths[i], ch, bg);
        if (cr < 0) goto cleanup;
        if (ai == s_start && cr > max_rows) max_rows = cr;
    }

    if (max_rows > 1) {
        for (int i = 0; i < n; i++)
            rc_fill_unwritten(ctx->buf, x + offsets[i], y + y_offsets[i],
                              col_widths[i], max_rows, bg);
    }

    result = max_rows;
cleanup:
    for (int i = 0; i < n; i++) Py_DECREF(act_arr[i]);
    return result;
}

/* ── Box ──────────────────────────────────────────────────────────── */

/* Border chars: tl, tr, bl, br, hz, vt */
static const Py_UCS4 border_rounded[] =
    {0x256D, 0x256E, 0x2570, 0x256F, 0x2500, 0x2502};
static const Py_UCS4 border_normal[] =
    {0x250C, 0x2510, 0x2514, 0x2518, 0x2500, 0x2502};
static const Py_UCS4 border_double[] =
    {0x2554, 0x2557, 0x255A, 0x255D, 0x2550, 0x2551};
static const Py_UCS4 border_heavy[] =
    {0x250F, 0x2513, 0x2517, 0x251B, 0x2501, 0x2503};

static const Py_UCS4 *lookup_border(PyObject *style) {
    if (style == s_rounded) return border_rounded;
    if (style == s_normal)  return border_normal;
    if (style == s_double)  return border_double;
    if (style == s_heavy)   return border_heavy;
    return border_rounded; /* fallback */
}

static int render_box(RenderCtx *ctx, PyObject *node,
                      int x, int y, int w, int h, Style bg) {
    PyObject *children = SLOT(node, off_children);
    Py_ssize_t cn = children_len(children);
    if (cn < 0) return -1;
    if (cn == 0) return 0;
    PyObject *child = children_item(ctx, children, 0);
    if (!child) return -1;

    PyObject *style_obj = SLOT(node, off_box_style);   /* borrowed */
    PyObject *title_obj = SLOT(node, off_box_title);    /* borrowed */
    int pad = slot_int(node, off_box_padding);

    const Py_UCS4 *bdr = lookup_border(style_obj);
    Py_UCS4 tl = bdr[0], tr = bdr[1], bl = bdr[2], br = bdr[3];
    Py_UCS4 hz = bdr[4], vt = bdr[5];

    /* Compute inner width. */
    int child_w = c_measure_node(ctx, child);
    if (child_w < 0) { Py_DECREF(child); return -1; }
    int child_grow = slot_int(child, off_grow);
    int content_w = child_w + pad * 2;
    int title_w = 0;
    Py_ssize_t title_len = PyUnicode_GET_LENGTH(title_obj);
    if (title_len > 0) title_w = str_display_width(title_obj) + 2;
    int natural = content_w > title_w ? content_w : title_w;
    int inner = child_grow ? (w - 2 > 0 ? w - 2 : 0)
                           : (natural < w - 2 ? natural : (w - 2 > 0 ? w - 2 : 0));

    int child_h = (h >= 0) ? (h - 2 > 0 ? h - 2 : 0) : -1;
    int cw = inner - pad * 2;
    if (cw < 0) cw = 0;

    BufferObject *buf = ctx->buf;

    /* Top border. */
    if (y >= 0 && y < buf->height) {
        rc_set_cell(buf, x, y, tl, bg);
        if (title_len > 0) {
            /* " title hz..." */
            rc_set_cell(buf, x + 1, y, ' ', bg);
            PyObject *trunc = truncate_line(title_obj, inner - 2, 't');
            if (!trunc && PyErr_Occurred()) PyErr_Clear();
            if (trunc) {
                int tw = str_display_width(trunc);
                parse_line_into(buf, x + 2, y, tw, trunc, bg);
                rc_set_cell(buf, x + 2 + tw, y, ' ', bg);
                for (int c = x + 3 + tw; c < x + 1 + inner; c++)
                    rc_set_cell(buf, c, y, hz, bg);
                Py_DECREF(trunc);
            }
        } else {
            for (int c = x + 1; c < x + 1 + inner; c++)
                rc_set_cell(buf, c, y, hz, bg);
        }
        rc_set_cell(buf, x + 1 + inner, y, tr, bg);
    }

    /* Measure child height, fill interior for opacity, render on top. */
    int cr = c_render_node(ctx, child, x + 1 + pad,
                           ctx->buf->height, cw, child_h, bg);
    if (cr < 0) { Py_DECREF(child); return -1; }
    int content_rows = cr > 0 ? cr : 1;
    rc_fill_region(buf, x + 1, y + 1, inner, content_rows, bg);
    c_render_node(ctx, child, x + 1 + pad, y + 1, cw, child_h, bg);
    Py_DECREF(child);

    for (int r = 0; r < content_rows; r++) {
        int row = y + 1 + r;
        if (row >= buf->height) break;
        rc_set_cell(buf, x, row, vt, bg);
        rc_set_cell(buf, x + 1 + inner, row, vt, bg);
    }

    /* Bottom border. */
    int bot = y + 1 + content_rows;
    if (bot >= 0 && bot < buf->height) {
        rc_set_cell(buf, x, bot, bl, bg);
        for (int c = x + 1; c < x + 1 + inner; c++)
            rc_set_cell(buf, c, bot, hz, bg);
        rc_set_cell(buf, x + 1 + inner, bot, br, bg);
    }

    return 2 + content_rows;
}

/* ── Scroll ───────────────────────────────────────────────────────── */

static int render_scroll(RenderCtx *ctx, PyObject *node,
                         int x, int y, int w, int h, Style bg) {
    if (h <= 0) return 0;

    PyObject *state = SLOT(node, off_scroll_state);     /* borrowed */
    PyObject *children = SLOT(node, off_children);      /* borrowed */
    Py_ssize_t total = children_len(children);
    if (total < 0) return -1;

    ss_set_int(state, off_ss_height, h);
    ss_set_int(state, off_ss_total, (int)total);

    int max_off = (int)total > h ? (int)total - h : 0;
    int follow = slot_bool(state, off_ss_follow);
    int offset = follow ? max_off : slot_int(state, off_ss_offset);
    if (offset < 0) offset = 0;
    if (offset > max_off) offset = max_off;
    ss_set_int(state, off_ss_offset, offset);

    if ((int)total > h && offset >= max_off)
        ss_set_bool(state, off_ss_follow, 1);

    int rows = 0;
    for (Py_ssize_t i = (Py_ssize_t)offset; i < total && rows < h; i++) {
        int remaining = h - rows;
        PyObject *child = children_item(ctx, children, i);
        if (!child) return -1;
        int cr = c_render_node(ctx, child, x, y + rows, w, remaining, bg);
        Py_DECREF(child);
        if (cr < 0) return -1;
        if (cr > remaining) cr = remaining;
        rows += cr;
    }

    return h;
}

/* ── Table ────────────────────────────────────────────────────────── */

static int render_table(RenderCtx *ctx, PyObject *node,
                        int x, int y, int w, int h, Style bg) {
    PyObject *rows = SLOT(node, off_table_rows);
    if (!PyList_Check(rows) || PyList_GET_SIZE(rows) == 0)
        return 1;  /* empty table: one blank row */

    int spacing = slot_int(node, off_table_spacing);
    Py_ssize_t nr = PyList_GET_SIZE(rows);

    int col_w[256] = {0};
    int grow_w[256] = {0};
    int num_cols = table_measure_cols(ctx, rows, nr, col_w, grow_w);
    if (num_cols < 0) return -1;
    if (num_cols == 0) return 0;
    if (num_cols > 256) {
        PyErr_SetString(PyExc_OverflowError,
                        "Table: too many columns (max 256)");
        return -1;
    }

    /* Resolve grow columns. */
    int resolved[256];
    int gidx[256], gwt[256];
    int ng = 0, has_grow = 0;
    for (int ci = 0; ci < num_cols; ci++) {
        resolved[ci] = col_w[ci];
        if (grow_w[ci]) {
            gidx[ng] = ci; gwt[ng] = grow_w[ci]; ng++;
            has_grow = 1;
        }
    }
    if (has_grow) {
        int gap_total = spacing * (num_cols > 1 ? num_cols - 1 : 0);
        int fixed = gap_total;
        for (int ci = 0; ci < num_cols; ci++)
            if (!grow_w[ci]) fixed += resolved[ci];
        int remaining = w - fixed;
        if (remaining < 0) remaining = 0;
        distribute_flex(remaining, gidx, gwt, ng, resolved);
    }

    /* Compute column x offsets. */
    int col_x[256];
    int cx = 0;
    for (int ci = 0; ci < num_cols; ci++) {
        col_x[ci] = cx;
        cx += resolved[ci];
        if (ci < num_cols - 1) cx += spacing;
    }

    /* Render rows — pre-fill each row so jagged rows get padded. */
    int table_w = cx;  /* total width of all columns + spacing */
    Py_ssize_t visible = (h >= 0 && h < nr) ? h : nr;
    for (Py_ssize_t r = 0; r < visible; r++) {
        /* Fill row with spaces so missing columns are visible. */
        rc_fill_region(ctx->buf, x, y + (int)r, table_w, 1, bg);
        PyObject *cells = SLOT(PyList_GET_ITEM(rows, r), off_trow_cells);
        if (!cells) continue;
        Py_ssize_t nc = PyList_GET_SIZE(cells);
        for (Py_ssize_t ci = 0; ci < nc && ci < num_cols; ci++) {
            c_render_node(ctx, PyList_GET_ITEM(cells, ci),
                          x + col_x[ci], y + (int)r,
                          resolved[ci], 1, bg);
        }
    }

    return (int)visible;
}

/* ── ZStack ───────────────────────────────────────────────────────── */

static int render_zstack(RenderCtx *ctx, PyObject *node,
                         int x, int y, int w, int h, Style bg) {
    PyObject *children = SLOT(node, off_children); /* borrowed */
    Py_ssize_t n = children_len(children);
    if (n < 0) return -1;
    if (n == 0) return (h >= 0) ? h : 1;

    PyObject *jc = SLOT(node, off_zstack_jc); /* borrowed */
    PyObject *ai = SLOT(node, off_zstack_ai); /* borrowed */

    int is_start = (jc == s_start && ai == s_start);

    int canvas_h = h;
    Py_ssize_t first_done = 0;
    if (canvas_h < 0) {
        PyObject *first = children_item(ctx, children, 0);
        if (!first) return -1;
        if (is_start) {
            canvas_h = c_render_node(ctx, first, x, y, w, -1, bg);
            Py_DECREF(first);
            if (canvas_h < 0) return -1;
            first_done = 1;
        } else {
            canvas_h = c_render_node(ctx, first, x, ctx->buf->height,
                                     w, -1, bg);
            Py_DECREF(first);
            if (canvas_h < 0) return -1;
        }
    }

    for (Py_ssize_t i = first_done; i < n; i++) {
        PyObject *child = children_item(ctx, children, i);
        if (!child) return -1;

        if (is_start) {
            int cr = c_render_node(ctx, child, x, y, w, canvas_h, bg);
            Py_DECREF(child);
            if (cr < 0) return -1;
            continue;
        }

        int g = slot_int(child, off_grow);
        if (g && canvas_h >= 0) {
            c_render_node(ctx, child, x, y, w, canvas_h, bg);
            Py_DECREF(child);
            continue;
        }

        int layer_h = c_render_node(ctx, child, x, ctx->buf->height,
                                    w, canvas_h, bg);
        if (layer_h < 0) { Py_DECREF(child); return -1; }

        int layer_w;
        if (SLOT(child, off_width) == Py_None && Py_TYPE(child) == ZStackType_) {
            layer_w = w;
        } else {
            layer_w = c_measure_node(ctx, child);
            if (layer_w < 0) { Py_DECREF(child); return -1; }
        }

        int row_off = 0, col_off = 0;
        if (ai == s_end)       row_off = canvas_h - layer_h;
        else if (ai == s_center) row_off = (canvas_h - layer_h) / 2;
        if (jc == s_end)       col_off = w - layer_w;
        else if (jc == s_center) col_off = (w - layer_w) / 2;
        if (row_off < 0) row_off = 0;
        if (col_off < 0) col_off = 0;

        c_render_node(ctx, child, x + col_off, y + row_off,
                      w, canvas_h, bg);
        Py_DECREF(child);
    }

    rc_fill_unwritten(ctx->buf, x, y, w, canvas_h, bg);
    return canvas_h;
}

/* ── Input ────────────────────────────────────────────────────────── */

static int render_input(RenderCtx *ctx, PyObject *node,
                        int x, int y, int w, int h, Style bg) {
    PyObject *buf_obj = SLOT(node, off_input_buffer); /* borrowed */

    int active = slot_bool(node, off_input_active);

    /* Check if value is empty. */
    PyObject *val = PyObject_GetAttr(buf_obj, a_value);
    int empty = (!val || !PyUnicode_Check(val) ||
                 PyUnicode_GET_LENGTH(val) == 0);
    Py_XDECREF(val);

    if (empty && !active) {
        PyObject *ph = SLOT(node, off_input_placeholder); /* borrowed */
        if (ph && PyUnicode_Check(ph) && PyUnicode_GET_LENGTH(ph) > 0) {
            Style dim = bg;
            dim.flags |= FLAG_DIM;
            Py_ssize_t len = PyUnicode_GET_LENGTH(ph);
            int kind = PyUnicode_KIND(ph);
            const void *data = PyUnicode_DATA(ph);
            int col = x;
            for (Py_ssize_t i = 0; i < len && col < x + w; i++) {
                Py_UCS4 ch = PyUnicode_READ(kind, data, i);
                int cw = cwidth(ch);
                if (cw <= 0) continue;
                rc_set_cell(ctx->buf, col, y, ch, dim);
                if (cw == 2) {
                    rc_set_cell(ctx->buf, col + 1, y, WIDE_CHAR, dim);
                    col += 2;
                } else {
                    col++;
                }
            }
        }
        return 1;
    }

    PyObject *txt_obj = PyObject_CallFunctionObjArgs(
        py_display_text, buf_obj, NULL);
    if (!txt_obj) return -1;

    Py_ssize_t txt_len = PyUnicode_GET_LENGTH(txt_obj);
    int kind = PyUnicode_KIND(txt_obj);
    const void *data = PyUnicode_DATA(txt_obj);

    int cursor = -1;
    if (active) {
        PyObject *cur_obj = PyObject_CallFunctionObjArgs(
            py_display_cursor, buf_obj, NULL);
        if (!cur_obj) { Py_DECREF(txt_obj); return -1; }
        cursor = (int)PyLong_AsLong(cur_obj);
        Py_DECREF(cur_obj);
    }

    Py_ssize_t raw_len = active && cursor >= txt_len
                         ? txt_len + 1 : txt_len;
    if (raw_len == 0) {
        Py_DECREF(txt_obj);
        return 1;
    }

    int rows = 0;
    for (Py_ssize_t pos = 0; pos < raw_len; pos += w) {
        if (h >= 0 && rows >= h) break;
        int row_y = y + rows;
        Py_ssize_t chunk_end = pos + w;
        if (chunk_end > raw_len) chunk_end = raw_len;
        int col = x;
        for (Py_ssize_t i = pos; i < chunk_end && col < x + w; i++) {
            Py_UCS4 ch = (i < txt_len)
                         ? PyUnicode_READ(kind, data, i) : ' ';
            Style s = bg;
            if (active && (int)i == cursor)
                s.flags |= FLAG_REVERSE;
            rc_set_cell(ctx->buf, col, row_y, ch, s);
            col++;
        }
        rows++;
    }

    Py_DECREF(txt_obj);
    return rows > 0 ? rows : 1;
}

/* Render a Python list of strings into cells. */
static int render_string_list(RenderCtx *ctx, PyObject *list,
                              int x, int y, int w, int h, Style bg) {
    Py_ssize_t nlines = PyList_GET_SIZE(list);
    int rows = 0;
    for (Py_ssize_t i = 0; i < nlines; i++) {
        if (h >= 0 && rows >= h) break;
        parse_line_into(ctx->buf, x, y + rows, w,
                        PyList_GET_ITEM(list, i), bg);
        rows++;
    }
    return rows;
}

/* ── Scrollbar ───────────────────────────────────────────────────── */

static int render_scrollbar(RenderCtx *ctx, PyObject *node,
                            int x, int y, int w, int h, Style bg) {
    PyObject *state = SLOT(node, off_scrollbar_state); /* borrowed */

    int sh = slot_int(state, off_ss_height);
    int total = slot_int(state, off_ss_total);
    int offset = slot_int(state, off_ss_offset);

    if (sh <= 0 || total <= sh)
        return sh > 0 ? sh : 0;

    PyObject *fn = SLOT(node, off_scrollbar_render_fn); /* borrowed */
    Py_INCREF(fn); /* protect during call */
    PyObject *result = PyObject_CallFunction(fn, "iii", sh, total, offset);
    Py_DECREF(fn);
    if (!result) return -1;

    if (!PyList_Check(result)) {
        Py_DECREF(result);
        return sh;
    }
    int rows = render_string_list(ctx, result, x, y, w, h, bg);
    Py_DECREF(result);
    return rows;
}

/* ── Custom ──────────────────────────────────────────────────────── */

static int render_custom(RenderCtx *ctx, PyObject *node,
                         int x, int y, int w, int h, Style bg) {
    PyObject *fn = PyObject_GetAttr(node, a_render_fn);
    if (!fn) return -1;

    PyObject *result;
    if (h >= 0)
        result = PyObject_CallFunction(fn, "ii", w, h);
    else
        result = PyObject_CallFunction(fn, "iO", w, Py_None);
    Py_DECREF(fn);
    if (!result) return -1;

    if (!PyList_Check(result)) {
        Py_DECREF(result);
        return 0;
    }
    int rows = render_string_list(ctx, result, x, y, w, h, bg);
    Py_DECREF(result);
    return rows;
}

/* ── Type dispatch ────────────────────────────────────────────────── */

static int dispatch_render(RenderCtx *ctx, PyTypeObject *tp,
                           PyObject *node,
                           int x, int y, int w, int h, Style bg) {
    if (tp == TextType_)       return render_text(ctx, node, x, y, w, h, bg);
    if (tp == HStackType_)     return render_hstack(ctx, node, x, y, w, h, bg);
    if (tp == VStackType_)     return render_vstack(ctx, node, x, y, w, h, bg);
    if (tp == ZStackType_)     return render_zstack(ctx, node, x, y, w, h, bg);
    if (tp == BoxType_)        return render_box(ctx, node, x, y, w, h, bg);
    if (tp == ScrollType_)     return render_scroll(ctx, node, x, y, w, h, bg);
    if (tp == TableType_)      return render_table(ctx, node, x, y, w, h, bg);
    if (tp == ForeachType_)    return render_foreach(ctx, node, x, y, w, h, bg);
    if (tp == CondType_)       return render_cond(ctx, node, x, y, w, h, bg);
    if (tp == SpacerType_)     return render_spacer(ctx, node, x, y, w, h, bg);
    if (tp == InputType_)      return render_input(ctx, node, x, y, w, h, bg);
    if (tp == ScrollbarType_)  return render_scrollbar(ctx, node, x, y, w, h, bg);
    return render_custom(ctx, node, x, y, w, h, bg);
}

/* ── Framing + dispatch ───────────────────────────────────────────── */
/*
 * c_render_framed reads the node's width/height/bg/overflow and
 * adjusts the render region, then dispatches to the type-specific
 * renderer.  Only called for C-handled node types.
 */
static int c_render_framed(RenderCtx *ctx, PyTypeObject *tp,
                           PyObject *node,
                           int x, int y, int w, int h, Style bg) {
    /* Direct slot reads — borrowed refs, no DECREF needed. */
    PyObject *nw  = SLOT(node, off_width);
    PyObject *nh  = SLOT(node, off_height);
    PyObject *nbg = SLOT(node, off_bg);

    int has_frame = (nw != Py_None || nh != Py_None || nbg != Py_None);
    if (!has_frame)
        return dispatch_render(ctx, tp, node, x, y, w, h, bg);

    int has_explicit_h = (nh != Py_None);
    int has_explicit_w = (nw != Py_None);
    PyObject *ovf = SLOT(node, off_overflow);
    int clips = (ovf != s_visible);

    /* Resolve explicit sizes. */
    int rw = rc_resolve_size(nw, w);
    int rh = rc_resolve_size(nh, h >= 0 ? h : 0);
    if (rw >= 0) w = rw < w ? rw : w;
    if (rh >= 0) {
        int ch = (h >= 0) ? (rh < h ? rh : h) : rh;
        h = ch;
    }

    /* Pre-fill background. */
    if (nbg != Py_None) {
        int bgc = (int)PyLong_AsLong(nbg);
        bg = (Style){COLOR_EMPTY,
                     {COLOR_INDEXED, (uint8_t)bgc, 0, 0},
                     0, {0, 0}};
        rc_fill_region(ctx->buf, x, y, w, h >= 0 ? h : 1, bg);
    }

    if (has_explicit_w && clips && h >= 0)
        rc_fill_region(ctx->buf, x, y, w, h, bg);

    /* Dispatch to type-specific renderer. */
    int rows = dispatch_render(ctx, tp, node, x, y, w, h, bg);

    /* Deferred fill: bg or explicit width+clip was set but h was
     * unconstrained — fill after content render so we know the height. */
    if (rows > 0 && h < 0 &&
        ((!style_is_empty(bg) && bg.bg.kind != COLOR_NONE) ||
         (has_explicit_w && clips)))
        rc_fill_unwritten(ctx->buf, x, y, w, rows, bg);

    if (has_explicit_h && rows >= 0 && h >= 0 && rows < h)
        rows = h;

    return rows;
}

/* ── c_render_node — top-level dispatch ───────────────────────────── */

static int c_render_node(RenderCtx *ctx, PyObject *node,
                         int x, int y, int w, int h, Style bg) {
    if (w <= 0) return 0;
    if (ctx->depth >= MAX_RENDER_DEPTH) {
        PyErr_SetString(PyExc_RecursionError,
                        "node tree exceeds max render depth");
        return -1;
    }
    ctx->depth++;

    PyTypeObject *tp = Py_TYPE(node);
    int rows;

    /* Bare Node() — renders empty. */
    if (tp == NodeType_) {
        rows = 0;
    }
    /* All concrete types: framing + type dispatch. */
    else {
        rows = c_render_framed(ctx, tp, node, x, y, w, h, bg);
    }

    ctx->depth--;
    return rows;
}

/* ── Python entry point ───────────────────────────────────────────── */
/*
 * render_to_buffer(node, buffer) -> int
 *
 * Walk the node tree and write directly into the buffer's cell grid.
 * Returns the number of content rows, or raises on error.
 */
static PyObject *mod_render_to_buffer(PyObject *self, PyObject *args) {
    PyObject *node;
    BufferObject *buf;
    int h = -2;  /* sentinel: use buffer height */

    if (!PyArg_ParseTuple(args, "OO!|i", &node, &BufferType, &buf, &h))
        return NULL;

    if (init_render_types() < 0)
        return NULL;

    int render_h = (h == -2) ? buf->height : h;

    PyObject *mcache = PyDict_New();
    if (!mcache) return NULL;
    PyObject *ccache = PyDict_New();
    if (!ccache) { Py_DECREF(mcache); return NULL; }

    RenderCtx ctx = {buf, mcache, ccache, 0};
    int rows = c_render_node(&ctx, node, 0, 0,
                             buf->width, render_h,
                             STYLE_EMPTY);

    Py_DECREF(mcache);
    Py_DECREF(ccache);

    if (rows < 0) return NULL;
    return PyLong_FromLong(rows);
}
