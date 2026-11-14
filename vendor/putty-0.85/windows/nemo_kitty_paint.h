/* SPDX-License-Identifier: MIT */
#ifndef NEMO_KITTY_PAINT_H
#define NEMO_KITTY_PAINT_H
#include "nemo_gpu.h"
typedef struct NemoKittyPainter NemoKittyPainter;
/* Coordinates and clip are client pixels. Under-text painting is performed
 * inside the current GDI text run, including GPU scratch runs. */
bool nemo_kitty_intersects(Terminal *, RECT clip, int ox, int oy,
                           bool foreground, bool default_background);
bool nemo_kitty_paint(NemoKittyPainter **, Terminal *, HDC, RECT clip, int ox, int oy,
                      bool foreground, bool default_background, NemoGPU *);
void nemo_kitty_paint_free(NemoKittyPainter **);
#endif
