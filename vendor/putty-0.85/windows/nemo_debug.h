/* SPDX-License-Identifier: MIT */
#ifndef NEMO_DEBUG_H
#define NEMO_DEBUG_H
#include "putty.h"

/* Little-endian wire protocol, documented in docs/AUTOMATION.md. */
#define NEMO_DEBUG_MESSAGE (WM_APP + 71)
#define NEMO_DEBUG_MAX_INPUT 65536
#define NEMO_DEBUG_MAX_OUTPUT (16 * 1024 * 1024)
enum { NDBG_LIST=1, NDBG_TEXT, NDBG_INPUT, NDBG_PASTE, NDBG_KEY, NDBG_IMAGE };
typedef struct NemoDebugRequest {
    unsigned op, status, kind;
    uint64_t session;
    strbuf *input, *output;
} NemoDebugRequest;
typedef void (*NemoDebugDispatch)(NemoDebugRequest *);
extern bool nemo_debug_enabled;
bool nemo_debug_start(HWND, NemoDebugDispatch);
void nemo_debug_dispatch(void);
void nemo_debug_stop(void);
#endif
