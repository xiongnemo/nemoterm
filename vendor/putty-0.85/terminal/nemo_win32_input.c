/* SPDX-License-Identifier: MIT */
#include "nemo_win32_input.h"
#include <stdio.h>
#include <string.h>

int nemo_win32_encode(const NemoWin32Key *key, char *out, size_t size)
{
    char encoded[NEMO_WIN32_ENCODED_MAX];
    int n = snprintf(encoded, sizeof(encoded), "\033[%u;%u;%u;%u;%u;%u_",
                     (unsigned)key->vk, (unsigned)key->scan,
                     (unsigned)key->character, key->down ? 1u : 0u,
                     (unsigned)key->control, (unsigned)key->repeat);
    if (n < 0 || (size_t)n >= sizeof(encoded) || (size_t)n > size) return -1;
    memcpy(out, encoded, n);
    return n;
}
