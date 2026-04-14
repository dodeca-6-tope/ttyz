/*
 * text.c — Text measurement, transformation, and rendering.
 *
 * Pure string utilities (display_width, char_width, strip_ansi, truncate,
 * slice_at_width) plus TextRender type.
 */

/* ── char_width ──────────────────────────────────────────────────── */

static PyObject *mod_char_width(PyObject *self, PyObject *arg) {
    if (!PyUnicode_Check(arg) || PyUnicode_GET_LENGTH(arg) != 1) {
        PyErr_SetString(PyExc_TypeError, "expected a single character");
        return NULL;
    }
    Py_UCS4 ch = PyUnicode_READ_CHAR(arg, 0);
    return PyLong_FromLong(cwidth(ch));
}

/* ── display_width ────────────────────────────────────────────────── */

static PyObject *mod_display_width(PyObject *self, PyObject *arg) {
    if (!PyUnicode_Check(arg)) {
        PyErr_SetString(PyExc_TypeError, "expected a string");
        return NULL;
    }
    return PyLong_FromLong(str_display_width(arg));
}

/* ── strip_ansi ──────────────────────────────────────────────────── */
/*
 * strip_ansi(s) -> str
 *
 * Remove all escape sequences (CSI, OSC, etc.) from a string.
 * Bulk-copies spans between escapes instead of encoding char-by-char.
 */
static PyObject *mod_strip_ansi(PyObject *self, PyObject *arg) {
    if (!PyUnicode_Check(arg)) {
        PyErr_SetString(PyExc_TypeError, "expected a string");
        return NULL;
    }

    Py_ssize_t len = PyUnicode_GET_LENGTH(arg);

    /* Fast: no ESC at all. */
    if (PyUnicode_FindChar(arg, 0x1B, 0, len, 1) < 0) {
        Py_INCREF(arg);
        return arg;
    }

    /* ASCII fast path: work directly with bytes, bulk-copy spans. */
    if (PyUnicode_IS_ASCII(arg)) {
        const char *src = PyUnicode_AsUTF8(arg);
        char *buf = (char *)malloc((size_t)len);
        if (!buf) return PyErr_NoMemory();
        Py_ssize_t out = 0;
        Py_ssize_t pos = 0;
        while (pos < len) {
            /* Find next ESC. */
            Py_ssize_t esc = pos;
            while (esc < len && src[esc] != '\033') esc++;
            /* Copy span before ESC. */
            if (esc > pos) {
                memcpy(buf + out, src + pos, (size_t)(esc - pos));
                out += esc - pos;
            }
            if (esc >= len) break;
            /* Skip escape sequence (CSI, OSC, or other). */
            pos = skip_escape_ascii(src, esc, len);
        }
        PyObject *result = PyUnicode_FromStringAndSize(buf, out);
        free(buf);
        return result;
    }

    /* Non-ASCII: scan codepoints, bulk-copy via PyUnicode_Substring. */
    int kind = PyUnicode_KIND(arg);
    const void *data = PyUnicode_DATA(arg);

    /* Single pass: count non-escape characters and find max codepoint. */
    Py_ssize_t out_len = 0;
    Py_UCS4 maxchar = 0;
    for (Py_ssize_t pos = 0; pos < len; ) {
        Py_UCS4 ch = PyUnicode_READ(kind, data, pos);
        if (ch == 0x1B) {
            pos = skip_escape(data, kind, pos, len);
        } else {
            if (ch > maxchar) maxchar = ch;
            out_len++;
            pos++;
        }
    }

    PyObject *result = PyUnicode_New(out_len, maxchar);
    if (!result) return NULL;

    int out_kind = PyUnicode_KIND(result);
    void *out_data = PyUnicode_DATA(result);
    Py_ssize_t out_pos = 0;
    for (Py_ssize_t pos = 0; pos < len; ) {
        Py_UCS4 ch = PyUnicode_READ(kind, data, pos);
        if (ch == 0x1B) {
            pos = skip_escape(data, kind, pos, len);
        } else {
            PyUnicode_WRITE(out_kind, out_data, out_pos++, ch);
            pos++;
        }
    }

    return result;
}

