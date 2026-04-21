/*
 * outbuf.h — Growable byte buffer + integer-to-ASCII helpers.
 *
 * Shared output target for dump/diff/truncate/wrap/SGR codec paths.
 */

#ifndef TTYZ_OUTBUF_H
#define TTYZ_OUTBUF_H

#include "core.h"

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

/* Fast unsigned int → ASCII digits (handles 0–9999 inline, fallback for larger). */
static inline int uint_to_str(unsigned val, char *out) {
    if (val < 10)  { out[0] = '0' + val; return 1; }
    if (val < 100) { out[0] = '0' + val / 10; out[1] = '0' + val % 10; return 2; }
    if (val < 1000) {
        out[0] = '0' + val / 100;
        out[1] = '0' + val / 10 % 10;
        out[2] = '0' + val % 10;
        return 3;
    }
    char tmp[10];
    int n = 0;
    do { tmp[n++] = '0' + val % 10; val /= 10; } while (val);
    for (int i = 0; i < n; i++) out[i] = tmp[n - 1 - i];
    return n;
}

/* Emit CSI cursor-position sequence: ESC [ row ; col H */
static void outbuf_moveto(OutBuf *b, int row, int col) {
    char tmp[16];
    memcpy(tmp, "\033[", 2);
    int n = 2;
    n += uint_to_str((unsigned)row, tmp + n);
    tmp[n++] = ';';
    n += uint_to_str((unsigned)col, tmp + n);
    tmp[n++] = 'H';
    outbuf_add(b, tmp, (size_t)n);
}

/* Write n space characters. */
static inline void outbuf_spaces(OutBuf *b, int n) {
    if (n <= 0) return;
    outbuf_grow(b, (size_t)n);
    if (b->oom) return;
    memset(b->data + b->len, ' ', (size_t)n);
    b->len += (size_t)n;
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

#endif /* TTYZ_OUTBUF_H */
