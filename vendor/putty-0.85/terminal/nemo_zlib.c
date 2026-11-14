/* SPDX-License-Identifier: MIT */
#include "nemo_zlib.h"
#include "puff/puff.h"
#include <limits.h>
#include <stdint.h>

static uint32_t adler32(const unsigned char *p, size_t length)
{
    uint32_t a = 1, b = 0;
    while (length) {
        /* This block bound keeps both sums within uint32_t before reduction. */
        size_t count = length < 5552 ? length : 5552;
        length -= count;
        while (count--) { a += *p++; b += a; }
        a %= 65521; b %= 65521;
    }
    return b << 16 | a;
}

bool nemo_zlib_decode(void *output, size_t output_bytes,
                      const void *input, size_t input_bytes)
{
    if (!output || !input || input_bytes < 6 || input_bytes > ULONG_MAX ||
        output_bytes > ULONG_MAX) return false;
    const unsigned char *p = input;
    unsigned header = (unsigned)p[0] << 8 | p[1];
    if ((p[0] & 15) != 8 || (p[0] >> 4) > 7 || (p[1] & 32) || header % 31)
        return false;
    unsigned long in = (unsigned long)(input_bytes - 6);
    unsigned long out = (unsigned long)output_bytes;
    unsigned long window = 1ul << ((p[0] >> 4) + 8);
    if (nemo_puff(output, &out, p + 2, &in, window) || out != output_bytes ||
        in > input_bytes - 6) return false;
    const unsigned char *checksum = p + 2 + in;
    uint32_t expected = (uint32_t)checksum[0] << 24 | (uint32_t)checksum[1] << 16 |
        (uint32_t)checksum[2] << 8 | checksum[3];
    return adler32(output, output_bytes) == expected;
}
