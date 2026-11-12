/* SPDX-License-Identifier: MIT */
#ifndef NEMO_MOK_H
#define NEMO_MOK_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "nemo_keyboard.h"

typedef struct NemoModifyKeys {
    int8_t level; /* -1 disabled by CSI > 4 n; 0..3 are XTMODKEYS levels */
    uint8_t format;
    uint32_t ignore; /* xterm/X11 modifier mask, independent of wire modifiers */
} NemoModifyKeys;

enum NemoModifiedKeyKind { NMK_TEXT, NMK_TAB, NMK_ENTER, NMK_BACKSPACE, NMK_ESCAPE };
typedef struct NemoModifiedKey {
    uint32_t key, factored_key; /* layout character before/after factoring */
    unsigned modifiers, type; /* NEMO_KEY_* modifiers; press/repeat/release */
    enum NemoModifiedKeyKind kind;
} NemoModifiedKey;

#define NEMO_MOK_ENCODED_MAX 32
void nemo_mok_reset(NemoModifyKeys *, int level, int format);
unsigned nemo_mok_xstate(unsigned modifiers);
/* -1 retains the existing translator, 0 consumes without output. A positive
 * result is one complete protocol sequence or a preserved ASCII control chord. */
int nemo_mok_encode(const NemoModifyKeys *, const NemoModifiedKey *, char *, size_t);
#endif
