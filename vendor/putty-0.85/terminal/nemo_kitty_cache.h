/* SPDX-License-Identifier: MIT */
#ifndef NEMO_KITTY_CACHE_H
#define NEMO_KITTY_CACHE_H
#include "nemo_kitty.h"
#include "nemo_raster.h"

#define NEMO_KITTY_IMAGE_MAX 128u
#define NEMO_KITTY_AXIS_MAX 8192u
typedef struct NemoKittyCache NemoKittyCache;
typedef struct NemoKittyImage NemoKittyImage;
typedef enum NemoKittyImageStatus {
    NEMO_KITTY_IMAGE_OK, NEMO_KITTY_IMAGE_INVALID,
    NEMO_KITTY_IMAGE_UNSUPPORTED, NEMO_KITTY_IMAGE_LIMIT,
    NEMO_KITTY_IMAGE_NOMEM, NEMO_KITTY_IMAGE_DECODE,
    NEMO_KITTY_IMAGE_BUSY
} NemoKittyImageStatus;
typedef struct NemoKittyImageResult {
    NemoKittyImageStatus status;
    NemoKittyImage *image;
    uint32_t id, number;
    unsigned width, height;
    bool changed, query;
} NemoKittyImageResult;

/* Admission includes retained cache data and transient decode/allocation costs.
 * The owner adds transport and other protocols' storage to these numbers.
 * When evict is false (queries), admission must not mutate any image state. */
typedef bool (*NemoKittyCacheAdmission)(void *, size_t current, size_t extra, bool evict);
typedef bool (*NemoKittyPngDecode)(void *, const void *, size_t, NemoRaster *,
                                 NemoRasterAdmission, void *);
/* Discard all placement references before the image is freed. This callback
 * must not mutate the cache; read-only accessors remain available. */
typedef void (*NemoKittyImageRemoved)(void *, const NemoKittyImage *);
NemoKittyCache *nemo_kitty_cache_new(size_t budget, NemoKittyCacheAdmission,
                                   NemoKittyPngDecode, NemoKittyImageRemoved, void *);
void nemo_kitty_cache_free(NemoKittyCache *);
void nemo_kitty_cache_clear(NemoKittyCache *);
size_t nemo_kitty_cache_memory(const NemoKittyCache *);
unsigned nemo_kitty_cache_count(const NemoKittyCache *);
uint64_t nemo_kitty_cache_generation(const NemoKittyCache *);

/* Handle t/T image loading or q decoder validation. No placement or terminal
 * response is performed here. Queries never retain data, allocate client ids,
 * evict images, or change existing ids. Unsupported media/codec combinations
 * fail explicitly without accessing a filename or shared-memory name. */
NemoKittyImageResult nemo_kitty_cache_load(NemoKittyCache *, const NemoKittyPacket *);
/* Nonzero id or number, but not both. Number lookup chooses the newest image.
 * Returned image/raster pointers are borrowed until a mutating cache operation.
 * The placement owner must track removals through the callback above. */
NemoKittyImage *nemo_kitty_cache_find(NemoKittyCache *, uint32_t id, uint32_t number);
uint32_t nemo_kitty_image_id(const NemoKittyImage *);
uint32_t nemo_kitty_image_number(const NemoKittyImage *);
const NemoRaster *nemo_kitty_image_raster(const NemoKittyImage *);
unsigned nemo_kitty_image_references(const NemoKittyImage *);
bool nemo_kitty_image_reference(NemoKittyCache *, NemoKittyImage *, bool add);
bool nemo_kitty_cache_remove(NemoKittyCache *, NemoKittyImage *);
#endif
