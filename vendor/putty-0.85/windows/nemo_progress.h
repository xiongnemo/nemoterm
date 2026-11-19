/* SPDX-License-Identifier: MIT */
#ifndef NEMO_PROGRESS_H
#define NEMO_PROGRESS_H
#include <windows.h>
/* One per top-level window. The shell may create its button after the first OSC. */
typedef struct NemoTaskbarButton {
    BOOL ready, pending, attempted;
    unsigned state, value;
    HRESULT result;
} NemoTaskbarButton;
HRESULT nemo_shell_progress(HWND window, unsigned state, unsigned value);
void nemo_shell_progress_cleanup(void);
#endif
