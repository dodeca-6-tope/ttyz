/*
 * buffer.c — Cell-based terminal buffer: ANSI in, ANSI out.
 *
 * Buffer type (2D cell grid) with parse_line, dump, and diff methods.
 */

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
        Py_UCS4 ch = cells[i].ch;
        if (ch == WIDE_CHAR) continue;
        if (ch == UNWRITTEN) ch = ' ';
        len += encode_utf8(ch, utf8 + len);
    }
    PyObject *result = PyUnicode_DecodeUTF8(utf8, len, NULL);
    free(utf8);
    return result;
}

/* ── row_styled — ANSI-styled text for one row ────────────────────── */

static PyObject *Buffer_row_styled(BufferObject *self, PyObject *args) {
    int row;
    if (!PyArg_ParseTuple(args, "i", &row)) return NULL;
    if (row < 0 || row >= self->height) {
        PyErr_SetString(PyExc_IndexError, "row out of range");
        return NULL;
    }

    int w = self->width;
    Cell *cells = self->cells + row * w;

    /* Find rightmost written cell (strip trailing unwritten cells). */
    int last = w - 1;
    while (last >= 0 && cells[last].ch == UNWRITTEN)
        last--;

    if (last < 0) {
        /* Entirely blank row. */
        return PyUnicode_FromStringAndSize("", 0);
    }

    OutBuf out;
    if (outbuf_init(&out, (size_t)(last + 1) * 8 + 64) < 0)
        return PyErr_NoMemory();

    Style active = STYLE_EMPTY;
    for (int i = 0; i <= last; i++) {
        Cell c = cells[i];
        if (c.ch == WIDE_CHAR) continue;
        if (!style_eq(c.style, active)) {
            emit_sgr(&out, c.style);
            active = c.style;
        }
        Py_UCS4 ch = (c.ch == UNWRITTEN) ? ' ' : c.ch;
        char u8[4];
        int u8len = encode_utf8(ch, u8);
        outbuf_add(&out, u8, (size_t)u8len);
    }

    if (!style_is_empty(active))
        outbuf_add(&out, "\033[0m", 4);

    return outbuf_to_pystr(&out);
}

/* ── parse_line ────────────────────────────────────────────────────── */

