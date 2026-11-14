/* SPDX-License-Identifier: MIT */
#ifndef NEMO_KITTY_LAYOUT_H
#define NEMO_KITTY_LAYOUT_H
#include "nemo_kitty.h"

typedef enum NemoKittyLayoutStatus {
    NEMO_KITTY_LAYOUT_OK, NEMO_KITTY_LAYOUT_INVALID,
    NEMO_KITTY_LAYOUT_UNSUPPORTED, NEMO_KITTY_LAYOUT_LIMIT
} NemoKittyLayoutStatus;

typedef struct NemoKittyLayout {
    uint32_t source_x, source_y, source_width, source_height;
    uint32_t offset_x, offset_y, effective_columns, effective_rows;
    uint32_t advance_columns, advance_rows;
    double left, top, right, bottom;
    int32_t z;
} NemoKittyLayout;

/* Ordinary placement geometry only; no allocation, identity or terminal state.
 * Coordinates are cell pixels before viewport clipping or scrolling. The owner
 * applies cursor deltas through its normal wrap/scroll path, moves placements
 * with that scroll, and re-evaluates geometry when cell metrics change.
 * Explicit c/r fill their rectangle; a single explicit axis keeps source aspect.
 * Virtual/relative placements are rejected until their separate model exists.
 * Failure leaves the output unchanged. Source axes and cell sizes are <=8192. */
NemoKittyLayoutStatus nemo_kitty_layout(
    const NemoKittyCommand *, uint32_t image_width, uint32_t image_height,
    int32_t column, int32_t row, uint32_t cell_width, uint32_t cell_height,
    NemoKittyLayout *);
#endif
