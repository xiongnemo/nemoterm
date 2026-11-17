/* SPDX-License-Identifier: MIT */
#ifndef NEMO_REGIS_FONT_H
#define NEMO_REGIS_FONT_H
#include <stdbool.h>
#include <stddef.h>
#include <wchar.h>

typedef struct NemoRegisFontWin NemoRegisFontWin;
/* One terminal owns one lazy font provider. No HWND, screen DC, global cache,
 * or font installation. The default face is the profile's selected face. */
NemoRegisFontWin *nemo_regis_font_new(const wchar_t *family, int weight);
void nemo_regis_font_free(NemoRegisFontWin *);
size_t nemo_regis_font_bytes(const NemoRegisFontWin *);
typedef struct NemoRegisFontInfo {
    wchar_t family[32];
    int pixel_height, weight, left, top;
    unsigned width, height;
} NemoRegisFontInfo;
bool nemo_regis_font_info(const NemoRegisFontWin *, NemoRegisFontInfo *);
/* NemoRegisConfig.glyph callback. Empty font selects the default; a nonempty
 * UTF-8 name selects a Windows family. Returns a tightly packed binary mask.
 * The returned dimensions fit both requested bounds and capacity. */
bool nemo_regis_font_glyph(void *, const char *font, unsigned character,
                           unsigned max_width, unsigned max_height,
                           unsigned char *pixels, size_t capacity,
                           unsigned *width, unsigned *height);
#endif
