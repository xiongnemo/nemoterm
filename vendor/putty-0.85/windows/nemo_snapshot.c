/* SPDX-License-Identifier: MIT
 * Windows 8 Compression API and bounded GDI band snapshots.
 * https://learn.microsoft.com/windows/win32/cmpapi/using-the-compression-api
 * https://learn.microsoft.com/windows/win32/api/wingdi/nf-wingdi-createdibsection
 * https://learn.microsoft.com/windows/win32/api/wingdi/nf-wingdi-setdibitstodevice
 */
#if !defined(_WIN32_WINNT) || _WIN32_WINNT < 0x0602
#undef _WIN32_WINNT
#define _WIN32_WINNT 0x0602
#endif
#if !defined(NTDDI_VERSION) || NTDDI_VERSION < 0x06020000
#undef NTDDI_VERSION
#define NTDDI_VERSION 0x06020000
#endif
#include "nemo_snapshot.h"
#include <compressapi.h>
#include <limits.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define BAND_HEIGHT 32

typedef union AllocationHeader {
    long double alignment;
    void *pointer_alignment;
    unsigned char padding[MEMORY_ALLOCATION_ALIGNMENT];
    size_t charged;
} AllocationHeader;
/* Preserve the Windows malloc alignment when returning header + 1,
 * without requiring C11 max_align_t in PuTTY's C99 build. */
typedef char HeaderAlignmentCheck[
    sizeof(AllocationHeader) % MEMORY_ALLOCATION_ALIGNMENT == 0 ? 1 : -1];

typedef struct SnapshotBand {
    void *data;
    size_t size;
} SnapshotBand;

struct NemoSnapshot {
    int width, height, band_height;
    unsigned band_count;
    size_t stride, pixel_bytes, pixel_charge;
    size_t budget, allocated, peak, compressed;
    NemoSnapshotFailure allocation_failure;
    SnapshotBand *bands;
    HBITMAP bitmap;
    void *pixels;
    COMPRESSOR_HANDLE compressor;
    DECOMPRESSOR_HANDLE decompressor;
};

static void set_error(NemoSnapshotError *error, NemoSnapshotFailure reason,
                      const char *stage, DWORD win32_error)
{
    if (reason != NEMO_SNAPSHOT_OK && !win32_error)
        win32_error = ERROR_GEN_FAILURE;
    if (error) {
        error->reason = reason;
        error->stage = stage;
        error->win32_error = win32_error;
    }
    SetLastError(win32_error);
}

static bool charge(NemoSnapshot *s, size_t amount)
{
    if (amount > s->budget - s->allocated) {
        s->allocation_failure = NEMO_SNAPSHOT_BUDGET_EXCEEDED;
        SetLastError(ERROR_NOT_ENOUGH_QUOTA);
        return false;
    }
    s->allocated += amount;
    if (s->peak < s->allocated)
        s->peak = s->allocated;
    return true;
}

static void *__cdecl snapshot_allocate(void *ctx, SIZE_T size)
{
    NemoSnapshot *s = ctx;
    AllocationHeader *header;
    if (size > SIZE_MAX - sizeof(*header) ||
        !charge(s, size + sizeof(*header))) {
        s->allocation_failure = NEMO_SNAPSHOT_BUDGET_EXCEEDED;
        SetLastError(ERROR_NOT_ENOUGH_QUOTA);
        return NULL;
    }
    header = malloc(size + sizeof(*header));
    if (!header) {
        s->allocated -= size + sizeof(*header);
        s->allocation_failure = NEMO_SNAPSHOT_OUT_OF_MEMORY;
        SetLastError(ERROR_NOT_ENOUGH_MEMORY);
        return NULL;
    }
    header->charged = size + sizeof(*header);
    return header + 1;
}

static void __cdecl snapshot_deallocate(void *ctx, void *ptr)
{
    NemoSnapshot *s = ctx;
    if (ptr) {
        AllocationHeader *header = (AllocationHeader *)ptr - 1;
        s->allocated -= header->charged;
        free(header);
    }
}

static void codec_error(NemoSnapshot *s, NemoSnapshotError *error,
                        const char *stage)
{
    NemoSnapshotFailure reason = s->allocation_failure;
    DWORD code = GetLastError();
    if (reason == NEMO_SNAPSHOT_OK)
        reason = NEMO_SNAPSHOT_CODEC_FAILURE;
    else if (reason == NEMO_SNAPSHOT_BUDGET_EXCEEDED)
        code = ERROR_NOT_ENOUGH_QUOTA;
    else if (reason == NEMO_SNAPSHOT_OUT_OF_MEMORY)
        code = ERROR_NOT_ENOUGH_MEMORY;
    set_error(error, reason, stage, code);
}

