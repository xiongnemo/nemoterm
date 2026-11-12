#include "putty.h"
#include "nemo_font_fallback.h"
#include "nemo_font_cmap.h"
#include <assert.h>

void modalfatalbox(const char *fmt, ...) { (void)fmt; abort(); }

static void exercise(const wchar_t *requested, bool known_primary, bool raster)
{
    HDC dc = CreateCompatibleDC(NULL); assert(dc);
    HFONT primary = CreateFontW(-16, 0, 0, 0, FW_LIGHT, FALSE, FALSE, FALSE,
        DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, DEFAULT_QUALITY,
        DEFAULT_PITCH, requested); assert(primary);
    HFONT original = SelectObject(dc, primary);
    wchar_t face[LF_FACESIZE];
    assert(GetTextFaceW(dc, LF_FACESIZE, face));
    printf("Requested %ls; initially selected %ls\n", requested, face);
    fflush(stdout);
    if (known_primary) assert(!wcscmp(face, requested));
    struct NemoFontFallback *state = NULL;
    DWORD before = GetGuiResources(GetCurrentProcess(), GR_GDIOBJECTS);
    assert(!nemo_font_fallback(&state, dc, 'A', 8, NULL) && !state);
    wchar_t icons[] = {0xf120, 0xf07b, 0xe0b0};
    for (size_t i = 0; i < lenof(icons); i++) {
        WORD glyph;
        assert(GetGlyphIndicesW(dc, icons+i, 1, &glyph, GGI_MARK_NONEXISTING_GLYPHS) != GDI_ERROR);
        HFONT fallback = nemo_font_fallback(&state, dc, icons[i], 8, NULL);
        assert(!!fallback == (glyph == 0 || glyph == 65535));
        if (fallback) {
            HFONT old = SelectObject(dc, fallback);
            wchar_t face[LF_FACESIZE]; GetTextFaceW(dc, LF_FACESIZE, face);
            assert(!wcscmp(face, L"Symbols Nerd Font Mono"));
            assert(GetGlyphIndicesW(dc, icons+i, 1, &glyph, GGI_MARK_NONEXISTING_GLYPHS) != GDI_ERROR);
            assert(glyph && glyph != 65535);
            SelectObject(dc, old);
        }
    }
    assert(!nemo_font_fallback(&state, dc, 0x1f600, 16, NULL)); /* not an icon font emoji */
    /* A missing family can resolve to an outline or bitmap font. Check the
     * actual selected face; raster fonts cannot contain supplementary glyphs. */
    TEXTMETRICW metrics; assert(GetTextMetricsW(dc, &metrics));
    bool actual_raster = !(metrics.tmPitchAndFamily & (TMPF_VECTOR | TMPF_TRUETYPE | TMPF_DEVICE));
    if (known_primary) assert(actual_raster == raster);
    DWORD length = GetFontData(dc, 0x70616d63, 0, NULL, 0);
    unsigned primary_glyph = 0;
    bool known_cmap = length != GDI_ERROR && length >= 4 && length <= 1024*1024;
    if (known_cmap) {
        void *data = malloc(length); assert(data);
        assert(GetFontData(dc, 0x70616d63, 0, data, length) == length);
        primary_glyph = nemo_cmap_glyph(data, length, 0xf0001);
        free(data);
    }
    assert(GetTextFaceW(dc, LF_FACESIZE, face));
    printf("Selected after registration %ls; cmap bytes %lu; U+F0001 glyph %u\n",
           face, (unsigned long)length, primary_glyph);
    fflush(stdout);
    if (known_primary && !raster) assert(known_cmap && !primary_glyph);
    WORD supplementary;
    HFONT fallback = nemo_font_fallback(&state, dc, 0xf0001, 8, &supplementary);
    assert(!!fallback == (actual_raster || (known_cmap && !primary_glyph)));
    if (fallback) assert(supplementary == 3731);
    if (known_primary) {
        for (int i = 0; i < 500; i++)
            assert(nemo_font_fallback(&state, dc, 0xf120, 6+i%24, NULL));
    }
    assert(GetGuiResources(GetCurrentProcess(), GR_GDIOBJECTS) <= before+8);
    nemo_font_fallback_free(&state); assert(!state);
    assert(GetGuiResources(GetCurrentProcess(), GR_GDIOBJECTS) == before);
    SelectObject(dc, original); DeleteObject(primary); DeleteDC(dc);
}

int main(void)
{
    exercise(L"Consolas", true, false);
    exercise(L"Courier", true, true);
    exercise(L"SarasaTermSC Nerd Font Light", false, false);
    exercise(L"Nemo Test Missing Font 938471", false, false);
    puts("Font fallback preserves supported glyphs, handles supplementary icons and releases its bounded cache");
    return 0;
}
