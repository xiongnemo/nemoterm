/* SPDX-License-Identifier: MIT */
#ifndef NEMO_GRAPHEME_H
#define NEMO_GRAPHEME_H
#include <stdbool.h>
#include <stdint.h>

/* Streaming Unicode 18.0.0 extended grapheme boundaries (UAX #29 rev. 49).
 * No text storage, allocation, locale, UTF decoder or terminal width policy.
 * Zero initialization starts a new stream. State may span input chunks.
 * Each invalid scalar is isolated as a replacement-character cluster.
 * This is not an advertisement of terminal mode 2027 support. */
typedef struct NemoGraphemeState {
    unsigned char previous, started, ri_odd, ep_extend, ep_zwj, indic_linker;
} NemoGraphemeState;

void nemo_grapheme_reset(NemoGraphemeState *state);
/* Consume one scalar; true iff there is a boundary immediately before it. */
bool nemo_grapheme_feed(NemoGraphemeState *state, uint32_t scalar);

#endif
