/* SPDX-License-Identifier: MIT
 * Protocol references (implementation is original):
 * https://vt100.net/docs/vt3xx-gp/chapter14.html
 * https://vt100.net/docs/vt3xx-gp/chapter2.html
 * https://invisible-island.net/xterm/ctlseqs/ctlseqs.html#h3-Sixel-Graphics
 *
 * Width/height include declared raster extents and actually set pixels.
 * Raster extents are not a clipping rectangle (DEC chapter 14).
 * Pixel colors are baked at drawing time; changing a register does not
 * retroactively recolor pixels already drawn or graphics retained elsewhere.
 */
#include "nemo_sixel.h"

#include <stdlib.h>
#include <string.h>
#include <limits.h>

#define TILE_SIDE 32u
#define BUCKET_COUNT 256u
#define PARAM_COUNT 5u

typedef struct SixelTile {
    struct SixelTile *next;
    unsigned tx, ty;
    uint32_t pixels[TILE_SIDE * TILE_SIDE];
} SixelTile;

struct NemoSixel {
    NemoSixelAllocationGuard allocation_guard;
    void *allocation_context;
    SixelTile *buckets[BUCKET_COUNT];
    uint32_t palette[NEMO_SIXEL_PALETTE_SIZE];
    uint32_t foreground, background, params[PARAM_COUNT];
    unsigned x, y, width, height, aspect_vertical, aspect_horizontal;
    unsigned param_index;
    unsigned char command;
    bool parameter_overflow, seen_pixels, finished;
    size_t allocated_bytes, budget_bytes;
    NemoSixelStatus status;
};

static unsigned bucket(unsigned tx, unsigned ty)
{
    return (tx * 31u + ty * 73u) % BUCKET_COUNT;
}

static uint32_t rgb(unsigned r, unsigned g, unsigned b)
{
    return UINT32_C(0xff000000) | (r << 16) | (g << 8) | b;
}

static unsigned percent(unsigned p)
{
    if (p > 100) p = 100;
    return (p * 255 + 50) / 100;
}

static void default_palette(NemoSixel *s)
{
    static const unsigned char dec[16][3] = {
        {0, 0, 0}, {20, 20, 80}, {80, 13, 13}, {20, 80, 20},
        {80, 20, 80}, {20, 80, 80}, {80, 80, 20}, {53, 53, 53},
        {26, 26, 26}, {33, 33, 60}, {60, 26, 26}, {33, 60, 33},
        {60, 33, 60}, {33, 60, 60}, {60, 60, 33}, {80, 80, 80}
    };
    static const unsigned char level[6] = {0, 95, 135, 175, 215, 255};
    unsigned i;
    for (i = 0; i < 16; i++)
        s->palette[i] = rgb(percent(dec[i][0]), percent(dec[i][1]),
                            percent(dec[i][2]));
    for (i = 16; i < 232; i++) {
        unsigned n = i - 16;
        s->palette[i] = rgb(level[n / 36], level[(n / 6) % 6], level[n % 6]);
    }
    for (i = 232; i < 256; i++) {
        unsigned v = 8 + (i - 232) * 10;
        s->palette[i] = rgb(v, v, v);
    }
}

void nemo_sixel_free(NemoSixel *s)
{
    unsigned i;
    if (!s) return;
    for (i = 0; i < BUCKET_COUNT; i++) {
        SixelTile *t = s->buckets[i];
        while (t) {
            SixelTile *next = t->next;
            free(t);
            t = next;
        }
    }
    free(s);
}

void nemo_sixel_reset(NemoSixel *s, uint32_t foreground,
                      uint32_t background, bool transparent)
{
    unsigned i;
    size_t limit;
    if (!s) return;
    limit = s->budget_bytes;
    for (i = 0; i < BUCKET_COUNT; i++) {
        SixelTile *t = s->buckets[i];
        while (t) {
            SixelTile *next = t->next;
            free(t);
            t = next;
        }
    }
    memset(s, 0, sizeof(*s));
    s->budget_bytes = limit;
    s->allocated_bytes = sizeof(*s);
    s->foreground = foreground | UINT32_C(0xff000000);
    s->background = transparent ? 0 : background | UINT32_C(0xff000000);
    s->aspect_vertical = s->aspect_horizontal = 1;
    default_palette(s);
}

NemoSixel *nemo_sixel_init(size_t budget_bytes, uint32_t foreground,
                         uint32_t background, bool transparent)
{
    NemoSixel *s;
    if (!budget_bytes) budget_bytes = NEMO_SIXEL_DEFAULT_BUDGET;
    if (budget_bytes < sizeof(*s)) return NULL;
    s = calloc(1, sizeof(*s));
    if (!s) return NULL;
    s->budget_bytes = budget_bytes;
    nemo_sixel_reset(s, foreground, background, transparent);
    return s;
}

static bool fail(NemoSixel *s, NemoSixelStatus status)
{
    if (s->status == NEMO_SIXEL_OK) s->status = status;
    return false;
}

