/* SPDX-License-Identifier: MIT */
#ifndef NEMO_DROP_H
#define NEMO_DROP_H
#include "putty.h"
#include <shellapi.h>
typedef struct NemoDropTarget {
    bool ready;
    int shell;
    wchar_t *distro;
} NemoDropTarget;
void nemo_drop_target_init(NemoDropTarget *, Conf *, const wchar_t *command, int shell);
void nemo_drop_record_launch(Seat *, Conf *, const wchar_t *command, int shell);
/* A bounded, quoted path list; caller owns the result. Does not free HDROP. */
wchar_t *nemo_drop_paths(HDROP, Conf *, const NemoDropTarget *, size_t *length);
#endif
