/*
 * core.h — Cells, styles, colors. The types every other unit shares.
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

/* ── Per-cell extra codepoints (ZWJ, VS16, continuation) ──────────── */
/* Stored in a side table on the Buffer so Cell stays 16 bytes.        */

#define CELL_EXTRA_MAX 3

typedef struct {
    int     pos;                    /* cell index (row * width + col) */
    Py_UCS4 cp[CELL_EXTRA_MAX];
    uint8_t n;
} CellExtra;

#endif /* TTYZ_CORE_H */
