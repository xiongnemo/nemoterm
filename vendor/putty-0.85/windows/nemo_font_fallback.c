/* Private embedded Nerd symbols; normal text retains the user's chosen font. */
#include "putty.h"
#include "nemo_font_cmap.h"
#include "nemo_font_fallback.h"

#define FONT_RESOURCE 40001
#define FONT_CACHE 8
#define CMAP_LIMIT (1024*1024)

struct FontSlot { LOGFONTW spec; HFONT font; };
struct NemoFontFallback {
    bool attempted;
    HANDLE resource;
    const void *image, *cmap;
    DWORD image_size;
    size_t cmap_size;
    struct FontSlot slots[FONT_CACHE];
    unsigned next;
    HFONT primary;
    void *primary_cmap;
    size_t primary_cmap_size;
};

static bool primary_has(struct NemoFontFallback *s, HDC dc, uint32_t cp)
{
    if (cp <= 65535) {
        wchar_t text = (wchar_t)cp;
        WORD glyph;
        DWORD result = GetGlyphIndicesW(dc, &text, 1, &glyph, GGI_MARK_NONEXISTING_GLYPHS);
        return result == GDI_ERROR || (glyph != 0 && glyph != 65535);
    }
    /* GetGlyphIndicesW works in UTF-16 units. Read the actual selected font's
     * cmap for supplementary-plane symbols, without guessing from surrogates. */
    HFONT primary = GetCurrentObject(dc, OBJ_FONT);
    if (s->primary != primary) {
        sfree(s->primary_cmap); s->primary_cmap = NULL; s->primary_cmap_size = 0;
        s->primary = primary;
        DWORD length = GetFontData(dc, 0x70616d63, 0, NULL, 0); /* cmap, little endian tag */
        if (length != GDI_ERROR && length >= 4 && length <= CMAP_LIMIT) {
            void *data = snewn(length, char);
            if (GetFontData(dc, 0x70616d63, 0, data, length) == length) {
                s->primary_cmap = data; s->primary_cmap_size = length;
            } else sfree(data);
        }
    }
    return !s->primary_cmap || nemo_cmap_glyph(s->primary_cmap, s->primary_cmap_size, cp);
}

HFONT nemo_font_fallback(struct NemoFontFallback **state, HDC dc,
                         uint32_t cp, int advance, WORD *glyph_index)
{
    /* The embedded symbol set starts at U+23FB. Most terminal text avoids
     * even looking up the resource, let alone registering another font. */
    if (cp < 0x2300 || advance <= 0) return NULL;
    if (!*state) {
        *state = snew(struct NemoFontFallback);
        memset(*state, 0, sizeof(**state));
        HMODULE module = GetModuleHandleW(NULL);
        HRSRC r = FindResourceW(module, MAKEINTRESOURCEW(FONT_RESOURCE), MAKEINTRESOURCEW(10));
        if (r) {
            (*state)->image = LockResource(LoadResource(module, r));
            (*state)->image_size = SizeofResource(module, r);
            (*state)->cmap = nemo_font_cmap((*state)->image, (*state)->image_size, &(*state)->cmap_size);
        }
    }
    struct NemoFontFallback *s = *state;
    unsigned glyph = nemo_cmap_glyph(s->cmap, s->cmap_size, cp);
    if (!glyph || primary_has(s, dc, cp)) return NULL;
    if (!s->attempted) {
        DWORD count = 0;
        s->resource = AddFontMemResourceEx((void *)s->image, s->image_size, NULL, &count);
        s->attempted = true;
    }
    if (!s->resource) return NULL;
    if (glyph_index) *glyph_index = (WORD)glyph;
    LOGFONTW spec = {0};
    if (!GetObjectW(GetCurrentObject(dc, OBJ_FONT), sizeof(spec), &spec)) return NULL;
    wcscpy(spec.lfFaceName, L"Symbols Nerd Font Mono");
    spec.lfWidth = advance;
    spec.lfCharSet = DEFAULT_CHARSET;
    spec.lfPitchAndFamily = DEFAULT_PITCH | FF_DONTCARE;
    for (unsigned i = 0; i < FONT_CACHE; i++)
        if (s->slots[i].font && !memcmp(&s->slots[i].spec, &spec, sizeof(spec))) return s->slots[i].font;
    struct FontSlot *slot = &s->slots[s->next++ % FONT_CACHE];
    if (slot->font) DeleteObject(slot->font);
    slot->spec = spec;
    slot->font = CreateFontIndirectW(&spec);
    return slot->font;
}

void nemo_font_fallback_free(struct NemoFontFallback **state)
{
    struct NemoFontFallback *s = *state;
    if (!s) return;
    for (unsigned i = 0; i < FONT_CACHE; i++)
        if (s->slots[i].font) DeleteObject(s->slots[i].font);
    if (s->resource) RemoveFontMemResourceEx(s->resource);
    sfree(s->primary_cmap);
    sfree(s); *state = NULL;
}
