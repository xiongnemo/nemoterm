/* SPDX-License-Identifier: MIT */
#ifndef NEMO_POINTER_WIN_H
#define NEMO_POINTER_WIN_H
#include <windows.h>
#include "nemo_pointer.h"

/* Shared stock cursors retain the Windows theme. Custom monochrome cursors
 * are created lazily in bounded 8-pixel size buckets from 32 through 128. */
HCURSOR nemo_pointer_cursor(NemoPointerShape, unsigned requested_size);
/* Call on the UI thread after all terminal windows have been destroyed. */
void nemo_pointer_cursors_free(void);
#endif
