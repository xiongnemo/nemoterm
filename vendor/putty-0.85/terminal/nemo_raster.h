/* SPDX-License-Identifier: MIT */
#ifndef NEMO_RASTER_H
#define NEMO_RASTER_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define NEMO_RASTER_MAX_FRAMES 256u
typedef struct NemoRasterFrame {
    uint32_t *pixels;
    unsigned delay_ms;
} NemoRasterFrame;

/* Straight-alpha BGRA, top down. The decoder transfers raster-owned pixels;
 * nemo_raster_free releases either one static bitmap or the complete composed
 * frame cache, independently of PuTTY's allocator. */
typedef struct NemoRaster {
    uint32_t *pixels;
    unsigned width, height;
    size_t bytes;
    bool partial_alpha;
    NemoRasterFrame *frames;
    unsigned frame_count, frame_index, plays;
    uint32_t last_tick;
    uint64_t elapsed, duration;
    bool started, finished;
} NemoRaster;
/* Pixel ownership must use this pair with the same byte count. Large Windows
 * buffers have independent reservations so replacing an image releases its
 * storage instead of leaving that block inside the general-purpose heap. */
void *nemo_raster_pixels_allocate(size_t bytes);
void nemo_raster_pixels_free(void *, size_t bytes);
/* Called after reading dimensions, before allocating or decoding pixels. */
typedef bool (*NemoRasterAdmission)(void *, unsigned, unsigned, size_t);

/* Immutable composed frame cache, with a bounded allocation computed before
 * the platform decoder calls its owner's admission callback. */
size_t nemo_raster_storage(unsigned width, unsigned height, unsigned frames);
bool nemo_raster_allocate(NemoRaster *, unsigned width, unsigned height,
                          unsigned frames, size_t budget);
void nemo_raster_free(NemoRaster *);

typedef struct NemoRasterComposer {
    unsigned base;
    unsigned left, top, width, height;
    uint32_t background;
    bool valid, clear;
} NemoRasterComposer;
bool nemo_raster_prepare(NemoRaster *, unsigned frame, const NemoRasterComposer *);
bool nemo_raster_dispose(NemoRaster *, NemoRasterComposer *, unsigned frame,
                         unsigned disposal, unsigned left, unsigned top,
                         unsigned width, unsigned height);
/* Return milliseconds until the next visible frame, or zero when stopped.
 * Zero-delay intermediate frames are composed but skipped. An all-zero file
 * stops at its final frame instead of creating a zero-delay timer loop. */
unsigned nemo_raster_tick(NemoRaster *, uint32_t now, bool *changed);
#endif
