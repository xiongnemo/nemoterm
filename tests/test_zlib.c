/* SPDX-License-Identifier: MIT */
#include "nemo_zlib.h"
#ifdef NDEBUG
#undef NDEBUG
#endif
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "zlib_reference.h"
static unsigned checks;
#define CHECK(x) do { checks++; assert(x); } while (0)

static bool guarded(const void *input, size_t length, size_t size,
                    const unsigned char *expected)
{
    unsigned char *storage = malloc(size + 32);
    CHECK(storage);
    memset(storage, 0xa5, size + 32);
    bool result = nemo_zlib_decode(storage + 16, size, input, length);
    for (unsigned i = 0; i < 16; i++) {
        CHECK(storage[i] == 0xa5);
        CHECK(storage[size + 16 + i] == 0xa5);
    }
    if (result && expected) CHECK(!memcmp(storage + 16, expected, size));
    free(storage);
    return result;
}

int main(void)
{
    for (size_t i = 0; i < sizeof(zlib_reference)/sizeof(*zlib_reference); i++) {
        const ZlibReference *r = &zlib_reference[i];
        CHECK(guarded(r->encoded, r->encoded_size, r->decoded_size, r->decoded));
        /* Every truncated stream and every insufficient output size must fail
         * without touching the caller's neighboring bytes. */
        for (size_t n = 0; n < r->encoded_size; n++)
            CHECK(!guarded(r->encoded, n, r->decoded_size, NULL));
        for (size_t n = 0; n < r->decoded_size; n++)
            CHECK(!guarded(r->encoded, r->encoded_size, n, NULL));
        CHECK(!guarded(r->encoded, r->encoded_size, r->decoded_size + 1, NULL));
        unsigned char *copy = malloc(r->encoded_size * 2 + 8);
        CHECK(copy);
        memcpy(copy, r->encoded, r->encoded_size);
        for (unsigned n = 1; n <= 4; n++) {
            copy[r->encoded_size-n] ^= 1;
            CHECK(!guarded(copy, r->encoded_size, r->decoded_size, NULL));
            copy[r->encoded_size-n] ^= 1;
        }
        memcpy(copy+r->encoded_size, r->encoded, r->encoded_size);
        CHECK(guarded(copy, r->encoded_size*2, r->decoded_size, r->decoded));
        memset(copy+r->encoded_size, 0xa5, 8);
        CHECK(guarded(copy, r->encoded_size+8, r->decoded_size, r->decoded));
        /* RFC 1950 header: invalid method/window/check bits or a dictionary
         * request cannot be accepted as an ordinary Kitty zlib stream. */
        unsigned char header_output[512];
        CHECK(r->decoded_size <= sizeof(header_output));
        for (unsigned h = 0; h < 65536; h++) {
            copy[0] = (unsigned char)(h >> 8); copy[1] = (unsigned char)h;
            if ((copy[0]&15) != 8 || (copy[0]>>4) > 7 || (copy[1]&32) || h%31)
                CHECK(!nemo_zlib_decode(header_output, r->decoded_size, copy, r->encoded_size));
        }
        free(copy);
    }
    static const unsigned char empty[] = {120,156,3,0,0,0,0,1};
    unsigned char output[1];
    CHECK(guarded(empty, sizeof(empty), 0, NULL));
    CHECK(!guarded(empty, sizeof(empty), 1, NULL));
    CHECK(!nemo_zlib_decode(NULL, 0, empty, sizeof(empty)));
    CHECK(!nemo_zlib_decode(output, 1, NULL, 8));
    CHECK(!nemo_zlib_decode(output, SIZE_MAX, empty, sizeof(empty)));
    CHECK(!nemo_zlib_decode(output, 1, empty, SIZE_MAX));
    printf("Bounded zlib: %u checks passed\n", checks);
    return 0;
}
