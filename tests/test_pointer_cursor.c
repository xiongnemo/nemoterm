/* SPDX-License-Identifier: MIT */
#ifndef _CRT_SECURE_NO_WARNINGS
#define _CRT_SECURE_NO_WARNINGS
#endif
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

/* Isolate first-use GDI/font caches from cursor lifetime accounting. This
 * control does not call the cursor implementation or create any cursor. */
static int observer_control(void)
{
    HDC dc = CreateCompatibleDC(NULL); CHECK(dc != NULL);
    BITMAPINFO info = {0}; void *pixels = NULL;
    info.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    info.bmiHeader.biWidth = 32; info.bmiHeader.biHeight = -32;
    info.bmiHeader.biPlanes = 1; info.bmiHeader.biBitCount = 32;
    HBITMAP bitmap = CreateDIBSection(dc, &info, DIB_RGB_COLORS, &pixels, NULL, 0);
    CHECK(bitmap != NULL && pixels != NULL);
    HGDIOBJ old = SelectObject(dc, bitmap);
    HGDIOBJ oldfont = SelectObject(dc, GetStockObject(DEFAULT_GUI_FONT));
    HBRUSH light = CreateSolidBrush(RGB(246,246,246));
    HBRUSH dark = CreateSolidBrush(RGB(30,30,30));
    RECT rect = {0, 0, 32, 32};
    CHECK(light && dark && FillRect(dc, &rect, light));
    rect.right = 16; CHECK(FillRect(dc, &rect, dark));
    SetBkMode(dc, TRANSPARENT); SetTextColor(dc, RGB(0,0,0));
    CHECK(DrawTextA(dc, "control", -1, &rect, DT_LEFT | DT_SINGLELINE));
    CHECK(GdiFlush());
    SelectObject(dc, oldfont); SelectObject(dc, old);
    CHECK(DeleteObject(light)); CHECK(DeleteObject(dark));
    CHECK(DeleteObject(bitmap)); CHECK(DeleteDC(dc)); CHECK(GdiFlush());
    return 0;
}

static int atlas(unsigned size)
{
    DWORD initial = GetGuiResources(GetCurrentProcess(), GR_GDIOBJECTS);
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
    DWORD previous = GetGuiResources(GetCurrentProcess(), GR_GDIOBJECTS);
    printf("Atlas %u setup: GDI %lu -> %lu\n", size, initial, previous);
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
        DWORD after = GetGuiResources(GetCurrentProcess(), GR_GDIOBJECTS);
        if (after != previous) printf("Atlas %u after %s: GDI %lu -> %lu\n", size, names[shape], previous, after);
        previous = after;
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
    DWORD before_flush = GetGuiResources(GetCurrentProcess(), GR_GDIOBJECTS);
    CHECK(GdiFlush());
    printf("Atlas %u cleanup: GDI before flush=%lu after flush=%lu initial=%lu\n", size,
           before_flush, GetGuiResources(GetCurrentProcess(), GR_GDIOBJECTS), initial);
    return 0;
}

static void resources(const char *stage)
{
    printf("%-26s user=%lu gdi=%lu\n", stage,
           GetGuiResources(GetCurrentProcess(), GR_USEROBJECTS),
           GetGuiResources(GetCurrentProcess(), GR_GDIOBJECTS));
    fflush(stdout);
}

/* Independent Win32 controls, each mode run in a new process. The resource
 * gate below still starts from its original baseline. */
static int cursor_control(const char *mode)
{
    HCURSOR stock=LoadCursor(NULL,IDC_IBEAM);
    CHECK(stock);
    resources("stock loaded");
    if (!strcmp(mode,"--activate-only")) {
        HCURSOR previous=SetCursor(stock); resources("SetCursor(stock)");
        SetCursor(previous); resources("SetCursor(previous)"); return 0;
    }
    HDC dc=CreateCompatibleDC(NULL); CHECK(dc);
    BITMAPINFO bi={0}; bi.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);
    bi.bmiHeader.biWidth=32; bi.bmiHeader.biHeight=-32;
    bi.bmiHeader.biPlanes=1; bi.bmiHeader.biBitCount=32;
    void *bits=NULL;
    HBITMAP dib=CreateDIBSection(dc,&bi,DIB_RGB_COLORS,&bits,NULL,0); CHECK(dib && bits);
    HGDIOBJ old=SelectObject(dc,dib); CHECK(old!=NULL && old!=HGDI_ERROR);
    memset(bits,0xff,32*32*4);
    resources("DIB ready");
    CHECK(DrawIconEx(dc,0,0,stock,32,32,0,NULL,DI_NORMAL));CHECK(GdiFlush());
    resources("DrawIconEx(stock)");
    CHECK(SelectObject(dc,old)==dib);
    if (!strcmp(mode,"--indirect")) {
        unsigned char maskbits[128]={0};
        HBITMAP mask=CreateBitmap(32,32,1,1,maskbits); CHECK(mask);
        ICONINFO icon={0};icon.xHotspot=4;icon.yHotspot=5;
        icon.hbmMask=mask;icon.hbmColor=dib;
        HCURSOR custom=CreateIconIndirect(&icon);CHECK(custom);
        resources("CreateIconIndirect");
        HCURSOR previous=SetCursor(custom); resources("select indirect");
        SetCursor(previous); CHECK(DestroyCursor(custom)); CHECK(DeleteObject(mask));
        resources("destroy indirect");
    }
    CHECK(DeleteObject(dib));CHECK(DeleteDC(dc));CHECK(GdiFlush());resources("control released");
    return 0;
}