static PyObject *Buffer_parse_line(BufferObject *self, PyObject *args) {
    int row;
    PyObject *line;

    if (!PyArg_ParseTuple(args, "iU", &row, &line))
        return NULL;
    if (row < 0 || row >= self->height) {
        PyErr_SetString(PyExc_IndexError, "row out of range");
        return NULL;
    }

    int w = self->width;
    Cell *cells = self->cells + row * w;
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
    Color fg = COLOR_EMPTY, bg = COLOR_EMPTY;
    uint16_t flags = 0;
    Style style = STYLE_EMPTY;

    while (pos < len && col < w) {
        Py_UCS4 ch = PyUnicode_READ(kind, data, pos);

        if (ch == 0x1B) {
            if (pos + 1 < len &&
                PyUnicode_READ(kind, data, pos + 1) == '[') {
                /* CSI: scan to final byte, parse SGR */
                Py_ssize_t end = pos + 2;
                while (end < len) {
                    Py_UCS4 fb = PyUnicode_READ(kind, data, end);
                    end++;
                    if (fb >= 0x40 && fb <= 0x7E) break;
                }
                /* Only parse SGR (final byte 'm'); skip other CSI. */
                if (PyUnicode_READ(kind, data, end - 1) == 'm')  {
                    parse_sgr(data, kind, pos + 2, end - 1,
                              &fg, &bg, &flags);
                    style = (Style){fg, bg, flags, {0, 0}};
                }
                pos = end;
            } else {
                pos = skip_escape(data, kind, pos, len);
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

/* ── dump ─────────────────────────────────────────────────────────── */

static PyObject *Buffer_dump(BufferObject *self, PyObject *args) {
    int w = self->width;
    int h = self->height;
    Cell *cells = self->cells;

    OutBuf out;
    if (outbuf_init(&out, (size_t)(w * h) * 8 + (size_t)h * 16 + 64) < 0)
        return PyErr_NoMemory();

    outbuf_add(&out, "\033[0m", 4);  /* reset to known state */
    Style active = STYLE_EMPTY;

    for (int row = 0; row < h; row++) {
        outbuf_moveto(&out, row + 1, 1);
        int off = row * w;
        for (int col = 0; col < w; col++) {
            Cell c = cells[off + col];
            if (c.ch == WIDE_CHAR) continue;
            if (!style_eq(c.style, active)) {
                emit_sgr(&out, c.style);
                active = c.style;
            }
            Py_UCS4 ch = (c.ch == UNWRITTEN) ? ' ' : c.ch;
            char u8[4];
            int u8len = encode_utf8(ch, u8);
            outbuf_add(&out, u8, (size_t)u8len);
        }
    }

    if (!style_is_empty(active))
        outbuf_add(&out, "\033[0m", 4);

    return outbuf_to_pystr(&out);
}

/* ── diff ──────────────────────────────────────────────────────────── */

static PyObject *Buffer_diff(BufferObject *self, PyObject *args) {
    BufferObject *prev;
    if (!PyArg_ParseTuple(args, "O!", &BufferType, &prev))
        return NULL;

    if (self->width != prev->width || self->height != prev->height) {
        PyErr_SetString(PyExc_ValueError,
                        "diff requires buffers with the same dimensions");
        return NULL;
    }

    int w = self->width;
    int h = self->height;
    Cell *cc = self->cells;
    Cell *pc = prev->cells;

    OutBuf out;
    if (outbuf_init(&out, 4096) < 0)
        return PyErr_NoMemory();

    Style active = STYLE_EMPTY;

    for (int row = 0; row < h; row++) {
        int off = row * w;

        /* Skip identical rows */
        if (memcmp(cc + off, pc + off, (size_t)w * sizeof(Cell)) == 0)
            continue;

        int col = 0;
        while (col < w) {
            Cell c = cc[off + col];
            Cell p = pc[off + col];
            if (c.ch == p.ch && style_eq(c.style, p.style)) { col++; continue; }
            if (c.ch == WIDE_CHAR) { col++; continue; }

            /* Start a dirty run */
            outbuf_moveto(&out, row + 1, col + 1);
            if (!style_eq(c.style, active)) {
                emit_sgr(&out, c.style);
                active = c.style;
            }
            Py_UCS4 ch = (c.ch == UNWRITTEN) ? ' ' : c.ch;
            char u8[4];
            outbuf_add(&out, u8, (size_t)encode_utf8(ch, u8));
            col++;

            /* Extend run with adjacent dirty cells */
            while (col < w) {
                Cell c2 = cc[off + col];
                Cell p2 = pc[off + col];
                if (c2.ch == p2.ch && style_eq(c2.style, p2.style)) break;
                if (c2.ch == WIDE_CHAR) { col++; continue; }
                if (!style_eq(c2.style, active)) {
                    emit_sgr(&out, c2.style);
                    active = c2.style;
                }
                Py_UCS4 ch2 = (c2.ch == UNWRITTEN) ? ' ' : c2.ch;
                outbuf_add(&out, u8, (size_t)encode_utf8(ch2, u8));
                col++;
            }
        }
    }

    if (!style_is_empty(active))
        outbuf_add(&out, "\033[0m", 4);

    return outbuf_to_pystr(&out);
}

/* ── Method table ─────────────────────────────────────────────────── */

static PyMethodDef Buffer_methods[] = {
    {"row_text",    (PyCFunction)Buffer_row_text,    METH_VARARGS, "Plain text of a row."},
    {"row_styled",  (PyCFunction)Buffer_row_styled,  METH_VARARGS, "ANSI-styled text of a row."},
    {"parse_line",  (PyCFunction)Buffer_parse_line,  METH_VARARGS, "Parse ANSI line into a row."},
    {"dump",        (PyCFunction)Buffer_dump,          METH_NOARGS,  "Serialize entire buffer to ANSI."},
    {"diff",        (PyCFunction)Buffer_diff,         METH_VARARGS, "Render cell-level diff to ANSI."},
    {NULL}
};

static PyMemberDef Buffer_members[] = {
    {"width",  Py_T_INT, offsetof(BufferObject, width),  Py_READONLY, NULL},
    {"height", Py_T_INT, offsetof(BufferObject, height), Py_READONLY, NULL},
    {NULL}
};

static PyTypeObject BufferType = {
    .ob_base      = PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name      = "ttyz.ext.Buffer",
    .tp_basicsize = sizeof(BufferObject),
    .tp_flags     = Py_TPFLAGS_DEFAULT,
    .tp_new       = PyType_GenericNew,
    .tp_init      = (initproc)Buffer_init,
    .tp_dealloc   = (destructor)Buffer_dealloc,
    .tp_methods   = Buffer_methods,
    .tp_members   = Buffer_members,
    .tp_doc       = "Fixed-size 2D grid of styled cells.",
};
