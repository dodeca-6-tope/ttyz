/*
 * render.c — Direct node-to-cell tree renderer.
 *
 * Walks Python Node objects and writes directly into BufferObject cells,
 * bypassing intermediate list[str] and ANSI re-parsing.
 *
 * All node types are handled in C: Text, HStack, VStack, ZStack, Box,
 * Scroll, Table, Foreach, Cond, Spacer, Input, Scrollbar, ListView,
 * Custom.
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
static PyTypeObject *CustomType_;
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
static PyTypeObject *ListViewType_;
static PyTypeObject *InputType_;

/* Interned attribute name strings. */
static PyObject *a_children;
static PyObject *a_grow;
static PyObject *a_width;
static PyObject *a_height;
static PyObject *a_bg;
static PyObject *a_overflow;
static PyObject *a_text_render;
static PyObject *a_padding_w;
static PyObject *a_spacing;
static PyObject *a_has_flex;
static PyObject *a_min_length;
static PyObject *a_style;
static PyObject *a_title;
static PyObject *a_padding;
static PyObject *a_justify_content;
static PyObject *a_align_items;
static PyObject *a_state;
static PyObject *a_offset;
static PyObject *a_follow;
static PyObject *a_max_offset;
static PyObject *a_rows;
static PyObject *a_cells;
static PyObject *a_buffer;
static PyObject *a_active;
static PyObject *a_placeholder;
static PyObject *a_value;
static PyObject *a_total;
static PyObject *a_wrap;
static PyObject *a_render_fn;
static PyObject *a_cursor;
static PyObject *a_items;
static PyObject *a_scroll;
static PyObject *a_key;
static PyObject *a_cache;

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

/* Python helpers for Input rendering. */
static PyObject *py_display_text;
static PyObject *py_display_cursor;

/* ── init_render_types — lazy one-time setup ──────────────────────── */

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

    LOAD(NodeType_,      "ttyz.components.base",      "Node");
    LOAD(CustomType_,    "ttyz.components.base",      "Custom");
    LOAD(TextType_,      "ttyz.components.text",      "Text");
    LOAD(HStackType_,    "ttyz.components.hstack",    "HStack");
    LOAD(VStackType_,    "ttyz.components.vstack",    "VStack");
    LOAD(ZStackType_,    "ttyz.components.zstack",    "ZStack");
    LOAD(BoxType_,       "ttyz.components.box",        "Box");
    LOAD(SpacerType_,    "ttyz.components.spacer",    "Spacer");
    LOAD(CondType_,      "ttyz.components.cond",      "Cond");
    LOAD(ForeachType_,   "ttyz.components.foreach",   "Foreach");
    LOAD(ScrollType_,    "ttyz.components.scroll",    "Scroll");
    LOAD(ScrollbarType_, "ttyz.components.scrollbar",  "Scrollbar");
    LOAD(TableType_,     "ttyz.components.table",     "Table");
    LOAD(ListViewType_,  "ttyz.components.list",       "ListView");
    LOAD(InputType_,     "ttyz.components.input",     "Input");
#undef LOAD

#define INTERN(var, name) do {                        \
    var = PyUnicode_InternFromString(name);            \
    if (!var) return -1;                               \
} while (0)

    INTERN(a_children,        "children");
    INTERN(a_grow,            "grow");
    INTERN(a_width,           "width");
    INTERN(a_height,          "height");
    INTERN(a_bg,              "bg");
    INTERN(a_overflow,        "overflow");
    INTERN(a_text_render,     "text_render");
    INTERN(a_padding_w,       "padding_w");
    INTERN(a_spacing,         "spacing");
    INTERN(a_has_flex,        "has_flex");
    INTERN(a_min_length,      "min_length");
    INTERN(a_style,           "style");
    INTERN(a_title,           "title");
    INTERN(a_padding,         "padding");
    INTERN(a_justify_content, "justify_content");
    INTERN(a_align_items,     "align_items");
    INTERN(a_state,           "state");
    INTERN(a_offset,          "offset");
    INTERN(a_follow,          "follow");
    INTERN(a_max_offset,      "max_offset");
    INTERN(a_rows,            "rows");
    INTERN(a_cells,           "cells");
    INTERN(a_buffer,          "buffer");
    INTERN(a_active,          "active");
    INTERN(a_placeholder,     "placeholder");
    INTERN(a_value,           "value");
    INTERN(a_total,           "total");
    INTERN(a_wrap,            "wrap");
    INTERN(a_render_fn,       "render_fn");
    INTERN(a_cursor,          "cursor");
    INTERN(a_items,           "items");
    INTERN(a_scroll,          "scroll");
    INTERN(a_key,             "key");
    INTERN(a_cache,           "cache");
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

    render_types_ready = 1;
    return 0;
}

/* ── RenderCtx ────────────────────────────────────────────────────── */

#define MAX_RENDER_DEPTH 200

struct RenderCtx {
    BufferObject *buf;
    PyObject     *mcache;   /* dict[node, int] for measure */
    int           depth;
};

/* ── Helpers ──────────────────────────────────────────────────────── */

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
    Cell cell = {' ', style};
    for (int r = y; r < y1; r++) {
        Cell *row = buf->cells + r * buf->width;
        for (int c = x; c < x1; c++)
            row[c] = cell;
    }
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

/* Quick int attr read.  Returns dflt if attribute is missing. */
static int rc_int_attr(PyObject *obj, PyObject *name, int dflt) {
    PyObject *v = PyObject_GetAttr(obj, name);
    if (!v) {
        if (PyErr_ExceptionMatches(PyExc_AttributeError)) PyErr_Clear();
        return dflt;
    }
    int r = (int)PyLong_AsLong(v);
    Py_DECREF(v);
    return r;
}

/* Quick bool attr read. */
static int rc_bool_attr(PyObject *obj, PyObject *name, int dflt) {
    PyObject *v = PyObject_GetAttr(obj, name);
    if (!v) {
        if (PyErr_ExceptionMatches(PyExc_AttributeError)) PyErr_Clear();
        return dflt;
    }
    int r = PyObject_IsTrue(v);
    Py_DECREF(v);
    return r;
}

/* Set an integer attribute on a Python object. */
static void rc_set_int(PyObject *obj, PyObject *name, int val) {
    PyObject *v = PyLong_FromLong(val);
    if (v) {
        if (PyObject_SetAttr(obj, name, v) < 0) PyErr_Clear();
        Py_DECREF(v);
    }
}

