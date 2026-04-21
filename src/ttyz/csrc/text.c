/*
 * text.c — Text string utilities.
 *
 * truncate_line, wrap_line_into — used by render.c.
 */

/* ── slice_ansi_visible ───────────────────────────────────────────── */
/*
 * Extract the substring occupying visible columns [vis_start, vis_end)
 * while preserving every escape sequence in the source verbatim, so
 * SGR state (colors, attributes) carries through into the slice.
 */
static PyObject *slice_ansi_visible(PyObject *s, int vis_start, int vis_end) {
    Py_ssize_t len = PyUnicode_GET_LENGTH(s);
    int kind = PyUnicode_KIND(s);
    const void *data = PyUnicode_DATA(s);

    OutBuf ob;
    if (outbuf_init(&ob, (size_t)len) < 0) return PyErr_NoMemory();

    int vi = 0;
    for (Py_ssize_t pos = 0; pos < len; ) {
        Py_UCS4 ch = PyUnicode_READ(kind, data, pos);
        if (ch == 0x1B) {
            Py_ssize_t end = skip_escape(data, kind, pos, len);
            for (Py_ssize_t k = pos; k < end; k++) {
                char u8[4];
                Py_UCS4 ec = PyUnicode_READ(kind, data, k);
                outbuf_add(&ob, u8, (size_t)encode_utf8(ec, u8));
            }
            pos = end;
        } else {
            int cw = cwidth(ch);
            if (vi >= vis_start && vi + cw <= vis_end) {
                char u8[4];
                outbuf_add(&ob, u8, (size_t)encode_utf8(ch, u8));
            }
            vi += cw;
            pos++;
        }
    }
    return outbuf_to_pystr(&ob);
}

/* ── truncate_line (head / middle / tail) ─────────────────────────── */
/*
 * Truncate a single line to `width` visible columns with ellipsis.
 * Preserves ANSI escape sequences so colored text stays colored after
 * truncation. Returns a new Python string.
 */
