/* SPDX-License-Identifier: MIT */
#include "putty.h"
#include "nemo_clipboard.h"

bool nemo_open_clipboard(HWND hwnd)
{
    /* Clipboard viewers can briefly hold the lock after an update. Keep copy
     * synchronous so Copy and Paste cannot race a deferred write, but bound
     * retries to 100 ms rather than blocking the UI indefinitely. */
    ULONGLONG deadline = GetTickCount64() + 100;
    while (!OpenClipboard(hwnd)) {
        ULONGLONG now = GetTickCount64();
        if (now >= deadline) return false;
        Sleep((DWORD)min(10, deadline-now));
    }
    return true;
}
