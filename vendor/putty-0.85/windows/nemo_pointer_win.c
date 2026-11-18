/* SPDX-License-Identifier: MIT */
#include "nemo_pointer_win.h"
#include "nemo_pointer_glyph.h"
#include <stdlib.h>
#include <string.h>

enum { CURSOR_SIZES = (NEMO_POINTER_CURSOR_MAX-32)/8+1 };
static HCURSOR owned[CURSOR_SIZES][NEMO_POINTER_GLYPH_COUNT];

HCURSOR nemo_pointer_cursor(NemoPointerShape shape, unsigned requested_size)
{
    LPCTSTR stock = NULL;
    switch (shape) {
      case NEMO_POINTER_NONE: case NEMO_POINTER_DEFAULT: stock = IDC_ARROW; break;
      case NEMO_POINTER_TEXT: stock = IDC_IBEAM; break;
      case NEMO_POINTER_POINTER: stock = IDC_HAND; break;
      case NEMO_POINTER_HELP: stock = IDC_HELP; break;
      case NEMO_POINTER_WAIT: stock = IDC_WAIT; break;
      case NEMO_POINTER_PROGRESS: stock = IDC_APPSTARTING; break;
      case NEMO_POINTER_CROSSHAIR: stock = IDC_CROSS; break;
      case NEMO_POINTER_MOVE: stock = IDC_SIZEALL; break;
      case NEMO_POINTER_E_RESIZE: case NEMO_POINTER_W_RESIZE:
      case NEMO_POINTER_EW_RESIZE: stock = IDC_SIZEWE; break;
      case NEMO_POINTER_N_RESIZE: case NEMO_POINTER_S_RESIZE:
      case NEMO_POINTER_NS_RESIZE: stock = IDC_SIZENS; break;
      case NEMO_POINTER_NE_RESIZE: case NEMO_POINTER_SW_RESIZE:
      case NEMO_POINTER_NESW_RESIZE: stock = IDC_SIZENESW; break;
      case NEMO_POINTER_NW_RESIZE: case NEMO_POINTER_SE_RESIZE:
      case NEMO_POINTER_NWSE_RESIZE: stock = IDC_SIZENWSE; break;
      case NEMO_POINTER_NOT_ALLOWED: case NEMO_POINTER_NO_DROP: stock = IDC_NO; break;
      default: break;
    }
    if (stock) return LoadCursor(NULL, stock);
    int index = nemo_pointer_glyph_index(shape);
    if (index < 0) return LoadCursor(NULL, IDC_ARROW);
    unsigned size = requested_size < 32 ? 32 : requested_size;
    if (size > NEMO_POINTER_CURSOR_MAX) size = NEMO_POINTER_CURSOR_MAX;
    unsigned bucket = (size-32+7)/8;
    HCURSOR *slot = &owned[bucket][index];
    if (!*slot) {
        size = 32+bucket*8;
        uint8_t and_mask[NEMO_POINTER_CURSOR_MAX*NEMO_POINTER_CURSOR_MAX/8];
        uint8_t xor_mask[sizeof(and_mask)];
        unsigned hot_x, hot_y;
        if (nemo_pointer_glyph_masks(shape, size, and_mask, xor_mask,
                                    sizeof(and_mask), &hot_x, &hot_y))
            *slot = CreateCursor(GetModuleHandleW(NULL), (int)hot_x, (int)hot_y,
                                 (int)size, (int)size, and_mask, xor_mask);
    }
    return *slot ? *slot : LoadCursor(NULL, IDC_ARROW);
}

/* One recoloured handle for the UI thread. Never modify a Windows-owned
 * cursor. Preserve its native shape, dimensions and hotspot. */
static HCURSOR tinted_source, tinted;
static COLORREF tinted_fg, tinted_bg;

static uint32_t cursor_argb(COLORREF c)
{
    return 0xff000000u | ((uint32_t)GetRValue(c) << 16) |
        ((uint32_t)GetGValue(c) << 8) | GetBValue(c);
}

