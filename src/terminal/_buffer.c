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

/* ── char width (calls Python wcwidth package) ────────────────────── */

static PyObject *py_wcwidth_fn = NULL;  /* cached reference to wcwidth.wcwidth */

static int init_wcwidth(void) {
    PyObject *mod = PyImport_ImportModule("wcwidth");
    if (!mod) return -1;
    py_wcwidth_fn = PyObject_GetAttrString(mod, "wcwidth");
    Py_DECREF(mod);
    return py_wcwidth_fn ? 0 : -1;
}

static inline int cwidth(Py_UCS4 ch) {
    if (ch >= 0x20 && ch < 0x7F) return 1;  /* ASCII printable */
    if (ch < 0x80) return 0;                 /* ASCII control */
    /* Call Python wcwidth for non-ASCII (CJK, emoji, etc.) */
    PyObject *result = PyObject_CallFunction(py_wcwidth_fn, "C", ch);
    if (!result) { PyErr_Clear(); return 0; }
    int w = (int)PyLong_AsLong(result);
    Py_DECREF(result);
    return w > 0 ? w : 0;
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
    .tp_name      = "terminal._buffer.Buffer",
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
    if (PyUnicode_IS_ASCII(line) &&
        PyUnicode_FindChar(line, 0x1B, 0, len, 1) < 0) {
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
            if (pos + 1 < len && PyUnicode_READ(kind, data, pos + 1) == '[') {
                Py_ssize_t end = pos + 2;
                while (end < len && PyUnicode_READ(kind, data, end) != 'm')
                    end++;
                parse_sgr(data, kind, pos + 2, end, &fg, &bg, &flags);
                style = fg | (bg << BG_SHIFT) | (flags << FLAGS_SHIFT);
                pos = end + 1;
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

/* ── Module definition ─────────────────────────────────────────────── */

static PyMethodDef module_methods[] = {
    {"parse_line",  mod_parse_line,  METH_VARARGS, "Parse ANSI line into buffer row."},
    {"render_full", mod_render_full, METH_VARARGS, "Render entire buffer to ANSI."},
    {"render_diff", mod_render_diff, METH_VARARGS, "Render cell-level diff to ANSI."},
    {NULL}
};

static struct PyModuleDef module_def = {
    PyModuleDef_HEAD_INIT,
    .m_name    = "terminal._buffer",
    .m_doc     = "C-accelerated cell buffer for terminal rendering.",
    .m_size    = -1,
    .m_methods = module_methods,
};

PyMODINIT_FUNC PyInit__buffer(void) {
    if (PyType_Ready(&BufferType) < 0)
        return NULL;

    PyObject *m = PyModule_Create(&module_def);
    if (!m) return NULL;

    Py_INCREF(&BufferType);
    if (PyModule_AddObject(m, "Buffer", (PyObject *)&BufferType) < 0) {
        Py_DECREF(&BufferType);
        Py_DECREF(m);
        return NULL;
    }

    if (PyModule_AddIntConstant(m, "EMPTY", STYLE_EMPTY) < 0) {
        Py_DECREF(m);
        return NULL;
    }

    if (init_wcwidth() < 0) {
        Py_DECREF(m);
        return NULL;
    }

    return m;
}
