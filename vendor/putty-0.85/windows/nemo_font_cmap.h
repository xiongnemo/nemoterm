#ifndef NEMO_FONT_CMAP_H
#define NEMO_FONT_CMAP_H
#include <stddef.h>
#include <stdint.h>
/* Bounded OpenType Unicode cmap lookup. Zero denotes a missing glyph. */
unsigned nemo_cmap_glyph(const void *table, size_t size, uint32_t codepoint);
const void *nemo_font_cmap(const void *font, size_t size, size_t *cmap_size);
#endif
