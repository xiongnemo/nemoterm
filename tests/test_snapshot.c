/* SPDX-License-Identifier: MIT
 * Native Windows, off-screen tests for the bounded snapshot renderer.
 * No windows are created and no message loop is entered.
 */
#include "nemo_snapshot.h"
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#define SNAPSHOT_BUDGET ((size_t)8 * 1024 * 1024)
#define SENTINEL_PIXEL UINT32_C(0x00abcdef)

/* Keep the checks active in Release builds, including under NDEBUG. */
#define CHECK(condition) do { \
    if (!(condition)) { \
        fprintf(stderr, "%s:%d: %s (Win32 error %lu)\n", \
                __FILE__, __LINE__, #condition, \
                (unsigned long)GetLastError()); \
        exit(1); \
    } \
} while (0)

typedef struct TestSurface {
    HDC dc;
    HBITMAP bitmap;
    HGDIOBJ previous_bitmap;
    uint32_t *pixels;
    int width, height;
} TestSurface;

static TestSurface surface_create(int width, int height)
{
    TestSurface surface = {0};
    BITMAPINFO bi = {0};
    void *pixels = NULL;

    surface.width = width;
    surface.height = height;
    surface.dc = CreateCompatibleDC(NULL);
    CHECK(surface.dc);
    bi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    bi.bmiHeader.biWidth = width;
    bi.bmiHeader.biHeight = -height;
    bi.bmiHeader.biPlanes = 1;
    bi.bmiHeader.biBitCount = 32;
    bi.bmiHeader.biCompression = BI_RGB;
    surface.bitmap = CreateDIBSection(surface.dc, &bi, DIB_RGB_COLORS,
                                      &pixels, NULL, 0);
    CHECK(surface.bitmap && pixels);
    surface.pixels = pixels;
    surface.previous_bitmap = SelectObject(surface.dc, surface.bitmap);
    CHECK(surface.previous_bitmap && surface.previous_bitmap != HGDI_ERROR);
    return surface;
}

static void surface_free(TestSurface *surface)
{
    CHECK(SelectObject(surface->dc, surface->previous_bitmap) == surface->bitmap);
    CHECK(DeleteObject(surface->bitmap));
    CHECK(DeleteDC(surface->dc));
}

static uint32_t coordinate_pixel(int x, int y)
{
    return ((uint32_t)(x & 255) << 16) |
        ((uint32_t)(y & 255) << 8) | (uint32_t)((x + y) & 255);
}

static bool render_coordinates(HDC dc, int top, int height, void *ctx)
{
    int width = *(int *)ctx;
    RECT clip;
    CHECK(GetClipBox(dc, &clip) != ERROR);
    CHECK(clip.left == 0 && clip.top == top);
    CHECK(clip.right == width && clip.bottom == top + height);

    /* Absolute client coordinates exercise the band's viewport transform. */
    for (int y = top; y < top + height; y++) {
        for (int x = 0; x < width; x++)
            CHECK(SetPixelV(dc, x, y, RGB(x & 255, y & 255, (x + y) & 255)));
    }
    return true;
}

static bool render_failure(HDC dc, int top, int height, void *ctx)
{
    (void)dc;
    (void)top;
    (void)height;
    (void)ctx;
    SetLastError(ERROR_CANCELLED);
    return false;
}

static bool render_stripes(HDC dc, int top, int height, void *ctx)
{
    int width = *(int *)ctx;
    for (int y = top; y < top + height; y++) {
        RECT line = {0, y, width, y + 1};
        HBRUSH brush = CreateSolidBrush(RGB(y & 255, (y >> 2) & 255, 19));
        CHECK(brush);
        CHECK(FillRect(dc, &line, brush));
        CHECK(DeleteObject(brush));
    }
    return true;
}

static bool render_noise(HDC dc, int top, int height, void *ctx)
{
    int width = *(int *)ctx;
    DIBSECTION dib;
    CHECK(GetObject(GetCurrentObject(dc, OBJ_BITMAP), sizeof(dib), &dib) ==
          sizeof(dib));
    CHECK(GdiFlush());
    uint32_t *pixels = dib.dsBm.bmBits;

    /* Deterministic high-entropy pixels force the cache to exceed its
     * budget partway through capture, after earlier bands were retained.
     * Writing the band DIB directly avoids millions of SetPixel calls. */
    for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
            uint32_t value = (uint32_t)(top + y) * (uint32_t)width +
                (uint32_t)x + 1;
            value ^= value >> 16;
            value *= UINT32_C(0x7feb352d);
            value ^= value >> 15;
            value *= UINT32_C(0x846ca68b);
            value ^= value >> 16;
            pixels[(size_t)y * width + x] = value & UINT32_C(0x00ffffff);
        }
    }
    return true;
}

static NemoSnapshot *create_checked(int width, int height,
                                    NemoSnapshotRender render, void *ctx)
{
    NemoSnapshotError error;
    NemoSnapshot *snapshot = nemo_snapshot_create(
        width, height, SNAPSHOT_BUDGET, render, ctx, &error);
    if (!snapshot) {
        fprintf(stderr, "snapshot creation failed: reason=%d stage=%s "
                "Win32 error=%lu\n", error.reason, error.stage,
                (unsigned long)error.win32_error);
    }
    CHECK(snapshot);
    return snapshot;
}

