/* SPDX-License-Identifier: MIT */
#ifndef NEMO_KITTY_PLACEMENTS_H
#define NEMO_KITTY_PLACEMENTS_H
#include "nemo_kitty_cache.h"
#include "nemo_kitty_layout.h"

#define NEMO_KITTY_PLACEMENT_MAX 512u
typedef struct NemoKittyPlacements NemoKittyPlacements;
typedef struct NemoKittyPlacement NemoKittyPlacement;
typedef enum NemoKittyPlacementStatus {
    NEMO_KITTY_PLACE_OK, NEMO_KITTY_PLACE_INVALID, NEMO_KITTY_PLACE_UNSUPPORTED,
    NEMO_KITTY_PLACE_LIMIT, NEMO_KITTY_PLACE_NOMEM, NEMO_KITTY_PLACE_NOT_FOUND
} NemoKittyPlacementStatus;
typedef struct NemoKittyView {
    const NemoKittyImage *image;
    uint32_t id, placement;
    int32_t z;
    double left, top, right, bottom;
    double source_left, source_top, source_right, source_bottom;
} NemoKittyView;
/* This metadata-only admission callback must not mutate the placement store
 * or its image cache. The owner accounts for their combined image budget. */
typedef bool (*NemoKittyPlacementAdmission)(void *, size_t current, size_t extra);
NemoKittyPlacements *nemo_kitty_placements_new(
    NemoKittyCache *, size_t budget, NemoKittyPlacementAdmission, void *);
void nemo_kitty_placements_free(NemoKittyPlacements *);
void nemo_kitty_placements_clear(NemoKittyPlacements *);
size_t nemo_kitty_placements_memory(const NemoKittyPlacements *);
unsigned nemo_kitty_placements_count(const NemoKittyPlacements *);
uint64_t nemo_kitty_placements_generation(const NemoKittyPlacements *);
/* Call only from the cache's image-removed callback, before it frees the
 * image. No cache mutation/reference operation is performed by this hook. */
void nemo_kitty_placements_image_removed(NemoKittyPlacements *, const NemoKittyImage *);

/* image is borrowed from this cache (load result or find), with no intervening
 * cache mutation. Named pairs replace atomically; p=0 always adds a view.
 * out is assigned only on success, for the terminal's cursor movement path. */
NemoKittyPlacementStatus nemo_kitty_placements_put(
    NemoKittyPlacements *, NemoKittyImage *, const NemoKittyCommand *,
    int32_t column, int32_t row, uint32_t cell_width, uint32_t cell_height,
    NemoKittyLayout *out);
/* Read-only drawing order: ascending z then image id. Equal keys retain
 * insertion order. Iterator/view pointers expire at any store mutation. */
const NemoKittyPlacement *nemo_kitty_placements_first(const NemoKittyPlacements *);
const NemoKittyPlacement *nemo_kitty_placement_next(const NemoKittyPlacement *);
bool nemo_kitty_placement_view(const NemoKittyPlacement *, uint32_t cw, uint32_t ch,
                               NemoKittyView *);
NemoKittyPlacementStatus nemo_kitty_placements_delete(
    NemoKittyPlacements *, const NemoKittyCommand *, int32_t cursor_column,
    int32_t cursor_row, uint32_t columns, uint32_t rows, uint32_t cw, uint32_t ch,
    unsigned *deleted);
/* Positive lines scroll upward. With margins, only wholly contained views
 * move, and exposed source pixels are clipped permanently. Full-page scroll
 * retains views in bounded history; painting applies the viewport separately.
 * This does not implement terminal parsing, cursor movement or text erasure. */
void nemo_kitty_placements_scroll(NemoKittyPlacements *, int32_t top, int32_t bottom,
    int32_t lines, bool margins, uint32_t history_rows, uint32_t cw, uint32_t ch);
#endif
