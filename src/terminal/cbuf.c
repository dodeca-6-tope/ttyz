/*
 * _buffer — C extension for cell-based terminal rendering.
 *
 * Provides Buffer (2D cell grid), ANSI→cell parsing, and cell-level diffing.
 * Each cell is (codepoint, packed_style) for fast comparison.
 */

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <structmember.h>

/* ── Style packing ─────────────────────────────────────────────────── */

#define BG_SHIFT      9
#define FLAGS_SHIFT  18
#define STYLE_EMPTY   0
#define WIDE_CHAR     0   /* ch == 0 marks wide-char continuation */

typedef struct {
    Py_UCS4  ch;
    uint32_t style;
} Cell;

#define BLANK_CELL (Cell){' ', STYLE_EMPTY}

/* ── Growable byte buffer ──────────────────────────────────────────── */

typedef struct {
    char  *data;
    size_t len;
    size_t cap;
    int    oom;     /* set on allocation failure — skips further writes */
} OutBuf;

static int outbuf_init(OutBuf *b, size_t cap) {
    b->data = (char *)malloc(cap);
    b->len  = 0;
    b->cap  = cap;
    b->oom  = (b->data == NULL);
    return b->oom ? -1 : 0;
}

static void outbuf_free(OutBuf *b) {
    free(b->data);
}

static inline void outbuf_grow(OutBuf *b, size_t need) {
    if (b->oom || b->len + need <= b->cap) return;
    size_t newcap = b->cap;
    while (b->len + need > newcap) newcap *= 2;
    char *p = (char *)realloc(b->data, newcap);
    if (!p) { b->oom = 1; return; }
    b->data = p;
    b->cap  = newcap;
}

static inline void outbuf_add(OutBuf *b, const char *s, size_t n) {
    outbuf_grow(b, n);
    if (b->oom) return;
    memcpy(b->data + b->len, s, n);
    b->len += n;
}

static void outbuf_printf(OutBuf *b, const char *fmt, ...) {
    va_list ap;
    char tmp[64];
    va_start(ap, fmt);
    int n = vsnprintf(tmp, sizeof(tmp), fmt, ap);
    va_end(ap);
    if (n > 0) outbuf_add(b, tmp, (size_t)n);
}

/* Helper: convert OutBuf to Python str, or raise MemoryError on OOM. */
static PyObject *outbuf_to_pystr(OutBuf *b) {
    if (b->oom) {
        outbuf_free(b);
        return PyErr_NoMemory();
    }
    PyObject *result = PyUnicode_DecodeUTF8(b->data, (Py_ssize_t)b->len, NULL);
    outbuf_free(b);
    return result;
}

/* ── UTF-8 encoding ────────────────────────────────────────────────── */

static inline int encode_utf8(Py_UCS4 ch, char *out) {
    if (ch < 0x80)    { out[0] = (char)ch; return 1; }
    if (ch < 0x800)   { out[0] = 0xC0 | (ch >> 6);
                        out[1] = 0x80 | (ch & 0x3F); return 2; }
    if (ch < 0x10000) { out[0] = 0xE0 | (ch >> 12);
                        out[1] = 0x80 | ((ch >> 6) & 0x3F);
                        out[2] = 0x80 | (ch & 0x3F); return 3; }
    out[0] = 0xF0 | (ch >> 18);
    out[1] = 0x80 | ((ch >> 12) & 0x3F);
    out[2] = 0x80 | ((ch >> 6) & 0x3F);
    out[3] = 0x80 | (ch & 0x3F);
    return 4;
}

/* ── SGR output ────────────────────────────────────────────────────── */

static void emit_sgr(OutBuf *b, uint32_t style) {
    if (style == STYLE_EMPTY) {
        outbuf_add(b, "\033[0m", 4);
        return;
    }
    uint32_t fg    = style & 0x1FF;
    uint32_t bg    = (style >> BG_SHIFT) & 0x1FF;
    uint32_t flags = (style >> FLAGS_SHIFT) & 0xF;

    char tmp[64];
    int n = snprintf(tmp, sizeof(tmp), "\033[0");
    if (flags & 1) { tmp[n++] = ';'; tmp[n++] = '1'; }
    if (flags & 2) { tmp[n++] = ';'; tmp[n++] = '2'; }
    if (flags & 4) { tmp[n++] = ';'; tmp[n++] = '3'; }
    if (flags & 8) { tmp[n++] = ';'; tmp[n++] = '7'; }
    if (fg) n += snprintf(tmp + n, sizeof(tmp) - n, ";38;5;%u", fg - 1);
    if (bg) n += snprintf(tmp + n, sizeof(tmp) - n, ";48;5;%u", bg - 1);
    tmp[n++] = 'm';
    outbuf_add(b, tmp, (size_t)n);
}

/* ── SGR parameter parsing ─────────────────────────────────────────── */

