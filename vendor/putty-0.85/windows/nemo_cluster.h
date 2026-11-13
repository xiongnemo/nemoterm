/* SPDX-License-Identifier: MIT */
#ifndef NEMO_CLUSTER_H
#define NEMO_CLUSTER_H
#include <windows.h>
#include <stdbool.h>
#include <stddef.h>

typedef struct NemoClusterRenderer NemoClusterRenderer;
#ifdef __cplusplus
extern "C" {
#endif
/* The caller supplies exactly one bounded UTF-16 cluster and its grid box.
 * The selected font in dc determines style and pixel size. y_offset supports
 * the clipped bottom half of DEC double-height rows. No input is modified.
 * Layout/allocation failure leaves the destination unchanged for a fallback.
 * transparent preserves existing destination pixels under combining/shadow
 * glyphs; otherwise background fills the cell before drawing.
 * Only system DLLs are loaded, lazily on first use. UI thread only. */
bool nemo_cluster_draw(NemoClusterRenderer **, HDC dc, const RECT *box,
                      const wchar_t *text, unsigned units, int y_offset,
                      COLORREF foreground, COLORREF background, bool emoji,
                      float horizontal_scale, bool shadow_bold, bool transparent);
void nemo_cluster_free(NemoClusterRenderer **);
/* Retained raster scratch bytes, excluding system font/factory allocations. */
size_t nemo_cluster_raster_bytes(const NemoClusterRenderer *);
#ifdef __cplusplus
}
#endif
#endif
