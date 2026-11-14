/* SPDX-License-Identifier: MIT */
#ifndef NEMO_RASTER_H
#define NEMO_RASTER_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* Straight-alpha BGRA, top down. The decoder transfers malloc-owned pixels;
 * the terminal frees them with free(), independently of PuTTY's allocator. */
typedef struct NemoRaster {
    uint32_t *pixels;
    unsigned width, height;
    size_t bytes;
    bool partial_alpha;
} NemoRaster;
/* Called after reading dimensions, before allocating or decoding pixels. */
typedef bool (*NemoRasterAdmission)(void *, unsigned, unsigned, size_t);
#endif