static PyObject *truncate_line(PyObject *raw_line, int width, char mode) {
    Py_ssize_t rlen = PyUnicode_GET_LENGTH(raw_line);
    int has_esc = (PyUnicode_FindChar(raw_line, 0x1B, 0, rlen, 1) >= 0);

    /* ANSI-aware path. */
    if (has_esc) {
        int vw = str_display_width(raw_line);
        if (vw <= width) {
            Py_INCREF(raw_line);
            return raw_line;
        }
        if (width <= 0)
            return PyUnicode_FromStringAndSize("", 0);

        PyObject *ell = PyUnicode_FromString("\xe2\x80\xa6");
        if (!ell) return NULL;
        PyObject *result = NULL;

        if (mode == 'h') {
            int budget = width - 1;
            PyObject *right = slice_ansi_visible(raw_line, vw - budget, vw);
            if (!right) { Py_DECREF(ell); return NULL; }
            result = PyUnicode_Concat(ell, right);
            Py_DECREF(right);
        } else if (mode == 'm') {
            int left_w = (width - 1) / 2;
            int right_w = width - 1 - left_w;
            PyObject *left = slice_ansi_visible(raw_line, 0, left_w);
            if (!left) { Py_DECREF(ell); return NULL; }
            PyObject *right = slice_ansi_visible(raw_line, vw - right_w, vw);
            if (!right) { Py_DECREF(left); Py_DECREF(ell); return NULL; }
            result = PyUnicode_FromFormat("%U%U%U", left, ell, right);
            Py_DECREF(left);
            Py_DECREF(right);
        } else {
            int budget = width - 1;
            PyObject *left = slice_ansi_visible(raw_line, 0, budget);
            if (!left) { Py_DECREF(ell); return NULL; }
            result = PyUnicode_Concat(left, ell);
            Py_DECREF(left);
        }
        Py_DECREF(ell);
        return result;
    }

    /* Plain text path: operate on raw_line directly. */
    PyObject *line = raw_line;
    Py_INCREF(line);

    int dw = str_display_width(line);
    if (dw <= width) {
        return line; /* already owns ref */
    }
    if (width <= 0) {
        Py_DECREF(line);
        return PyUnicode_FromStringAndSize("", 0);
    }

    Py_ssize_t len = PyUnicode_GET_LENGTH(line);
    int kind = PyUnicode_KIND(line);
    const void *data = PyUnicode_DATA(line);

    PyObject *result = NULL;

    if (mode == 'h') {
        /* head: "…<tail>" — scan from the right */
        int budget = width - 1;
        int w = 0;
        Py_ssize_t i = len;
        while (i > 0) {
            Py_UCS4 ch = PyUnicode_READ(kind, data, i - 1);
            int cw = cwidth(ch);
            if (w + cw > budget) break;
            w += cw;
            i--;
        }
        int gap = budget - w;
        PyObject *ell = PyUnicode_FromString("\xe2\x80\xa6");
        if (!ell) goto done;
        PyObject *tail = PyUnicode_Substring(line, i, len);
        if (!tail) { Py_DECREF(ell); goto done; }
        if (gap > 0) {
            PyObject *sp = make_spaces(gap);
            if (!sp) { Py_DECREF(ell); Py_DECREF(tail); goto done; }
            result = PyUnicode_FromFormat("%U%U%U", ell, sp, tail);
            Py_DECREF(sp);
        } else {
            result = PyUnicode_FromFormat("%U%U", ell, tail);
        }
        Py_DECREF(ell);
        Py_DECREF(tail);
    } else if (mode == 'm') {
        /* middle: "<left>…<right>" */
        int left_w = (width - 1) / 2;
        int right_w = width - 1 - left_w;
        int w = 0;
        Py_ssize_t li = 0;
        while (li < len && w < left_w) {
            w += cwidth(PyUnicode_READ(kind, data, li));
            if (w <= left_w) li++;
            else break;
        }
        PyObject *left = PyUnicode_Substring(line, 0, li);
        if (!left) goto done;
        w = 0;
        Py_ssize_t ri = len;
        while (ri > 0 && w < right_w) {
            Py_UCS4 ch = PyUnicode_READ(kind, data, ri - 1);
            int cw = cwidth(ch);
            if (w + cw <= right_w) { w += cw; ri--; }
            else break;
        }
        PyObject *right = PyUnicode_Substring(line, ri, len);
        if (!right) { Py_DECREF(left); goto done; }
        PyObject *ell = PyUnicode_FromString("\xe2\x80\xa6");
        if (!ell) { Py_DECREF(left); Py_DECREF(right); goto done; }
        result = PyUnicode_FromFormat("%U%U%U", left, ell, right);
        Py_DECREF(left);
        Py_DECREF(ell);
        Py_DECREF(right);
    } else {
        /* tail (default): "<head>…" */
        int w = 0;
        int budget = width - 1;
        Py_ssize_t cut = 0;
        while (cut < len) {
            int cw = cwidth(PyUnicode_READ(kind, data, cut));
            if (w + cw > budget) break;
            w += cw;
            cut++;
        }
        PyObject *head = PyUnicode_Substring(line, 0, cut);
        if (!head) goto done;
        PyObject *ell = PyUnicode_FromString("\xe2\x80\xa6");
        if (!ell) { Py_DECREF(head); goto done; }
        result = PyUnicode_Concat(head, ell);
        Py_DECREF(head);
        Py_DECREF(ell);
    }

done:
    Py_DECREF(line);
    return result;
}

/* ── wrap_line ────────────────────────────────────────────────────── */
/*
 * Word-wrap a single line into a Python list of strings.
 * Splits on spaces, falls back to character-wrap for long words.
 * Appends results to `out` (a Python list).  Returns 0 on success, -1 on error.
 */
