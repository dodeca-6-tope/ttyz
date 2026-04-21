/*
 * ansi.h — Unicode + ANSI scanning: UTF-8, wcwidth, escape-skip, width.
 *
 * Pure helpers for reading Python strings that may contain ANSI escapes.
 * Knows nothing about cells, buffers, or node trees.
 */

#ifndef TTYZ_ANSI_H
#define TTYZ_ANSI_H

#include "core.h"

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

/* ── char width (system wcwidth) ──────────────────────────────────── */

static inline int cwidth(Py_UCS4 ch) {
    if (ch >= 0x20 && ch < 0x7F) return 1;  /* ASCII printable */
    if (ch < 0x80) return 0;                 /* ASCII control */
    int w = wcwidth((wchar_t)ch);
    return w > 0 ? w : 0;
}

/* ── Escape sequence skippers ─────────────────────────────────────── */

/* Skip any escape sequence starting at pos (Unicode).  Always advances
   past the sequence. */
static inline Py_ssize_t skip_escape(const void *data, int kind,
                                      Py_ssize_t pos, Py_ssize_t len) {
    if (pos + 1 >= len) return pos + 1;
    Py_UCS4 next = PyUnicode_READ(kind, data, pos + 1);

    if (next == '[') {
        /* CSI: ESC [ ... final_byte (0x40-0x7E) */
        Py_ssize_t end = pos + 2;
        while (end < len) {
            Py_UCS4 fb = PyUnicode_READ(kind, data, end);
            end++;
            if (fb >= 0x40 && fb <= 0x7E) break;
        }
        return end;
    }

    if (next == ']') {
        /* OSC: ESC ] ... terminated by BEL or ST (ESC \) */
        Py_ssize_t end = pos + 2;
        while (end < len) {
            Py_UCS4 ch = PyUnicode_READ(kind, data, end);
            if (ch == 0x07) return end + 1;              /* BEL */
            if (ch == 0x1B && end + 1 < len &&
                PyUnicode_READ(kind, data, end + 1) == '\\')
                return end + 2;                           /* ST */
            end++;
        }
        return end;
    }

    /* Other ESC sequence (e.g. ESC ( B): skip ESC + next byte */
    return pos + 2;
}

/* Skip past a ZWJ emoji continuation: (FE0F? 200D visible_char)*.
   Call after consuming a wide (cw >= 2) base character.
   Returns the number of additional codepoints consumed. */
static inline Py_ssize_t skip_zwj_tail(const void *data, int kind,
                                        Py_ssize_t pos, Py_ssize_t len) {
    Py_ssize_t start = pos;
    while (pos < len) {
        Py_UCS4 ch = PyUnicode_READ(kind, data, pos);
        if (ch == 0xFE0F) { pos++; continue; }          /* VS16 */
        if (ch == 0x200D && pos + 1 < len) {             /* ZWJ */
            Py_UCS4 after = PyUnicode_READ(kind, data, pos + 1);
            if (cwidth(after) >= 1) { pos += 2; continue; }
        }
        break;
    }
    return pos - start;
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
        if (ch == 0x1B) { pos = skip_escape(data, kind, pos, len); continue; }
        int cw = cwidth(ch);
        width += cw;
        pos++;
        /* Skip ZWJ continuations — the cluster counts as one glyph. */
        if (cw >= 2) pos += skip_zwj_tail(data, kind, pos, len);
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
    PyObject *s = PyUnicode_New(n, 127);
    if (!s) return NULL;
    memset(PyUnicode_1BYTE_DATA(s), ' ', (size_t)n);
    return s;
}

#endif /* TTYZ_ANSI_H */
