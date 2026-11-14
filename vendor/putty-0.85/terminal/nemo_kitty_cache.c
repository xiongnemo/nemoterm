/* SPDX-License-Identifier: MIT */
#include "nemo_kitty_cache.h"
#include "nemo_zlib.h"
#include <limits.h>
#include <stdlib.h>
#include <string.h>

struct NemoKittyImage {
    struct NemoKittyImage *next;
    NemoRaster raster;
    uint32_t id, number;
    unsigned references;
    uint64_t age, sequence;
};
struct NemoKittyCache {
    NemoKittyImage *images;
    size_t budget, used, temporary;
    unsigned count;
    uint32_t next_id;
    uint64_t clock, generation, sequence;
    bool busy;
    NemoKittyCacheAdmission admit;
    NemoKittyPngDecode png;
    NemoKittyImageRemoved removed;
    void *ctx;
};

size_t nemo_kitty_cache_memory(const NemoKittyCache *s)
{ return s ? s->used + s->temporary : 0; }
unsigned nemo_kitty_cache_count(const NemoKittyCache *s)
{ return s ? s->count : 0; }
uint64_t nemo_kitty_cache_generation(const NemoKittyCache *s)
{ return s ? s->generation : 0; }
uint32_t nemo_kitty_image_id(const NemoKittyImage *im)
{ return im ? im->id : 0; }
uint32_t nemo_kitty_image_number(const NemoKittyImage *im)
{ return im ? im->number : 0; }
uint64_t nemo_kitty_image_sequence(const NemoKittyImage *im)
{ return im ? im->sequence : 0; }
const NemoRaster *nemo_kitty_image_raster(const NemoKittyImage *im)
{ return im ? &im->raster : NULL; }
unsigned nemo_kitty_image_references(const NemoKittyImage *im)
{ return im ? im->references : 0; }

static NemoKittyImage **locate(NemoKittyCache *s, const NemoKittyImage *im)
{
    NemoKittyImage **link = &s->images;
    while (*link && *link != im) link = &(*link)->next;
    return link;
}

static void remove_image(NemoKittyCache *s, NemoKittyImage **link)
{
    NemoKittyImage *im = *link;
    if (s->removed) s->removed(s->ctx, im);
    *link = im->next;
    s->used -= sizeof(*im) + im->raster.bytes;
    s->count--;
    s->generation++;
    nemo_raster_free(&im->raster);
    free(im);
}

void nemo_kitty_cache_clear(NemoKittyCache *s)
{
    if (!s || s->busy) return;
    s->busy = true;
    while (s->images) remove_image(s, &s->images);
    s->busy = false;
}

void nemo_kitty_cache_free(NemoKittyCache *s)
{
    if (!s || s->busy) return;
    nemo_kitty_cache_clear(s);
    free(s);
}

NemoKittyCache *nemo_kitty_cache_new(size_t budget, NemoKittyCacheAdmission admit,
                                   NemoKittyPngDecode png, NemoKittyImageRemoved removed,
                                   void *ctx)
{
    if (budget < sizeof(NemoKittyCache) ||
        (admit && !admit(ctx, 0, sizeof(NemoKittyCache), true))) return NULL;
    NemoKittyCache *s = calloc(1, sizeof(*s));
    if (s) {
        s->budget = budget; s->used = sizeof(*s); s->next_id = 1;
        s->admit = admit; s->png = png; s->removed = removed; s->ctx = ctx;
    }
    return s;
}

static NemoKittyImage *find(const NemoKittyCache *s, uint32_t id, uint32_t number)
{
    if ((!id && !number) || (id && number)) return NULL;
    /* New images are prepended, so number lookup naturally finds the newest. */
    for (NemoKittyImage *im = s->images; im; im = im->next)
        if (id ? im->id == id : im->number == number) return im;
    return NULL;
}

NemoKittyImage *nemo_kitty_cache_find(NemoKittyCache *s, uint32_t id, uint32_t number)
{
    if (!s || s->busy) return NULL;
    NemoKittyImage *im = find(s, id, number);
    if (im) im->age = ++s->clock;
    return im;
}

const NemoKittyImage *nemo_kitty_cache_peek(const NemoKittyCache *s, uint32_t id, uint32_t number)
{
    return s && !s->busy ? find(s,id,number) : NULL;
}

bool nemo_kitty_image_reference(NemoKittyCache *s, NemoKittyImage *im, bool add)
{
    if (!s || s->busy || !im || !*locate(s, im)) return false;
    if (add) {
        if (im->references == UINT_MAX) return false;
        im->references++;
    } else {
        if (!im->references) return false;
        im->references--;
    }
    return true;
}

bool nemo_kitty_cache_remove(NemoKittyCache *s, NemoKittyImage *im)
{
    if (!s || s->busy || !im) return false;
    NemoKittyImage **link = locate(s, im);
    if (!*link || (im->references && !s->removed)) return false;
    s->busy = true;
    remove_image(s, link);
    s->busy = false;
    return true;
}

