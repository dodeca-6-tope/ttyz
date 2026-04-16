/*
 * core.h — Terminal primitives: cells, styles, colors, and string helpers.
 */

#ifndef TTYZ_CORE_H
#define TTYZ_CORE_H

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <structmember.h>
#include <wchar.h>

/* ── Style representation ─────────────────────────────────────────── */

#define WIDE_CHAR     0   /* ch == 0 marks wide-char continuation */

/* Color kinds */
#define COLOR_NONE    0
#define COLOR_INDEXED 1   /* 256-color palette: value in .r */
#define COLOR_RGB     2   /* 24-bit true color */

typedef struct {
    uint8_t kind;   /* COLOR_NONE / COLOR_INDEXED / COLOR_RGB */
    uint8_t r;      /* red or palette index */
    uint8_t g;
    uint8_t b;
} Color;

#define COLOR_EMPTY ((Color){COLOR_NONE, 0, 0, 0})

/* Attribute flags (bit positions in uint16_t) */
#define FLAG_BOLD          (1 << 0)
#define FLAG_DIM           (1 << 1)
#define FLAG_ITALIC        (1 << 2)
#define FLAG_UNDERLINE     (1 << 3)
#define FLAG_BLINK         (1 << 4)
#define FLAG_REVERSE       (1 << 5)
#define FLAG_INVISIBLE     (1 << 6)
#define FLAG_STRIKETHROUGH (1 << 7)
#define FLAG_OVERLINE      (1 << 8)

typedef struct {
    Color    fg;
    Color    bg;
    uint16_t flags;
    uint8_t  _pad[2]; /* keep struct 12 bytes for alignment */
} Style;

#define STYLE_EMPTY ((Style){COLOR_EMPTY, COLOR_EMPTY, 0, {0, 0}})

static inline int style_eq(Style a, Style b) {
    return memcmp(&a, &b, sizeof(Style)) == 0;
}

static inline int style_is_empty(Style s) {
    Style empty = STYLE_EMPTY;
    return memcmp(&s, &empty, sizeof(Style)) == 0;
}

typedef struct {
    Py_UCS4 ch;
    Style   style;
} Cell;

#define UNWRITTEN  1   /* ch == 1 marks an unwritten cell */
#define BLANK_CELL ((Cell){UNWRITTEN, STYLE_EMPTY})

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

/* Skip any escape sequence in a raw char buffer starting at src[pos]
   (which must be ESC).  Handles CSI, OSC (BEL / ST), and other ESC+byte.
   Returns the position AFTER the sequence. */
static inline Py_ssize_t skip_escape_ascii(const char *src, Py_ssize_t pos,
                                            Py_ssize_t len) {
    if (pos + 1 >= len) return pos + 1;
    char next = src[pos + 1];

    if (next == '[') {
        /* CSI: ESC [ ... final_byte (0x40-0x7E) */
        Py_ssize_t end = pos + 2;
        while (end < len && !((unsigned char)src[end] >= 0x40 &&
                              (unsigned char)src[end] <= 0x7E))
            end++;
        if (end < len) end++; /* skip final byte */
        return end;
    }

    if (next == ']') {
        /* OSC: ESC ] ... terminated by BEL or ST (ESC \) */
        Py_ssize_t end = pos + 2;
        while (end < len) {
            if (src[end] == 0x07) return end + 1;              /* BEL */
            if (src[end] == '\033' && end + 1 < len &&
                src[end + 1] == '\\')
                return end + 2;                                 /* ST */
            end++;
        }
        return end;
    }

    /* Other ESC sequence (e.g. ESC ( B): skip ESC + next byte */
    return pos + 2;
}

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
    PyObject *s = PyUnicode_New(n, 127);
    if (!s) return NULL;
    memset(PyUnicode_1BYTE_DATA(s), ' ', (size_t)n);
    return s;
}

/* ── SGR output ────────────────────────────────────────────────────── */

static void emit_color(char *tmp, int *n, Color c, int is_bg) {
    if (c.kind == COLOR_NONE) return;
    tmp[(*n)++] = ';';
    *n += uint_to_str(is_bg ? 48 : 38, tmp + *n);
    if (c.kind == COLOR_INDEXED) {
        memcpy(tmp + *n, ";5;", 3); *n += 3;
        *n += uint_to_str(c.r, tmp + *n);
    } else {
        memcpy(tmp + *n, ";2;", 3); *n += 3;
        *n += uint_to_str(c.r, tmp + *n);
        tmp[(*n)++] = ';';
        *n += uint_to_str(c.g, tmp + *n);
        tmp[(*n)++] = ';';
        *n += uint_to_str(c.b, tmp + *n);
    }
}

