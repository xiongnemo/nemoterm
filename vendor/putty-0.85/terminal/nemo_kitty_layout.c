/* SPDX-License-Identifier: MIT */
#include "nemo_kitty_layout.h"
#include "nemo_kitty_cache.h"
#include <string.h>

static uint32_t smaller(uint32_t a, uint32_t b) { return a < b ? a : b; }

/* Ceil a positive integer ratio without adding denominator-1 to numerator. */
static bool cells(uint64_t pixels_numerator, uint64_t pixels_denominator,
                  uint32_t cell_size, uint32_t *out)
{
    uint64_t denominator = pixels_denominator * cell_size;
    uint64_t n = pixels_numerator / denominator +
        (pixels_numerator % denominator != 0);
    if (!n || n > UINT32_MAX) return false;
    *out = (uint32_t)n;
    return true;
}

NemoKittyLayoutStatus nemo_kitty_layout(
    const NemoKittyCommand *c, uint32_t iw, uint32_t ih,
    int32_t column, int32_t row, uint32_t cw, uint32_t ch,
    NemoKittyLayout *out)
{
    NemoKittyLayout g;
    uint32_t columns, rows, width, height;
    uint64_t pixels;
    if (!c || !out || !iw || !ih || !cw || !ch)
        return NEMO_KITTY_LAYOUT_INVALID;
    if (iw > NEMO_KITTY_AXIS_MAX || ih > NEMO_KITTY_AXIS_MAX ||
        cw > NEMO_KITTY_AXIS_MAX || ch > NEMO_KITTY_AXIS_MAX)
        return NEMO_KITTY_LAYOUT_LIMIT;
    if (nemo_kitty_get(c, 'U') || nemo_kitty_get(c, 'P') ||
        nemo_kitty_get(c, 'Q') || nemo_kitty_get(c, 'H') || nemo_kitty_get(c, 'V'))
        return NEMO_KITTY_LAYOUT_UNSUPPORTED;
    if (nemo_kitty_get(c, 'C') > 1) return NEMO_KITTY_LAYOUT_INVALID;
    memset(&g, 0, sizeof(g));
    g.source_x = nemo_kitty_get(c, 'x');
    g.source_y = nemo_kitty_get(c, 'y');
    if (g.source_x >= iw || g.source_y >= ih) return NEMO_KITTY_LAYOUT_INVALID;
    width = nemo_kitty_get(c, 'w'); height = nemo_kitty_get(c, 'h');
    g.source_width = smaller(width ? width : iw, iw - g.source_x);
    g.source_height = smaller(height ? height : ih, ih - g.source_y);
    g.offset_x = smaller(nemo_kitty_get(c, 'X'), cw - 1);
    g.offset_y = smaller(nemo_kitty_get(c, 'Y'), ch - 1);
    g.z = nemo_kitty_signed(c, 'z');
    columns = nemo_kitty_get(c, 'c'); rows = nemo_kitty_get(c, 'r');
    g.effective_columns = columns; g.effective_rows = rows;
    /* Cursor occupancy includes the offset. Keep this distinct from the
     * drawable rectangle, where an explicit cell extent includes the offset
     * within its allotted space. Independent kitty captures cover both. */
    if (!columns) {
        pixels = rows ? ((uint64_t)rows * ch + g.offset_y) * g.source_width :
            (uint64_t)g.source_width + g.offset_x;
        if (!cells(pixels, rows ? g.source_height : 1, cw, &g.effective_columns))
            return NEMO_KITTY_LAYOUT_LIMIT;
    }
    if (!rows) {
        pixels = columns ? ((uint64_t)columns * cw + g.offset_x) * g.source_height :
            (uint64_t)g.source_height + g.offset_y;
        if (!cells(pixels, columns ? g.source_width : 1, ch, &g.effective_rows))
            return NEMO_KITTY_LAYOUT_LIMIT;
    }
    g.left = (double)column * cw + g.offset_x;
    g.top = (double)row * ch + g.offset_y;
    if (columns) g.right = ((double)column + columns) * cw;
    if (rows) g.bottom = ((double)row + rows) * ch;
    if (!columns) {
        double extent = rows ? (g.bottom - g.top) * g.source_width / g.source_height :
            g.source_width;
        g.right = g.left + extent;
    }
    if (!rows) g.bottom = g.top + (g.right - g.left) * g.source_height / g.source_width;
    if (nemo_kitty_get(c, 'C') != 1) {
        g.advance_columns = g.effective_columns;
        g.advance_rows = g.effective_rows - 1;
    }
    *out = g;
    return NEMO_KITTY_LAYOUT_OK;
}
