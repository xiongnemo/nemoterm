/* SPDX-License-Identifier: MIT */
#include "nemo_window_size.h"
#include <stdint.h>

static bool axis(int value, bool pixels, int current, int cells, int cell,
                 int padding, int limit, int *result)
{
    if (value < -1 || value > 65535 || current <= 0 || cells <= 0 ||
        cell <= 0 || padding < 0 || limit <= padding || cell > limit-padding)
        return false;
    int64_t requested;
    if (!value) requested = limit;
    else if (pixels) requested = value < 0 ? current : value;
    else requested = (int64_t)(value < 0 ? cells : value)*cell + padding;
    /* Match XTerm's pre-limit Dimension check for character requests. */
    if (!pixels && requested > 65535) return false;
    if (requested > limit) requested = limit;
    if (requested < padding+cell) requested = padding+cell;
    *result = (int)requested;
    return true;
}

bool nemo_window_size(const NemoWindowSize *m, int width, int height, bool pixels,
                      int *client_width, int *client_height)
{
    int w, h;
    if (!axis(width, pixels, m->width, m->cols, m->cell_width,
              m->padding_width, m->limit_width, &w) ||
        !axis(height, pixels, m->height, m->rows, m->cell_height,
              m->padding_height, m->limit_height, &h)) return false;
    *client_width = w; *client_height = h;
    return true;
}