/* ── slice_at_width ──────────────────────────────────────────────── */
/*
 * slice_at_width(s, max_width) -> str
 *
 * Slice a plain (non-ANSI) string to fit within max_width display columns.
 */
static PyObject *mod_slice_at_width(PyObject *self, PyObject *args) {
    PyObject *s;
    int max_width;
    if (!PyArg_ParseTuple(args, "Ui", &s, &max_width))
        return NULL;

    if (max_width <= 0)
        return PyUnicode_FromStringAndSize("", 0);

    Py_ssize_t len = PyUnicode_GET_LENGTH(s);

    /* ASCII fast path: width == length. */
    if (PyUnicode_IS_ASCII(s)) {
        if (len <= max_width) {
            Py_INCREF(s);
            return s;
        }
        return PyUnicode_Substring(s, 0, max_width);
    }

    /* Wide-char scan. */
    int kind = PyUnicode_KIND(s);
    const void *data = PyUnicode_DATA(s);
    int w = 0;
    for (Py_ssize_t i = 0; i < len; i++) {
        Py_UCS4 ch = PyUnicode_READ(kind, data, i);
        int cw = cwidth(ch);
        if (w + cw > max_width)
            return PyUnicode_Substring(s, 0, i);
        w += cw;
    }
    Py_INCREF(s);
    return s;
}

/* ── truncate ────────────────────────────────────────────────────── */
/*
 * truncate(s, max_width, ellipsis=False) -> str
 *
 * Truncate a string to max_width visible characters.
 * If ellipsis is true and the string is truncated, append "...".
 * Single-pass: scans characters and stops as soon as the budget is hit,
 * never measuring the full string when truncation is needed.
 */
