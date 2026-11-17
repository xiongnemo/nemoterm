/* SPDX-License-Identifier: MIT
 * Native ReGIS glyphs. The parser performs rotation, slant and rescaling.
 * This provider returns monochrome glyphs in a common Latin-1 bounding box,
 * so a narrow character does not independently stretch to the full cell.
 */
#include "nemo_regis_font.h"
#include <windows.h>
#include <limits.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define GLYPH_CAPACITY 8192U
#define MAX_FONT_HEIGHT 72U

struct NemoRegisFontWin {
    HDC dc;
    HBITMAP bitmap;
    HGDIOBJ original_bitmap;
    HFONT font;
    HGDIOBJ original;
    wchar_t family[LF_FACESIZE], cached_family[LF_FACESIZE];
    int weight, left, top, pixel_height;
    unsigned requested_width, requested_height, width, height;
    size_t capacity;
};

static const MAT2 identity = {{0,1},{0,0},{0,0},{0,1}};

static void discard_font(NemoRegisFontWin *provider)
{
    if (provider->font) {
        SelectObject(provider->dc, provider->original);
        DeleteObject(provider->font);
        provider->font = NULL;
    }
}

NemoRegisFontWin *nemo_regis_font_new(const wchar_t *family, int weight)
{
    if (!family || !*family || wcslen(family) >= LF_FACESIZE ||
        weight < 0 || weight > 1000) return NULL;
    NemoRegisFontWin *provider = calloc(1, sizeof(*provider));
    if (!provider) return NULL;
    memcpy(provider->family, family, (wcslen(family)+1)*sizeof(*family));
    provider->weight = weight;
    /* GDI resources are allocated only on the first actual glyph request. */
    return provider;
}

void nemo_regis_font_free(NemoRegisFontWin *provider)
{
    if (!provider) return;
    discard_font(provider);
    if (provider->dc) {
        if (provider->bitmap) {
            SelectObject(provider->dc, provider->original_bitmap);
            DeleteObject(provider->bitmap);
        }
        DeleteDC(provider->dc);
    }
    free(provider);
}

size_t nemo_regis_font_bytes(const NemoRegisFontWin *provider)
{
    return provider ? sizeof(*provider) : 0;
}

bool nemo_regis_font_info(const NemoRegisFontWin *provider, NemoRegisFontInfo *info)
{
    if (!provider || !provider->font || !info) return false;
    memcpy(info->family, provider->cached_family, sizeof(info->family));
    info->pixel_height = provider->pixel_height; info->weight = provider->weight;
    info->left = provider->left; info->top = provider->top;
    info->width = provider->width; info->height = provider->height;
    return true;
}

static bool glyph_metrics(HDC dc, unsigned character, GLYPHMETRICS *metrics)
{
    WCHAR ch = (WCHAR)character;
    WORD index;
    return GetGlyphIndicesW(dc, &ch, 1, &index, GGI_MARK_NONEXISTING_GLYPHS) != GDI_ERROR &&
        index != 0xffff &&
        GetGlyphOutlineW(dc, index, GGO_BITMAP | GGO_GLYPH_INDEX, metrics, 0, NULL, &identity) != GDI_ERROR;
}