static void rc_set_bool(PyObject *obj, PyObject *name, int val) {
    PyObject *v = val ? Py_True : Py_False;
    if (PyObject_SetAttr(obj, name, v) < 0) PyErr_Clear();
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
            col += 2;
        } else {
            col++;
        }
        pos++;
    }
}

/* ── Measure ──────────────────────────────────────────────────────── */

static int c_measure_node(RenderCtx *ctx, PyObject *node) {
    /* Cache lookup. */
    PyObject *cached = PyDict_GetItem(ctx->mcache, node);  /* borrowed */
    if (cached) return (int)PyLong_AsLong(cached);

    int result = 0;
    PyTypeObject *tp = Py_TYPE(node);

    /* Check explicit non-percentage width first. */
    PyObject *node_w = PyObject_GetAttr(node, a_width);
    if (!node_w) return -1;
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
                Py_DECREF(node_w);
                goto cache;
            }
        }
    }
    Py_DECREF(node_w);

    if (tp == TextType_) {
        PyObject *tr = PyObject_GetAttr(node, a_text_render);
        if (!tr) return -1;
        CTextRenderObject *ct = (CTextRenderObject *)tr;
        int pw = rc_int_attr(node, a_padding_w, 0);
        result = ct->visible_w + pw;
        Py_DECREF(tr);
    }
    else if (tp == SpacerType_) {
        result = rc_int_attr(node, a_min_length, 0);
    }
    else if (tp == HStackType_) {
        /* sum of children + spacing */
        PyObject *children = PyObject_GetAttr(node, a_children);
        if (!children) return -1;
        int sp = rc_int_attr(node, a_spacing, 0);
        Py_ssize_t n = PyTuple_GET_SIZE(children);
        int count = 0;
        for (Py_ssize_t i = 0; i < n; i++) {
            PyObject *c = PyTuple_GET_ITEM(children, i);
            int cw = c_measure_node(ctx, c);
            if (cw < 0) { Py_DECREF(children); return -1; }
            PyObject *cg = PyObject_GetAttr(c, a_grow);
            int g = cg ? (int)PyLong_AsLong(cg) : 0;
            Py_XDECREF(cg);
            PyObject *cwid = PyObject_GetAttr(c, a_width);
            int has_w = (cwid && cwid != Py_None);
            Py_XDECREF(cwid);
            if (cw > 0 || g || has_w) { result += cw; count++; }
        }
        if (count > 1) result += sp * (count - 1);
        Py_DECREF(children);
    }
    else if (tp == BoxType_) {
        PyObject *children = PyObject_GetAttr(node, a_children);
        if (!children) return -1;
        int pad = rc_int_attr(node, a_padding, 0);
        if (PyTuple_GET_SIZE(children) > 0) {
            int cw = c_measure_node(ctx, PyTuple_GET_ITEM(children, 0));
            if (cw < 0) { Py_DECREF(children); return -1; }
            int content_w = cw + pad * 2;
            int title_w = 0;
            PyObject *title = PyObject_GetAttr(node, a_title);
            if (title && PyUnicode_Check(title) &&
                PyUnicode_GET_LENGTH(title) > 0)
                title_w = str_display_width(title) + 2;
            Py_XDECREF(title);
            result = (content_w > title_w ? content_w : title_w) + 2;
        }
        Py_DECREF(children);
    }
    else if (tp == TableType_) {
        PyObject *rows = PyObject_GetAttr(node, a_rows);
        if (!rows) return -1;
        if (PyList_Check(rows) && PyList_GET_SIZE(rows) > 0) {
            int spacing = rc_int_attr(node, a_spacing, 0);
            int num_cols = 0;
            Py_ssize_t nr = PyList_GET_SIZE(rows);
            /* Find max column count. */
            for (Py_ssize_t r = 0; r < nr; r++) {
                PyObject *cells = PyObject_GetAttr(
                    PyList_GET_ITEM(rows, r), a_cells);
                if (cells) {
                    int nc = (int)PyList_GET_SIZE(cells);
                    if (nc > num_cols) num_cols = nc;
                    Py_DECREF(cells);
                }
            }
            /* Max width per column. */
            int cw[256];
            for (int i = 0; i < 256; i++) cw[i] = 0;
            for (Py_ssize_t r = 0; r < nr; r++) {
                PyObject *cells = PyObject_GetAttr(
                    PyList_GET_ITEM(rows, r), a_cells);
                if (!cells) continue;
                Py_ssize_t nc = PyList_GET_SIZE(cells);
                for (Py_ssize_t ci = 0; ci < nc && ci < 256; ci++) {
                    int m = c_measure_node(ctx,
                                           PyList_GET_ITEM(cells, ci));
                    if (m < 0) { Py_DECREF(cells); Py_DECREF(rows); return -1; }
                    if (m > cw[ci]) cw[ci] = m;
                }
                Py_DECREF(cells);
            }
            for (int ci = 0; ci < num_cols && ci < 256; ci++)
                result += cw[ci];
            if (num_cols > 1)
                result += spacing * (num_cols - 1);
        }
        Py_DECREF(rows);
    }
    else if (tp == InputType_) {
        PyObject *buf = PyObject_GetAttr(node, a_buffer);
        if (buf) {
            PyObject *val = PyObject_GetAttr(buf, a_value);
            if (val && PyUnicode_Check(val) && PyUnicode_GET_LENGTH(val) > 0) {
                result = str_display_width(val);
                if (rc_bool_attr(node, a_active, 0)) result++;
            } else {
                PyObject *ph = PyObject_GetAttr(node, a_placeholder);
                result = (ph && PyUnicode_Check(ph))
                         ? (int)PyUnicode_GET_LENGTH(ph) : 0;
                Py_XDECREF(ph);
            }
            Py_XDECREF(val);
            Py_DECREF(buf);
        }
    }
    else if (tp == ScrollbarType_) {
        result = 1;
    }
    else if (tp == CondType_) {
        PyObject *children = PyObject_GetAttr(node, a_children);
        if (!children) return -1;
        if (PyTuple_GET_SIZE(children) > 0)
            result = c_measure_node(ctx, PyTuple_GET_ITEM(children, 0));
        Py_DECREF(children);
    }
    else {
        /* VStack, ZStack, Scroll, Foreach, others: max of children. */
        PyObject *children = PyObject_GetAttr(node, a_children);
        if (!children) return -1;
        Py_ssize_t n = PyTuple_GET_SIZE(children);
        for (Py_ssize_t i = 0; i < n; i++) {
            int cw = c_measure_node(ctx,
                                    PyTuple_GET_ITEM(children, i));
            if (cw < 0) { Py_DECREF(children); return -1; }
            if (cw > result) result = cw;
        }
        Py_DECREF(children);
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

/* ── Type-specific renderers ──────────────────────────────────────── */

/* ── Text ─────────────────────────────────────────────────────────── */

static int render_text(RenderCtx *ctx, PyObject *node,
                       int x, int y, int w, int h, Style bg) {
    PyObject *tr_obj = PyObject_GetAttr(node, a_text_render);
    if (!tr_obj) return -1;
    CTextRenderObject *tr = (CTextRenderObject *)tr_obj;

    int pl = tr->pl, pr = tr->pr;
    int inner_x = x + pl;
    int inner_w = w - pl - pr;
    if (inner_w < 0) inner_w = 0;

    int rows = 0;

    if (tr->mode == TEXT_PLAIN) {
        /* Lines returned as-is — most common path. */
        Py_ssize_t n = PyList_GET_SIZE(tr->lines);
        for (Py_ssize_t i = 0; i < n && (h < 0 || rows < h); i++) {
            parse_line_into(ctx->buf, x, y + rows, w,
                            PyList_GET_ITEM(tr->lines, i), bg);
            rows++;
        }
    }
    else if (tr->mode == TEXT_PADDED) {
        /* Lines with left/right padding (no wrap/truncation).
         * Use the text's natural width, not the full available width. */
        int content_w = tr->visible_w;
        Py_ssize_t n = PyList_GET_SIZE(tr->lines);
        for (Py_ssize_t i = 0; i < n && (h < 0 || rows < h); i++) {
            int row_y = y + rows;
            /* Fill left padding with spaces. */
            for (int c = x; c < inner_x && c < x + w; c++)
                rc_set_cell(ctx->buf, c, row_y, ' ', bg);
            parse_line_into(ctx->buf, inner_x, row_y, content_w,
                            PyList_GET_ITEM(tr->lines, i), bg);
            /* Fill right padding with spaces. */
            int rp_start = inner_x + content_w;
            for (int c = rp_start; c < rp_start + pr && c < x + w; c++)
                rc_set_cell(ctx->buf, c, row_y, ' ', bg);
            rows++;
        }
    }
    else {
        /* TEXT_FULL — call CTextRender to get processed lines
         * (handles wrap + truncation), then parse into cells. */
        PyObject *result;
        if (h >= 0)
            result = PyObject_CallFunction(tr_obj, "ii", w, h);
        else
            result = PyObject_CallFunction(tr_obj, "iO", w, Py_None);
        if (!result) { Py_DECREF(tr_obj); return -1; }

        Py_ssize_t n = PyList_GET_SIZE(result);
        for (Py_ssize_t i = 0; i < n && (h < 0 || rows < h); i++) {
            parse_line_into(ctx->buf, x, y + rows, w,
                            PyList_GET_ITEM(result, i), bg);
            rows++;
        }
        Py_DECREF(result);
    }

    Py_DECREF(tr_obj);
    return rows;
}

/* ── VStack ───────────────────────────────────────────────────────── */

static int render_vstack(RenderCtx *ctx, PyObject *node,
                         int x, int y, int w, int h, Style bg) {
    PyObject *children = PyObject_GetAttr(node, a_children);
    if (!children) return -1;
    Py_ssize_t n = PyTuple_GET_SIZE(children);
    if (n == 0) { Py_DECREF(children); return 0; }

    int spacing = rc_int_attr(node, a_spacing, 0);

    int has_flex = (h >= 0) ? rc_bool_attr(node, a_has_flex, 0) : 0;

    if (!has_flex) {
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
            PyObject *child = PyTuple_GET_ITEM(children, i);
            int cr = c_render_node(ctx, child, x, y + rows, w,
                                   -1, bg);
            if (cr < 0) { Py_DECREF(children); return -1; }
            rows += cr;
        }
        Py_DECREF(children);
        return rows;
    }

    /* ── Flex layout: two passes. ────────────────────────────────── */
    /* Pass 1: measure non-grow children, collect grow items. */
    int *child_h = (int *)calloc((size_t)n, sizeof(int));
    if (!child_h) { Py_DECREF(children); return (PyErr_NoMemory(), -1); }

    int used = spacing * (int)(n > 1 ? n - 1 : 0);
    int grow_idx[256], grow_wt[256];
    int ng = 0;

    for (Py_ssize_t i = 0; i < n; i++) {
        PyObject *child = PyTuple_GET_ITEM(children, i);
        int g = rc_int_attr(child, a_grow, 0);
        PyObject *ch_obj = PyObject_GetAttr(child, a_height);
        int has_h = (ch_obj && ch_obj != Py_None);
        Py_XDECREF(ch_obj);

        if (g && !has_h) {
            /* Grow child — height assigned in pass 2. */
            child_h[i] = -1;
            if (ng >= 256) {
                PyErr_SetString(PyExc_OverflowError,
                                "VStack: too many grow children (max 256)");
                free(child_h); Py_DECREF(children); return -1;
            }
            grow_idx[ng] = (int)i; grow_wt[ng] = g; ng++;
        } else {
            /* Fixed child — dry-run off-screen to measure height. */
            int offscreen = ctx->buf->height;
            int ch = has_h ? h : -1;
            int cr = c_render_node(ctx, child, x, offscreen, w, ch, bg);
            if (cr < 0) { free(child_h); Py_DECREF(children); return -1; }
            child_h[i] = cr;
            used += cr;
        }
    }

    /* Distribute remaining space among grow items. */
    int remaining = h - used;
    if (remaining < 0) remaining = 0;
    if (ng > 0) {
        long tw = 0;
        for (int j = 0; j < ng; j++) tw += grow_wt[j];
        long cum = 0, cs = 0;
        for (int j = 0; j < ng; j++) {
            cum += grow_wt[j];
            long tgt = (long)remaining * cum / tw;
            child_h[grow_idx[j]] = (int)(tgt - cs);
            cs = tgt;
        }
    }

    /* Pass 2: render all children at computed y positions. */
    int row = 0;
    for (Py_ssize_t i = 0; i < n; i++) {
        if (i > 0 && spacing) row += spacing;
        PyObject *child = PyTuple_GET_ITEM(children, i);
        int g = rc_int_attr(child, a_grow, 0);
        PyObject *ch_obj = PyObject_GetAttr(child, a_height);
        int has_h = (ch_obj && ch_obj != Py_None);
        Py_XDECREF(ch_obj);

        if (g && !has_h) {
            /* Grow child — render with assigned height. */
            int cr = c_render_node(ctx, child, x, y + row, w,
                                   child_h[i], bg);
            if (cr < 0) { free(child_h); Py_DECREF(children); return -1; }
            row += child_h[i];  /* use allocated height for layout */
        } else {
            /* Fixed child — re-render at correct position. */
            int cr = c_render_node(ctx, child, x, y + row, w,
                                   has_h ? h : -1, bg);
            if (cr < 0) { free(child_h); Py_DECREF(children); return -1; }
            row += child_h[i] >= 0 ? child_h[i] : cr;
        }
    }

    free(child_h);
    Py_DECREF(children);
    return row;
}