static int band_height(const NemoSnapshot *s, unsigned band)
{
    int remaining = s->height - (int)(band * BAND_HEIGHT);
    return remaining < BAND_HEIGHT ? remaining : BAND_HEIGHT;
}

static bool decode_band(NemoSnapshot *s, unsigned band,
                        NemoSnapshotError *error)
{
    SIZE_T written = 0;
    size_t expected = s->stride * (size_t)band_height(s, band);
    if (!ResetDecompressor(s->decompressor) ||
        !Decompress(s->decompressor, s->bands[band].data,
                    s->bands[band].size, s->pixels, s->pixel_bytes, &written)) {
        codec_error(s, error, "decompress band");
        return false;
    }
    if (written != expected) {
        set_error(error, NEMO_SNAPSHOT_CODEC_FAILURE,
                  "decompressed size mismatch", ERROR_INVALID_DATA);
        return false;
    }
    return true;
}

void nemo_snapshot_free(NemoSnapshot *s)
{
    if (!s)
        return;
    if (s->compressor)
        CloseCompressor(s->compressor);
    if (s->decompressor)
        CloseDecompressor(s->decompressor);
    if (s->bitmap)
        DeleteObject(s->bitmap);
    if (s->bands) {
        for (unsigned i = 0; i < s->band_count; i++)
            snapshot_deallocate(s, s->bands[i].data);
        snapshot_deallocate(s, s->bands);
    }
    free(s);
}

