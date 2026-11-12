/* OpenType cmap formats 4, 12 and 13. No allocations or unaligned reads. */
#include "nemo_font_cmap.h"
#include <string.h>

static unsigned u16(const unsigned char *p) { return (unsigned)p[0]*256+p[1]; }
static uint32_t u32(const unsigned char *p) {
    return (uint32_t)u16(p)*65536+u16(p+2);
}

const void *nemo_font_cmap(const void *font, size_t size, size_t *cmap_size)
{
    const unsigned char *p = font;
    *cmap_size = 0;
    if (!p || size < 12 || u16(p+4) > (size-12)/16) return NULL;
    for (unsigned i = 0; i < u16(p+4); i++) {
        const unsigned char *record = p+12+16*i;
        if (memcmp(record, "cmap", 4)) continue;
        size_t offset = u32(record+8), length = u32(record+12);
        if (offset > size || length > size-offset) return NULL;
        *cmap_size = length;
        return p+offset;
    }
    return NULL;
}

static unsigned glyph(const unsigned char *p, size_t n, uint32_t cp)
{
    unsigned format = u16(p);
    if (format == 12 || format == 13) {
        if (n < 16 || u32(p+4) < 16 || u32(p+4) > n) return 0;
        n = u32(p+4);
        size_t lo = 0, hi = u32(p+12);
        if (hi > (n-16)/12) return 0;
        while (lo < hi) {
            size_t mid = lo+(hi-lo)/2;
            const unsigned char *group = p+16+12*mid;
            uint32_t first = u32(group), last = u32(group+4);
            if (cp < first) hi = mid;
            else if (cp > last) lo = mid+1;
            else {
                uint64_t index = u32(group+8);
                if (format == 12) index += cp-first;
                return index <= 65535 ? (unsigned)index : 0;
            }
        }
    } else if (format == 4 && cp <= 65535) {
        if (n < 16 || u16(p+2) < 16 || u16(p+2) > n) return 0;
        n = u16(p+2);
        unsigned segments = u16(p+6)/2;
        if (!segments || (u16(p+6)&1) || segments > (n-16)/8) return 0;
        size_t lo = 0, hi = segments;
        while (lo < hi) {
            size_t mid = lo+(hi-lo)/2;
            if (u16(p+14+2*mid) < cp) lo = mid+1;
            else hi = mid;
        }
        if (lo == segments) return 0;
        unsigned first = u16(p+16+2*segments+2*lo);
        if (cp < first) return 0;
        unsigned delta = u16(p+16+4*segments+2*lo);
        size_t at = 16+6*segments+2*lo;
        unsigned distance = u16(p+at);
        if (!distance) return (cp+delta)&65535;
        at += distance+2*(cp-first);
        if (at > n-2) return 0;
        unsigned index = u16(p+at);
        return index ? (index+delta)&65535 : 0;
    }
    return 0;
}

unsigned nemo_cmap_glyph(const void *table, size_t size, uint32_t cp)
{
    const unsigned char *p = table, *best = NULL;
    size_t best_size = 0;
    unsigned priority = 0;
    if (!p || size < 4 || u16(p) || cp > 0x10ffff ||
        (cp >= 0xd800 && cp <= 0xdfff) || u16(p+2) > (size-4)/8) return 0;
    for (unsigned i = 0; i < u16(p+2); i++) {
        const unsigned char *record = p+4+8*i;
        unsigned platform = u16(record), encoding = u16(record+2);
        if (!(platform == 0 || (platform == 3 && (encoding == 1 || encoding == 10)))) continue;
        size_t offset = u32(record+4);
        if (offset > size-2) continue;
        unsigned format = u16(p+offset);
        unsigned rank = format == 12 ? 3 : format == 13 ? 2 : format == 4 ? 1 : 0;
        if (rank > priority) { priority = rank; best = p+offset; best_size = size-offset; }
    }
    return best ? glyph(best, best_size, cp) : 0;
}