/* Also bound logical geometry, not just allocated tiles: sparse hostile
 * images must not cause unbounded rendering/scanline loops downstream. */
static bool grow_extent(NemoSixel *s, unsigned width, unsigned height)
{
    if (width < s->width) width = s->width;
    if (height < s->height) height = s->height;
    if (width > NEMO_SIXEL_MAX_DIMENSION || height > NEMO_SIXEL_MAX_DIMENSION ||
        (height && (size_t)width > s->budget_bytes / 4 / height))
        return fail(s, NEMO_SIXEL_LIMIT);
    s->width = width;
    s->height = height;
    return true;
}

static SixelTile *find_tile(NemoSixel *s, unsigned tx, unsigned ty)
{
    unsigned hash = bucket(tx, ty), i;
    SixelTile *t;
    for (t = s->buckets[hash]; t; t = t->next)
        if (t->tx == tx && t->ty == ty) return t;
    if (sizeof(*t) > s->budget_bytes - s->allocated_bytes) {
        fail(s, NEMO_SIXEL_LIMIT);
        return NULL;
    }
    if (s->allocation_guard &&
        !s->allocation_guard(s->allocation_context, s->allocated_bytes, sizeof(*t))) {
        fail(s, NEMO_SIXEL_LIMIT);
        return NULL;
    }
    t = malloc(sizeof(*t));
    if (!t) {
        fail(s, NEMO_SIXEL_OUT_OF_MEMORY);
        return NULL;
    }
    s->allocated_bytes += sizeof(*t);
    t->tx = tx;
    t->ty = ty;
    for (i = 0; i < TILE_SIDE * TILE_SIDE; i++) t->pixels[i] = s->background;
    t->next = s->buckets[hash];
    s->buckets[hash] = t;
    return t;
}

static bool draw_sixel(NemoSixel *s, unsigned bits, uint32_t repeat)
{
    unsigned highest = 0, bit, end;
    if (!repeat) repeat = 1;
    if (repeat > NEMO_SIXEL_MAX_DIMENSION - s->x)
        return fail(s, NEMO_SIXEL_LIMIT);
    end = s->x + repeat;
    s->seen_pixels = true;
    if (!bits) {
        s->x = end;
        return true;
    }
    for (bit = 0; bit < 6; bit++)
        if (bits & (1u << bit)) highest = bit + 1;
    if (!grow_extent(s, end, s->y + highest)) return false;
    for (bit = 0; bit < 6; bit++) {
        unsigned x = s->x, y = s->y + bit;
        if (!(bits & (1u << bit))) continue;
        while (x < end) {
            SixelTile *t = find_tile(s, x / TILE_SIDE, y / TILE_SIDE);
            unsigned n = TILE_SIDE - x % TILE_SIDE, j;
            uint32_t *p;
            if (!t) return false;
            if (n > end - x) n = end - x;
            p = &t->pixels[(y % TILE_SIDE) * TILE_SIDE + x % TILE_SIDE];
            for (j = 0; j < n; j++) p[j] = s->foreground;
            x += n;
        }
    }
    s->x = end;
    return true;
}

/* Integer HLS conversion. DEC hue is blue=0, red=120, green=240. */
static uint32_t hls(unsigned hue, unsigned light, unsigned saturation)
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
    return rgb(((r + base) * 255 + 5000) / 10000,
               ((g + base) * 255 + 5000) / 10000,
               ((b + base) * 255 + 5000) / 10000);
}

void nemo_sixel_set_aspect(NemoSixel *s, unsigned vertical, unsigned horizontal)
{
    unsigned a, b;
    if (!s || !vertical || !horizontal) return;
    a = vertical;
    b = horizontal;
    while (b) {
        unsigned t = a % b;
        a = b;
        b = t;
    }
    s->aspect_vertical = vertical / a;
    s->aspect_horizontal = horizontal / a;
}

static bool commit_parameters(NemoSixel *s)
{
    const uint32_t *p = s->params;
    if (s->parameter_overflow) return fail(s, NEMO_SIXEL_MALFORMED);
    if (s->command == '#') {
        if (p[0] >= NEMO_SIXEL_PALETTE_SIZE)
            return fail(s, NEMO_SIXEL_LIMIT);
        if (s->param_index == 4) {
            if (p[1] == 2)
                s->palette[p[0]] = rgb(percent(p[2]), percent(p[3]), percent(p[4]));
            else if (p[1] == 1)
                s->palette[p[0]] = hls(p[2], p[3], p[4]);
            else return fail(s, NEMO_SIXEL_MALFORMED);
        } else if (s->param_index != 0) {
            return fail(s, NEMO_SIXEL_MALFORMED);
        }
        s->foreground = s->palette[p[0]];
    } else if (s->command == '"' && !s->seen_pixels) {
        if (s->param_index < 1) return fail(s, NEMO_SIXEL_MALFORMED);
        nemo_sixel_set_aspect(s, p[0] ? p[0] : 1, p[1] ? p[1] : 1);
        if (!grow_extent(s, p[2], p[3])) return false;
    }
    s->command = 0;
    return true;
}

