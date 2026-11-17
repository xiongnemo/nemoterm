/* SPDX-License-Identifier: MIT
 * Native, terminal-owned adapter for the pinned XTerm ReGIS parser.
 * The caller creates this lazily. No process-global parsing or drawing state.
 */
#ifndef NEMO_REGIS_H
#define NEMO_REGIS_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef struct NemoRegis NemoRegis;
typedef enum NemoRegisResult {
    NEMO_REGIS_OK, NEMO_REGIS_INVALID, NEMO_REGIS_LIMIT, NEMO_REGIS_NOMEM
} NemoRegisResult;
typedef struct NemoRegisConfig {
    unsigned width, height, max_width, max_height;
    unsigned colours; /* 2..1024; VT340 normally uses 16 */
    int terminal_id;
    size_t memory_limit; /* includes owner, pages, tiles, fonts and input */
    uint64_t work_limit; /* per complete request, zero selects the default */
    bool private_colours;
    void *user;
    /* Reserve/release the entire owner's footprint in the caller's shared
     * image budget. Releases cannot fail; growing reservations can fail. */
    bool (*resize_memory)(void *, size_t old_bytes, size_t new_bytes);
    void (*reply)(void *, const char *, size_t);
    void (*refresh)(void *);
    /* Report timing requests to a scheduler; the decoder never sleeps. */
    void (*delay)(void *, unsigned milliseconds);
    bool (*glyph)(void *, const char *font, unsigned character,
                  unsigned max_width, unsigned max_height,
                  unsigned char *pixels, size_t capacity,
                  unsigned *width, unsigned *height);
} NemoRegisConfig;

NemoRegis *nemo_regis_new(const NemoRegisConfig *);
void nemo_regis_free(NemoRegis *);
void nemo_regis_reset(NemoRegis *); /* RIS: release every page and alphabet */
void nemo_regis_screen(NemoRegis *, unsigned alternate);
void nemo_regis_private_colours(NemoRegis *, bool);
NemoRegisResult nemo_regis_parse(NemoRegis *, unsigned mode,
                                const void *data, size_t length);
size_t nemo_regis_bytes(const NemoRegis *);
unsigned nemo_regis_display_page(const NemoRegis *);
/* Straight ARGB, zero for transparent pixels; coordinates are unscaled. */
size_t nemo_regis_read_row(const NemoRegis *, unsigned page, unsigned y,
                          unsigned x, uint32_t *out, size_t count);
bool nemo_regis_page_size(const NemoRegis *, unsigned page,
                          unsigned *width, unsigned *height);
#endif