/* ── Foreach ──────────────────────────────────────────────────────── */

static int render_foreach(RenderCtx *ctx, PyObject *node,
                          int x, int y, int w, int h, Style bg) {
    PyObject *children = PyObject_GetAttr(node, a_children);
    if (!children) return -1;
    Py_ssize_t n = PyTuple_GET_SIZE(children);

    int rows = 0;
    for (Py_ssize_t i = 0; i < n; i++) {
        if (h >= 0 && rows >= h) break;
        int remaining = (h >= 0) ? h - rows : -1;
        int cr = c_render_node(ctx, PyTuple_GET_ITEM(children, i),
                               x, y + rows, w, remaining, bg);
        if (cr < 0) { Py_DECREF(children); return -1; }
        rows += cr;
    }

    Py_DECREF(children);
    return rows;
}

/* ── Cond ─────────────────────────────────────────────────────────── */

static int render_cond(RenderCtx *ctx, PyObject *node,
                       int x, int y, int w, int h, Style bg) {
    PyObject *children = PyObject_GetAttr(node, a_children);
    if (!children) return -1;
    if (PyTuple_GET_SIZE(children) == 0) {
        Py_DECREF(children);
        return 0;
    }
    PyObject *child = PyTuple_GET_ITEM(children, 0);
    Py_DECREF(children);
    return c_render_node(ctx, child, x, y, w, h, bg);
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
        PyObject *cwid = PyObject_GetAttr(c, a_width);
        int has_w = (cwid && cwid != Py_None);
        if (has_w) {
            col_widths[i] = rc_resolve_size(cwid, w);
        } else {
            col_widths[i] = c_measure_node(ctx, c);
            if (col_widths[i] < 0) { Py_XDECREF(cwid); return -1; }
        }
        Py_XDECREF(cwid);
        int g = rc_int_attr(c, a_grow, 0);
        if (!has_w && g) {
            if (ng >= 256) {
                PyErr_SetString(PyExc_OverflowError,
                                "HStack: too many grow children (max 256)");
                return -1;
            }
            grow_idx[ng] = i;
            grow_wt[ng] = g;
            ng++;
            /* Grow columns start at 0 — their space comes entirely from
               the flex distribution, matching vstack flex behavior. */
            col_widths[i] = 0;
        }
        used += col_widths[i];
    }

    int remaining = w - used;
    if (remaining < 0) remaining = 0;
    if (ng > 0 && remaining > 0) {
        long total_wt = 0;
        for (int j = 0; j < ng; j++) total_wt += grow_wt[j];
        long cum_w = 0, cum_s = 0;
        for (int j = 0; j < ng; j++) {
            cum_w += grow_wt[j];
            long target = (long)remaining * cum_w / total_wt;
            col_widths[grow_idx[j]] += (int)(target - cum_s);
            cum_s = target;
        }
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
        PyObject *c = PyTuple_GET_ITEM(children, i);
        int cw = c_measure_node(ctx, c);
        if (cw < 0) return -1;
        if (cw == 0) continue;

        int needed = col > 0 ? col + spacing + cw : cw;
        if (needed > w && col > 0) {
            row_off++;
            col = 0;
        }
        if (h >= 0 && row_off >= h) break;
        int cx = col > 0 ? col + spacing : 0;
        c_render_node(ctx, c, x + cx, y + row_off, cw, 1, bg);
        col = cx + cw;
    }
    return row_off + 1;
}

