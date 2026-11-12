#include "nemo_font_cmap.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv)
{
    const char *path = argc > 1 ? argv[1] : "vendor/nerd-fonts/SymbolsNerdFontMono-Regular.ttf";
    FILE *f = fopen(path, "rb"); assert(f);
    assert(!fseek(f, 0, SEEK_END)); long length = ftell(f); assert(length > 0);
    rewind(f); unsigned char *data = malloc((size_t)length); assert(data);
    assert(fread(data, 1, (size_t)length, f) == (size_t)length); fclose(f);
    size_t size;
    const unsigned char *cmap = nemo_font_cmap(data, (size_t)length, &size);
    assert(cmap && size);
    assert(nemo_cmap_glyph(cmap, size, 0xf120) == 2809);
    assert(nemo_cmap_glyph(cmap, size, 0xf07b) == 2644);
    assert(nemo_cmap_glyph(cmap, size, 0xf0001) == 3731);
    assert(nemo_cmap_glyph(cmap, size, 0xf0002) == 3732);
    assert(!nemo_cmap_glyph(cmap, size, 0x1f600));
    assert(!nemo_cmap_glyph(cmap, size, 0xd800));
    assert(!nemo_cmap_glyph(cmap, size, 0x110000));
    /* Every truncated prefix must be safe under ASan/UBSan. */
    for (size_t i = 0; i < size; i++) {
        (void)nemo_cmap_glyph(cmap, i, 0xf120);
        (void)nemo_cmap_glyph(cmap, i, 0xf0001);
    }
    for (size_t i = 0; i < 512; i++) {
        size_t ignored; (void)nemo_font_cmap(data, i, &ignored);
    }
    /* Format 4: direct delta, range-offset array, a zero missing glyph and
     * a nonzero delta applied after the indirect lookup. */
    unsigned char table[] = {
        0,0,0,1, 0,3,0,1, 0,0,0,12,
        0,4,0,36, 0,0,0,4, 0,0,0,0,0,0,
        0,66,255,255, 0,0, 0,65,255,255,
        0,2,0,1, 0,4,0,0, 0,5,0,0
    };
    assert(nemo_cmap_glyph(table, sizeof(table), 'A') == 7);
    assert(!nemo_cmap_glyph(table, sizeof(table), 'B'));
    assert(!nemo_cmap_glyph(table, sizeof(table), 'C'));
    table[40] = table[41] = 0;  /* first segment idRangeOffset */
    assert(nemo_cmap_glyph(table, sizeof(table), 'A') == 67);
    /* Hostile lengths and offsets remain bounded. */
    for (size_t i = 0; i < sizeof(table); i++) {
        unsigned char old = table[i]; table[i] = 255;
        (void)nemo_cmap_glyph(table, sizeof(table), 'A'); table[i] = old;
    }
    free(data);
    puts("Font cmap BMP/supplementary mapping, missing glyphs and malformed bounds passed");
    return 0;
}