NemoSnapshot *nemo_snapshot_create(int width, int height, size_t budget,
                                 NemoSnapshotRender render, void *ctx,
                                 NemoSnapshotError *error)
{
    NemoSnapshotError local_error;
    NemoSnapshot *s = NULL;
    HDC dc = NULL;
    HGDIOBJ previous_bitmap = NULL;
    void *compressed_scratch = NULL;
    size_t scratch_capacity = 0;
    BITMAPINFO bi = {0};
    COMPRESS_ALLOCATION_ROUTINES alloc;

    if (!error)
        error = &local_error;
    set_error(error, NEMO_SNAPSHOT_OK, "success", ERROR_SUCCESS);
    if (width <= 0 || width > INT_MAX / 4 || height <= 0 ||
        !budget || !render) {
        set_error(error, NEMO_SNAPSHOT_INVALID_ARGUMENT,
                  "snapshot arguments", ERROR_INVALID_PARAMETER);
        return NULL;
    }
    if (budget < sizeof(*s)) {
        set_error(error, NEMO_SNAPSHOT_BUDGET_EXCEEDED,
                  "snapshot object", ERROR_NOT_ENOUGH_QUOTA);
        return NULL;
    }
    s = calloc(1, sizeof(*s));
    if (!s) {
        set_error(error, NEMO_SNAPSHOT_OUT_OF_MEMORY,
                  "snapshot object", ERROR_NOT_ENOUGH_MEMORY);
        return NULL;
    }
    s->width = width;
    s->height = height;
    s->band_height = height < BAND_HEIGHT ? height : BAND_HEIGHT;
    s->band_count = (unsigned)(((size_t)height + BAND_HEIGHT - 1) / BAND_HEIGHT);
    s->budget = budget;
    s->allocated = s->peak = sizeof(*s);
    s->stride = (size_t)width * 4;
    if (s->stride > (SIZE_MAX - 4095) / (size_t)s->band_height ||
        sizeof(*s->bands) > SIZE_MAX / s->band_count) {
        set_error(error, NEMO_SNAPSHOT_INVALID_ARGUMENT,
                  "snapshot dimensions overflow", ERROR_ARITHMETIC_OVERFLOW);
        goto fail;
    }
    s->pixel_bytes = s->stride * (size_t)s->band_height;
    s->pixel_charge = (s->pixel_bytes + 4095) & ~(size_t)4095;
    if (!charge(s, s->pixel_charge)) {
        codec_error(s, error, "snapshot band pixels");
        goto fail;
    }
    s->bands = snapshot_allocate(s, s->band_count * sizeof(*s->bands));
    if (!s->bands) {
        codec_error(s, error, "snapshot band directory");
        goto fail;
    }
    memset(s->bands, 0, s->band_count * sizeof(*s->bands));
    alloc.Allocate = snapshot_allocate;
    alloc.Free = snapshot_deallocate;
    alloc.UserContext = s;
    if (!CreateCompressor(COMPRESS_ALGORITHM_XPRESS_HUFF, &alloc,
                          &s->compressor)) {
        codec_error(s, error, "create XPRESS_HUFF compressor");
        goto fail;
    }
    SetLastError(ERROR_SUCCESS);
    dc = CreateCompatibleDC(NULL);
    if (!dc) {
        set_error(error, NEMO_SNAPSHOT_GDI_FAILURE,
                  "create snapshot DC", GetLastError());
        goto fail;
    }
    bi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    bi.bmiHeader.biWidth = width;
    bi.bmiHeader.biHeight = -s->band_height;
    bi.bmiHeader.biPlanes = 1;
    bi.bmiHeader.biBitCount = 32;
    bi.bmiHeader.biCompression = BI_RGB;
    s->bitmap = CreateDIBSection(dc, &bi, DIB_RGB_COLORS,
                                 &s->pixels, NULL, 0);
    if (!s->bitmap || !s->pixels) {
        set_error(error, NEMO_SNAPSHOT_GDI_FAILURE,
                  "create snapshot band DIB", GetLastError());
        goto fail;
    }
    previous_bitmap = SelectObject(dc, s->bitmap);
    if (!previous_bitmap || previous_bitmap == HGDI_ERROR) {
        previous_bitmap = NULL;
        set_error(error, NEMO_SNAPSHOT_GDI_FAILURE,
                  "select snapshot DIB", GetLastError());
        goto fail;
    }

    for (unsigned i = 0; i < s->band_count; i++) {
        int top = (int)(i * BAND_HEIGHT), lines = band_height(s, i);
        int saved = SaveDC(dc);
        SIZE_T required = 0, written = 0;
        size_t raw_size = s->stride * (size_t)lines;
        if (!saved) {
            set_error(error, NEMO_SNAPSHOT_GDI_FAILURE,
                      "save snapshot DC", GetLastError());
            goto fail;
        }
        /* This is the only uncompressed pixel allocation. Zeroing also
         * prevents untouched pixels leaking previous bands' contents. */
        memset(s->pixels, 0, s->pixel_bytes);
        if (!SetViewportOrgEx(dc, 0, -top, NULL) ||
            IntersectClipRect(dc, 0, top, width, top + lines) == ERROR) {
            set_error(error, NEMO_SNAPSHOT_GDI_FAILURE,
                      "clip snapshot band", GetLastError());
            RestoreDC(dc, saved);
            goto fail;
        }
        SetLastError(ERROR_SUCCESS);
        bool rendered = render(dc, top, lines, ctx);
        DWORD render_error = GetLastError();
        bool restored = RestoreDC(dc, saved) != 0;
        /* Required before CPU reads pixels written by batched GDI. */
        bool flushed = GdiFlush() != 0;
        if (!rendered || !restored || !flushed) {
            set_error(error, !rendered ? NEMO_SNAPSHOT_RENDER_FAILURE :
                      NEMO_SNAPSHOT_GDI_FAILURE, "render snapshot band",
                      !rendered ? render_error : GetLastError());
            goto fail;
        }
        /* BI_RGB's fourth byte has no display meaning. Canonicalize it
         * instead of storing GDI's unspecified alpha values. */
        for (size_t p = 0; p < raw_size / 4; p++)
            ((uint32_t *)s->pixels)[p] &= UINT32_C(0x00ffffff);
        if (!ResetCompressor(s->compressor)) {
            codec_error(s, error, "reset band compressor");
            goto fail;
        }
        if (Compress(s->compressor, s->pixels, raw_size, NULL, 0, &required) ||
            GetLastError() != ERROR_INSUFFICIENT_BUFFER || !required) {
            codec_error(s, error, "size compressed band");
            goto fail;
        }
        /* The sizing query returns a success guarantee (often almost
         * raw_size), not the final compressed length. Keep just one such
         * scratch buffer; retaining its capacity per band wastes a frame. */
        if (required > scratch_capacity) {
            snapshot_deallocate(s, compressed_scratch);
            compressed_scratch = snapshot_allocate(s, required);
            scratch_capacity = required;
            if (!compressed_scratch) {
                codec_error(s, error, "allocate compression scratch");
                goto fail;
            }
        }
        if (!ResetCompressor(s->compressor) ||
            !Compress(s->compressor, s->pixels, raw_size, compressed_scratch,
                      scratch_capacity, &written) || !written ||
            written > scratch_capacity) {
            codec_error(s, error, "compress snapshot band");
            goto fail;
        }
        s->bands[i].data = snapshot_allocate(s, written);
        if (!s->bands[i].data) {
            codec_error(s, error, "allocate compressed band");
            goto fail;
        }
        memcpy(s->bands[i].data, compressed_scratch, written);
        s->bands[i].size = written;
        s->compressed += written;
    }
    snapshot_deallocate(s, compressed_scratch);
    compressed_scratch = NULL;
    SelectObject(dc, previous_bitmap);
    previous_bitmap = NULL;
    DeleteDC(dc);
    dc = NULL;
    CloseCompressor(s->compressor);
    s->compressor = NULL;
    if (!CreateDecompressor(COMPRESS_ALGORITHM_XPRESS_HUFF, &alloc,
                            &s->decompressor)) {
        codec_error(s, error, "create snapshot decompressor");
        goto fail;
    }
    /* Preflight every independently compressed band. This catches errors
     * and charges the codec's lazy workspace before accepting the freeze. */
    for (unsigned i = 0; i < s->band_count; i++) {
        if (!decode_band(s, i, error))
            goto fail;
    }
    set_error(error, NEMO_SNAPSHOT_OK, "success", ERROR_SUCCESS);
    return s;

fail:
    if (dc) {
        if (previous_bitmap)
            SelectObject(dc, previous_bitmap);
        DeleteDC(dc);
    }
    snapshot_deallocate(s, compressed_scratch);
    nemo_snapshot_free(s);
    SetLastError(error->win32_error);
    return NULL;
}