static int wrap_line_into(PyObject *line, int width, PyObject *out) {
    if (width <= 0 || str_display_width(line) <= width) {
        Py_INCREF(line);
        return PyList_Append(out, line) < 0 ? (Py_DECREF(line), -1) : (Py_DECREF(line), 0);
    }

    /* Split on spaces. */
    PyObject *sep = PyUnicode_FromStringAndSize(" ", 1);
    if (!sep) return -1;
    PyObject *words = PyUnicode_Split(line, sep, -1);
    Py_DECREF(sep);
    if (!words) return -1;

    Py_ssize_t nwords = PyList_GET_SIZE(words);
    /* current: the line being built.  Always an owned ref. */
    PyObject *current = PyUnicode_FromStringAndSize("", 0);
    if (!current) { Py_DECREF(words); return -1; }
    int cur_w = 0;
    int err = 0;

    for (Py_ssize_t i = 0; i < nwords; i++) {
        /* own_word: owned copy of the word (NULL = use borrowed from list). */
        PyObject *own_word = NULL;
        PyObject *word = PyList_GET_ITEM(words, i); /* borrowed */
        int word_w = str_display_width(word);
        int needed = cur_w > 0 ? cur_w + 1 + word_w : word_w;

        if (needed <= width) {
            PyObject *joined;
            if (cur_w > 0) {
                joined = PyUnicode_FromFormat("%U %U", current, word);
            } else {
                Py_INCREF(word);
                joined = word;
            }
            Py_DECREF(current);
            if (!joined) { err = 1; current = NULL; break; }
            current = joined;
            cur_w = needed;
            continue;
        }

        /* Flush current line if non-empty. */
        if (cur_w > 0) {
            if (PyList_Append(out, current) < 0) { err = 1; break; }
            Py_DECREF(current);
            current = PyUnicode_FromStringAndSize("", 0);
            if (!current) { err = 1; break; }
            cur_w = 0;
        }

        /* Character-wrap long words. */
        while (word_w > width) {
            Py_ssize_t wlen = PyUnicode_GET_LENGTH(word);
            int wkind = PyUnicode_KIND(word);
            const void *wdata = PyUnicode_DATA(word);
            int w = 0;
            Py_ssize_t cut = 0;
            while (cut < wlen) {
                int cw = cwidth(PyUnicode_READ(wkind, wdata, cut));
                if (w + cw > width) break;
                w += cw;
                cut++;
            }
            /* Avoid splitting ZWJ emoji sequences (e.g. 👩‍🔧).
               If cut lands right after a ZWJ, backtrack to before
               the cluster so the whole sequence stays on one line. */
            {
                Py_ssize_t safe = cut;
                while (safe > 0) {
                    Py_UCS4 prev = PyUnicode_READ(wkind, wdata, safe - 1);
                    if (prev != 0x200D) break;
                    /* Back past ZWJ */
                    safe--;
                    /* Back past zero-width modifiers (VS, combining) */
                    while (safe > 0) {
                        Py_UCS4 ch = PyUnicode_READ(wkind, wdata, safe - 1);
                        if (cwidth(ch) == 0 && ch != 0x200D) safe--;
                        else break;
                    }
                    /* Back past the base character */
                    if (safe > 0) safe--;
                }
                if (safe > 0 && safe < cut) cut = safe;
            }
            if (cut == 0) cut = 1;
            PyObject *chunk = PyUnicode_Substring(word, 0, cut);
            if (!chunk) { err = 1; break; }
            if (PyList_Append(out, chunk) < 0) {
                Py_DECREF(chunk); err = 1; break;
            }
            Py_DECREF(chunk);
            PyObject *rest = PyUnicode_Substring(word, cut, wlen);
            if (!rest) { err = 1; break; }
            Py_XDECREF(own_word); /* free previous owned copy */
            own_word = rest;
            word = rest;
            word_w = str_display_width(word);
        }
        if (err) break;

        /* Remainder fits on a new line — becomes new current. */
        Py_DECREF(current);
        Py_INCREF(word);
        current = word;
        cur_w = word_w;
        Py_XDECREF(own_word);
    }

    if (!err) {
        /* Flush last line. */
        if (cur_w > 0 || PyList_GET_SIZE(out) == 0) {
            if (PyList_Append(out, current) < 0) err = 1;
        }
    }
    Py_XDECREF(current);
    Py_DECREF(words);
    return err ? -1 : 0;
}

/* end of text.c */