static int render_hstack(RenderCtx *ctx, PyObject *node,
                         int x, int y, int w, int h, Style bg) {
    PyObject *children = PyObject_GetAttr(node, a_children);
    if (!children) return -1;
    Py_ssize_t nc = PyTuple_GET_SIZE(children);

    int spacing = rc_int_attr(node, a_spacing, 0);

    /* Wrap mode. */
    if (rc_bool_attr(node, a_wrap, 0)) {
        int r = render_hstack_wrap(ctx, children, nc, spacing,
                                   x, y, w, h, bg);
        Py_DECREF(children);
        return r;
    }

    /* Read justify / align. */
    PyObject *jc = PyObject_GetAttr(node, a_justify_content);
    PyObject *ai = PyObject_GetAttr(node, a_align_items);
    if (!jc || !ai) {
        Py_XDECREF(jc); Py_XDECREF(ai); Py_DECREF(children);
        return -1;
    }

    /* Collect active children (measure > 0 or grow or width). */
    PyObject *act_arr[512];
    int n = 0;
    for (Py_ssize_t i = 0; i < nc; i++) {
        PyObject *c = PyTuple_GET_ITEM(children, i);
        int m = c_measure_node(ctx, c);
        if (m < 0) {
            Py_DECREF(jc); Py_DECREF(ai); Py_DECREF(children);
            return -1;
        }
        int g = rc_int_attr(c, a_grow, 0);
        PyObject *cwid = PyObject_GetAttr(c, a_width);
        int has_w = (cwid && cwid != Py_None);
        Py_XDECREF(cwid);
        if (m > 0 || g || has_w) {
            if (n >= 512) {
                PyErr_SetString(PyExc_OverflowError,
                                "HStack: too many active children (max 512)");
                Py_DECREF(jc); Py_DECREF(ai); Py_DECREF(children);
                return -1;
            }
            act_arr[n++] = c;
        }
    }

    if (n == 0) {
        Py_DECREF(jc); Py_DECREF(ai); Py_DECREF(children);
        return (h >= 0) ? h : 1;
    }

    /* Flex distribution. */
    int col_widths[512];
    int remaining = flex_dist(ctx, act_arr, n, col_widths, w, spacing);
    if (remaining < 0) {
        Py_DECREF(jc); Py_DECREF(ai); Py_DECREF(children);
        return -1;
    }

    /* Compute x offsets based on justify_content. */
    int offsets[512];
    int cx = 0;
    if (jc == s_end) {
        cx = remaining;
    } else if (jc == s_center) {
        cx = remaining / 2;
    }
    /* "between" distributes remaining among gaps. */
    int gap_extras[512];
    if (jc == s_between && n > 1 && remaining > 0) {
        long tw = (long)(n - 1);
        long cw = 0, cs = 0;
        for (int i = 0; i < n - 1; i++) {
            cw += 1;
            long tgt = remaining * cw / tw;
            gap_extras[i] = (int)(tgt - cs);
            cs = tgt;
        }
    } else {
        for (int i = 0; i < n; i++) gap_extras[i] = 0;
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
            int g = rc_int_attr(act_arr[i], a_grow, 0);
            int ch = g ? h : -1;
            int cr = c_render_node(ctx, act_arr[i],
                                   x + offsets[i], offscreen,
                                   col_widths[i], ch, bg);
            if (cr < 0) {
                Py_DECREF(jc); Py_DECREF(ai); Py_DECREF(children);
                return -1;
            }
            col_heights[i] = cr;
            if (cr > max_rows) max_rows = cr;
        }

        /* Compute y offsets based on align_items. */
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

    /* Render each child into its column.
     * Pre-fill grow columns with 1 row of spaces (for single-row padding). */
    for (int i = 0; i < n; i++) {
        int g = rc_int_attr(act_arr[i], a_grow, 0);
        if (g)
            rc_fill_region(ctx->buf, x + offsets[i], y + y_offsets[i],
                           col_widths[i], 1, bg);
        int ch = g ? h : -1;
        int cr = c_render_node(ctx, act_arr[i],
                               x + offsets[i], y + y_offsets[i],
                               col_widths[i], ch, bg);
        if (cr < 0) {
            Py_DECREF(jc); Py_DECREF(ai); Py_DECREF(children);
            return -1;
        }
        if (ai == s_start && cr > max_rows) max_rows = cr;
    }

    /* Fill unwritten cells in each column area so background is visible
     * in multi-row hstacks where shorter columns leave gaps. */
    if (max_rows > 1) {
        for (int i = 0; i < n; i++)
            rc_fill_unwritten(ctx->buf, x + offsets[i], y + y_offsets[i],
                              col_widths[i], max_rows, bg);
    }

    Py_DECREF(jc);
    Py_DECREF(ai);
    Py_DECREF(children);
    return max_rows;
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
    PyObject *children = PyObject_GetAttr(node, a_children);
    if (!children) return -1;
    if (PyTuple_GET_SIZE(children) == 0) {
        Py_DECREF(children);
        return 0;
    }
    PyObject *child = PyTuple_GET_ITEM(children, 0);

    PyObject *style_obj = PyObject_GetAttr(node, a_style);
    PyObject *title_obj = PyObject_GetAttr(node, a_title);
    int pad = rc_int_attr(node, a_padding, 0);
    if (!style_obj || !title_obj) {
        Py_XDECREF(style_obj); Py_XDECREF(title_obj);
        Py_DECREF(children);
        return -1;
    }

    const Py_UCS4 *bdr = lookup_border(style_obj);
    Py_UCS4 tl = bdr[0], tr = bdr[1], bl = bdr[2], br = bdr[3];
    Py_UCS4 hz = bdr[4], vt = bdr[5];

    /* Compute inner width. */
    int child_w = c_measure_node(ctx, child);
    if (child_w < 0) goto box_err;
    int child_grow = rc_int_attr(child, a_grow, 0);
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
            /* Truncate title to fit. */
            PyObject *t_args = Py_BuildValue("(Oi)", title_obj, inner - 2);
            PyObject *t_kw = Py_BuildValue("{s:O}", "ellipsis", Py_True);
            PyObject *trunc = (t_args && t_kw)
                              ? mod_truncate(NULL, t_args, t_kw) : NULL;
            Py_XDECREF(t_args);
            Py_XDECREF(t_kw);
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
    int offscreen = ctx->buf->height;
    int cr = c_render_node(ctx, child, x + 1 + pad, offscreen, cw, child_h, bg);
    if (cr < 0) goto box_err;
    int content_rows = cr > 0 ? cr : 1;

    /* Fill entire interior (box must be opaque over ZStack layers). */
    rc_fill_region(buf, x + 1, y + 1, inner, content_rows, bg);

    /* Render child on top of fill — single content render. */
    c_render_node(ctx, child, x + 1 + pad, y + 1, cw, child_h, bg);

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

    Py_DECREF(style_obj);
    Py_DECREF(title_obj);
    Py_DECREF(children);
    return 2 + content_rows;

box_err:
    Py_XDECREF(style_obj);
    Py_XDECREF(title_obj);
    Py_DECREF(children);
    return -1;
}