static bool feed_byte(NemoSixel *s, unsigned char c)
{
    if (s->command) {
        if (c >= '0' && c <= '9') {
            uint32_t *p = &s->params[s->param_index];
            unsigned digit = c - '0';
            if (*p > (UINT32_MAX - digit) / 10) {
                s->parameter_overflow = true;
            } else {
                *p = *p * 10 + digit;
            }
            return true;
        }
        if (c == ';' && s->command != '!') {
            if (s->param_index + 1 < PARAM_COUNT) s->param_index++;
            else s->parameter_overflow = true;
            return true;
        }
        /* Line wrapping in encoders can occur even within parameters. */
        if (c == '\r' || c == '\n' || c == '\t' || c == ' ') return true;
        if (s->command == '!') {
            uint32_t repeat = s->params[0];
            s->command = 0;
            if (s->parameter_overflow || c < '?' || c > '~')
                return fail(s, NEMO_SIXEL_MALFORMED);
            return draw_sixel(s, c - '?', repeat);
        }
        if (!commit_parameters(s)) return false;
    }
    if (c >= '?' && c <= '~') return draw_sixel(s, c - '?', 1);
    if (c == '!' || c == '#' || c == '"') {
        s->command = c;
        s->param_index = 0;
        s->parameter_overflow = false;
        memset(s->params, 0, sizeof(s->params));
    } else if (c == '$') {
        s->x = 0;
    } else if (c == '-') {
        if (s->y > NEMO_SIXEL_MAX_DIMENSION - 6)
            return fail(s, NEMO_SIXEL_LIMIT);
        s->y += 6;
        s->x = 0;
    } else if (c == 0x18 || c == 0x1a || c == 0x1b || c == 0x9c) {
        /* Framing/cancellation belongs to the enclosing terminal parser. */
        return fail(s, NEMO_SIXEL_MALFORMED);
    }
    return true;
}

bool nemo_sixel_feed(NemoSixel *s, const void *data, size_t size)
{
    const unsigned char *p = data;
    size_t i;
    if (!s || s->status != NEMO_SIXEL_OK || s->finished) return false;
    if (!p && size) return fail(s, NEMO_SIXEL_MALFORMED);
    for (i = 0; i < size; i++)
        if (!feed_byte(s, p[i])) return false;
    return true;
}

bool nemo_sixel_finish(NemoSixel *s)
{
    if (!s || s->status != NEMO_SIXEL_OK) return false;
    if (s->finished) return true;
    if (s->command == '!') return fail(s, NEMO_SIXEL_MALFORMED);
    if (s->command && !commit_parameters(s)) return false;
    s->finished = true;
    return true;
}

NemoSixelStats nemo_sixel_stats(const NemoSixel *s)
{
    NemoSixelStats out;
    memset(&out, 0, sizeof(out));
    if (!s) {
        out.status = NEMO_SIXEL_OUT_OF_MEMORY;
        return out;
    }
    out.width = s->width;
    out.height = s->height;
    out.aspect_vertical = s->aspect_vertical;
    out.aspect_horizontal = s->aspect_horizontal;
    out.allocated_bytes = s->allocated_bytes;
    out.budget_bytes = s->budget_bytes;
    out.status = s->status;
    out.finished = s->finished;
    return out;
}

size_t nemo_sixel_read_row(const NemoSixel *s, unsigned y, unsigned x,
                          uint32_t *bgra, size_t count)
{
    size_t written = 0;
    if (!s || !bgra || y >= s->height || x >= s->width) return 0;
    if (count > s->width - x) count = s->width - x;
    while (written < count) {
        unsigned tx = x / TILE_SIDE, ty = y / TILE_SIDE;
        size_t n = TILE_SIDE - x % TILE_SIDE, j;
        const SixelTile *t;
        if (n > count - written) n = count - written;
        for (t = s->buckets[bucket(tx, ty)]; t; t = t->next)
            if (t->tx == tx && t->ty == ty) break;
        if (t) {
            memcpy(bgra + written,
                   &t->pixels[(y % TILE_SIDE) * TILE_SIDE + x % TILE_SIDE],
                   n * sizeof(*bgra));
        } else {
            for (j = 0; j < n; j++) bgra[written + j] = s->background;
        }
        x += (unsigned)n;
        written += n;
    }
    return written;
}

void nemo_sixel_get_palette(const NemoSixel *s, uint32_t palette[256])
{
    if (s && palette) memcpy(palette, s->palette, sizeof(s->palette));
}

void nemo_sixel_set_palette(NemoSixel *s, const uint32_t palette[256])
{
    unsigned i;
    if (!s || !palette) return;
    for (i = 0; i < 256; i++) s->palette[i] = palette[i] | UINT32_C(0xff000000);
}

void nemo_sixel_set_allocation_guard(NemoSixel *s,
                                    NemoSixelAllocationGuard guard, void *ctx)
{
    if (!s) return;
    s->allocation_guard = guard;
    s->allocation_context = ctx;
}