static PyObject *mod_truncate(PyObject *self, PyObject *args, PyObject *kw) {
    PyObject *s;
    int max_width;
    int ellipsis = 0;
    static char *kwlist[] = {"s", "max_width", "ellipsis", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kw, "Ui|p", kwlist,
                                      &s, &max_width, &ellipsis))
        return NULL;

    if (max_width <= 0)
        return PyUnicode_FromStringAndSize("", 0);

    Py_ssize_t len = PyUnicode_GET_LENGTH(s);
    int has_esc = (PyUnicode_FindChar(s, 0x1B, 0, len, 1) >= 0);

    /* ── No escapes: single-pass scan + truncate ──────────────── */
    if (!has_esc) {
        /* ASCII: width == length, no scan needed. */
        if (PyUnicode_IS_ASCII(s)) {
            if (len <= max_width) {
                Py_INCREF(s);
                return s;
            }
            int target = ellipsis ? max_width - 1 : max_width;
            if (target <= 0)
                return PyUnicode_FromStringAndSize("", 0);
            const char *src = PyUnicode_AsUTF8(s);
            if (ellipsis) {
                /* Build "head..." in one buffer. */
                char *buf = (char *)malloc((size_t)target + 3);
                if (!buf) return PyErr_NoMemory();
                memcpy(buf, src, (size_t)target);
                memcpy(buf + target, "\xe2\x80\xa6", 3);
                PyObject *result = PyUnicode_FromStringAndSize(buf, target + 3);
                free(buf);
                return result;
            }
            return PyUnicode_FromStringAndSize(src, target);
        }

        /* Non-ASCII, no escapes: single-pass width scan.
           We scan up to max_width visible columns. If we reach the end
           of the string within budget, return it unchanged. Otherwise
           truncate at the overflow point. */
        int kind = PyUnicode_KIND(s);
        const void *data = PyUnicode_DATA(s);
        int target = ellipsis ? max_width - 1 : max_width;
        int w = 0;
        Py_ssize_t cut = -1; /* position where we'd cut for truncation */
        for (Py_ssize_t i = 0; i < len; i++) {
            int cw = cwidth(PyUnicode_READ(kind, data, i));
            if (cut < 0 && w + cw > target)
                cut = i;
            if (w + cw > max_width) {
                /* Definitely needs truncation — cut was already set. */
                if (target <= 0)
                    return PyUnicode_FromStringAndSize("", 0);
                PyObject *head = PyUnicode_Substring(s, 0, cut);
                if (!head) return NULL;
                if (!ellipsis) return head;
                PyObject *ell = PyUnicode_FromString("\xe2\x80\xa6");
                if (!ell) { Py_DECREF(head); return NULL; }
                PyObject *result = PyUnicode_Concat(head, ell);
                Py_DECREF(head);
                Py_DECREF(ell);
                return result;
            }
            w += cw;
        }
        /* Fits within max_width. */
        Py_INCREF(s);
        return s;
    }

    /* ── ANSI path: single-pass clip, preserve escapes ────────── */
    int kind = PyUnicode_KIND(s);
    const void *data = PyUnicode_DATA(s);
    int target = ellipsis ? max_width - 1 : max_width;

    /* First check if total visible width fits — but bail early. */
    int vis = 0;
    int needs_trunc = 0;
    for (Py_ssize_t pos = 0; pos < len; ) {
        Py_UCS4 ch = PyUnicode_READ(kind, data, pos);
        if (ch == 0x1B) {
            pos = skip_escape(data, kind, pos, len);
        } else {
            vis += cwidth(ch);
            if (vis > max_width) { needs_trunc = 1; break; }
            pos++;
        }
    }
    if (!needs_trunc) {
        Py_INCREF(s);
        return s;
    }

    if (target <= 0)
        return PyUnicode_FromStringAndSize("", 0);

    /* ASCII ANSI fast path: bulk-copy spans between escapes. */
    if (PyUnicode_IS_ASCII(s)) {
        const char *src = PyUnicode_AsUTF8(s);
        /* Worst case: full input + reset + ellipsis. */
        char *buf = (char *)malloc((size_t)len + 7);
        if (!buf) return PyErr_NoMemory();
        Py_ssize_t out = 0;
        int w = 0;
        Py_ssize_t pos = 0;
        while (pos < len) {
            if (src[pos] == '\033') {
                /* Copy escape verbatim (CSI, OSC, or other). */
                Py_ssize_t esc_start = pos;
                pos = skip_escape_ascii(src, pos, len);
                memcpy(buf + out, src + esc_start, (size_t)(pos - esc_start));
                out += pos - esc_start;
            } else {
                /* ASCII: cwidth == 1 for printable. */
                if (w + 1 > target) break;
                buf[out++] = src[pos++];
                w++;
            }
        }
        memcpy(buf + out, "\033[0m", 4);
        out += 4;
        if (ellipsis) {
            memcpy(buf + out, "\xe2\x80\xa6", 3);
            out += 3;
        }
        PyObject *result = PyUnicode_DecodeUTF8(buf, out, NULL);
        free(buf);
        return result;
    }

    /* Non-ASCII ANSI: OutBuf path. */
    OutBuf ob;
    if (outbuf_init(&ob, (size_t)len) < 0)
        return PyErr_NoMemory();

    int w = 0;
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
            if (w + cw > target) break;
            char u8[4];
            outbuf_add(&ob, u8, (size_t)encode_utf8(ch, u8));
            w += cw;
            pos++;
        }
    }

    outbuf_add(&ob, "\033[0m", 4);
    if (ellipsis)
        outbuf_add(&ob, "\xe2\x80\xa6", 3);

    return outbuf_to_pystr(&ob);
}

/* ── truncate_line (head / middle / tail) ─────────────────────────── */
/*
 * Truncate a single line to `width` visible columns with ellipsis.
 * Operates on stripped (non-ANSI) text.  Returns a new Python string.
 */
