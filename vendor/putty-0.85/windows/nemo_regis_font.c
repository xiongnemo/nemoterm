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
    uint32_t *bitmap_pixels;
    unsigned bitmap_width, bitmap_height;
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
    return provider ? sizeof(*provider) +
        (size_t)provider->bitmap_width*provider->bitmap_height*sizeof(uint32_t) : 0;
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

static bool resize_surface(NemoRegisFontWin *provider, unsigned width, unsigned height)
{
    if (!width || !height || width > GLYPH_CAPACITY/height) return false;
    if (provider->bitmap && provider->bitmap_width==width && provider->bitmap_height==height)
        return true;
    BITMAPINFO info = {0};
    info.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    info.bmiHeader.biWidth = (LONG)width; info.bmiHeader.biHeight = -(LONG)height;
    info.bmiHeader.biPlanes = 1; info.bmiHeader.biBitCount = 32;
    info.bmiHeader.biCompression = BI_RGB;
    uint32_t *pixels = NULL;
    HBITMAP bitmap = CreateDIBSection(provider->dc, &info, DIB_RGB_COLORS, (void **)&pixels, NULL, 0);
    if (!bitmap) return false;
    HGDIOBJ previous = SelectObject(provider->dc, bitmap);
    if (!previous || previous==HGDI_ERROR) { DeleteObject(bitmap); return false; }
    if (provider->bitmap) DeleteObject(provider->bitmap);
    else provider->original_bitmap = previous;
    provider->bitmap = bitmap; provider->bitmap_pixels = pixels;
    provider->bitmap_width = width; provider->bitmap_height = height;
    return true;
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
        if (!resize_surface(provider,1,1)) {
            DeleteDC(provider->dc); provider->dc=NULL;
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
    WCHAR ch = (WCHAR)character;
    WORD index;
    if (GetGlyphIndicesW(provider->dc, &ch, 1, &index, GGI_MARK_NONEXISTING_GLYPHS) == GDI_ERROR ||
        index == 0xffff || !resize_surface(provider,provider->width,provider->height)) return false;
    /* GGO_BITMAP and actual GDI drawing disagree for some hinted composite
     * glyphs in Sarasa. Render the selected glyph, as Xft does upstream, then
     * copy its mask. Never use a hand-adjusted offset or an accent exception. */
    memset(provider->bitmap_pixels,0,count*sizeof(uint32_t));
    SetBkMode(provider->dc,TRANSPARENT);
    SetTextColor(provider->dc,RGB(255,255,255));
    SetTextAlign(provider->dc,TA_LEFT | TA_BASELINE | TA_NOUPDATECP);
    if (!ExtTextOutW(provider->dc,-provider->left,-provider->top,ETO_GLYPH_INDEX,
                     NULL,(const WCHAR *)&index,1,NULL) || !GdiFlush()) return false;
    for (size_t i=0;i<count;i++) pixels[i]=(provider->bitmap_pixels[i]&0xffffffU)!=0;
    *width = provider->width; *height = provider->height;
    return true;
}