unsigned nemo_kitty_cache_prune_range(NemoKittyCache *s, uint32_t first, uint32_t last)
{
    if (!s || s->busy || first>last) return 0;
    unsigned count=0;
    s->busy=true;
    NemoKittyImage **link=&s->images;
    while (*link) {
        NemoKittyImage *image=*link;
        if (image->id && image->id>=first && image->id<=last && !image->references) {
            remove_image(s,link);count++;
        } else link=&image->next;
    }
    s->busy=false;return count;
}

static bool evict_one(NemoKittyCache *s, const NemoKittyImage *protect)
{
    NemoKittyImage **oldest = NULL;
    for (NemoKittyImage **link = &s->images; *link; link = &(*link)->next) {
        NemoKittyImage *im = *link;
        if (im == protect || (im->references && !s->removed)) continue;
        if (!oldest || (!im->references && (*oldest)->references) ||
            (!!im->references == !!(*oldest)->references && im->age < (*oldest)->age))
            oldest = link;
    }
    if (!oldest) return false;
    remove_image(s, oldest);
    return true;
}

static bool reserve(NemoKittyCache *s, size_t extra,
                    const NemoKittyImage *protect, bool may_evict)
{
    if (extra > s->budget - sizeof(*s)) return false;
    for (;;) {
        size_t current = nemo_kitty_cache_memory(s);
        if (current <= s->budget && extra <= s->budget - current &&
            (!s->admit || s->admit(s->ctx, current, extra, may_evict))) return true;
        if (!may_evict || !evict_one(s, protect)) return false;
    }
}

typedef struct DecodeContext {
    NemoKittyCache *cache;
    NemoKittyImage *protect;
    bool query, called;
    unsigned width, height;
    size_t bytes;
    NemoKittyImageStatus failure;
} DecodeContext;

static bool pixels_admit(void *ctx, unsigned width, unsigned height, size_t bytes)
{
    DecodeContext *d = ctx;
    NemoKittyCache *s = d->cache;
    if (d->called || !width || !height || width > NEMO_KITTY_AXIS_MAX ||
        height > NEMO_KITTY_AXIS_MAX || !bytes ||
        bytes < (uint64_t)width * height * 4) {
        d->failure = NEMO_KITTY_IMAGE_DECODE;
        return false;
    }
    size_t metadata = d->query ? 0 : sizeof(NemoKittyImage);
    if (bytes > SIZE_MAX - metadata || !reserve(s, bytes + metadata, d->protect, !d->query)) {
        d->failure = NEMO_KITTY_IMAGE_LIMIT;
        return false;
    }
    d->called = true; d->width = width; d->height = height; d->bytes = bytes;
    s->temporary += bytes + metadata;
    return true;
}

static NemoKittyImageStatus decode_png(DecodeContext *d, const void *data,
                                       size_t length, NemoRaster *raster)
{
    static const unsigned char signature[8] = {137,80,78,71,13,10,26,10};
    if (length < sizeof(signature) || memcmp(data, signature, sizeof(signature)))
        return NEMO_KITTY_IMAGE_DECODE;
    if (!d->cache->png) return NEMO_KITTY_IMAGE_UNSUPPORTED;
    if (!d->cache->png(d->cache->ctx, data, length, raster, pixels_admit, d))
        return d->failure ? d->failure : NEMO_KITTY_IMAGE_DECODE;
    if (d->failure || !d->called || raster->width != d->width || raster->height != d->height ||
        raster->bytes != d->bytes || !raster->pixels || raster->frame_count > 1)
        return NEMO_KITTY_IMAGE_DECODE;
    return NEMO_KITTY_IMAGE_OK;
}