static PyObject *truncate_line(PyObject *raw_line, int width, char mode) {
    /* Strip ANSI before truncating — head/middle/tail all operate on
       plain text.  If no escapes, stripped == raw_line (fast path). */
    PyObject *line = mod_strip_ansi(NULL, raw_line);
    if (!line) return NULL;

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

/* ── TextRender type ──────────────────────────────────────────────── */
/*
 * TextRender(value, truncation, pl, pr, wrap) — callable text renderer.
 *
 * Parses value into lines, computes visible_w, and selects a render mode.
 * Calling the instance with (w, h?) produces the rendered lines.
 */

#define TEXT_PLAIN    0
#define TEXT_PADDED   1
#define TEXT_FULL     2

typedef struct {
    PyObject_HEAD
    int       mode;       /* TEXT_PLAIN / TEXT_PADDED / TEXT_FULL */
    PyObject *lines;      /* list[str] — pre-computed */
    int       visible_w;  /* max display width of content lines */
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

static int CTextRender_init(CTextRenderObject *self, PyObject *args, PyObject *kw) {
    static char *kwlist[] = {"value", "truncation", "pl", "pr", "wrap", NULL};
    PyObject *value, *truncation;
    int pl, pr, wrap;

    if (!PyArg_ParseTupleAndKeywords(args, kw, "OOiip", kwlist,
                                      &value, &truncation, &pl, &pr, &wrap))
        return -1;

    /* Convert to string. */
    PyObject *raw;
    if (PyUnicode_Check(value)) {
        raw = value;
        Py_INCREF(raw);
    } else {
        raw = PyObject_Str(value);
        if (!raw) return -1;
    }

    /* Parse lines: split on \n, compute display_width. */
    PyObject *lines;
    int visible_w;
    Py_ssize_t rlen = PyUnicode_GET_LENGTH(raw);

    if (PyUnicode_FindChar(raw, '\n', 0, rlen, 1) < 0) {
        /* Single line (common case). */
        lines = PyList_New(1);
        if (!lines) { Py_DECREF(raw); return -1; }
        Py_INCREF(raw);
        PyList_SET_ITEM(lines, 0, raw);
        visible_w = str_display_width(raw);
    } else {
        /* Multi-line: split and measure each. */
        lines = PyUnicode_Splitlines(raw, 0);
        if (!lines) { Py_DECREF(raw); return -1; }
        Py_ssize_t n = PyList_GET_SIZE(lines);
        if (n == 0) {
            Py_DECREF(lines);
            lines = PyList_New(1);
            if (!lines) { Py_DECREF(raw); return -1; }
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

    /* Store fields — release any previous values on re-init. */
    Py_XDECREF(self->lines);
    Py_XDECREF(self->pad_l);
    Py_XDECREF(self->pad_r);
    Py_XDECREF(self->truncation);

    self->mode = mode;
    self->lines = lines;  /* owns the ref from creation above */
    self->visible_w = visible_w;
    self->pl = pl;
    self->pr = pr;
    self->pad_l = pl > 0 ? make_spaces(pl) : PyUnicode_FromStringAndSize("", 0);
    self->pad_r = pr > 0 ? make_spaces(pr) : PyUnicode_FromStringAndSize("", 0);
    if (is_trunc) {
        Py_INCREF(truncation);
        self->truncation = truncation;
    } else {
        self->truncation = NULL;
    }
    self->wrap = wrap;

    Py_DECREF(raw);
    return 0;
}

/* Helper: pad a single line with pad_l / pad_r if needed. */
static PyObject *pad_line(PyObject *line, PyObject *pad_l, PyObject *pad_r,
                          int pl, int pr) {
    if (!pl && !pr) {
        Py_INCREF(line);
        return line;
    }
    return PyUnicode_FromFormat("%U%U%U", pad_l, line, pad_r);
}

static PyObject *CTextRender_call(CTextRenderObject *self,
                                   PyObject *args, PyObject *kw) {
    int w;
    PyObject *h_obj = Py_None;
    static char *kwlist[] = {"w", "h", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kw, "i|O", kwlist, &w, &h_obj))
        return NULL;

    switch (self->mode) {
    case TEXT_PLAIN:
        Py_INCREF(self->lines);
        return self->lines;

    case TEXT_PADDED: {
        Py_ssize_t n = PyList_GET_SIZE(self->lines);
        PyObject *result = PyList_New(n);
        if (!result) return NULL;
        for (Py_ssize_t i = 0; i < n; i++) {
            PyObject *line = PyList_GET_ITEM(self->lines, i);
            PyObject *padded = pad_line(line, self->pad_l, self->pad_r,
                                        self->pl, self->pr);
            if (!padded) { Py_DECREF(result); return NULL; }
            PyList_SET_ITEM(result, i, padded);
        }
        return result;
    }

    case TEXT_FULL: {
        int inner = w - self->pl - self->pr;
        Py_ssize_t nlines = PyList_GET_SIZE(self->lines);
        const char *tmode = self->truncation
            ? PyUnicode_AsUTF8(self->truncation) : NULL;

        PyObject *chunks = PyList_New(0);
        if (!chunks) return NULL;

        for (Py_ssize_t i = 0; i < nlines; i++) {
            PyObject *line = PyList_GET_ITEM(self->lines, i);

            if (self->wrap && inner > 0) {
                if (wrap_line_into(line, inner, chunks) < 0) {
                    Py_DECREF(chunks);
                    return NULL;
                }
            } else if (tmode && inner > 0) {
                PyObject *trunc = truncate_line(line, inner, tmode[0]);
                if (!trunc) { Py_DECREF(chunks); return NULL; }
                if (PyList_Append(chunks, trunc) < 0) {
                    Py_DECREF(trunc); Py_DECREF(chunks); return NULL;
                }
                Py_DECREF(trunc);
            } else {
                Py_INCREF(line);
                if (PyList_Append(chunks, line) < 0) {
                    Py_DECREF(line); Py_DECREF(chunks); return NULL;
                }
                Py_DECREF(line);
            }
        }

        /* Apply padding. */
        if (self->pl || self->pr) {
            Py_ssize_t nc = PyList_GET_SIZE(chunks);
            PyObject *result = PyList_New(nc);
            if (!result) { Py_DECREF(chunks); return NULL; }
            for (Py_ssize_t i = 0; i < nc; i++) {
                PyObject *c = PyList_GET_ITEM(chunks, i);
                PyObject *padded = pad_line(c, self->pad_l, self->pad_r,
                                            self->pl, self->pr);
                if (!padded) { Py_DECREF(result); Py_DECREF(chunks); return NULL; }
                PyList_SET_ITEM(result, i, padded);
            }
            Py_DECREF(chunks);
            return result;
        }

        return chunks;
    }
    }
    Py_RETURN_NONE;
}

static PyMemberDef CTextRender_members[] = {
    {"visible_w", Py_T_INT, offsetof(CTextRenderObject, visible_w), Py_READONLY, NULL},
    {NULL}
};

static PyTypeObject CTextRenderType = {
    .ob_base      = PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name      = "ttyz.ext.TextRender",
    .tp_basicsize = sizeof(CTextRenderObject),
    .tp_flags     = Py_TPFLAGS_DEFAULT,
    .tp_new       = PyType_GenericNew,
    .tp_init      = (initproc)CTextRender_init,
    .tp_dealloc   = (destructor)CTextRender_dealloc,
    .tp_call      = (ternaryfunc)CTextRender_call,
    .tp_members   = CTextRender_members,
    .tp_doc       = "TextRender(value, truncation, pl, pr, wrap) — callable text renderer.",
};