static void emit_sgr(OutBuf *b, Style style) {
    if (style_is_empty(style)) {
        outbuf_add(b, "\033[0m", 4);
        return;
    }

    char tmp[80];
    memcpy(tmp, "\033[0", 3);
    int n = 3;
    uint16_t f = style.flags;
    if (f & FLAG_BOLD)          { tmp[n++] = ';'; tmp[n++] = '1'; }
    if (f & FLAG_DIM)           { tmp[n++] = ';'; tmp[n++] = '2'; }
    if (f & FLAG_ITALIC)        { tmp[n++] = ';'; tmp[n++] = '3'; }
    if (f & FLAG_UNDERLINE)     { tmp[n++] = ';'; tmp[n++] = '4'; }
    if (f & FLAG_BLINK)         { tmp[n++] = ';'; tmp[n++] = '5'; }
    if (f & FLAG_REVERSE)       { tmp[n++] = ';'; tmp[n++] = '7'; }
    if (f & FLAG_INVISIBLE)     { tmp[n++] = ';'; tmp[n++] = '8'; }
    if (f & FLAG_STRIKETHROUGH) { tmp[n++] = ';'; tmp[n++] = '9'; }
    if (f & FLAG_OVERLINE)      { memcpy(tmp + n, ";53", 3); n += 3; }
    emit_color(tmp, &n, style.fg, 0);
    emit_color(tmp, &n, style.bg, 1);
    tmp[n++] = 'm';
    outbuf_add(b, tmp, (size_t)n);
}

/* ── SGR parameter parsing ─────────────────────────────────────────── */

/*
 * State machine for parsing SGR parameters, supporting:
 *   38;5;N (indexed fg), 48;5;N (indexed bg),
 *   38;2;R;G;B (RGB fg), 48;2;R;G;B (RGB bg),
 *   and all standard attribute codes.
 */
static void parse_sgr(const void *data, int kind,
                      Py_ssize_t start, Py_ssize_t end,
                      Color *fg, Color *bg, uint16_t *flags)
{
    int num = -1;
    int state = 0;
    uint8_t rgb[3] = {0, 0, 0};

    for (Py_ssize_t i = start; i <= end; i++) {
        Py_UCS4 c = (i < end) ? PyUnicode_READ(kind, data, i) : ';';

        if (c >= '0' && c <= '9') {
            num = (num < 0 ? 0 : num * 10) + (int)(c - '0');
            continue;
        }

        /* separator or end */
        if (num < 0) num = 0;

        switch (state) {
        case 2: /* fg indexed */
            *fg = (Color){COLOR_INDEXED, (uint8_t)num, 0, 0};
            state = 0; break;
        case 4: /* bg indexed */
            *bg = (Color){COLOR_INDEXED, (uint8_t)num, 0, 0};
            state = 0; break;
        case 5: /* fg RGB: R */
            rgb[0] = (uint8_t)num; state = 6; break;
        case 6: /* fg RGB: G */
            rgb[1] = (uint8_t)num; state = 7; break;
        case 7: /* fg RGB: B */
            *fg = (Color){COLOR_RGB, rgb[0], rgb[1], (uint8_t)num};
            state = 0; break;
        case 8: /* bg RGB: R */
            rgb[0] = (uint8_t)num; state = 9; break;
        case 9: /* bg RGB: G */
            rgb[1] = (uint8_t)num; state = 10; break;
        case 10: /* bg RGB: B */
            *bg = (Color){COLOR_RGB, rgb[0], rgb[1], (uint8_t)num};
            state = 0; break;
        case 1: /* after 38 */
            if (num == 5) { state = 2; goto next; }
            if (num == 2) { state = 5; goto next; }
            state = 0; break;
        case 3: /* after 48 */
            if (num == 5) { state = 4; goto next; }
            if (num == 2) { state = 8; goto next; }
            state = 0; break;
        default: /* state 0 */
            if (num >= 30 && num <= 37) {
                *fg = (Color){COLOR_INDEXED, (uint8_t)(num - 30), 0, 0};
            } else if (num >= 40 && num <= 47) {
                *bg = (Color){COLOR_INDEXED, (uint8_t)(num - 40), 0, 0};
            } else if (num >= 90 && num <= 97) {
                *fg = (Color){COLOR_INDEXED, (uint8_t)(num - 90 + 8), 0, 0};
            } else if (num >= 100 && num <= 107) {
                *bg = (Color){COLOR_INDEXED, (uint8_t)(num - 100 + 8), 0, 0};
            } else switch (num) {
            case  0: *fg = COLOR_EMPTY; *bg = COLOR_EMPTY; *flags = 0; break;
            case  1: *flags |= FLAG_BOLD; break;
            case  2: *flags |= FLAG_DIM; break;
            case  3: *flags |= FLAG_ITALIC; break;
            case  4: *flags |= FLAG_UNDERLINE; break;
            case  5: *flags |= FLAG_BLINK; break;
            case  7: *flags |= FLAG_REVERSE; break;
            case  8: *flags |= FLAG_INVISIBLE; break;
            case  9: *flags |= FLAG_STRIKETHROUGH; break;
            case 22: *flags &= ~(FLAG_BOLD | FLAG_DIM); break;
            case 23: *flags &= ~FLAG_ITALIC; break;
            case 24: *flags &= ~FLAG_UNDERLINE; break;
            case 25: *flags &= ~FLAG_BLINK; break;
            case 27: *flags &= ~FLAG_REVERSE; break;
            case 28: *flags &= ~FLAG_INVISIBLE; break;
            case 29: *flags &= ~FLAG_STRIKETHROUGH; break;
            case 39: *fg = COLOR_EMPTY; break;
            case 49: *bg = COLOR_EMPTY; break;
            case 53: *flags |= FLAG_OVERLINE; break;
            case 55: *flags &= ~FLAG_OVERLINE; break;
            case 38: state = 1; goto next;
            case 48: state = 3; goto next;
            }
            state = 0;
            break;
        }
    next:
        num = -1;
    }
}

#endif /* TTYZ_CORE_H */