/* ── Scroll ───────────────────────────────────────────────────────── */

static int render_scroll(RenderCtx *ctx, PyObject *node,
                         int x, int y, int w, int h, Style bg) {
    if (h <= 0) return 0;

    PyObject *state = PyObject_GetAttr(node, a_state);
    PyObject *children = PyObject_GetAttr(node, a_children);
    if (!state || !children) {
        Py_XDECREF(state); Py_XDECREF(children);
        return -1;
    }

    Py_ssize_t total = PyTuple_GET_SIZE(children);

    /* Update state. */
    rc_set_int(state, a_height, h);
    rc_set_int(state, a_total, (int)total);

    int follow = rc_bool_attr(state, a_follow, 0);
    int max_off = rc_int_attr(state, a_max_offset, 0);

    int offset;
    if (follow) {
        offset = max_off;
    } else {
        offset = rc_int_attr(state, a_offset, 0);
    }
    if (offset < 0) offset = 0;
    if (offset > max_off) offset = max_off;
    rc_set_int(state, a_offset, offset);

    if ((int)total > h && offset >= max_off)
        rc_set_bool(state, a_follow, 1);

    /* Render visible children (like _fill_rows). */
    int rows = 0;
    for (Py_ssize_t i = (Py_ssize_t)offset; i < total && rows < h; i++) {
        int remaining = h - rows;
        int cr = c_render_node(ctx, PyTuple_GET_ITEM(children, i),
                               x, y + rows, w, remaining, bg);
        if (cr < 0) { Py_DECREF(state); Py_DECREF(children); return -1; }
        if (cr > remaining) cr = remaining;
        rows += cr;
    }

    Py_DECREF(state);
    Py_DECREF(children);
    return h;  /* Scroll always fills its height. */
}

