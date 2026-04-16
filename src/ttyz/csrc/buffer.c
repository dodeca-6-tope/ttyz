/*
 * buffer.c — Cell-based terminal buffer: ANSI in, ANSI out.
 *
 * Buffer type (2D cell grid) with dump and diff methods.
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

/* ── dump ─────────────────────────────────────────────────────────── */

static PyObject *Buffer_dump(BufferObject *self, PyObject *args) {
    int w = self->width;
    int h = self->height;
    Cell *cells = self->cells;

    OutBuf out;
    if (outbuf_init(&out, (size_t)(w * h) * 8 + (size_t)h * 16 + 64) < 0)
        return PyErr_NoMemory();

    Style active = STYLE_EMPTY;

    for (int row = 0; row < h; row++) {
        if (row > 0)
            outbuf_add(&out, "\n", 1);

        int off = row * w;

        /* Find rightmost written cell (strip trailing unwritten). */
        int last = w - 1;
        while (last >= 0 && cells[off + last].ch == UNWRITTEN)
            last--;

        for (int col = 0; col <= last; col++) {
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
    {"dump",        (PyCFunction)Buffer_dump,          METH_NOARGS,  "Newline-separated styled rows."},
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