static HCURSOR tint_cursor(HCURSOR source, COLORREF fg, COLORREF bg)
{
    ICONINFO icon = {0}, result = {0};
    BITMAP m;
    BITMAPINFO bi = {0};
    HDC dc = NULL;
    HBITMAP dib = NULL, mask = NULL;
    HGDIOBJ old = NULL;
    uint32_t *black = NULL, *pixels = NULL;
    unsigned char *inks = NULL, *and_mask = NULL;
    HCURSOR cursor = NULL;
    unsigned n_fg = 0, n_bg = 0;
    if (!source || !GetIconInfo(source, &icon)) return NULL;
    if (GetObject(icon.hbmMask, sizeof(m), &m) != sizeof(m)) goto done;
    int w = m.bmWidth, h = icon.hbmColor ? m.bmHeight : m.bmHeight/2;
    if (w <= 0 || h <= 0 || w > NEMO_POINTER_CURSOR_MAX || h > NEMO_POINTER_CURSOR_MAX) goto done;
    size_t n = (size_t)w*h, stride = 2*((w+15)/16);
    black = malloc(n*sizeof(*black)); inks = calloc(n,1); and_mask = calloc(h,stride);
    if (!black || !inks || !and_mask || !(dc=CreateCompatibleDC(NULL))) goto done;
    bi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    bi.bmiHeader.biWidth = w; bi.bmiHeader.biHeight = -h;
    bi.bmiHeader.biPlanes = 1; bi.bmiHeader.biBitCount = 32;
    dib = CreateDIBSection(dc,&bi,DIB_RGB_COLORS,(void **)&pixels,NULL,0);
    if (!dib || !pixels || !(old=SelectObject(dc,dib)) || old==HGDI_ERROR) goto done;
    memset(pixels,0,n*sizeof(*pixels));
    if (!DrawIconEx(dc,0,0,source,w,h,0,NULL,DI_NORMAL) || !GdiFlush()) goto done;
    memcpy(black,pixels,n*sizeof(*black)); memset(pixels,0xff,n*sizeof(*pixels));
    if (!DrawIconEx(dc,0,0,source,w,h,0,NULL,DI_NORMAL) || !GdiFlush()) goto done;
    /* Composite onto black and white so transparent and XOR pixels can be
     * distinguished from black/white ink even for a stock monochrome I-beam. */
    for (size_t i=0; i<n; i++) {
        uint32_t b=black[i]&0xffffffu, t=pixels[i]&0xffffffu;
        if (b==0 && t==0xffffffu) continue;
        unsigned light = ((b>>16)&255) + ((b>>8)&255) + (b&255);
        inks[i] = light >= 3*128 ? 1 : 2;
        if (inks[i]==1) n_fg++; else n_bg++;
    }
    if (!n_fg && !n_bg) goto done;
    for (int y=0; y<h; y++) for (int x=0; x<w; x++) {
        size_t i=(size_t)y*w+x;
        unsigned ink=inks[i];
        if (!n_fg || !n_bg) {
            /* A single-ink theme has no outline: keep its original stroke
             * as the foreground and add a one-pixel contrasting outline. */
            if (ink) ink=1;
            else if ((x>0 && inks[i-1]) || (x+1<w && inks[i+1]) ||
                     (y>0 && inks[i-w]) || (y+1<h && inks[i+w])) ink=2;
        }
        pixels[i] = ink ? cursor_argb(ink == 1 ? fg : bg) : 0;
        if (!ink) and_mask[(size_t)y*stride+x/8] |= (unsigned char)(0x80u >> (x%8));
    }
    SelectObject(dc,old); old=NULL;
    mask = CreateBitmap(w,h,1,1,and_mask);
    if (!mask) goto done;
    result.xHotspot=icon.xHotspot; result.yHotspot=icon.yHotspot;
    result.hbmMask=mask; result.hbmColor=dib;
    cursor=CreateIconIndirect(&result);
  done:
    if (old && old!=HGDI_ERROR) SelectObject(dc,old);
    if (dib) DeleteObject(dib);
    if (mask) DeleteObject(mask);
    if (dc) DeleteDC(dc);
    if (icon.hbmMask) DeleteObject(icon.hbmMask);
    if (icon.hbmColor) DeleteObject(icon.hbmColor);
    free(black); free(inks); free(and_mask);
    return cursor;
}

void nemo_pointer_select(HCURSOR source, bool custom, COLORREF fg, COLORREF bg)
{
    if (custom && tinted && tinted_source==source && tinted_fg==fg && tinted_bg==bg) {
        SetCursor(tinted);
        return;
    }
    HCURSOR next = custom ? tint_cursor(source,fg,bg) : NULL;
    SetCursor(next ? next : source);
    if (tinted) DestroyCursor(tinted);
    tinted=next; tinted_source=source; tinted_fg=fg; tinted_bg=bg;
}

void nemo_pointer_cursors_free(void)
{
    if (tinted) {
        if (GetCursor()==tinted) SetCursor(LoadCursor(NULL,IDC_ARROW));
        DestroyCursor(tinted); tinted=NULL; tinted_source=NULL;
    }
    for (unsigned size = 0; size < CURSOR_SIZES; size++)
        for (unsigned index = 0; index < NEMO_POINTER_GLYPH_COUNT; index++) {
            HCURSOR cursor = owned[size][index];
            if (!cursor) continue;
            if (GetCursor() == cursor) SetCursor(LoadCursor(NULL, IDC_ARROW));
            DestroyCursor(cursor);
            owned[size][index] = NULL;
        }
}