static bool select_font(NemoRegisFontWin *provider, const wchar_t *family,
                        unsigned maxw, unsigned maxh, size_t capacity)
{
    if (provider->font && !wcscmp(family, provider->cached_family) &&
        maxw == provider->requested_width && maxh == provider->requested_height &&
        capacity == provider->capacity) return true;
    discard_font(provider);
    if (!provider->dc) {
        provider->dc = CreateCompatibleDC(NULL);
        if (!provider->dc) return false;
        provider->original = GetCurrentObject(provider->dc, OBJ_FONT);
        /* Match the frontend's colour surface when GDI realizes the font;
         * a new memory DC initially has a monochrome stock bitmap. */
        BITMAPINFO bitmap = {0};
        bitmap.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
        bitmap.bmiHeader.biWidth = 1; bitmap.bmiHeader.biHeight = -1;
        bitmap.bmiHeader.biPlanes = 1; bitmap.bmiHeader.biBitCount = 32;
        bitmap.bmiHeader.biCompression = BI_RGB;
        void *bits = NULL;
        provider->bitmap = CreateDIBSection(provider->dc, &bitmap, DIB_RGB_COLORS, &bits, NULL, 0);
        if (!provider->bitmap) { DeleteDC(provider->dc); provider->dc=NULL; return false; }
        provider->original_bitmap = SelectObject(provider->dc, provider->bitmap);
        if (!provider->original_bitmap || provider->original_bitmap == HGDI_ERROR) {
            DeleteObject(provider->bitmap); DeleteDC(provider->dc);
            provider->dc=NULL; provider->bitmap=NULL;
            return false;
        }
    }
    /* Like the upstream Xft search, cap font size and use a finite descending
     * search. No terminal-supplied coordinate can cause an unbounded search. */
    unsigned start = maxh < MAX_FONT_HEIGHT ? maxh : MAX_FONT_HEIGHT;
    for (unsigned size = start; size; size--) {
        HFONT font = CreateFontW(-(int)size, 0, 0, 0, provider->weight, FALSE,
            FALSE, FALSE, DEFAULT_CHARSET, OUT_TT_ONLY_PRECIS, CLIP_DEFAULT_PRECIS,
            NONANTIALIASED_QUALITY, FIXED_PITCH | FF_MODERN, family);
        if (!font) return false;
        HGDIOBJ previous = SelectObject(provider->dc, font);
        if (!previous || previous == HGDI_ERROR) { DeleteObject(font); return false; }
        provider->font = font;
        wchar_t actual[LF_FACESIZE];
        if (!GetTextFaceW(provider->dc, LF_FACESIZE, actual) || lstrcmpiW(actual, family)) {
            discard_font(provider);
            return false; /* Never mistake silent font substitution for success. */
        }
        int left = INT_MAX, top = INT_MAX, right = INT_MIN, bottom = INT_MIN;
        for (unsigned ch = 33; ch < 256; ch++) {
            if (ch >= 127 && ch <= 160) continue;
            GLYPHMETRICS gm;
            if (!glyph_metrics(provider->dc, ch, &gm) || !gm.gmBlackBoxX || !gm.gmBlackBoxY)
                continue;
            /* Real fonts cannot need these oversized boxes at <=72px. The
             * bounds also make the following signed arithmetic explicit. */
            if (gm.gmBlackBoxX > GLYPH_CAPACITY || gm.gmBlackBoxY > GLYPH_CAPACITY ||
                gm.gmptGlyphOrigin.x < -8192 || gm.gmptGlyphOrigin.x > 8192 ||
                gm.gmptGlyphOrigin.y < -8192 || gm.gmptGlyphOrigin.y > 8192) continue;
            int x = gm.gmptGlyphOrigin.x, y = -gm.gmptGlyphOrigin.y;
            if (x < left) left = x;
            if (y < top) top = y;
            if (x+(int)gm.gmBlackBoxX > right) right = x+(int)gm.gmBlackBoxX;
            if (y+(int)gm.gmBlackBoxY > bottom) bottom = y+(int)gm.gmBlackBoxY;
        }
        if (left != INT_MAX && right > left && bottom > top) {
            unsigned width = (unsigned)(right-left), height = (unsigned)(bottom-top);
            if (width <= maxw && height <= maxh && width <= capacity/height) {
                provider->left = left; provider->top = top;
                provider->pixel_height = (int)size;
                provider->width = width; provider->height = height;
                provider->requested_width = maxw; provider->requested_height = maxh;
                provider->capacity = capacity;
                memcpy(provider->cached_family, family, (wcslen(family)+1)*sizeof(*family));
                return true;
            }
        }
        discard_font(provider);
    }
    return false;
}

bool nemo_regis_font_glyph(void *ctx, const char *font, unsigned character,
                           unsigned maxw, unsigned maxh, unsigned char *pixels,
                           size_t capacity, unsigned *width, unsigned *height)
{
    NemoRegisFontWin *provider = ctx;
    if (width) *width = 0;
    if (height) *height = 0;
    if (!provider || !font || !pixels || !width || !height || !maxw || !maxh ||
        !capacity || capacity > GLYPH_CAPACITY || character > 255 ||
        character < 32 || (character >= 127 && character < 160)) return false;
    wchar_t family[LF_FACESIZE];
    if (*font) {
        if (!MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, font, -1,
                                 family, LF_FACESIZE)) return false;
    } else {
        memcpy(family, provider->family, sizeof(family));
    }
    if (!select_font(provider, family, maxw, maxh, capacity)) return false;
    size_t count = (size_t)provider->width * provider->height;
    memset(pixels, 0, count);
    /* GDI's outline query can report GDI_ERROR for blank space. These two
     * Latin-1 spaces have advance but no ink; keep a valid empty cell. */
    if (character == 32 || character == 160) {
        *width = provider->width; *height = provider->height;
        return true;
    }
    GLYPHMETRICS gm;
    if (!glyph_metrics(provider->dc, character, &gm)) return false;
    if (gm.gmBlackBoxX && gm.gmBlackBoxY) {
        if (gm.gmBlackBoxX > provider->width || gm.gmBlackBoxY > provider->height) return false;
        int x = gm.gmptGlyphOrigin.x-provider->left;
        int y = -gm.gmptGlyphOrigin.y-provider->top;
        if (x < 0 || y < 0 || (unsigned)x > provider->width-gm.gmBlackBoxX ||
            (unsigned)y > provider->height-gm.gmBlackBoxY) return false;
        unsigned char bits[GLYPH_CAPACITY];
        size_t stride = ((size_t)gm.gmBlackBoxX+31)/32*4;
        if (stride > sizeof(bits)/gm.gmBlackBoxY) return false;
        WCHAR ch = (WCHAR)character;
        WORD index;
        if (GetGlyphIndicesW(provider->dc, &ch, 1, &index, GGI_MARK_NONEXISTING_GLYPHS) == GDI_ERROR ||
            index == 0xffff) return false;
        DWORD length = GetGlyphOutlineW(provider->dc, index, GGO_BITMAP | GGO_GLYPH_INDEX, &gm,
                                        sizeof(bits), bits, &identity);
        if (length == GDI_ERROR || (length && length < stride*gm.gmBlackBoxY)) return false;
        for (unsigned yy = 0; length && yy < gm.gmBlackBoxY; yy++)
            for (unsigned xx = 0; xx < gm.gmBlackBoxX; xx++)
                pixels[((unsigned)y+yy)*provider->width+(unsigned)x+xx] =
                    (bits[yy*stride+xx/8] & (128U >> (xx%8))) != 0;
    }
    *width = provider->width; *height = provider->height;
    return true;
}
