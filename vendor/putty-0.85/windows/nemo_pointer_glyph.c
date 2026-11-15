/* SPDX-License-Identifier: MIT */
#include "nemo_pointer_glyph.h"
#include <stdlib.h>
#include <string.h>

typedef struct { int x, y; } Point;
typedef struct { uint8_t ink[32][32]; } Glyph;
/* 0 = transparent, 1 = black outline, 2 = white interior. */
static void pixel(Glyph *g, int x, int y, uint8_t ink)
{
    if ((unsigned)x < 32 && (unsigned)y < 32) g->ink[y][x] = ink;
}
static void line(Glyph *g, Point a, Point b, uint8_t ink)
{
    int dx = abs(b.x-a.x), sx = a.x < b.x ? 1 : -1;
    int dy = -abs(b.y-a.y), sy = a.y < b.y ? 1 : -1, error = dx+dy;
    for (;;) {
        pixel(g, a.x, a.y, ink);
        if (a.x == b.x && a.y == b.y) break;
        int next = 2*error;
        if (next >= dy) { error += dy; a.x += sx; }
        if (next <= dx) { error += dx; a.y += sy; }
    }
}
static void polygon(Glyph *g, const Point *p, size_t count)
{
    for (int y = 0; y < 32; y++) for (int x = 0; x < 32; x++) {
        bool inside = false;
        for (size_t i = 0, j = count-1; i < count; j = i++)
            if ((p[i].y > y) != (p[j].y > y) &&
                x < (p[j].x-p[i].x)*(y-p[i].y)/(p[j].y-p[i].y)+p[i].x)
                inside = !inside;
        if (inside) pixel(g, x, y, 2);
    }
    for (size_t i = 0; i < count; i++) line(g, p[i], p[(i+1)%count], 1);
}
#define POLYGON(g, ...) do { const Point p[] = {__VA_ARGS__}; \
    polygon(g, p, sizeof(p)/sizeof(*p)); } while (0)

int nemo_pointer_glyph_index(NemoPointerShape shape)
{
    switch (shape) {
      case NEMO_POINTER_ALIAS: return 0;
      case NEMO_POINTER_CELL: return 1;
      case NEMO_POINTER_COPY: return 2;
      case NEMO_POINTER_GRAB: return 3;
      case NEMO_POINTER_GRABBING: return 4;
      case NEMO_POINTER_VERTICAL_TEXT: return 5;
      case NEMO_POINTER_ZOOM_IN: return 6;
      case NEMO_POINTER_ZOOM_OUT: return 7;
      default: return -1;
    }
}

static void glyph(Glyph *g, NemoPointerShape shape, unsigned *hx, unsigned *hy)
{
    *hx = 15; *hy = 15;
    switch (shape) {
      case NEMO_POINTER_ALIAS:
      case NEMO_POINTER_COPY:
        POLYGON(g, {3,2}, {3,22}, {8,17}, {12,26}, {16,24}, {12,15}, {22,15});
        POLYGON(g, {17,18}, {30,18}, {30,30}, {17,30});
        if (shape == NEMO_POINTER_COPY) {
            line(g, (Point){20,24}, (Point){27,24}, 1);
            line(g, (Point){24,20}, (Point){24,28}, 1);
        } else {
            line(g, (Point){20,27}, (Point){20,24}, 1);
            line(g, (Point){20,24}, (Point){27,24}, 1);
            line(g, (Point){24,21}, (Point){27,24}, 1);
            line(g, (Point){24,27}, (Point){27,24}, 1);
        }
        *hx = 3; *hy = 2;
        break;
      case NEMO_POINTER_CELL:
        POLYGON(g, {13,3}, {18,3}, {18,13}, {28,13}, {28,18}, {18,18},
                {18,28}, {13,28}, {13,18}, {3,18}, {3,13}, {13,13});
        break;
      case NEMO_POINTER_GRAB:
        POLYGON(g, {8,28}, {6,23}, {2,17}, {2,15}, {4,14}, {8,18},
                {7,8}, {8,6}, {10,6}, {12,15}, {12,4}, {14,3}, {16,4},
                {17,15}, {18,5}, {20,5}, {21,7}, {21,16}, {24,9},
                {26,9}, {27,11}, {25,23}, {22,28});
        *hx = 15; *hy = 14;
        break;
      case NEMO_POINTER_GRABBING:
        POLYGON(g, {8,27}, {5,22}, {3,16}, {4,13}, {7,13}, {8,16},
                {8,10}, {10,8}, {13,8}, {15,7}, {18,8}, {21,8},
                {23,10}, {26,11}, {27,14}, {25,23}, {22,27});
        line(g, (Point){13,9}, (Point){13,15}, 1);
        line(g, (Point){18,9}, (Point){18,15}, 1);
        line(g, (Point){23,11}, (Point){23,16}, 1);
        *hx = 15; *hy = 15;
        break;
      case NEMO_POINTER_VERTICAL_TEXT:
        POLYGON(g, {4,9}, {7,9}, {7,14}, {24,14}, {24,9}, {27,9},
                {27,22}, {24,22}, {24,17}, {7,17}, {7,22}, {4,22});
        break;
      case NEMO_POINTER_ZOOM_IN:
      case NEMO_POINTER_ZOOM_OUT:
        POLYGON(g, {17,20}, {20,17}, {29,26}, {26,29});
        for (int y = 2; y <= 22; y++) for (int x = 2; x <= 22; x++) {
            int distance = (x-12)*(x-12)+(y-12)*(y-12);
            if (distance <= 100) pixel(g, x, y, distance >= 64 ? 1 : 2);
        }
        line(g, (Point){7,12}, (Point){17,12}, 1);
        if (shape == NEMO_POINTER_ZOOM_IN)
            line(g, (Point){12,7}, (Point){12,17}, 1);
        *hx = 12; *hy = 12;
        break;
      default: break;
    }
}

bool nemo_pointer_glyph_masks(NemoPointerShape shape, unsigned size,
    uint8_t *and_mask, uint8_t *xor_mask, size_t capacity,
    unsigned *hot_x, unsigned *hot_y)
{
    if (nemo_pointer_glyph_index(shape) < 0 || size < 32 ||
        size > NEMO_POINTER_CURSOR_MAX || !and_mask || !xor_mask ||
        !hot_x || !hot_y) return false;
    size_t stride = ((size + 15u)/16u)*2u, bytes = stride*size;
    if (bytes > capacity) return false;
    Glyph g = {{{0}}}; unsigned hx, hy;
    glyph(&g, shape, &hx, &hy);
    memset(and_mask, 255, bytes); memset(xor_mask, 0, bytes);
    for (unsigned y = 0; y < size; y++) for (unsigned x = 0; x < size; x++) {
        uint8_t ink = g.ink[y*32u/size][x*32u/size];
        size_t index = y*stride + x/8u;
        uint8_t bit = (uint8_t)(128u >> (x%8u));
        if (ink) and_mask[index] &= (uint8_t)~bit;
        if (ink == 2) xor_mask[index] |= bit;
    }
    /* Each output pixel samples floor(position*32/size). Round the hotspot
     * up to the first pixel that actually contains the base hotspot, rather
     * than placing it in the preceding transparent pixel at fractional DPI. */
    *hot_x = (hx*size+31u)/32u; *hot_y = (hy*size+31u)/32u;
    return true;
}
