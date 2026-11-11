/* SPDX-License-Identifier: MIT */
#ifndef NEMO_SNAPSHOT_H
#define NEMO_SNAPSHOT_H

#include <windows.h>
#include <stdbool.h>
#include <stddef.h>

typedef struct NemoSnapshot NemoSnapshot;

typedef enum NemoSnapshotFailure {
    NEMO_SNAPSHOT_OK,
    NEMO_SNAPSHOT_INVALID_ARGUMENT,
    NEMO_SNAPSHOT_BUDGET_EXCEEDED,
    NEMO_SNAPSHOT_OUT_OF_MEMORY,
    NEMO_SNAPSHOT_GDI_FAILURE,
    NEMO_SNAPSHOT_CODEC_FAILURE,
    NEMO_SNAPSHOT_RENDER_FAILURE
} NemoSnapshotFailure;

typedef struct NemoSnapshotError {
    NemoSnapshotFailure reason;
    DWORD win32_error;
    const char *stage;                 /* static string; never free it */
} NemoSnapshotError;

typedef struct NemoSnapshotStats {
    size_t budget_bytes, allocated_bytes, peak_bytes, compressed_bytes;
    unsigned bands;
} NemoSnapshotStats;

/* Draw every pixel of this band, including the window margins. Coordinates
 * are absolute client coordinates: the DC already maps (0,top) to (0,0)
 * and clips to [0,width) x [top,top+height). The DC/bitmap remain ours.
 * The callback may change DC state, but must not delete or replace its
 * bitmap, pump messages, or change the terminal being captured.
 * Return false if rendering failed (optionally set GetLastError).
 */
typedef bool (*NemoSnapshotRender)(HDC, int top, int height, void *ctx);

/* Windows 8+; link cabinet and gdi32. Synchronous, single-threaded API.
 * Keeps lossless XPRESS_HUFF bands and only one 32-row, top-down BGRA DIB.
 * No full-window uncompressed image is allocated. Creating or painting a
 * snapshot never invokes a window's WM_PAINT or pumps the message loop.
 *
 * budget covers the object, band directory, allocation headers, compressed
 * blocks, codec allocations (via custom allocators), and page-rounded DIB
 * pixels. It excludes OS GDI handle/heap bookkeeping and memory allocated
 * by render. A zero budget is invalid. Failure is all-or-nothing and frees
 * all module allocations. error may be NULL; GetLastError is also set.
 *
 * The caller must invalidate its display cache after capture, on success
 * AND failure, if render updated a cache without drawing on the window.
 */
NemoSnapshot *nemo_snapshot_create(int width, int height, size_t budget,
                                 NemoSnapshotRender render, void *ctx,
                                 NemoSnapshotError *error);

/* Paint only the intersection with clip (NULL means the entire snapshot),
 * preserving the destination DC's existing clipping and other state.
 * Destination coordinates are client pixels (MM_TEXT). No live terminal
 * state or render callback is accessed. Empty/clipped-away areas succeed.
 * A false return requires the caller to abandon the freeze and repaint.
 */
bool nemo_snapshot_paint(NemoSnapshot *, HDC dest, const RECT *clip,
                         NemoSnapshotError *error);
NemoSnapshotStats nemo_snapshot_stats(const NemoSnapshot *);
void nemo_snapshot_free(NemoSnapshot *);

#endif
