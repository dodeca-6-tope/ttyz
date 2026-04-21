/*
 * cells.c — ANSI ↔ cells primitives.
 *
 * The dual of buffer.c: where dump/diff go cells→ANSI, these helpers
 * take ANSI/plain strings and write them into a BufferObject's grid.
 * No node-tree knowledge — just bytes and styles into cells.
 */

/* Write a single cell (bounds-checked). */
static inline void rc_set_cell(BufferObject *buf, int col, int row,
                               Py_UCS4 ch, Style style) {
    if (col >= 0 && col < buf->width && row >= 0 && row < buf->height)
        buf->cells[row * buf->width + col] = (Cell){ch, style};
}

/* Fill a rectangle with blank cells of the given style. */
static void rc_fill_region(BufferObject *buf, int x, int y, int w, int h,
                           Style style) {
    int x1 = x + w, y1 = y + h;
    if (x < 0) x = 0;
    if (y < 0) y = 0;
    if (x1 > buf->width)  x1 = buf->width;
    if (y1 > buf->height) y1 = buf->height;
    int rw = x1 - x;
    if (rw <= 0 || y >= y1) return;
    Cell cell = {' ', style};
    /* Fill first row, memcpy to rest. */
    Cell *first = buf->cells + y * buf->width + x;
    for (int c = 0; c < rw; c++) first[c] = cell;
    size_t row_bytes = (size_t)rw * sizeof(Cell);
    for (int r = y + 1; r < y1; r++)
        memcpy(buf->cells + r * buf->width + x, first, row_bytes);
}

/* Fill only UNWRITTEN cells in a region — used after rendering content
   so that gaps get the background without overwriting content. */
static void rc_fill_unwritten(BufferObject *buf, int x, int y, int w, int h,
                               Style style) {
    int x1 = x + w, y1 = y + h;
    if (x < 0) x = 0;
    if (y < 0) y = 0;
    if (x1 > buf->width)  x1 = buf->width;
    if (y1 > buf->height) y1 = buf->height;
    Cell cell = {' ', style};
    for (int r = y; r < y1; r++) {
        Cell *row = buf->cells + r * buf->width;
        for (int c = x; c < x1; c++)
            if (row[c].ch == UNWRITTEN)
                row[c] = cell;
    }
}

/* ── parse_line_into — write an ANSI string into cells ───────────── */
/*
 * Parses a Python string (which may contain ANSI escapes) and writes
 * cells at (x, y) up to max_w columns.  bg_style provides the
 * inherited background — unstyled content and SGR resets inherit it.
 */
static void parse_line_into(BufferObject *buf, int x, int y, int max_w,
                            PyObject *line, Style bg_style) {
    if (y < 0 || y >= buf->height || max_w <= 0) return;
    Py_ssize_t len = PyUnicode_GET_LENGTH(line);
    if (len == 0) return;

    int bw = buf->width;
    Cell *cells = buf->cells + y * bw;
    int col_end = x + max_w;
    if (col_end > bw) col_end = bw;
    if (x >= col_end) return;

    /* ASCII fast path: no escapes, no wide chars. */
    if (is_plain_ascii(line)) {
        const char *src = PyUnicode_AsUTF8(line);
        Py_ssize_t n = len;
        if (x + n > col_end) n = col_end - x;
        for (Py_ssize_t i = 0; i < n; i++)
            cells[x + (int)i] = (Cell){
                (Py_UCS4)(unsigned char)src[i], bg_style};
        return;
    }

    /* ANSI + wide-char path. */
    int kind = PyUnicode_KIND(line);
    const void *data = PyUnicode_DATA(line);
    int col = x;
    Py_ssize_t pos = 0;
    Color fg = COLOR_EMPTY, bg_c = bg_style.bg;
    uint16_t flags = 0;
    Style style = bg_style;

    while (pos < len && col < col_end) {
        Py_UCS4 ch = PyUnicode_READ(kind, data, pos);

        if (ch == 0x1B) {
            if (pos + 1 < len &&
                PyUnicode_READ(kind, data, pos + 1) == '[') {
                /* CSI sequence — find final byte, parse SGR. */
                Py_ssize_t end = pos + 2;
                while (end < len) {
                    Py_UCS4 fb = PyUnicode_READ(kind, data, end);
                    end++;
                    if (fb >= 0x40 && fb <= 0x7E) break;
                }
                /* Only parse SGR (final byte 'm'); skip other CSI. */
                if (PyUnicode_READ(kind, data, end - 1) == 'm') {
                    parse_sgr(data, kind, pos + 2, end - 1,
                              &fg, &bg_c, &flags);
                    /* Inherit parent bg when text has no explicit bg. */
                    if (bg_c.kind == COLOR_NONE &&
                        bg_style.bg.kind != COLOR_NONE)
                        bg_c = bg_style.bg;
                    style = (Style){fg, bg_c, flags, {0, 0}};
                }
                pos = end;
            } else {
                pos = skip_escape(data, kind, pos, len);
            }
            continue;
        }

        int cw = cwidth(ch);
        if (cw <= 0) { pos++; continue; }
        if (cw == 2 && col + 1 >= col_end) { pos++; continue; }

        cells[col] = (Cell){ch, style};
        if (cw == 2) {
            cells[col + 1] = (Cell){WIDE_CHAR, style};
            /* Absorb ZWJ continuation into side table extras. */
            int cell_pos = y * bw + col;
            Py_ssize_t tail_start = pos + 1;
            while (tail_start < len) {
                Py_UCS4 nc = PyUnicode_READ(kind, data, tail_start);
                if (nc == 0xFE0F) {                          /* VS16 */
                    buf_add_extra(buf, cell_pos, nc);
                    tail_start++;
                    continue;
                }
                if (nc == 0x200D && tail_start + 1 < len) {  /* ZWJ + next */
                    Py_UCS4 after = PyUnicode_READ(kind, data, tail_start + 1);
                    if (cwidth(after) >= 1) {
                        buf_add_extra(buf, cell_pos, nc);
                        buf_add_extra(buf, cell_pos, after);
                        tail_start += 2;
                        continue;
                    }
                }
                break;
            }
            pos = tail_start;
            col += 2;
        } else {
            col++;
            pos++;
        }
    }
}

/* Write a padded line: left-pad, content, right-pad. */
static void render_padded_line(BufferObject *buf, int x, int y, int w,
                               int pl, int pr, int max_w,
                               PyObject *line, Style bg) {
    int inner_x = x + pl;
    for (int c = x; c < inner_x && c < x + w; c++)
        rc_set_cell(buf, c, y, ' ', bg);
    parse_line_into(buf, inner_x, y, max_w, line, bg);
    int rp = inner_x + max_w;
    for (int c = rp; c < rp + pr && c < x + w; c++)
        rc_set_cell(buf, c, y, ' ', bg);
}