/* ── Table ────────────────────────────────────────────────────────── */

static int render_table(RenderCtx *ctx, PyObject *node,
                        int x, int y, int w, int h, Style bg) {
    PyObject *rows = PyObject_GetAttr(node, a_rows);
    if (!rows) return -1;
    if (!PyList_Check(rows) || PyList_GET_SIZE(rows) == 0) {
        Py_DECREF(rows);
        return 1;  /* empty table: one blank row */
    }

    int spacing = rc_int_attr(node, a_spacing, 0);
    Py_ssize_t nr = PyList_GET_SIZE(rows);

    /* Measure columns. */
    int num_cols = 0;
    for (Py_ssize_t r = 0; r < nr; r++) {
        PyObject *cells = PyObject_GetAttr(
            PyList_GET_ITEM(rows, r), a_cells);
        if (cells) {
            int nc = (int)PyList_GET_SIZE(cells);
            if (nc > num_cols) num_cols = nc;
            Py_DECREF(cells);
        }
    }
    if (num_cols == 0) {
        Py_DECREF(rows);
        return 0;
    }
    if (num_cols > 256) {
        PyErr_SetString(PyExc_OverflowError,
                        "Table: too many columns (max 256)");
        Py_DECREF(rows);
        return -1;
    }

    int col_w[256] = {0};
    int grow_w[256] = {0};
    int has_grow = 0;
    for (Py_ssize_t r = 0; r < nr; r++) {
        PyObject *cells = PyObject_GetAttr(
            PyList_GET_ITEM(rows, r), a_cells);
        if (!cells) continue;
        Py_ssize_t nc = PyList_GET_SIZE(cells);
        for (Py_ssize_t ci = 0; ci < nc && ci < 256; ci++) {
            PyObject *cell = PyList_GET_ITEM(cells, ci);
            int m = c_measure_node(ctx, cell);
            if (m < 0) { Py_DECREF(cells); Py_DECREF(rows); return -1; }
            if (m > col_w[ci]) col_w[ci] = m;
            int g = rc_int_attr(cell, a_grow, 0);
            if (g) { if (g > grow_w[ci]) grow_w[ci] = g; has_grow = 1; }
        }
        Py_DECREF(cells);
    }

    /* Resolve grow columns. */
    int resolved[256];
    for (int ci = 0; ci < num_cols; ci++) resolved[ci] = col_w[ci];
    if (has_grow) {
        int gap_total = spacing * (num_cols > 1 ? num_cols - 1 : 0);
        int fixed = gap_total;
        long total_gw = 0;
        for (int ci = 0; ci < num_cols; ci++) {
            if (grow_w[ci]) { total_gw += grow_w[ci]; }
            else { fixed += resolved[ci]; }
        }
        int remaining = w - fixed;
        if (remaining < 0) remaining = 0;
        if (total_gw > 0) {
            long cum = 0, cs = 0;
            for (int ci = 0; ci < num_cols; ci++) {
                if (!grow_w[ci]) continue;
                cum += grow_w[ci];
                long tgt = (long)remaining * cum / total_gw;
                resolved[ci] = (int)(tgt - cs);
                cs = tgt;
            }
        }
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
        PyObject *cells = PyObject_GetAttr(
            PyList_GET_ITEM(rows, r), a_cells);
        if (!cells) continue;
        Py_ssize_t nc = PyList_GET_SIZE(cells);
        for (Py_ssize_t ci = 0; ci < nc && ci < num_cols; ci++) {
            c_render_node(ctx, PyList_GET_ITEM(cells, ci),
                          x + col_x[ci], y + (int)r,
                          resolved[ci], 1, bg);
        }
        Py_DECREF(cells);
    }

    Py_DECREF(rows);
    return (int)visible;
}

/* ── ZStack ───────────────────────────────────────────────────────── */

static int render_zstack(RenderCtx *ctx, PyObject *node,
                         int x, int y, int w, int h, Style bg) {
    PyObject *children = PyObject_GetAttr(node, a_children);
    if (!children) return -1;
    Py_ssize_t n = PyTuple_GET_SIZE(children);
    if (n == 0) {
        Py_DECREF(children);
        return (h >= 0) ? h : 1;
    }

    PyObject *jc = PyObject_GetAttr(node, a_justify_content);
    PyObject *ai = PyObject_GetAttr(node, a_align_items);
    if (!jc || !ai) {
        Py_XDECREF(jc); Py_XDECREF(ai); Py_DECREF(children);
        return -1;
    }

    int is_start = (jc == s_start && ai == s_start);

    /* First layer establishes canvas height when h is unconstrained. */
    int canvas_h = h;
    Py_ssize_t first_done = 0;  /* 1 if first child already rendered in-place */
    if (canvas_h < 0) {
        PyObject *first = PyTuple_GET_ITEM(children, 0);
        if (is_start) {
            /* Render first child in-place — no offscreen duplicate. */
            canvas_h = c_render_node(ctx, first, x, y, w, -1, bg);
            if (canvas_h < 0) goto zstack_err;
            first_done = 1;
        } else {
            /* Alignment needs canvas_h before positioning; measure offscreen. */
            int offscreen = ctx->buf->height;
            canvas_h = c_render_node(ctx, first, x, offscreen, w, -1, bg);
            if (canvas_h < 0) goto zstack_err;
        }
    }

    /* Render layers, then fill unwritten cells with bg. */
    for (Py_ssize_t i = first_done; i < n; i++) {
        PyObject *child = PyTuple_GET_ITEM(children, i);

        if (is_start) {
            int cr = c_render_node(ctx, child, x, y, w, canvas_h, bg);
            if (cr < 0) goto zstack_err;
            continue;
        }

        /* Alignment: compute layer dimensions and offset. */
        int g = rc_int_attr(child, a_grow, 0);
        int layer_w, layer_h;

        if (g && canvas_h >= 0) {
            /* Grow child fills the canvas — offset is (0,0). */
            c_render_node(ctx, child, x, y, w, canvas_h, bg);
            continue;
        }

        /* Measure width and height. */
        PyObject *cwid = PyObject_GetAttr(child, a_width);
        int has_w = (cwid && cwid != Py_None);
        Py_XDECREF(cwid);

        /* Off-screen dry-run to measure height (and rendered width). */
        int offscreen = ctx->buf->height;
        layer_h = c_render_node(ctx, child, x, offscreen, w,
                                canvas_h, bg);
        if (layer_h < 0) goto zstack_err;

        if (has_w) {
            layer_w = c_measure_node(ctx, child);
            if (layer_w < 0) goto zstack_err;
        } else {
            /* Containers that fill their width (ZStack) use the full
             * available width.  Others use their intrinsic measure. */
            PyTypeObject *ctp = Py_TYPE(child);
            if (ctp == ZStackType_)
                layer_w = w;
            else {
                layer_w = c_measure_node(ctx, child);
                if (layer_w < 0) goto zstack_err;
            }
        }

        /* Compute alignment offsets. */
        int row_off = 0, col_off = 0;
        if (ai == s_end)
            row_off = canvas_h - layer_h;
        else if (ai == s_center)
            row_off = (canvas_h - layer_h) / 2;
        if (jc == s_end)
            col_off = w - layer_w;
        else if (jc == s_center)
            col_off = (w - layer_w) / 2;
        if (row_off < 0) row_off = 0;
        if (col_off < 0) col_off = 0;

        c_render_node(ctx, child, x + col_off, y + row_off,
                      w, canvas_h, bg);
    }

    /* Fill unwritten cells with background (replaces pre-fill). */
    rc_fill_unwritten(ctx->buf, x, y, w, canvas_h, bg);

    Py_DECREF(jc);
    Py_DECREF(ai);
    Py_DECREF(children);
    return canvas_h;

zstack_err:
    Py_DECREF(jc);
    Py_DECREF(ai);
    Py_DECREF(children);
    return -1;
}