static void parse_sgr(const void *data, int kind,
                      Py_ssize_t start, Py_ssize_t end,
                      uint32_t *fg, uint32_t *bg, uint32_t *flags)
{
    int num = -1;
    int state = 0; /* 0=normal, 1=after 38, 2=after 38;5, 3=after 48, 4=after 48;5 */

    for (Py_ssize_t i = start; i <= end; i++) {
        Py_UCS4 c = (i < end) ? PyUnicode_READ(kind, data, i) : ';';

        if (c >= '0' && c <= '9') {
            num = (num < 0 ? 0 : num * 10) + (int)(c - '0');
            continue;
        }

        /* separator or end */
        if (num < 0) num = 0;

        if (state == 2) {
            *fg = (uint32_t)num + 1; state = 0;
        } else if (state == 4) {
            *bg = (uint32_t)num + 1; state = 0;
        } else if (state == 1 && num == 5) {
            state = 2;
        } else if (state == 3 && num == 5) {
            state = 4;
        } else {
            switch (num) {
            case  0: *fg = *bg = *flags = 0; break;
            case  1: *flags |= 1; break;
            case  2: *flags |= 2; break;
            case  3: *flags |= 4; break;
            case  7: *flags |= 8; break;
            case 38: state = 1; goto next;
            case 48: state = 3; goto next;
            }
            state = 0;
        }
    next:
        num = -1;
    }
}

/* ── char width (system wcwidth) ──────────────────────────────────── */

#include <wchar.h>

static inline int cwidth(Py_UCS4 ch) {
    if (ch >= 0x20 && ch < 0x7F) return 1;  /* ASCII printable */
    if (ch < 0x80) return 0;                 /* ASCII control */
    int w = wcwidth((wchar_t)ch);
    return w > 0 ? w : 0;
}

static PyObject *mod_char_width(PyObject *self, PyObject *arg) {
    if (!PyUnicode_Check(arg) || PyUnicode_GET_LENGTH(arg) != 1) {
        PyErr_SetString(PyExc_TypeError, "expected a single character");
        return NULL;
    }
    Py_UCS4 ch = PyUnicode_READ_CHAR(arg, 0);
    return PyLong_FromLong(cwidth(ch));
}

/* ── Unicode helpers ──────────────────────────────────────────────── */

/* Skip a CSI escape sequence (ESC [ ... final_byte) starting at pos.
   Returns the position AFTER the sequence, or pos if not a CSI. */
static inline Py_ssize_t skip_csi(const void *data, int kind,
                                   Py_ssize_t pos, Py_ssize_t len) {
    if (pos + 1 >= len || PyUnicode_READ(kind, data, pos + 1) != '[')
        return pos;
    Py_ssize_t end = pos + 2;
    while (end < len) {
        Py_UCS4 fb = PyUnicode_READ(kind, data, end);
        end++;
        if (fb >= 0x40 && fb <= 0x7E) break;
    }
    return end;
}

/* Compute display width of a Python unicode string (ANSI-aware). */
static int str_display_width(PyObject *s) {
    Py_ssize_t len = PyUnicode_GET_LENGTH(s);
    if (len == 0) return 0;
    /* Fast: pure ASCII, no escapes → width == length */
    if (PyUnicode_IS_ASCII(s) &&
        PyUnicode_FindChar(s, 0x1B, 0, len, 1) < 0)
        return (int)len;
    /* Slow: scan for wide chars and ANSI escapes */
    int kind = PyUnicode_KIND(s);
    const void *data = PyUnicode_DATA(s);
    int width = 0;
    for (Py_ssize_t pos = 0; pos < len; ) {
        Py_UCS4 ch = PyUnicode_READ(kind, data, pos);
        if (ch == 0x1B) { pos = skip_csi(data, kind, pos, len); continue; }
        width += cwidth(ch);
        pos++;
    }
    return width;
}

/* Check if a Python string is pure ASCII with no ANSI escapes. */
static inline int is_plain_ascii(PyObject *s) {
    return PyUnicode_IS_ASCII(s) &&
           PyUnicode_FindChar(s, 0x1B, 0, PyUnicode_GET_LENGTH(s), 1) < 0;
}

/* Build a Python string of n spaces. */
static PyObject *make_spaces(int n) {
    char *buf = (char *)malloc(n);
    if (!buf) return PyErr_NoMemory();
    memset(buf, ' ', n);
    PyObject *result = PyUnicode_FromStringAndSize(buf, n);
    free(buf);
    return result;
}

/* ── Buffer type ───────────────────────────────────────────────────── */

typedef struct {
    PyObject_HEAD
    int   width;
    int   height;
    Cell *cells;
} BufferObject;

static PyTypeObject BufferType; /* forward decl */

