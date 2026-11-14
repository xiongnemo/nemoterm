/* SPDX-License-Identifier: MIT */
#ifndef NEMO_ZLIB_H
#define NEMO_ZLIB_H
#include <stdbool.h>
#include <stddef.h>

/* Decode one RFC 1950 stream into exactly output_bytes of caller-owned storage.
 * No heap allocations, scanning mode, preset dictionary or gzip. The pointer
 * must be non-null even for an empty output. The caller reserves all output
 * storage before entry. Bytes after the first complete stream are ignored,
 * matching the Kitty image loader. Failure may have partially written output. */
bool nemo_zlib_decode(void *output, size_t output_bytes,
                      const void *input, size_t input_bytes);
#endif
