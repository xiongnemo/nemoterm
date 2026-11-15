/* SPDX-License-Identifier: MIT */
#define _CRT_SECURE_NO_WARNINGS
#include "nemo_pointer_win.h"
#include "nemo_pointer_glyph.h"
#include <stdio.h>
#include <string.h>

static unsigned checks;
#define CHECK(expr) do { checks++; if (!(expr)) { \
    fprintf(stderr, "%s:%d: %s (Win32=%lu)\n", __FILE__, __LINE__, #expr, GetLastError()); \
    return 1; } } while (0)
static const char *const names[] = {"automatic",
#define NAME(id, name) name,
    NEMO_POINTER_SHAPES(NAME)
#undef NAME
};

static int atlas(unsigned size)
{
    const int width = 960, height = 720;
    BITMAPINFO info = {0};
    info.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    info.bmiHeader.biWidth = width; info.bmiHeader.biHeight = -height;
    info.bmiHeader.biPlanes = 1; info.bmiHeader.biBitCount = 32;
    void *pixels = NULL;
    HDC dc = CreateCompatibleDC(NULL);
    CHECK(dc != NULL);
    HBITMAP bitmap = CreateDIBSection(dc, &info, DIB_RGB_COLORS, &pixels, NULL, 0);
    CHECK(bitmap != NULL && pixels != NULL);
    HGDIOBJ old = SelectObject(dc, bitmap);
    CHECK(old != NULL && (intptr_t)old != -1);
    RECT rect = {0, 0, width, height};
    HBRUSH light = CreateSolidBrush(RGB(246,246,246));
    HBRUSH dark = CreateSolidBrush(RGB(30,30,30));
    CHECK(light != NULL && dark != NULL);
    FillRect(dc, &rect, light);
    SetBkMode(dc, TRANSPARENT); SetTextColor(dc, RGB(0,0,0));
    HFONT font = (HFONT)GetStockObject(DEFAULT_GUI_FONT);
    HGDIOBJ oldfont = SelectObject(dc, font);
    for (unsigned shape = 1; shape < NEMO_POINTER_SHAPE_COUNT; shape++) {
        int x = (int)((shape-1)%6)*160, y = (int)((shape-1)/6)*144;
        RECT label = {x+4,y+3,x+158,y+23};
        DrawTextA(dc, names[shape], -1, &label, DT_LEFT | DT_SINGLELINE);
        /* Alternate light/dark cells; native GetIconInfo dimensions are
         * checked separately from this visual contact sheet. */
        RECT cell = {x+4,y+27,x+156,y+141};
        if ((shape-1)%2) FillRect(dc, &cell, dark);
        HCURSOR cursor = nemo_pointer_cursor((NemoPointerShape)shape, size);
        CHECK(DrawIconEx(dc, x+10, y+32, cursor, (int)size, (int)size, 0, NULL, DI_NORMAL));
    }
    CHECK(GdiFlush());
    char filename[80];
    snprintf(filename, sizeof(filename), "pointer-atlas-%u.bmp", size);
    FILE *file = fopen(filename, "wb"); CHECK(file != NULL);
    BITMAPFILEHEADER header = {0};
    header.bfType = 0x4d42; header.bfOffBits = sizeof(header)+sizeof(BITMAPINFOHEADER);
    header.bfSize = header.bfOffBits+(DWORD)(width*height*4);
    CHECK(fwrite(&header, 1, sizeof(header), file) == sizeof(header));
    CHECK(fwrite(&info.bmiHeader, 1, sizeof(info.bmiHeader), file) == sizeof(info.bmiHeader));
    size_t pixel_bytes = (size_t)width*(size_t)height*4;
    CHECK(fwrite(pixels, 1, pixel_bytes, file) == pixel_bytes);
    CHECK(fclose(file) == 0);
    SelectObject(dc, oldfont); SelectObject(dc, old);
    CHECK(DeleteObject(light)); CHECK(DeleteObject(dark)); CHECK(DeleteObject(bitmap));
    CHECK(DeleteDC(dc));
    return 0;
}

