/* SPDX-License-Identifier: MIT */
#define COBJMACROS
#include "nemo_progress.h"
#include <shobjidl.h>

/* GUI STA only. A terminal that never reports progress does not instantiate
 * the shell object. There is one object for the process, not one per tab. */
static ITaskbarList3 *taskbar;
void nemo_shell_progress_cleanup(void)
{
    if (taskbar) { ITaskbarList3_Release(taskbar); taskbar = NULL; }
}
HRESULT nemo_shell_progress(HWND window, unsigned state, unsigned value)
{
    static const TBPFLAG flags[] = {
        TBPF_NOPROGRESS, TBPF_NORMAL, TBPF_ERROR, TBPF_INDETERMINATE, TBPF_PAUSED
    };
    if (state >= sizeof(flags)/sizeof(*flags)) return E_INVALIDARG;
    HRESULT hr;
    if (!taskbar) {
        hr = CoCreateInstance(&CLSID_TaskbarList, NULL, CLSCTX_INPROC_SERVER,
                              &IID_ITaskbarList3, (void **)&taskbar);
        if (FAILED(hr)) return hr;
        hr = ITaskbarList3_HrInit(taskbar);
        if (FAILED(hr)) { nemo_shell_progress_cleanup(); return hr; }
    }
    /* Explorer can retain a determinate bar if switched directly to marquee. */
    if (state == 3) {
        hr = ITaskbarList3_SetProgressState(taskbar, window, TBPF_NOPROGRESS);
        if (FAILED(hr)) return hr;
    }
    hr = ITaskbarList3_SetProgressState(taskbar, window, flags[state]);
    if (SUCCEEDED(hr) && state && state != 3)
        hr = ITaskbarList3_SetProgressValue(taskbar, window, value, 100);
    return hr;
}
