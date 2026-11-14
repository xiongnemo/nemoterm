/* SPDX-License-Identifier: MIT */
#include "nemo_raster.h"
#include <stdlib.h>
#include <string.h>

size_t nemo_raster_storage(unsigned w, unsigned h, unsigned frames)
{
    if (!w || !h || !frames || frames > NEMO_RASTER_MAX_FRAMES) return 0;
    size_t metadata = frames * sizeof(NemoRasterFrame);
    if ((uint64_t)w * h > (SIZE_MAX - metadata) / 4 / frames) return 0;
    return (size_t)w * h * 4 * frames + metadata;
}

bool nemo_raster_allocate(NemoRaster *r, unsigned w, unsigned h,
                          unsigned frames, size_t budget)
{
    memset(r, 0, sizeof(*r));
    size_t bytes = nemo_raster_storage(w, h, frames);
    if (!bytes || bytes > budget) return false;
    r->frames = calloc(frames, sizeof(*r->frames));
    if (!r->frames) return false;
    r->frame_count = frames;
    for (unsigned i = 0; i < frames; i++) {
        r->frames[i].pixels = malloc((size_t)w * h * 4);
        if (!r->frames[i].pixels) { nemo_raster_free(r); return false; }
    }
    r->pixels = r->frames[0].pixels;
    r->width = w; r->height = h; r->bytes = bytes; r->plays = 1;
    return true;
}

void nemo_raster_free(NemoRaster *r)
{
    if (!r) return;
    if (r->frames) {
        for (unsigned i = 0; i < r->frame_count; i++) free(r->frames[i].pixels);
        free(r->frames);
    } else free(r->pixels);
    memset(r, 0, sizeof(*r));
}

bool nemo_raster_prepare(NemoRaster *r, unsigned frame, const NemoRasterComposer *c)
{
    if (!r->frames || frame >= r->frame_count ||
        (c->valid && c->base >= frame) || c->left > r->width || c->top > r->height ||
        c->width > r->width-c->left || c->height > r->height-c->top) return false;
    uint32_t *out = r->frames[frame].pixels;
    if (c->valid) memcpy(out, r->frames[c->base].pixels, (size_t)r->width*r->height*4);
    else for (size_t i = 0; i < (size_t)r->width*r->height; i++) out[i] = c->background;
    if (c->clear)
        for (unsigned y = c->top; y < c->top+c->height; y++)
            for (unsigned x = c->left; x < c->left+c->width; x++)
                out[(size_t)y*r->width+x] = c->background;
    return true;
}

bool nemo_raster_dispose(NemoRaster *r, NemoRasterComposer *c, unsigned frame,
                         unsigned disposal, unsigned left, unsigned top,
                         unsigned width, unsigned height)
{
    if (frame >= r->frame_count || disposal > 3 || left > r->width || top > r->height ||
        width > r->width-left || height > r->height-top) return false;
    /* Restoring previous keeps the same pre-frame base, including an earlier
     * background-clear rectangle. No saved full-canvas copy is allocated. */
    if (disposal == 3) return true;
    c->base = frame; c->valid = true; c->clear = disposal == 2;
    c->left = left; c->top = top; c->width = width; c->height = height;
    return true;
}

unsigned nemo_raster_tick(NemoRaster *r, uint32_t now, bool *changed)
{
    *changed = false;
    if (!r->frames || r->frame_count < 2 || r->finished) return 0;
    if (!r->started) {
        r->started = true;
        r->last_tick = now;
        for (unsigned i = 0; i < r->frame_count; i++) r->duration += r->frames[i].delay_ms;
    } else {
        r->elapsed += (uint32_t)(now-r->last_tick);
        r->last_tick = now;
    }
    unsigned index = r->frame_count-1, next = 0;
    if (!r->duration || (r->plays && r->elapsed/r->duration >= r->plays)) {
        r->finished = true;
    } else {
        uint64_t time = r->elapsed % r->duration;
        if (!r->plays) r->elapsed = time;
        for (index = 0; index < r->frame_count; index++) {
            if (time < r->frames[index].delay_ms) {
                next = (unsigned)(r->frames[index].delay_ms-time);
                break;
            }
            time -= r->frames[index].delay_ms;
        }
    }
    *changed = index != r->frame_index;
    r->frame_index = index;
    r->pixels = r->frames[index].pixels;
    return next;
}