static void Buffer_dealloc(BufferObject *self) {
    free(self->cells);
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static int Buffer_init(BufferObject *self, PyObject *args, PyObject *kw) {
    int w, h;
    if (!PyArg_ParseTuple(args, "ii", &w, &h)) return -1;
    if (w <= 0 || h <= 0) {
        PyErr_SetString(PyExc_ValueError, "width and height must be positive");
        return -1;
    }
    /* Guard against overflow: w * h * sizeof(Cell) */
    size_t n = (size_t)w * (size_t)h;
    if (n > (size_t)100000000) { /* ~800MB, way beyond any terminal */
        PyErr_SetString(PyExc_ValueError, "buffer too large");
        return -1;
    }

    /* Free previous cells if re-initialized */
    free(self->cells);

    self->width  = w;
    self->height = h;
    self->cells = (Cell *)malloc(n * sizeof(Cell));
    if (!self->cells) { PyErr_NoMemory(); return -1; }
    for (size_t i = 0; i < n; i++) self->cells[i] = BLANK_CELL;
    return 0;
}

static PyObject *Buffer_row_text(BufferObject *self, PyObject *args) {
    int row;
    if (!PyArg_ParseTuple(args, "i", &row)) return NULL;
    if (row < 0 || row >= self->height) {
        PyErr_SetString(PyExc_IndexError, "row out of range");
        return NULL;
    }
    int w = self->width;
    Cell *cells = self->cells + row * w;
    char *utf8 = (char *)malloc((size_t)w * 4 + 1);
    if (!utf8) return PyErr_NoMemory();
    int len = 0;
    for (int i = 0; i < w; i++) {
        if (cells[i].ch != WIDE_CHAR)
            len += encode_utf8(cells[i].ch, utf8 + len);
    }
    PyObject *result = PyUnicode_DecodeUTF8(utf8, len, NULL);
    free(utf8);
    return result;
}

static PyMethodDef Buffer_methods[] = {
    {"row_text", (PyCFunction)Buffer_row_text, METH_VARARGS, "Plain text of a row."},
    {NULL}
};

static PyMemberDef Buffer_members[] = {
    {"width",  Py_T_INT, offsetof(BufferObject, width),  Py_READONLY, NULL},
    {"height", Py_T_INT, offsetof(BufferObject, height), Py_READONLY, NULL},
    {NULL}
};

static PyTypeObject BufferType = {
    .ob_base      = PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name      = "terminal.cbuf.Buffer",
    .tp_basicsize = sizeof(BufferObject),
    .tp_flags     = Py_TPFLAGS_DEFAULT,
    .tp_new       = PyType_GenericNew,
    .tp_init      = (initproc)Buffer_init,
    .tp_dealloc   = (destructor)Buffer_dealloc,
    .tp_methods   = Buffer_methods,
    .tp_members   = Buffer_members,
    .tp_doc       = "Fixed-size 2D grid of styled cells.",
};

/* ── parse_line ────────────────────────────────────────────────────── */

static PyObject *mod_parse_line(PyObject *self, PyObject *args) {
    BufferObject *buf;
    int row;
    PyObject *line;

    if (!PyArg_ParseTuple(args, "O!iU", &BufferType, &buf, &row, &line))
        return NULL;
    if (row < 0 || row >= buf->height) {
        PyErr_SetString(PyExc_IndexError, "row out of range");
        return NULL;
    }

    int w = buf->width;
    Cell *cells = buf->cells + row * w;
    Py_ssize_t len = PyUnicode_GET_LENGTH(line);

    if (len == 0) Py_RETURN_NONE;

    int kind = PyUnicode_KIND(line);
    const void *data = PyUnicode_DATA(line);

    /* Fast path: pure ASCII, no escapes */
    if (is_plain_ascii(line)) {
        Py_ssize_t n = len < w ? len : w;
        const char *ascii = PyUnicode_AsUTF8(line);
        for (Py_ssize_t i = 0; i < n; i++)
            cells[i] = (Cell){(Py_UCS4)(unsigned char)ascii[i], STYLE_EMPTY};
        Py_RETURN_NONE;
    }

    /* Slow path: ANSI + wide chars */
    int col = 0;
    Py_ssize_t pos = 0;
    uint32_t fg = 0, bg = 0, flags = 0, style = STYLE_EMPTY;

    while (pos < len && col < w) {
        Py_UCS4 ch = PyUnicode_READ(kind, data, pos);

        if (ch == 0x1B) {
            Py_ssize_t end = skip_csi(data, kind, pos, len);
            if (end != pos) {
                /* CSI: find 'm' terminator for SGR parsing */
                Py_ssize_t m = pos + 2;
                while (m < end && PyUnicode_READ(kind, data, m) != 'm') m++;
                parse_sgr(data, kind, pos + 2, m, &fg, &bg, &flags);
                style = fg | (bg << BG_SHIFT) | (flags << FLAGS_SHIFT);
                pos = end;
            } else {
                pos++;
            }
            continue;
        }

        int cw = cwidth(ch);
        if (cw <= 0) { pos++; continue; }
        if (cw == 2 && col + 1 >= w) { pos++; continue; }

        cells[col] = (Cell){ch, style};
        if (cw == 2) {
            cells[col + 1] = (Cell){WIDE_CHAR, style};
            col += 2;
        } else {
            col++;
        }
        pos++;
    }

    Py_RETURN_NONE;
}

/* ── render_full ───────────────────────────────────────────────────── */

static PyObject *mod_render_full(PyObject *self, PyObject *args) {
    BufferObject *buf;
    if (!PyArg_ParseTuple(args, "O!", &BufferType, &buf))
        return NULL;

    int w = buf->width;
    int h = buf->height;
    Cell *cells = buf->cells;

    OutBuf out;
    if (outbuf_init(&out, (size_t)(w * h) * 8 + (size_t)h * 16 + 64) < 0)
        return PyErr_NoMemory();

    outbuf_add(&out, "\033[0m", 4);  /* reset to known state */
    uint32_t active = STYLE_EMPTY;

    for (int row = 0; row < h; row++) {
        outbuf_printf(&out, "\033[%d;1H", row + 1);
        int off = row * w;
        for (int col = 0; col < w; col++) {
            Cell c = cells[off + col];
            if (c.ch == WIDE_CHAR) continue;
            if (c.style != active) {
                emit_sgr(&out, c.style);
                active = c.style;
            }
            char u8[4];
            int u8len = encode_utf8(c.ch, u8);
            outbuf_add(&out, u8, (size_t)u8len);
        }
    }

    if (active != STYLE_EMPTY)
        outbuf_add(&out, "\033[0m", 4);

    return outbuf_to_pystr(&out);
}

/* ── render_diff ───────────────────────────────────────────────────── */

static PyObject *mod_render_diff(PyObject *self, PyObject *args) {
    BufferObject *cur, *prev;
    if (!PyArg_ParseTuple(args, "O!O!", &BufferType, &cur, &BufferType, &prev))
        return NULL;

    if (cur->width != prev->width || cur->height != prev->height) {
        PyErr_SetString(PyExc_ValueError,
                        "render_diff requires buffers with the same dimensions");
        return NULL;
    }

    int w = cur->width;
    int h = cur->height;
    Cell *cc = cur->cells;
    Cell *pc = prev->cells;
    size_t total = (size_t)w * (size_t)h;

    /* Early out: identical buffers */
    if (memcmp(cc, pc, total * sizeof(Cell)) == 0)
        return PyUnicode_FromStringAndSize("", 0);

    OutBuf out;
    if (outbuf_init(&out, 4096) < 0)
        return PyErr_NoMemory();

    uint32_t active = STYLE_EMPTY;

    for (int row = 0; row < h; row++) {
        int off = row * w;

        /* Skip identical rows */
        if (memcmp(cc + off, pc + off, (size_t)w * sizeof(Cell)) == 0)
            continue;

        int col = 0;
        while (col < w) {
            Cell c = cc[off + col];
            Cell p = pc[off + col];
            if (c.ch == p.ch && c.style == p.style) { col++; continue; }
            if (c.ch == WIDE_CHAR) { col++; continue; }

            /* Start a dirty run */
            outbuf_printf(&out, "\033[%d;%dH", row + 1, col + 1);
            if (c.style != active) {
                emit_sgr(&out, c.style);
                active = c.style;
            }
            char u8[4];
            outbuf_add(&out, u8, (size_t)encode_utf8(c.ch, u8));
            col++;

            /* Extend run with adjacent dirty cells */
            while (col < w) {
                Cell c2 = cc[off + col];
                Cell p2 = pc[off + col];
                if (c2.ch == p2.ch && c2.style == p2.style) break;
                if (c2.ch == WIDE_CHAR) { col++; continue; }
                if (c2.style != active) {
                    emit_sgr(&out, c2.style);
                    active = c2.style;
                }
                outbuf_add(&out, u8, (size_t)encode_utf8(c2.ch, u8));
                col++;
            }
        }
    }

    if (active != STYLE_EMPTY)
        outbuf_add(&out, "\033[0m", 4);

    return outbuf_to_pystr(&out);
}

/* ── display_width ────────────────────────────────────────────────── */

static PyObject *mod_display_width(PyObject *self, PyObject *arg) {
    if (!PyUnicode_Check(arg)) {
        PyErr_SetString(PyExc_TypeError, "expected a string");
        return NULL;
    }
    return PyLong_FromLong(str_display_width(arg));
}

/* ── render_flat_line ─────────────────────────────────────────────── */
/*
 * render_flat_line(items) -> str
 *
 * items: list of (offset: int, col_width: int, content: str)
 * Builds a single line by placing each content at its offset, padded to
 * col_width.  Gaps between items are filled with spaces.
 */
static PyObject *mod_render_flat_line(PyObject *self, PyObject *arg) {
    if (!PyList_Check(arg)) {
        PyErr_SetString(PyExc_TypeError, "expected a list");
        return NULL;
    }

    Py_ssize_t n = PyList_GET_SIZE(arg);
    if (n == 0) return PyUnicode_FromString("");

    /* First pass: compute total output width from last item. */
    PyObject *last = PyList_GET_ITEM(arg, n - 1);
    long last_off, last_cw;
    {
        PyObject *py_off = PyTuple_GET_ITEM(last, 0);
        PyObject *py_cw  = PyTuple_GET_ITEM(last, 1);
        last_off = PyLong_AsLong(py_off);
        last_cw  = PyLong_AsLong(py_cw);
    }
    Py_ssize_t total = last_off + last_cw;

    /* Allocate UCS-1 (ASCII) buffer filled with spaces. */
    PyObject *out = PyUnicode_New(total, 127);
    if (!out) return NULL;
    Py_UCS1 *buf = PyUnicode_1BYTE_DATA(out);
    memset(buf, ' ', total);

    /* Place each item. */
    for (Py_ssize_t i = 0; i < n; i++) {
        PyObject *tup = PyList_GET_ITEM(arg, i);
        long off = PyLong_AsLong(PyTuple_GET_ITEM(tup, 0));
        /* col_width unused — we already allocated total */
        PyObject *content = PyTuple_GET_ITEM(tup, 2);

        if (!PyUnicode_Check(content)) continue;
        Py_ssize_t clen = PyUnicode_GET_LENGTH(content);
        if (clen == 0) continue;

        /* ASCII content with no ANSI escapes: copy bytes directly.
           Content may be shorter than col_width — the buffer is
           pre-filled with spaces so padding is automatic. */
        if (is_plain_ascii(content)) {
            const Py_UCS1 *src = PyUnicode_1BYTE_DATA(content);
            Py_ssize_t copy = clen;
            if (off + copy > total) copy = total - off;
            if (copy > 0 && off >= 0)
                memcpy(buf + off, src, copy);
        } else {
            /* Non-ASCII or ANSI content: fall back to Python. */
            Py_DECREF(out);
            Py_RETURN_NONE;
        }
    }

    return out;
}

/* ── hstack_join_row ─────────────────────────────────────────────── */
/*
 * hstack_join_row(cells, col_widths, spacing) -> str
 *
 * cells:      list[str]  — rendered content for each column
 * col_widths: list[int]  — target width for each column
 * spacing:    int        — gap between columns
 *
 * For each cell: pad content to col_width with spaces, join with spacing.
 * ANSI-aware: skips escape sequences when measuring content width.
 */
static PyObject *mod_hstack_join_row(PyObject *self, PyObject *args) {
    PyObject *cells, *widths;
    int spacing;
    if (!PyArg_ParseTuple(args, "OOi", &cells, &widths, &spacing))
        return NULL;

    Py_ssize_t n = PyList_GET_SIZE(cells);
    if (n == 0) return PyUnicode_FromString("");

    /* Compute total output length. */
    Py_ssize_t total = 0;
    for (Py_ssize_t i = 0; i < n; i++) {
        total += PyLong_AsLong(PyList_GET_ITEM(widths, i));
        if (i > 0) total += spacing;
    }

    /* Pre-scan: if ALL cells are ASCII with no ANSI, use fast memcpy path. */
    int all_ascii = 1;
    for (Py_ssize_t i = 0; i < n; i++) {
        PyObject *cell = PyList_GET_ITEM(cells, i);
        if (!is_plain_ascii(cell)) {
            all_ascii = 0;
            break;
        }
    }

    if (all_ascii) {
        PyObject *out = PyUnicode_New(total, 127);
        if (!out) return NULL;
        Py_UCS1 *buf = PyUnicode_1BYTE_DATA(out);
        memset(buf, ' ', total);

        Py_ssize_t pos = 0;
        for (Py_ssize_t i = 0; i < n; i++) {
            if (i > 0) pos += spacing;  /* spacing already spaces via memset */
            long cw = PyLong_AsLong(PyList_GET_ITEM(widths, i));
            PyObject *cell = PyList_GET_ITEM(cells, i);
            Py_ssize_t clen = PyUnicode_GET_LENGTH(cell);
            Py_ssize_t copy = clen < cw ? clen : cw;
            memcpy(buf + pos, PyUnicode_1BYTE_DATA(cell), copy);
            pos += cw;
        }
        return out;
    }

    /* ANSI path: copy content while tracking visible width for padding. */
    OutBuf ob;
    if (outbuf_init(&ob, total * 2) < 0)
        return PyErr_NoMemory();

    for (Py_ssize_t i = 0; i < n; i++) {
        if (i > 0)
            for (int s = 0; s < spacing; s++)
                outbuf_add(&ob, " ", 1);

        long cw = PyLong_AsLong(PyList_GET_ITEM(widths, i));
        PyObject *cell = PyList_GET_ITEM(cells, i);
        Py_ssize_t clen = PyUnicode_GET_LENGTH(cell);
        int kind = PyUnicode_KIND(cell);
        const void *data = PyUnicode_DATA(cell);

        int vis = 0;
        for (Py_ssize_t j = 0; j < clen; ) {
            Py_UCS4 ch = PyUnicode_READ(kind, data, j);
            char u8[4];

            if (ch == 0x1B) {
                /* Copy CSI escape sequence verbatim (doesn't count as visible). */
                Py_ssize_t end = skip_csi(data, kind, j, clen);
                for (Py_ssize_t k = j; k < end; k++) {
                    Py_UCS4 ec = PyUnicode_READ(kind, data, k);
                    outbuf_add(&ob, u8, encode_utf8(ec, u8));
                }
                j = end;
            } else {
                outbuf_add(&ob, u8, encode_utf8(ch, u8));
                vis += cwidth(ch);
                j++;
            }
        }

        /* Pad to column width. */
        for (int g = vis; g < (int)cw; g++)
            outbuf_add(&ob, " ", 1);
    }

    return outbuf_to_pystr(&ob);
}

/* ── Renderable type ──────────────────────────────────────────────── */

typedef struct {
    PyObject_HEAD
    PyObject *render;         /* callable: (w, h?) -> list[str] */
    int       flex_basis;
    int       grow;
    PyObject *width;          /* str | Py_None */
    PyObject *height;         /* str | Py_None */
    PyObject *flat_children;  /* tuple | NULL (hstack flat path) */
    int       flat_spacing;
} CRenderableObject;

static PyTypeObject CRenderableType; /* forward decl */

static void CRenderable_dealloc(CRenderableObject *self) {
    Py_XDECREF(self->render);
    Py_XDECREF(self->width);
    Py_XDECREF(self->height);
    Py_XDECREF(self->flat_children);
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static int CRenderable_init(CRenderableObject *self, PyObject *args, PyObject *kw) {
    static char *kwlist[] = {"render", "flex_basis", "grow", "width", "height", NULL};
    PyObject *render = NULL, *width = Py_None, *height = Py_None;
    int flex_basis = 0, grow = 0;

    if (!PyArg_ParseTupleAndKeywords(args, kw, "O|iiOO", kwlist,
            &render, &flex_basis, &grow, &width, &height))
        return -1;

    Py_XDECREF(self->render);
    Py_INCREF(render);
    self->render = render;
    self->flex_basis = flex_basis;
    self->grow = grow;

    Py_XDECREF(self->width);
    Py_INCREF(width);
    self->width = width;

    Py_XDECREF(self->height);
    Py_INCREF(height);
    self->height = height;

    /* Optional fields: NULL by default (Python sees None via T_OBJECT) */
    Py_CLEAR(self->flat_children);
    self->flat_spacing = 0;

    return 0;
}

/* resolve "50%" or "28" against a parent dimension */
static PyObject *resolve_dim(PyObject *value, int parent, int axis) {
    if (value == NULL || value == Py_None)
        Py_RETURN_NONE;
    const char *s = PyUnicode_AsUTF8(value);
    if (!s) return NULL;
    Py_ssize_t slen = PyUnicode_GET_LENGTH(value);
    if (slen > 0 && s[slen - 1] == '%') {
        int pct = atoi(s);
        int base = parent;
        if (base <= 0) {
            /* fallback: os.get_terminal_size()[axis] */
            PyObject *os = PyImport_ImportModule("os");
            if (!os) return NULL;
            PyObject *gts = PyObject_CallMethod(os, "get_terminal_size", NULL);
            Py_DECREF(os);
            if (!gts) return NULL;
            PyObject *item = PySequence_GetItem(gts, axis);
            Py_DECREF(gts);
            if (!item) return NULL;
            base = (int)PyLong_AsLong(item);
            Py_DECREF(item);
        }
        return PyLong_FromLong(base * pct / 100);
    }
    return PyLong_FromLong(atoi(s));
}

static PyObject *CRenderable_resolve_width(CRenderableObject *self, PyObject *args) {
    int parent;
    if (!PyArg_ParseTuple(args, "i", &parent)) return NULL;
    return resolve_dim(self->width, parent, 0);
}

static PyObject *CRenderable_resolve_height(CRenderableObject *self, PyObject *args) {
    int parent;
    if (!PyArg_ParseTuple(args, "i", &parent)) return NULL;
    return resolve_dim(self->height, parent, 1);
}

static PyMethodDef CRenderable_methods[] = {
    {"resolve_width",  (PyCFunction)CRenderable_resolve_width,  METH_VARARGS, NULL},
    {"resolve_height", (PyCFunction)CRenderable_resolve_height, METH_VARARGS, NULL},
    {NULL}
};

static PyMemberDef CRenderable_members[] = {
    {"render",        T_OBJECT_EX, offsetof(CRenderableObject, render),       0, NULL},
    {"flex_basis",    T_INT,       offsetof(CRenderableObject, flex_basis),    0, NULL},
    {"grow",          T_INT,       offsetof(CRenderableObject, grow),          0, NULL},
    {"width",         T_OBJECT_EX, offsetof(CRenderableObject, width),        0, NULL},
    {"height",        T_OBJECT_EX, offsetof(CRenderableObject, height),       0, NULL},
    {"flat_children", T_OBJECT,    offsetof(CRenderableObject, flat_children), 0, NULL},
    {"flat_spacing",  T_INT,       offsetof(CRenderableObject, flat_spacing),  0, NULL},
    {NULL}
};

static PyTypeObject CRenderableType = {
    .ob_base      = PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name      = "terminal.cbuf.Renderable",
    .tp_basicsize = sizeof(CRenderableObject),
    .tp_flags     = Py_TPFLAGS_DEFAULT,
    .tp_new       = PyType_GenericNew,
    .tp_init      = (initproc)CRenderable_init,
    .tp_dealloc   = (destructor)CRenderable_dealloc,
    .tp_methods   = CRenderable_methods,
    .tp_members   = CRenderable_members,
    .tp_doc       = "Renderable component with flex layout properties.",
};

/* ── TextRender callable type ─────────────────────────────────────── */

#define TEXT_PLAIN    0
#define TEXT_PADDED   1
#define TEXT_FULL     2

typedef struct {
    PyObject_HEAD
    int       mode;       /* TEXT_PLAIN / TEXT_PADDED / TEXT_FULL */
    PyObject *lines;      /* list[str] — pre-computed */
    int       pl, pr;     /* padding left / right */
    PyObject *pad_l;      /* " " * pl or NULL */
    PyObject *pad_r;      /* " " * pr or NULL */
    PyObject *truncation; /* "tail"/"head"/"middle" or NULL */
    int       wrap;       /* bool */
} CTextRenderObject;

static PyTypeObject CTextRenderType; /* forward decl */

static void CTextRender_dealloc(CTextRenderObject *self) {
    Py_XDECREF(self->lines);
    Py_XDECREF(self->pad_l);
    Py_XDECREF(self->pad_r);
    Py_XDECREF(self->truncation);
    Py_TYPE(self)->tp_free((PyObject *)self);
}

/* Cached reference to Python fallback for wrap/non-ASCII truncation. */
static PyObject *py_text_full_render = NULL;

static PyObject *CTextRender_call(CTextRenderObject *self,
                                   PyObject *args, PyObject *kw) {
    int w;
    PyObject *h_obj = Py_None;
    static char *kwlist[] = {"w", "h", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kw, "i|O", kwlist, &w, &h_obj))
        return NULL;

    switch (self->mode) {
    case TEXT_PLAIN:
        /* Just return the pre-computed list. */
        Py_INCREF(self->lines);
        return self->lines;

    case TEXT_PADDED: {
        Py_ssize_t n = PyList_GET_SIZE(self->lines);
        PyObject *result = PyList_New(n);
        if (!result) return NULL;
        for (Py_ssize_t i = 0; i < n; i++) {
            PyObject *line = PyList_GET_ITEM(self->lines, i);
            PyObject *padded = PyUnicode_FromFormat("%U%U%U",
                self->pad_l, line, self->pad_r);
            if (!padded) { Py_DECREF(result); return NULL; }
            PyList_SET_ITEM(result, i, padded);
        }
        return result;
    }

    case TEXT_FULL: {
        int inner = w - self->pl - self->pr;

        /* C fast path: single-line plain-ASCII with tail truncation.
           Covers the hot case (list items).  Everything else → Python. */
        if (!self->wrap && self->truncation != NULL &&
            PyList_GET_SIZE(self->lines) == 1 && inner > 0) {
            PyObject *line = PyList_GET_ITEM(self->lines, 0);
            const char *tmode = PyUnicode_AsUTF8(self->truncation);
            if (is_plain_ascii(line) && tmode && tmode[0] == 't') {
                Py_ssize_t slen = PyUnicode_GET_LENGTH(line);
                PyObject *str;
                if (slen <= inner) {
                    Py_INCREF(line);
                    str = line;
                } else {
                    PyObject *head = PyUnicode_Substring(line, 0, inner - 1);
                    if (!head) return NULL;
                    PyObject *ell = PyUnicode_FromOrdinal(0x2026); /* U+2026 … */
                    if (!ell) { Py_DECREF(head); return NULL; }
                    str = PyUnicode_Concat(head, ell);
                    Py_DECREF(head);
                    Py_DECREF(ell);
                    if (!str) return NULL;
                }
                PyObject *result = PyList_New(1);
                if (!result) { Py_DECREF(str); return NULL; }
                PyList_SET_ITEM(result, 0, str);
                return result;
            }
        }

        /* Python fallback: wrap, non-ASCII, head/middle truncation. */
        if (!py_text_full_render) {
            PyErr_SetString(PyExc_RuntimeError, "text full render helper not set");
            return NULL;
        }
        return PyObject_CallFunction(py_text_full_render, "OiiiOO",
            self->lines, w, self->pl, self->pr,
            self->truncation ? self->truncation : Py_None,
            self->wrap ? Py_True : Py_False);
    }
    }
    Py_RETURN_NONE;
}

static PyTypeObject CTextRenderType = {
    .ob_base      = PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name      = "terminal.cbuf.TextRender",
    .tp_basicsize = sizeof(CTextRenderObject),
    .tp_flags     = Py_TPFLAGS_DEFAULT,
    .tp_new       = PyType_GenericNew,
    .tp_dealloc   = (destructor)CTextRender_dealloc,
    .tp_call      = (ternaryfunc)CTextRender_call,
    .tp_doc       = "C-accelerated text render callable.",
};

/* ── c_make_text factory ─────────────────────────────────────────── */
/*
 * c_make_text(value, truncation, pl, pr, wrap) -> (TextRender, lines, visible_w)
 */
static PyObject *mod_c_make_text(PyObject *self, PyObject *args) {
    PyObject *value, *truncation;
    int pl, pr, wrap;

    if (!PyArg_ParseTuple(args, "OOiip", &value, &truncation, &pl, &pr, &wrap))
        return NULL;

    /* Convert to string. */
    PyObject *raw;
    if (PyUnicode_Check(value)) {
        raw = value;
        Py_INCREF(raw);
    } else {
        raw = PyObject_Str(value);
        if (!raw) return NULL;
    }

    /* _parse_lines: split on \n, compute display_width. */
    PyObject *lines;
    int visible_w;
    Py_ssize_t rlen = PyUnicode_GET_LENGTH(raw);

    if (PyUnicode_FindChar(raw, '\n', 0, rlen, 1) < 0) {
        /* Single line (common case). */
        lines = PyList_New(1);
        if (!lines) { Py_DECREF(raw); return NULL; }
        Py_INCREF(raw);
        PyList_SET_ITEM(lines, 0, raw);
        visible_w = str_display_width(raw);
    } else {
        /* Multi-line: split and measure each. */
        lines = PyUnicode_Splitlines(raw, 0);
        if (!lines) { Py_DECREF(raw); return NULL; }
        Py_ssize_t n = PyList_GET_SIZE(lines);
        if (n == 0) {
            Py_DECREF(lines);
            lines = PyList_New(1);
            if (!lines) { Py_DECREF(raw); return NULL; }
            PyList_SET_ITEM(lines, 0, PyUnicode_FromString(""));
            visible_w = 0;
        } else {
            visible_w = 0;
            for (Py_ssize_t i = 0; i < n; i++) {
                int lw = str_display_width(PyList_GET_ITEM(lines, i));
                if (lw > visible_w) visible_w = lw;
            }
        }
    }

    /* Determine mode. */
    int is_trunc = (truncation != Py_None && truncation != NULL);
    int mode;
    if (!wrap && !is_trunc && pl == 0 && pr == 0)
        mode = TEXT_PLAIN;
    else if (!wrap && !is_trunc)
        mode = TEXT_PADDED;
    else
        mode = TEXT_FULL;

    /* Create CTextRenderObject. */
    CTextRenderObject *render = PyObject_New(CTextRenderObject, &CTextRenderType);
    if (!render) { Py_DECREF(lines); Py_DECREF(raw); return NULL; }
    render->mode = mode;
    Py_INCREF(lines);
    render->lines = lines;
    render->pl = pl;
    render->pr = pr;
    render->pad_l = pl > 0 ? make_spaces(pl) : PyUnicode_FromStringAndSize("", 0);
    render->pad_r = pr > 0 ? make_spaces(pr) : PyUnicode_FromStringAndSize("", 0);
    if (is_trunc) {
        Py_INCREF(truncation);
        render->truncation = truncation;
    } else {
        render->truncation = NULL;
    }
    render->wrap = wrap;

    Py_DECREF(raw);
    PyObject *result = Py_BuildValue("(ONi)", render, lines, visible_w);
    return result;
}

/* ── set_text_full_render_helper ─────────────────────────────────── */
static PyObject *mod_set_text_render_fallback(PyObject *self, PyObject *arg) {
    Py_XDECREF(py_text_full_render);
    Py_INCREF(arg);
    py_text_full_render = arg;
    Py_RETURN_NONE;
}

/* ── resolve_col_widths ────────────────────────────────────────────── */
/*
 * resolve_col_widths(bases, grows, width, spacing) -> list[int]
 *
 * bases:   list[int] — flex_basis for each column
 * grows:   list[int] — grow weight for each column (0 = fixed)
 * width:   int       — total available width
 * spacing: int       — gap between columns
 *
 * Returns resolved column widths with remaining space distributed
 * proportionally among grow columns.  Mirrors the Python
 * _resolve_col_widths + distribute logic.
 */
static PyObject *mod_resolve_col_widths(PyObject *self, PyObject *args) {
    PyObject *bases, *grows;
    int width, spacing;
    if (!PyArg_ParseTuple(args, "OOii", &bases, &grows, &width, &spacing))
        return NULL;

    Py_ssize_t n = PyList_GET_SIZE(bases);

    /* Build col_widths, collect grow weights. */
    long *col_widths = (long *)malloc(n * sizeof(long));
    if (!col_widths) return PyErr_NoMemory();

    long *grow_idx = (long *)malloc(n * sizeof(long));
    long *grow_wt  = (long *)malloc(n * sizeof(long));
    if (!grow_idx || !grow_wt) {
        free(col_widths); free(grow_idx); free(grow_wt);
        return PyErr_NoMemory();
    }

    Py_ssize_t ng = 0;
    long used = 0;
    for (Py_ssize_t i = 0; i < n; i++) {
        long b = PyLong_AsLong(PyList_GET_ITEM(bases, i));
        long g = PyLong_AsLong(PyList_GET_ITEM(grows, i));
        col_widths[i] = b;
        used += b;
        if (g) {
            grow_idx[ng] = i;
            grow_wt[ng]  = g;
            ng++;
        }
    }

    long gap_total = spacing * (n > 1 ? n - 1 : 0);
    long remaining = width - used - gap_total;
    if (remaining < 0) remaining = 0;

    /* Distribute remaining space among grow columns. */
    if (ng > 0 && remaining > 0) {
        long total_weight = 0;
        for (Py_ssize_t j = 0; j < ng; j++)
            total_weight += grow_wt[j];
        long cum_weight = 0, cum_space = 0;
        for (Py_ssize_t j = 0; j < ng; j++) {
            cum_weight += grow_wt[j];
            long target = remaining * cum_weight / total_weight;
            col_widths[grow_idx[j]] += target - cum_space;
            cum_space = target;
        }
    }

    /* Build result list. */
    PyObject *result = PyList_New(n);
    if (!result) { free(col_widths); free(grow_idx); free(grow_wt); return NULL; }
    for (Py_ssize_t i = 0; i < n; i++)
        PyList_SET_ITEM(result, i, PyLong_FromLong(col_widths[i]));

    free(col_widths);
    free(grow_idx);
    free(grow_wt);
    return result;
}

/* ── Module definition ─────────────────────────────────────────────── */

static PyMethodDef module_methods[] = {
    {"parse_line",  mod_parse_line,  METH_VARARGS, "Parse ANSI line into buffer row."},
    {"render_full", mod_render_full, METH_VARARGS, "Render entire buffer to ANSI."},
    {"render_diff", mod_render_diff, METH_VARARGS, "Render cell-level diff to ANSI."},
    {"char_width",     mod_char_width,     METH_O,       "Display width of a single character."},
    {"display_width",  mod_display_width,  METH_O,       "Display width of a string (ANSI-aware)."},
    {"render_flat_line", mod_render_flat_line, METH_O,    "Render flat layout items into a single line."},
    {"hstack_join_row",  mod_hstack_join_row,  METH_VARARGS, "Join cells with padding and spacing."},
    {"resolve_col_widths", mod_resolve_col_widths, METH_VARARGS, "Resolve flex column widths in one shot."},
    {"c_make_text", mod_c_make_text, METH_VARARGS, "Create a TextRender + parse lines + measure width."},
    {"set_text_render_fallback", mod_set_text_render_fallback, METH_O, "Set Python fallback for text full render."},
    {NULL}
};

static struct PyModuleDef module_def = {
    PyModuleDef_HEAD_INIT,
    .m_name    = "terminal.cbuf",
    .m_doc     = "C-accelerated cell buffer for terminal rendering.",
    .m_size    = -1,
    .m_methods = module_methods,
};

PyMODINIT_FUNC PyInit_cbuf(void) {
    if (PyType_Ready(&BufferType) < 0)
        return NULL;
    if (PyType_Ready(&CRenderableType) < 0)
        return NULL;
    if (PyType_Ready(&CTextRenderType) < 0)
        return NULL;

    PyObject *m = PyModule_Create(&module_def);
    if (!m) return NULL;

    Py_INCREF(&BufferType);
    if (PyModule_AddObject(m, "Buffer", (PyObject *)&BufferType) < 0) {
        Py_DECREF(&BufferType);
        Py_DECREF(m);
        return NULL;
    }

    Py_INCREF(&CRenderableType);
    if (PyModule_AddObject(m, "Renderable", (PyObject *)&CRenderableType) < 0) {
        Py_DECREF(&CRenderableType);
        Py_DECREF(m);
        return NULL;
    }

    if (PyModule_AddIntConstant(m, "EMPTY", STYLE_EMPTY) < 0) {
        Py_DECREF(m);
        return NULL;
    }

    return m;
}
