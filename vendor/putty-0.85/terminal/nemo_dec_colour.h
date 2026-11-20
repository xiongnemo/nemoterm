/* SPDX-License-Identifier: MIT
 * Shared by the terminal renderer and the embedded Windows console parser.
 * Keep only the last value of each indexed colour until the terminating ST.
 */
#ifndef NEMO_DEC_COLOUR_H
#define NEMO_DEC_COLOUR_H
#include <stdint.h>
#include <stdlib.h>
#include <limits.h>
#include <string.h>
#ifndef __cplusplus
#include <stdbool.h>
#endif

/* Integer HLS conversion. DEC hue is blue=0, red=120, green=240. */
static inline uint32_t nemo_dec_hls(unsigned hue, unsigned light, unsigned saturation)
{
    unsigned h = (hue % 360 + 240) % 360;
    unsigned chroma, x, base, r = 0, g = 0, b = 0;
    if (light > 100) light = 100;
    if (saturation > 100) saturation = 100;
    chroma = (100 - (unsigned)abs((int)(2 * light) - 100)) * saturation;
    x = chroma * (60 - (unsigned)abs((int)(h % 120) - 60)) / 60;
    base = light * 100 - chroma / 2;
    switch (h / 60) {
      case 0: r = chroma; g = x; break;
      case 1: r = x; g = chroma; break;
      case 2: g = chroma; b = x; break;
      case 3: g = x; b = chroma; break;
      case 4: r = x; b = chroma; break;
      default: r = chroma; b = x; break;
    }
    r = ((r + base) * 255 + 5000) / 10000;
    g = ((g + base) * 255 + 5000) / 10000;
    b = ((b + base) * 255 + 5000) / 10000;
    return UINT32_C(0xff000000) | (r << 16) | (g << 8) | b;
}

typedef struct NemoPendingColourTable {
    struct { bool enabled; uint8_t r, g, b; } entries[256];
    unsigned fields[5], field;
    bool invalid, digit;
} NemoPendingColourTable;

static inline void nemo_dec_colour_entry(struct NemoPendingColourTable *p)
{
    unsigned *v = p->fields;
    if (!p->invalid && p->digit && p->field == 4 && v[0] < 256 &&
        (v[1] == 1 || v[1] == 2)) {
        unsigned r, g, b;
        if (v[1] == 1) {
            uint32_t pixel = nemo_dec_hls(v[2], v[3], v[4]);
            r = (pixel >> 16) & 255; g = (pixel >> 8) & 255; b = pixel & 255;
        } else {
            r = ((v[2]<100u?v[2]:100u)*255+50)/100;
            g = ((v[3]<100u?v[3]:100u)*255+50)/100;
            b = ((v[4]<100u?v[4]:100u)*255+50)/100;
        }
        p->entries[v[0]].enabled = true;
        p->entries[v[0]].r = (uint8_t)r;
        p->entries[v[0]].g = (uint8_t)g;
        p->entries[v[0]].b = (uint8_t)b;
    }
    memset(p->fields, 0, sizeof(p->fields));
    p->field = 0; p->invalid = p->digit = false;
}

static inline void nemo_dec_colour_byte(struct NemoPendingColourTable *p, unsigned c)
{
    if (c == '/') {
        nemo_dec_colour_entry(p);
    } else if (p->invalid) {
        return;
    } else if (c >= '0' && c <= '9') {
        unsigned *v = &p->fields[p->field], digit = c-'0';
        if (*v > (UINT_MAX-digit)/10) p->invalid = true;
        else *v = *v*10 + digit;
        p->digit = true;
    } else if (c == ';' && p->field < 4 && p->digit) {
        p->field++; p->digit = false;
    } else {
        p->invalid = true;
    }
}

#endif