static void check_stats(NemoSnapshot *snapshot, unsigned expected_bands)
{
    NemoSnapshotStats stats = nemo_snapshot_stats(snapshot);
    CHECK(stats.bands == expected_bands);
    CHECK(stats.budget_bytes == SNAPSHOT_BUDGET);
    CHECK(stats.allocated_bytes <= stats.peak_bytes);
    CHECK(stats.peak_bytes <= stats.budget_bytes);
    CHECK(stats.compressed_bytes <= stats.allocated_bytes);
}

static void check_coordinates(const TestSurface *surface, const RECT *clip)
{
    CHECK(GdiFlush());
    for (int y = 0; y < surface->height; y++) {
        for (int x = 0; x < surface->width; x++) {
            bool inside = !clip ||
                (x >= clip->left && x < clip->right &&
                 y >= clip->top && y < clip->bottom);
            uint32_t expected = inside ? coordinate_pixel(x, y) : SENTINEL_PIXEL;
            uint32_t actual = surface->pixels[(size_t)y * surface->width + x];
            /* BI_RGB's fourth byte has no display meaning. */
            CHECK((actual & UINT32_C(0x00ffffff)) == expected);
        }
    }
}

static void test_pixels_and_partial_clip(void)
{
    int width = 129, height = 70;
    NemoSnapshotError error;
    NemoSnapshot *snapshot = create_checked(
        width, height, render_coordinates, &width);
    TestSurface surface = surface_create(width, height);
    check_stats(snapshot, 3);

    for (size_t i = 0; i < (size_t)width * height; i++)
        surface.pixels[i] = SENTINEL_PIXEL;

    /* Starts in the first band, crosses both boundaries, and ends in
     * the short final band. Pixels outside the clip must be untouched. */
    RECT clip = {11, 30, 83, 67};
    CHECK(nemo_snapshot_paint(snapshot, surface.dc, &clip, &error));
    check_coordinates(&surface, &clip);

    CHECK(nemo_snapshot_paint(snapshot, surface.dc, NULL, &error));
    check_coordinates(&surface, NULL);

    RECT outside = {500, 500, 600, 600};
    CHECK(nemo_snapshot_paint(snapshot, surface.dc, &outside, &error));
    check_coordinates(&surface, NULL);

    nemo_snapshot_free(snapshot);
    surface_free(&surface);
}

static void test_creation_failures(void)
{
    int width = 129, height = 70;
    NemoSnapshotError error;

    CHECK(!nemo_snapshot_create(width, height, 1,
                                render_coordinates, &width, &error));
    CHECK(error.reason == NEMO_SNAPSHOT_BUDGET_EXCEEDED);

    CHECK(!nemo_snapshot_create(width, height, SNAPSHOT_BUDGET,
                                render_failure, NULL, &error));
    CHECK(error.reason == NEMO_SNAPSHOT_RENDER_FAILURE);
    CHECK(error.win32_error == ERROR_CANCELLED);

    CHECK(!nemo_snapshot_create(0, height, SNAPSHOT_BUDGET,
                                render_coordinates, &width, &error));
    CHECK(error.reason == NEMO_SNAPSHOT_INVALID_ARGUMENT);
}

static DWORD gdi_objects(void)
{
    CHECK(GdiFlush());
    return GetGuiResources(GetCurrentProcess(), GR_GDIOBJECTS);
}

static void test_4k_budget_and_cleanup(void)
{
    int width = 3840, height = 2160;
    DWORD baseline = 0;

    for (int iteration = 0; iteration < 3; iteration++) {
        NemoSnapshot *snapshot = create_checked(
            width, height, render_stripes, &width);
        check_stats(snapshot, 68);
        if (iteration == 0) {
            NemoSnapshotStats stats = nemo_snapshot_stats(snapshot);
            printf("4K snapshot: retained=%zu peak=%zu compressed=%zu bytes\n",
                   stats.allocated_bytes, stats.peak_bytes,
                   stats.compressed_bytes);
        }
        nemo_snapshot_free(snapshot);

        /* GDI may initialize a process-local brush cache on first use.
         * Measure after warmup; each subsequent capture/free must return
         * to exactly that count rather than accumulate handles. */
        if (iteration == 0)
            baseline = gdi_objects();
        else
            CHECK(gdi_objects() == baseline);
    }

    NemoSnapshotError error;
    CHECK(!nemo_snapshot_create(width, height, SNAPSHOT_BUDGET,
                                render_noise, &width, &error));
    CHECK(error.reason == NEMO_SNAPSHOT_BUDGET_EXCEEDED);
    CHECK(error.win32_error == ERROR_NOT_ENOUGH_QUOTA);
    CHECK(gdi_objects() == baseline);

    CHECK(!nemo_snapshot_create(width, height, SNAPSHOT_BUDGET,
                                render_failure, NULL, &error));
    CHECK(error.reason == NEMO_SNAPSHOT_RENDER_FAILURE);
    CHECK(error.win32_error == ERROR_CANCELLED);
    CHECK(gdi_objects() == baseline);
}

int main(void)
{
    test_pixels_and_partial_clip();
    test_creation_failures();
    test_4k_budget_and_cleanup();
    puts("snapshot tests passed");
    return 0;
}
