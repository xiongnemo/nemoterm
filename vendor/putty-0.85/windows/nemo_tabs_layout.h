/* SPDX-License-Identifier: MIT */
#ifndef NEMO_TABS_LAYOUT_H
#define NEMO_TABS_LAYOUT_H
#include <stdbool.h>

/* Pixel geometry only: no windows, renderer state, sessions or allocation. */
typedef struct NemoTabRect { int x, y, width, height; } NemoTabRect;
typedef enum NemoTabSide {
    NEMO_TABS_TOP, NEMO_TABS_BOTTOM, NEMO_TABS_LEFT, NEMO_TABS_RIGHT
} NemoTabSide;
typedef struct NemoTabMetrics {
    int row, sidebar, minimum, preferred, padding;
} NemoTabMetrics;
typedef struct NemoTabLayout {
    NemoTabRect bar, content, add, previous, next;
    NemoTabSide side;
    NemoTabMetrics metrics;
    int count, first, visible, extent;
    bool vertical, overflow;
} NemoTabLayout;
typedef enum NemoTabHitKind {
    NEMO_TAB_NONE, NEMO_TAB_BODY, NEMO_TAB_CLOSE,
    NEMO_TAB_ADD, NEMO_TAB_PREVIOUS, NEMO_TAB_NEXT
} NemoTabHitKind;
typedef struct NemoTabHit { NemoTabHitKind kind; int index; } NemoTabHit;

/* Sidebar width is in 96-DPI units, clamped to 96..480; zero selects 192. */
NemoTabMetrics nemo_tabs_metrics(int dpi, int sidebar);
NemoTabLayout nemo_tabs_layout(int width, int height, NemoTabSide side,
                              NemoTabMetrics metrics, int count, int first);
NemoTabRect nemo_tabs_item(const NemoTabLayout *, int index);
NemoTabRect nemo_tabs_close(const NemoTabLayout *, int index);
NemoTabHit nemo_tabs_hit(const NemoTabLayout *, int x, int y);
int nemo_tabs_reveal(const NemoTabLayout *, int index);
/* Anchor and work area use screen coordinates, including negative monitors.
 * A preview is at most 320x200 physical pixels, independent of DPI. */
NemoTabRect nemo_tabs_preview(NemoTabRect anchor, NemoTabSide side,
                             NemoTabRect work, int width, int height, int gap);
#endif
