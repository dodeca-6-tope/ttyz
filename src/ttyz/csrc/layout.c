/*
 * layout.c — Spatial arrangement of content.
 *
 * pad_columns:      pad strings to column widths, join with spacing
 * place_at_offsets: place strings at absolute positions in a line
 * flex_distribute:  resolve flex basis + grow into column widths
 * distribute:       proportional integer distribution (Bresenham-style)
 */

/* ── place_at_offsets ─────────────────────────────────────────────── */
/*
 * place_at_offsets(items) -> str
 *
 * items: list of (offset: int, col_width: int, content: str)
 * Builds a single line by placing each content at its offset, padded to
 * col_width.  Gaps between items are filled with spaces.
 */
static PyObject *mod_place_at_offsets(PyObject *self, PyObject *arg) {
    if (!PyList_Check(arg)) {
        PyErr_SetString(PyExc_TypeError, "expected a list");
        return NULL;
    }

    Py_ssize_t n = PyList_GET_SIZE(arg);
    if (n == 0) return PyUnicode_FromString("");

    /* Validate items are tuples of length >= 3. */
    for (Py_ssize_t i = 0; i < n; i++) {
        PyObject *item = PyList_GET_ITEM(arg, i);
        if (!PyTuple_Check(item) || PyTuple_GET_SIZE(item) < 3) {
            PyErr_SetString(PyExc_TypeError,
                            "each item must be a tuple (offset, col_width, content)");
            return NULL;
        }
    }

    /* First pass: compute total output width from last item. */
    PyObject *last = PyList_GET_ITEM(arg, n - 1);
    long last_off = PyLong_AsLong(PyTuple_GET_ITEM(last, 0));
    long last_cw  = PyLong_AsLong(PyTuple_GET_ITEM(last, 1));
    if (last_off < 0) last_off = 0;
    if (last_cw < 0) last_cw = 0;
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

/* ── pad_columns ─────────────────────────────────────────────────── */
/*
 * pad_columns(cells, col_widths, spacing) -> str
 *
 * cells:      list[str]  — rendered content for each column
 * col_widths: list[int]  — target width for each column
 * spacing:    int        — gap between columns
 *
 * For each cell: pad content to col_width with spaces, join with spacing.
 * ANSI-aware: skips escape sequences when measuring content width.
 */
static PyObject *mod_pad_columns(PyObject *self, PyObject *args) {
    PyObject *cells, *widths;
    int spacing;
    if (!PyArg_ParseTuple(args, "OOi", &cells, &widths, &spacing))
        return NULL;

    if (!PyList_Check(cells) || !PyList_Check(widths)) {
        PyErr_SetString(PyExc_TypeError, "cells and col_widths must be lists");
        return NULL;
    }

    Py_ssize_t n = PyList_GET_SIZE(cells);
    if (n == 0) return PyUnicode_FromString("");

    if (PyList_GET_SIZE(widths) != n) {
        PyErr_SetString(PyExc_ValueError,
                        "cells and col_widths must have the same length");
        return NULL;
    }

    /* Compute total output length (clamp negative widths to 0). */
    Py_ssize_t total = 0;
    for (Py_ssize_t i = 0; i < n; i++) {
        long w = PyLong_AsLong(PyList_GET_ITEM(widths, i));
        total += w > 0 ? w : 0;
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
            if (cw < 0) cw = 0;
            PyObject *cell = PyList_GET_ITEM(cells, i);
            Py_ssize_t clen = PyUnicode_GET_LENGTH(cell);
            Py_ssize_t copy = clen < cw ? clen : cw;
            if (copy > 0)
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
            outbuf_spaces(&ob, spacing);

        long cw = PyLong_AsLong(PyList_GET_ITEM(widths, i));
        if (cw < 0) cw = 0;
        PyObject *cell = PyList_GET_ITEM(cells, i);
        Py_ssize_t clen = PyUnicode_GET_LENGTH(cell);
        int kind = PyUnicode_KIND(cell);
        const void *data = PyUnicode_DATA(cell);

        int vis = 0;
        for (Py_ssize_t j = 0; j < clen; ) {
            Py_UCS4 ch = PyUnicode_READ(kind, data, j);
            char u8[4];

            if (ch == 0x1B) {
                Py_ssize_t end = skip_escape(data, kind, j, clen);
                for (Py_ssize_t k = j; k < end; k++) {
                    Py_UCS4 ec = PyUnicode_READ(kind, data, k);
                    outbuf_add(&ob, u8, encode_utf8(ec, u8));
                }
                j = end;
            } else {
                int chw = cwidth(ch);
                if (vis + chw > (int)cw) break;
                outbuf_add(&ob, u8, encode_utf8(ch, u8));
                vis += chw;
                j++;
            }
        }

        outbuf_spaces(&ob, (int)cw - vis);
    }

    return outbuf_to_pystr(&ob);
}

/* ── flex_distribute ────────────────────────────────────────────── */
/*
 * flex_distribute(bases, grows, width, spacing) -> list[int]
 *
 * bases:   list[int] — flex_basis for each column
 * grows:   list[int] — grow weight for each column (0 = fixed)
 * width:   int       — total available width
 * spacing: int       — gap between columns
 *
 * Returns resolved column widths with remaining space distributed
 * proportionally among grow columns.
 */
static PyObject *mod_flex_distribute(PyObject *self, PyObject *args) {
    PyObject *bases, *grows;
    int width, spacing;
    if (!PyArg_ParseTuple(args, "OOii", &bases, &grows, &width, &spacing))
        return NULL;

    Py_ssize_t n = PyList_GET_SIZE(bases);

    /* Build col_widths, collect grow weights (single allocation). */
    long *buf = (long *)malloc(3 * (size_t)n * sizeof(long));
    if (!buf) return PyErr_NoMemory();
    long *col_widths = buf;
    long *grow_idx   = buf + n;
    long *grow_wt    = buf + 2 * n;

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
    if (!result) { free(buf); return NULL; }
    for (Py_ssize_t i = 0; i < n; i++)
        PyList_SET_ITEM(result, i, PyLong_FromLong(col_widths[i]));

    free(buf);
    return result;
}

/* ── distribute ───────────────────────────────────────────────────── */
/*
 * distribute(total, weights) -> list[int]
 *
 * Distribute total proportionally among weighted slots using cumulative
 * rounding (Bresenham-style) to avoid fractional remainders.
 */
static PyObject *mod_distribute(PyObject *self, PyObject *args) {
    int total;
    PyObject *weights;
    if (!PyArg_ParseTuple(args, "iO", &total, &weights))
        return NULL;

    if (!PyList_Check(weights)) {
        PyErr_SetString(PyExc_TypeError, "weights must be a list");
        return NULL;
    }

    Py_ssize_t n = PyList_GET_SIZE(weights);
    if (n == 0)
        return PyList_New(0);

    /* Unbox weights once into a C array. */
    long *wt = (long *)malloc((size_t)n * sizeof(long));
    if (!wt) return PyErr_NoMemory();

    long total_weight = 0;
    for (Py_ssize_t i = 0; i < n; i++) {
        wt[i] = PyLong_AsLong(PyList_GET_ITEM(weights, i));
        total_weight += wt[i];
    }

    PyObject *result = PyList_New(n);
    if (!result) { free(wt); return NULL; }

    if (total_weight == 0) {
        for (Py_ssize_t i = 0; i < n; i++)
            PyList_SET_ITEM(result, i, PyLong_FromLong(0));
        free(wt);
        return result;
    }

    long cum_weight = 0, cum_space = 0;
    for (Py_ssize_t i = 0; i < n; i++) {
        cum_weight += wt[i];
        long target = (long)total * cum_weight / total_weight;
        PyList_SET_ITEM(result, i, PyLong_FromLong(target - cum_space));
        cum_space = target;
    }
    free(wt);
    return result;
}
