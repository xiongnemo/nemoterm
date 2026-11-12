#include "putty.h"
#include "nemo_font_fallback.h"
#include "nemo_font_cmap.h"
#include <assert.h>

void modalfatalbox(const char *fmt, ...) { (void)fmt; abort(); }

int main(void)
{
    HDC dc = CreateCompatibleDC(NULL); assert(dc);
    HFONT primary = CreateFontW(-16, 0, 0, 0, FW_LIGHT, FALSE, FALSE, FALSE,
        DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, DEFAULT_QUALITY,
        DEFAULT_PITCH, L"SarasaTermSC Nerd Font Light"); assert(primary);
    HFONT original = SelectObject(dc, primary);
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
    WORD supplementary;
    assert(nemo_font_fallback(&state, dc, 0xf0001, 8, &supplementary));
    assert(supplementary == 3731);
    for (int i = 0; i < 500; i++) assert(nemo_font_fallback(&state, dc, 0xf120, 6+i%24, NULL));
    assert(GetGuiResources(GetCurrentProcess(), GR_GDIOBJECTS) <= before+8);
    nemo_font_fallback_free(&state); assert(!state);
    assert(GetGuiResources(GetCurrentProcess(), GR_GDIOBJECTS) == before);
    SelectObject(dc, original); DeleteObject(primary); DeleteDC(dc);
    puts("Font fallback preserves supported glyphs, handles supplementary icons and releases its bounded cache");
    return 0;
}