/* ── Input ────────────────────────────────────────────────────────── */

static int render_input(RenderCtx *ctx, PyObject *node,
                        int x, int y, int w, int h, Style bg) {
    PyObject *buf_obj = PyObject_GetAttr(node, a_buffer);
    if (!buf_obj) return -1;

    int active = rc_bool_attr(node, a_active, 0);

    /* Check if value is empty. */
    PyObject *val = PyObject_GetAttr(buf_obj, a_value);
    int empty = (!val || !PyUnicode_Check(val) ||
                 PyUnicode_GET_LENGTH(val) == 0);
    Py_XDECREF(val);

    if (empty && !active) {
        PyObject *ph = PyObject_GetAttr(node, a_placeholder);
        if (ph && PyUnicode_Check(ph) && PyUnicode_GET_LENGTH(ph) > 0) {
            /* Render placeholder with dim style. */
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
            Py_DECREF(ph);
        } else {
            Py_XDECREF(ph);
        }
        Py_DECREF(buf_obj);
        return 1;
    }

    /* Get display text via Python helper. */
    PyObject *txt_obj = PyObject_CallFunctionObjArgs(
        py_display_text, buf_obj, NULL);
    if (!txt_obj) { Py_DECREF(buf_obj); return -1; }

    Py_ssize_t txt_len = PyUnicode_GET_LENGTH(txt_obj);
    int kind = PyUnicode_KIND(txt_obj);
    const void *data = PyUnicode_DATA(txt_obj);

    int cursor = -1;
    if (active) {
        PyObject *cur_obj = PyObject_CallFunctionObjArgs(
            py_display_cursor, buf_obj, NULL);
        if (!cur_obj) {
            Py_DECREF(txt_obj); Py_DECREF(buf_obj);
            return -1;
        }
        cursor = (int)PyLong_AsLong(cur_obj);
        Py_DECREF(cur_obj);
    }

    /* Render text with character-based wrapping at width boundaries. */
    Py_ssize_t raw_len = active && cursor >= txt_len
                         ? txt_len + 1 : txt_len;
    if (raw_len == 0) {
        Py_DECREF(txt_obj);
        Py_DECREF(buf_obj);
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
    Py_DECREF(buf_obj);
    return rows > 0 ? rows : 1;
}

/* ── Scrollbar ───────────────────────────────────────────────────── */

static int render_scrollbar(RenderCtx *ctx, PyObject *node,
                            int x, int y, int w, int h, Style bg) {
    PyObject *state = PyObject_GetAttr(node, a_state);
    if (!state) return -1;

    int sh = rc_int_attr(state, a_height, 0);
    int total = rc_int_attr(state, a_total, 0);
    int offset = rc_int_attr(state, a_offset, 0);
    Py_DECREF(state);

    if (sh <= 0 || total <= sh)
        return sh > 0 ? sh : 0;

    /* Call node.render_fn(sh, total, offset) → list[str]. */
    PyObject *fn = PyObject_GetAttr(node, a_render_fn);
    if (!fn) return -1;
    PyObject *result = PyObject_CallFunction(fn, "iii", sh, total, offset);
    Py_DECREF(fn);
    if (!result) return -1;

    if (!PyList_Check(result)) {
        Py_DECREF(result);
        return sh;
    }
    Py_ssize_t nlines = PyList_GET_SIZE(result);
    int rows = 0;
    for (Py_ssize_t i = 0; i < nlines; i++) {
        if (h >= 0 && rows >= h) break;
        parse_line_into(ctx->buf, x, y + rows, w,
                        PyList_GET_ITEM(result, i), bg);
        rows++;
    }
    Py_DECREF(result);
    return rows;
}

/* ── ListView ────────────────────────────────────────────────────── */

static int render_listview(RenderCtx *ctx, PyObject *node,
                           int x, int y, int w, int h, Style bg) {
    if (h <= 0) return 0;

    PyObject *state = PyObject_GetAttr(node, a_state);
    if (!state) return -1;

    /* state.cursor = state.clamp(state.cursor) */
    int cur = rc_int_attr(state, a_cursor, 0);
    PyObject *clamped = PyObject_CallMethod(state, "clamp", "i", cur);
    if (clamped) {
        PyObject_SetAttr(state, a_cursor, clamped);
        cur = (int)PyLong_AsLong(clamped);
        Py_DECREF(clamped);
    } else {
        PyErr_Clear();
    }

    /* state.scroll.scroll_to_visible(state.cursor) */
    PyObject *scroll = PyObject_GetAttr(state, a_scroll);
    if (!scroll) { Py_DECREF(state); return -1; }
    PyObject *stv = PyObject_CallMethod(scroll, "scroll_to_visible",
                                        "i", cur);
    Py_XDECREF(stv);
    if (PyErr_Occurred()) PyErr_Clear();

    /* state.scroll.height = h */
    rc_set_int(scroll, a_height, h);

    /* state.scroll.total = state.total */
    int total = rc_int_attr(state, a_total, 0);
    rc_set_int(scroll, a_total, total);

    /* Clamp offset. */
    int max_off = rc_int_attr(scroll, a_max_offset, 0);
    int offset = rc_int_attr(scroll, a_offset, 0);
    if (offset < 0) offset = 0;
    if (offset > max_off) offset = max_off;
    rc_set_int(scroll, a_offset, offset);

    /* Get items, render_fn, and item cache. */
    PyObject *items = PyObject_GetAttr(state, a_items);
    PyObject *fn = PyObject_GetAttr(node, a_render_fn);
    if (!items || !fn) {
        Py_XDECREF(items); Py_XDECREF(fn);
        Py_DECREF(scroll); Py_DECREF(state);
        return -1;
    }
    PyObject *cache = PyObject_GetAttr(node, a_cache);
    if (!cache || !PyDict_Check(cache)) {
        Py_XDECREF(cache);
        cache = NULL;
    }

    Py_ssize_t nitems = PyList_GET_SIZE(items);
    int rows = 0;
    for (Py_ssize_t i = (Py_ssize_t)offset; i < nitems && rows < h; i++) {
        PyObject *item = PyList_GET_ITEM(items, i);
        int sel = ((int)i == cur) ? 1 : 0;
        PyObject *child = NULL;

        /* Try item cache: cache[item.key] = (id, sel, w, node). */
        PyObject *item_key = NULL;
        if (cache) {
            item_key = PyObject_GetAttr(item, a_key);
            if (item_key) {
                PyObject *entry = PyDict_GetItem(cache, item_key);
                if (entry && PyTuple_Check(entry) &&
                    PyTuple_GET_SIZE(entry) >= 4) {
                    Py_ssize_t cid = PyLong_AsSsize_t(
                        PyTuple_GET_ITEM(entry, 0));
                    int csel = PyTuple_GET_ITEM(entry, 1) == Py_True;
                    int cw = (int)PyLong_AsLong(
                        PyTuple_GET_ITEM(entry, 2));
                    if (!PyErr_Occurred() &&
                        cid == (Py_ssize_t)item &&
                        csel == sel && cw == w) {
                        child = PyTuple_GET_ITEM(entry, 3);
                        Py_INCREF(child);
                    }
                }
            } else {
                PyErr_Clear();
            }
        }

        if (!child) {
            child = PyObject_CallFunction(fn, "OO", item,
                                          sel ? Py_True : Py_False);
            /* Store in cache. */
            if (child && item_key) {
                PyObject *e = Py_BuildValue("(nOiO)",
                    (Py_ssize_t)item,
                    sel ? Py_True : Py_False, w, child);
                if (e) {
                    PyDict_SetItem(cache, item_key, e);
                    Py_DECREF(e);
                }
            }
        }
        Py_XDECREF(item_key);

        if (!child) {
            Py_XDECREF(cache);
            Py_DECREF(items); Py_DECREF(fn);
            Py_DECREF(scroll); Py_DECREF(state);
            return -1;
        }
        int remaining = h - rows;
        int cr = c_render_node(ctx, child, x, y + rows, w,
                               remaining, bg);
        Py_DECREF(child);
        if (cr < 0) {
            Py_XDECREF(cache);
            Py_DECREF(items); Py_DECREF(fn);
            Py_DECREF(scroll); Py_DECREF(state);
            return -1;
        }
        if (cr > remaining) cr = remaining;
        rows += cr;
    }

    Py_XDECREF(cache);
    Py_DECREF(items);
    Py_DECREF(fn);
    Py_DECREF(scroll);
    Py_DECREF(state);
    return h;
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
    Py_ssize_t nlines = PyList_GET_SIZE(result);
    int rows = 0;
    for (Py_ssize_t i = 0; i < nlines; i++) {
        if (h >= 0 && rows >= h) break;
        parse_line_into(ctx->buf, x, y + rows, w,
                        PyList_GET_ITEM(result, i), bg);
        rows++;
    }
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
    if (tp == ListViewType_)   return render_listview(ctx, node, x, y, w, h, bg);
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
    /* Read framing attributes. */
    PyObject *nw  = PyObject_GetAttr(node, a_width);
    PyObject *nh  = PyObject_GetAttr(node, a_height);
    PyObject *nbg = PyObject_GetAttr(node, a_bg);
    if (!nw || !nh || !nbg) {
        Py_XDECREF(nw); Py_XDECREF(nh); Py_XDECREF(nbg);
        return -1;
    }

    int has_frame = (nw != Py_None || nh != Py_None || nbg != Py_None);
    int has_explicit_h = (nh != Py_None);
    int has_explicit_w = (nw != Py_None);
    PyObject *ovf = PyObject_GetAttr(node, a_overflow);
    int clips = (ovf && ovf != s_visible);
    Py_XDECREF(ovf);

    if (has_frame) {
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
            if (h >= 0)
                rc_fill_region(ctx->buf, x, y, w, h, bg);
        }

        /* Fill explicit-width region with spaces so clip area is visible.
         * When h<0, this is deferred until after content render. */
        if (has_explicit_w && clips && h >= 0)
            rc_fill_region(ctx->buf, x, y, w, h, bg);
    }

    Py_DECREF(nw);
    Py_DECREF(nh);
    Py_DECREF(nbg);

    /* Dispatch to type-specific renderer. */
    int rows = dispatch_render(ctx, tp, node, x, y, w, h, bg);

    /* Deferred fill: when bg or explicit width+clip was set but h was
     * unconstrained, fill after content render so we know the height. */
    int need_deferred = (has_frame && rows > 0 && h < 0 &&
        ((!style_is_empty(bg) && bg.bg.kind != COLOR_NONE) ||
         (has_explicit_w && clips)));
    if (need_deferred) {
        rc_fill_unwritten(ctx->buf, x, y, w, rows, bg);
    }

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

    RenderCtx ctx = {buf, mcache, 0};
    int rows = c_render_node(&ctx, node, 0, 0,
                             buf->width, render_h,
                             STYLE_EMPTY);

    Py_DECREF(mcache);

    if (rows < 0) return NULL;
    return PyLong_FromLong(rows);
}
