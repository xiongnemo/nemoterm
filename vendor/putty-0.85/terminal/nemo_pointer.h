/* SPDX-License-Identifier: MIT */
#ifndef NEMO_POINTER_H
#define NEMO_POINTER_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define NEMO_POINTER_SHAPES(X) \
    X(ALIAS, "alias") X(CELL, "cell") X(COPY, "copy") \
    X(CROSSHAIR, "crosshair") X(DEFAULT, "default") \
    X(E_RESIZE, "e-resize") X(EW_RESIZE, "ew-resize") \
    X(GRAB, "grab") X(GRABBING, "grabbing") X(HELP, "help") \
    X(MOVE, "move") X(N_RESIZE, "n-resize") X(NE_RESIZE, "ne-resize") \
    X(NESW_RESIZE, "nesw-resize") X(NO_DROP, "no-drop") \
    X(NOT_ALLOWED, "not-allowed") X(NS_RESIZE, "ns-resize") \
    X(NW_RESIZE, "nw-resize") X(NWSE_RESIZE, "nwse-resize") \
    X(POINTER, "pointer") X(PROGRESS, "progress") \
    X(S_RESIZE, "s-resize") X(SE_RESIZE, "se-resize") \
    X(SW_RESIZE, "sw-resize") X(TEXT, "text") \
    X(VERTICAL_TEXT, "vertical-text") X(W_RESIZE, "w-resize") \
    X(WAIT, "wait") X(ZOOM_IN, "zoom-in") X(ZOOM_OUT, "zoom-out")

typedef enum NemoPointerShape {
    NEMO_POINTER_NONE,
#define NEMO_POINTER_ENUM(id, name) NEMO_POINTER_##id,
    NEMO_POINTER_SHAPES(NEMO_POINTER_ENUM)
#undef NEMO_POINTER_ENUM
    NEMO_POINTER_SHAPE_COUNT
} NemoPointerShape;

enum { NEMO_POINTER_STACK_MAX = 16, NEMO_POINTER_OSC_MAX = 2048,
       NEMO_POINTER_REPLY_MAX = 4096 };
typedef struct NemoPointerState {
    uint8_t count[2];
    uint8_t stack[2][NEMO_POINTER_STACK_MAX];
} NemoPointerState;

/* Zero-initialized state; the owner may allocate this only when first set.
 * No storage is attached to terminal cells. NULL means two empty stacks. */
NemoPointerShape nemo_pointer_current(const NemoPointerState *, bool alternate);
const char *nemo_pointer_name(NemoPointerShape);
/* A canonical, nonempty name only. Unknown names return NONE. */
NemoPointerShape nemo_pointer_lookup(const char *, size_t);
/* '=', '>' and '<' affect the selected stack only. Set/push accept NONE as
 * an explicit automatic-shape slot. Invalid arguments leave state intact. */
bool nemo_pointer_change(NemoPointerState *, bool alternate, char operation,
                         NemoPointerShape);

typedef enum NemoPointerResult {
    NEMO_POINTER_IGNORED, NEMO_POINTER_APPLIED, NEMO_POINTER_QUERY
} NemoPointerResult;
/* Complete OSC 22 payload only, without prefix/terminator. Query output is
 * unframed, length-delimited, and emitted only on QUERY. No allocation.
 * Query defaults match the frontend's text / raw-mouse arrow policy. */
NemoPointerResult nemo_pointer_command(NemoPointerState *, bool alternate,
    const char *payload, size_t length, char *reply, size_t capacity, size_t *used);

#endif