int main(void)
{
    /* Stock resources are shared with Windows and intentionally not destroyed. */
    for (unsigned shape = 0; shape < NEMO_POINTER_SHAPE_COUNT; shape++)
        if (nemo_pointer_glyph_index((NemoPointerShape)shape) < 0)
            CHECK(nemo_pointer_cursor((NemoPointerShape)shape, 32) != NULL);
    DWORD baseline_user = GetGuiResources(GetCurrentProcess(), GR_USEROBJECTS);
    DWORD baseline_gdi = GetGuiResources(GetCurrentProcess(), GR_GDIOBJECTS);
    HCURSOR cache[13][NEMO_POINTER_SHAPE_COUNT] = {{0}};
    unsigned custom = 0;
    for (unsigned size = 32; size <= 128; size += 8) {
        for (unsigned shape = 1; shape < NEMO_POINTER_SHAPE_COUNT; shape++) {
            HCURSOR cursor = nemo_pointer_cursor((NemoPointerShape)shape, size);
            CHECK(cursor != NULL); cache[(size-32)/8][shape] = cursor;
            ICONINFO info = {0}; BITMAP mask;
            CHECK(GetIconInfo(cursor, &info)); CHECK(!info.fIcon && info.hbmMask);
            CHECK(GetObject(info.hbmMask, sizeof(mask), &mask) == sizeof(mask));
            if (nemo_pointer_glyph_index((NemoPointerShape)shape) >= 0) {
                custom++;
                CHECK(info.hbmColor == NULL);
                CHECK(mask.bmWidth == (LONG)size && mask.bmHeight == (LONG)(2*size));
                CHECK(info.xHotspot < size && info.yHotspot < size);
                /* Native cursor masks must contain transparent background
                 * and opaque ink, without background-inverting pixels. */
                uint8_t bits[8192];
                LONG count = GetBitmapBits(info.hbmMask, sizeof(bits), bits);
                CHECK(count > 0 && (size_t)count == (size_t)mask.bmWidthBytes*size*2);
                size_t plane = (size_t)mask.bmWidthBytes*size;
                unsigned opaque = 0, transparent = 0, white = 0;
                for (size_t i = 0; i < plane; i++) {
                    CHECK(!(bits[i] & bits[plane+i]));
                    opaque += bits[i] != 255; transparent += bits[i] != 0;
                    white += bits[plane+i] != 0;
                }
                CHECK(opaque && transparent && white);
            }
            CHECK(DeleteObject(info.hbmMask));
            if (info.hbmColor) CHECK(DeleteObject(info.hbmColor));
        }
    }
    CHECK(custom == 104);
    DWORD warmed_user = GetGuiResources(GetCurrentProcess(), GR_USEROBJECTS);
    DWORD warmed_gdi = GetGuiResources(GetCurrentProcess(), GR_GDIOBJECTS);
    for (unsigned pass = 0; pass < 100; pass++)
        for (unsigned size = 32; size <= 128; size += 8)
            for (unsigned shape = 1; shape < NEMO_POINTER_SHAPE_COUNT; shape++)
                CHECK(nemo_pointer_cursor((NemoPointerShape)shape, size) == cache[(size-32)/8][shape]);
    CHECK(GetGuiResources(GetCurrentProcess(), GR_USEROBJECTS) == warmed_user);
    CHECK(GetGuiResources(GetCurrentProcess(), GR_GDIOBJECTS) == warmed_gdi);
    CHECK(atlas(32) == 0); CHECK(atlas(48) == 0); CHECK(atlas(96) == 0);
    SetCursor(cache[0][NEMO_POINTER_ZOOM_IN]);
    nemo_pointer_cursors_free();
    CHECK(GetCursor() == LoadCursor(NULL, IDC_ARROW));
    CHECK(GetGuiResources(GetCurrentProcess(), GR_USEROBJECTS) <= baseline_user);
    CHECK(GetGuiResources(GetCurrentProcess(), GR_GDIOBJECTS) <= baseline_gdi);
    /* A second lifetime after cleanup must create working resources again. */
    CHECK(nemo_pointer_cursor(NEMO_POINTER_GRAB, 40) != NULL);
    nemo_pointer_cursors_free(); nemo_pointer_cursors_free();
    CHECK(GetGuiResources(GetCurrentProcess(), GR_USEROBJECTS) <= baseline_user);
    printf("Native pointer resources: %u checks; 30 shapes; 13 sizes; 104 custom cursors; 39000 cache reads; passed\n", checks);
    return 0;
}
