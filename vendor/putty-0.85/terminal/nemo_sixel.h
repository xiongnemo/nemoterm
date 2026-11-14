/* SPDX-License-Identifier: MIT
 * Streaming Sixel bitmap decoder for NemoTerm. No platform dependencies.
 */
#ifndef NEMO_SIXEL_H
#define NEMO_SIXEL_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define NEMO_SIXEL_DEFAULT_BUDGET ((size_t)4 * 1024 * 1024)
#define NEMO_SIXEL_MAX_DIMENSION 8192u
#define NEMO_SIXEL_PALETTE_SIZE 256u

typedef struct NemoSixel NemoSixel;
typedef enum NemoSixelStatus {
    NEMO_SIXEL_OK,
    NEMO_SIXEL_LIMIT,
    NEMO_SIXEL_OUT_OF_MEMORY,
    NEMO_SIXEL_MALFORMED
} NemoSixelStatus;

typedef struct NemoSixelStats {
    unsigned width, height;
    unsigned aspect_vertical, aspect_horizontal;
    size_t allocated_bytes, budget_bytes;
    NemoSixelStatus status;
    bool finished;
} NemoSixelStats;

/* Colors are 0xAARRGGBB, i.e. BGRA bytes on little-endian Windows.
 * Budget covers all decoder allocations, including tiles and the object.
 * Zero budget selects DEFAULT_BUDGET. Allocator bookkeeping is not included.
 * Bitmap storage is tiled: small images do not allocate the full budget and
 * growth never makes a temporary second copy of the image.
 * Palette starts with VT340's 16 colors and an xterm-style cube/gray extension.
 * Pixels selected through # retain register identity and resolve its current
 * color when read. Until a # register is selected, set pixels use foreground.
 * Initial foreground/background pixels are independent of the palette.
 */
NemoSixel *nemo_sixel_init(size_t budget_bytes, uint32_t foreground,
                         uint32_t background, bool transparent);
void nemo_sixel_reset(NemoSixel *s, uint32_t foreground,
                      uint32_t background, bool transparent);
void nemo_sixel_free(NemoSixel *s);

/* Feed only Sixel payload after the DCS 'q', excluding ST/ESC/CAN/SUB.
 * Any chunk boundaries are permitted, including one byte at a time.
 * false means discard this image; continue consuming the enclosing DCS in
 * the terminal parser until ST or cancellation. Further feeds are harmless.
 * Finish commits a pending color/raster command and rejects a dangling '!'.
 */
bool nemo_sixel_feed(NemoSixel *s, const void *data, size_t size);
bool nemo_sixel_finish(NemoSixel *s);
NemoSixelStats nemo_sixel_stats(const NemoSixel *s);

/* Copy at most count pixels within [x,width) of a valid row. No allocation.
 * Output alpha is 0 or 255. Callers composite transparent pixels themselves.
 * No bitmap should be displayed when stats.status != NEMO_SIXEL_OK.
 */
size_t nemo_sixel_read_row(const NemoSixel *s, unsigned y, unsigned x,
                          uint32_t *bgra, size_t count);

/* DCS Pa is handled by the enclosing parser using this function; a raster
 * attributes command can override it. Decoder coordinates remain unscaled.
 * Rendering should scale by the reduced ratio, with its own output limit.
 */
void nemo_sixel_set_aspect(NemoSixel *s, unsigned vertical, unsigned horizontal);
/* These access the active palette, including shared storage when bound.
 * Palette updates can recolor finished images without changing their pixels. */
void nemo_sixel_get_palette(const NemoSixel *s, uint32_t palette[256]);
void nemo_sixel_set_palette(NemoSixel *s, const uint32_t palette[256]);

/* Bind an initialized opaque AARRGGBB palette before feeding the image.
 * The caller owns this array and must keep it alive until the decoder is freed
 * or reset. Binding belongs to this image and is unaffected by later changes
 * to the terminal's private/shared mode. Reset removes the binding.
 * changed is called after a parsed definition (or set_palette) changes shared
 * storage, even if the enclosing DCS is later canceled. It must not destroy or
 * re-enter the decoder. No pixel or palette allocation is made here. */
typedef void (*NemoSixelPaletteChanged)(void *);
bool nemo_sixel_share_palette(NemoSixel *s, uint32_t palette[256],
                             NemoSixelPaletteChanged changed, void *ctx);

/* Select 2..PALETTE_SIZE registers before drawing. Sixel register numbers
 * wrap modulo this count, as on DEC terminals. Reset restores PALETTE_SIZE. */
bool nemo_sixel_set_register_count(NemoSixel *s, unsigned count);

/* Optional shared-budget admission guard, called before each tile allocation.
 * current_bytes includes this decoder; allocation_bytes is the new request.
 * Return false to reject this image. The callback may evict other images.
 */
typedef bool (*NemoSixelAllocationGuard)(void *, size_t, size_t);
void nemo_sixel_set_allocation_guard(NemoSixel *s,
                                    NemoSixelAllocationGuard guard, void *ctx);

#endif
