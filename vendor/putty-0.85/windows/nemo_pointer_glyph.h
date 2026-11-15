/* SPDX-License-Identifier: MIT */
#ifndef NEMO_POINTER_GLYPH_H
#define NEMO_POINTER_GLYPH_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "nemo_pointer.h"

enum { NEMO_POINTER_GLYPH_COUNT = 8, NEMO_POINTER_CURSOR_MAX = 128 };
/* -1 means a shared system cursor, otherwise a dense custom-glyph index. */
int nemo_pointer_glyph_index(NemoPointerShape);
/* Top-down monochrome masks, word-aligned rows; no allocation. Transparent
 * pixels preserve the background. The masks never invert its colours. */
bool nemo_pointer_glyph_masks(NemoPointerShape, unsigned size,
    uint8_t *and_mask, uint8_t *xor_mask, size_t capacity,
    unsigned *hot_x, unsigned *hot_y);
#endif
