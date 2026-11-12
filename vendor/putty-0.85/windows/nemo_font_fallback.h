#ifndef NEMO_FONT_FALLBACK_H
#define NEMO_FONT_FALLBACK_H
struct NemoFontFallback;
/* Returns a borrowed cached font, or NULL to keep the selected primary font. */
HFONT nemo_font_fallback(struct NemoFontFallback **state, HDC dc,
                         uint32_t codepoint, int advance, WORD *glyph_index);
void nemo_font_fallback_free(struct NemoFontFallback **state);
#endif
