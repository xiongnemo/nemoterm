/* SPDX-License-Identifier: MIT */
#ifndef NEMO_WIN32_INPUT_H
#define NEMO_WIN32_INPUT_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

enum { NEMO_WIN32_ENCODED_MAX = 48 };
typedef struct NemoWin32Key {
    uint16_t vk, scan, character, repeat;
    uint32_t control;
    bool down;
} NemoWin32Key;

/* CSI Vk;Sc;Uc;Kd;Cs;Rc_ . Uc is a UTF-16 code unit, not a scalar.
 * Returns a complete sequence length, or -1 without changing the output. */
int nemo_win32_encode(const NemoWin32Key *, char *, size_t);

#endif
