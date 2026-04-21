/*
 * sgr.h — SGR (Select Graphic Rendition) codec.
 *
 * emit_sgr:  Style → ANSI bytes (into OutBuf)
 * parse_sgr: ANSI bytes → Color/flags (state machine)
 */

#ifndef TTYZ_SGR_H
#define TTYZ_SGR_H

#include "core.h"
#include "outbuf.h"

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

#endif /* TTYZ_SGR_H */