bool nemo_snapshot_paint(NemoSnapshot *s, HDC dest, const RECT *clip,
                         NemoSnapshotError *error)
{
    NemoSnapshotError local_error;
    RECT bounds, area;
    BITMAPINFO bi = {0};
    int saved, region;
    bool ok = true;
    if (!error)
        error = &local_error;
    set_error(error, NEMO_SNAPSHOT_OK, "success", ERROR_SUCCESS);
    if (!s || !dest) {
        set_error(error, NEMO_SNAPSHOT_INVALID_ARGUMENT,
                  "paint snapshot arguments", ERROR_INVALID_PARAMETER);
        return false;
    }
    bounds.left = bounds.top = 0;
    bounds.right = s->width;
    bounds.bottom = s->height;
    if (!IntersectRect(&area, &bounds, clip ? clip : &bounds))
        return true;
    saved = SaveDC(dest);
    if (!saved) {
        set_error(error, NEMO_SNAPSHOT_GDI_FAILURE,
                  "save destination DC", GetLastError());
        return false;
    }
    region = IntersectClipRect(dest, area.left, area.top, area.right, area.bottom);
    if (region == ERROR) {
        set_error(error, NEMO_SNAPSHOT_GDI_FAILURE,
                  "clip destination DC", GetLastError());
        ok = false;
        goto done;
    }
    if (region == NULLREGION)
        goto done;
    bi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    bi.bmiHeader.biWidth = s->width;
    bi.bmiHeader.biPlanes = 1;
    bi.bmiHeader.biBitCount = 32;
    bi.bmiHeader.biCompression = BI_RGB;
    for (unsigned i = (unsigned)area.top / BAND_HEIGHT;
         i <= (unsigned)(area.bottom - 1) / BAND_HEIGHT; i++) {
        int top = (int)(i * BAND_HEIGHT), lines = band_height(s, i);
        RECT band_rect = {0, top, s->width, top + lines};
        /* An update region may have holes even inside its bounding box. */
        if (!RectVisible(dest, &band_rect))
            continue;
        if (!decode_band(s, i, error)) {
            ok = false;
            break;
        }
        bi.bmiHeader.biHeight = -lines;
        if (!SetDIBitsToDevice(dest, 0, top, (DWORD)s->width, (DWORD)lines,
                               0, 0, 0, (UINT)lines, s->pixels, &bi,
                               DIB_RGB_COLORS)) {
            set_error(error, NEMO_SNAPSHOT_GDI_FAILURE,
                      "display snapshot band", GetLastError());
            ok = false;
            break;
        }
        /* The next band reuses pixels, so finish GDI's read first. */
        if (!GdiFlush()) {
            set_error(error, NEMO_SNAPSHOT_GDI_FAILURE,
                      "flush snapshot display", GetLastError());
            ok = false;
            break;
        }
    }
done:
    if (!RestoreDC(dest, saved) && ok) {
        set_error(error, NEMO_SNAPSHOT_GDI_FAILURE,
                  "restore destination DC", GetLastError());
        ok = false;
    }
    SetLastError(error->win32_error);
    return ok;
}

NemoSnapshotStats nemo_snapshot_stats(const NemoSnapshot *s)
{
    NemoSnapshotStats stats = {0};
    if (s) {
        stats.budget_bytes = s->budget;
        stats.allocated_bytes = s->allocated;
        stats.peak_bytes = s->peak;
        stats.compressed_bytes = s->compressed;
        stats.bands = s->band_count;
    }
    return stats;
}