static NemoKittyImageStatus decode(DecodeContext *d, const NemoKittyPacket *packet,
                                   NemoRaster *raster)
{
    const NemoKittyCommand *cmd = &packet->command;
    unsigned format = nemo_kitty_get(cmd, 'f');
    unsigned compression = nemo_kitty_get(cmd, 'o');
    if (nemo_kitty_get(cmd, 't') != 'd' || (compression && compression != 'z') ||
        (format != 24 && format != 32 && format != 100)) return NEMO_KITTY_IMAGE_UNSUPPORTED;
    if (!packet->data || !packet->length) return NEMO_KITTY_IMAGE_INVALID;
    if (packet->length > NEMO_KITTY_DATA_MAX) return NEMO_KITTY_IMAGE_LIMIT;
    if (format == 100) {
        if (!compression) return decode_png(d, packet->data, packet->length, raster);
        size_t size = nemo_kitty_get(cmd, 'S');
        if (!size) return NEMO_KITTY_IMAGE_INVALID;
        if (size > NEMO_KITTY_DATA_MAX || !reserve(d->cache, size, d->protect, !d->query))
            return NEMO_KITTY_IMAGE_LIMIT;
        unsigned char *png = malloc(size);
        if (!png) return NEMO_KITTY_IMAGE_NOMEM;
        d->cache->temporary += size;
        NemoKittyImageStatus status = NEMO_KITTY_IMAGE_DECODE;
        if (nemo_zlib_decode(png, size, packet->data, packet->length))
            status = decode_png(d, png, size, raster);
        free(png);
        d->cache->temporary -= size;
        return status;
    }
    unsigned width = nemo_kitty_get(cmd, 's'), height = nemo_kitty_get(cmd, 'v');
    if (!width || !height || width > NEMO_KITTY_AXIS_MAX || height > NEMO_KITTY_AXIS_MAX)
        return NEMO_KITTY_IMAGE_INVALID;
    uint64_t count = (uint64_t)width * height;
    unsigned channels = format / 8;
    if (!compression && count * channels != packet->length) return NEMO_KITTY_IMAGE_INVALID;
    if (!pixels_admit(d, width, height, (size_t)count * 4)) return NEMO_KITTY_IMAGE_LIMIT;
    raster->pixels = malloc((size_t)count * 4);
    if (!raster->pixels) return NEMO_KITTY_IMAGE_NOMEM;
    const unsigned char *source = packet->data;
    if (compression) {
        if (!nemo_zlib_decode(raster->pixels, (size_t)count * channels, packet->data, packet->length))
            return NEMO_KITTY_IMAGE_DECODE;
        source = (const unsigned char *)raster->pixels;
    }
    raster->width = width; raster->height = height; raster->bytes = (size_t)count * 4;
    /* Work backwards so packed RGB expands in the final four-byte raster. */
    for (size_t i = (size_t)count; i-- > 0;) {
        const unsigned char *p = source + i * channels;
        unsigned alpha = channels == 4 ? p[3] : 255;
        raster->pixels[i] = (uint32_t)alpha << 24 | (uint32_t)p[0] << 16 |
            (uint32_t)p[1] << 8 | p[2];
        raster->partial_alpha |= alpha != 0 && alpha != 255;
    }
    return NEMO_KITTY_IMAGE_OK;
}

static uint32_t available_id(NemoKittyCache *s)
{
    uint32_t id = s->next_id;
    for (unsigned i = 0; i <= s->count; i++) {
        if (!find(s, id, 0)) return id;
        if (!++id) id = 1;
    }
    return 0; /* More candidates than live ids are searched. */
}

NemoKittyImageResult nemo_kitty_cache_load(NemoKittyCache *s, const NemoKittyPacket *p)
{
    NemoKittyImageResult result = {0};
    result.status = NEMO_KITTY_IMAGE_INVALID;
    if (!s || !p) return result;
    if (s->busy) { result.status = NEMO_KITTY_IMAGE_BUSY; return result; }
    const NemoKittyCommand *c = &p->command;
    result.id = nemo_kitty_get(c, 'i'); result.number = nemo_kitty_get(c, 'I');
    uint32_t action = nemo_kitty_get(c, 'a');
    result.query = action == 'q';
    if ((action == 'q' && nemo_kitty_has(c, 'e')) ||
        (action != 'q' && action != 't' && action != 'T')) {
        result.status = NEMO_KITTY_IMAGE_UNSUPPORTED; return result;
    }
    if ((result.id && result.number) ||
        nemo_kitty_get(c, 'm') || (result.query && !result.id)) return result;
    s->busy = true;
    uint64_t generation = s->generation;
    NemoKittyImage *old = result.query ? NULL : find(s, result.id, 0);
    DecodeContext context = {s, old, result.query, false, 0, 0, 0, NEMO_KITTY_IMAGE_OK};
    NemoRaster raster = {0};
    if (old && old->references && !s->removed) {
        result.status = NEMO_KITTY_IMAGE_BUSY;
        goto done;
    }
    result.status = decode(&context, p, &raster);
    if (result.status != NEMO_KITTY_IMAGE_OK) goto done;
    result.width = raster.width; result.height = raster.height;
    if (result.query) goto done;
    while (!old && s->count >= NEMO_KITTY_IMAGE_MAX) {
        if (!evict_one(s, NULL)) { result.status = NEMO_KITTY_IMAGE_LIMIT; goto done; }
    }
    NemoKittyImage *im = calloc(1, sizeof(*im));
    if (!im) { result.status = NEMO_KITTY_IMAGE_NOMEM; goto done; }
    if (result.number) {
        result.id = available_id(s);
        if (!result.id) { free(im); result.status = NEMO_KITTY_IMAGE_LIMIT; goto done; }
        s->next_id = result.id + 1;
        if (!s->next_id) s->next_id = 1;
    }
    /* Retransmission keeps the internal image identity used for draw order. */
    im->sequence = old ? old->sequence : ++s->sequence;
    if (old) remove_image(s, locate(s, old));
    im->id = result.id; im->number = result.number;
    im->raster = raster; memset(&raster, 0, sizeof(raster));
    im->age = ++s->clock;
    im->next = s->images; s->images = im;
    s->used += sizeof(*im) + im->raster.bytes;
    s->count++; s->generation++;
    result.image = im;
  done:
    nemo_raster_free(&raster);
    s->temporary = 0;
    s->busy = false;
    result.changed = generation != s->generation;
    return result;
}