int main(int argc, char **argv)
{
    if (argc==2) {
        CHECK(!strcmp(argv[1],"--activate-only") || !strcmp(argv[1],"--draw-stock") || !strcmp(argv[1],"--indirect"));
        resources("cold"); CHECK(observer_control()==0);resources("observer warm");
        CHECK(cursor_control(argv[1])==0);resources("first pass");
        CHECK(cursor_control(argv[1])==0);resources("second pass");
        return 0;
    }

    DWORD cold_gdi = GetGuiResources(GetCurrentProcess(), GR_GDIOBJECTS);
    CHECK(observer_control() == 0);
    DWORD control_gdi = GetGuiResources(GetCurrentProcess(), GR_GDIOBJECTS);
    CHECK(observer_control() == 0);
    DWORD repeated_control_gdi = GetGuiResources(GetCurrentProcess(), GR_GDIOBJECTS);
    printf("GDI observer control without cursors: cold=%lu first=%lu repeated=%lu\n",
           cold_gdi, control_gdi, repeated_control_gdi);
    CHECK(repeated_control_gdi == control_gdi);
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
                char filename[100];
                snprintf(filename, sizeof(filename), "pointer-mask-%s-%u.bin", names[shape], size);
                FILE *file = fopen(filename, "wb"); CHECK(file != NULL);
                const uint32_t header[] = {(uint32_t)mask.bmWidth, (uint32_t)mask.bmHeight,
                    (uint32_t)mask.bmWidthBytes, info.xHotspot, info.yHotspot};
                CHECK(fwrite(header, 1, sizeof(header), file) == sizeof(header));
                CHECK(fwrite(bits, 1, (size_t)count, file) == (size_t)count);
                CHECK(fclose(file) == 0);
            }
            CHECK(DeleteObject(info.hbmMask));
            if (info.hbmColor) CHECK(DeleteObject(info.hbmColor));
        }
    }
    CHECK(custom == 104);
    DWORD warmed_user = GetGuiResources(GetCurrentProcess(), GR_USEROBJECTS);
    DWORD warmed_gdi = GetGuiResources(GetCurrentProcess(), GR_GDIOBJECTS);
    printf("Cursor resources: baseline user=%lu gdi=%lu; warmed user=%lu gdi=%lu\n",
           baseline_user, baseline_gdi, warmed_user, warmed_gdi);
    for (unsigned pass = 0; pass < 100; pass++)
        for (unsigned size = 32; size <= 128; size += 8)
            for (unsigned shape = 1; shape < NEMO_POINTER_SHAPE_COUNT; shape++)
                CHECK(nemo_pointer_cursor((NemoPointerShape)shape, size) == cache[(size-32)/8][shape]);
    CHECK(GetGuiResources(GetCurrentProcess(), GR_USEROBJECTS) == warmed_user);
    CHECK(GetGuiResources(GetCurrentProcess(), GR_GDIOBJECTS) == warmed_gdi);
    HCURSOR source = cache[0][NEMO_POINTER_CELL];
    resources("before application colour");
    nemo_pointer_select(source, true, RGB(18,164,92), RGB(214,50,180));
    resources("first application colour");
    HCURSOR first = GetCursor(); CHECK(first != NULL && first != source);
    nemo_pointer_select(source, true, RGB(18,164,92), RGB(214,50,180));
    CHECK(GetCursor() == first);
    DWORD tinted_user = GetGuiResources(GetCurrentProcess(), GR_USEROBJECTS);
    DWORD tinted_gdi = GetGuiResources(GetCurrentProcess(), GR_GDIOBJECTS);
    for (unsigned i=0; i<120; i++) {
        nemo_pointer_select(source, true, RGB(i,3,1), RGB(1,2,255-i));
        CHECK(GetCursor() && GetCursor() != source);
    }
    resources("after 120 recolours");
    CHECK(GetGuiResources(GetCurrentProcess(), GR_USEROBJECTS) == tinted_user);
    CHECK(GetGuiResources(GetCurrentProcess(), GR_GDIOBJECTS) == tinted_gdi);
    nemo_pointer_select(source, false, 0, 0); CHECK(GetCursor() == source);
    resources("restored source"); CHECK(GdiFlush()); resources("after restore flush");
    CHECK(GetGuiResources(GetCurrentProcess(), GR_USEROBJECTS) == warmed_user);
    CHECK(GetGuiResources(GetCurrentProcess(), GR_GDIOBJECTS) == warmed_gdi);
    CHECK(atlas(32) == 0); CHECK(atlas(48) == 0); CHECK(atlas(96) == 0);
    SetCursor(cache[0][NEMO_POINTER_ZOOM_IN]);
    nemo_pointer_cursors_free();
    printf("After atlases and cursor cleanup: user=%lu gdi=%lu\n",
           GetGuiResources(GetCurrentProcess(), GR_USEROBJECTS),
           GetGuiResources(GetCurrentProcess(), GR_GDIOBJECTS));
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
