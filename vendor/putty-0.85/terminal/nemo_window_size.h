/* SPDX-License-Identifier: MIT */
#ifndef NEMO_WINDOW_SIZE_H
#define NEMO_WINDOW_SIZE_H
#include <stdbool.h>

typedef struct NemoWindowSize {
    int width, height;             /* current client pixels */
    int cols, rows, cell_width, cell_height;
    int padding_width, padding_height;
    int limit_width, limit_height; /* available client pixels on this monitor */
} NemoWindowSize;

/* -1 keeps an axis, 0 uses its monitor limit. Parameters are bounded to the
 * XTerm 16-bit CSI range before cell-to-pixel multiplication. Unlike XTerm's
 * sub-cell windows, preserve at least one complete cell plus padding. No
 * allocation; the platform can still impose its own window minimum. */
bool nemo_window_size(const NemoWindowSize *, int width, int height, bool pixels,
                      int *client_width, int *client_height);
#endif
