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

/* Terminal policy, separate from UAX #29: max scalar width, wide/default
 * emoji at two cells, eligible VS16 may widen, no retroactive narrowing.
 * Start each cluster with a zeroed state. scalar_width is the caller's
 * legacy width (including its ambiguous-width preference). */
typedef struct NemoGraphemeWidth {
    unsigned char cells, emoji_base;
} NemoGraphemeWidth;
unsigned nemo_grapheme_cell_width(NemoGraphemeWidth *, uint32_t, int scalar_width);

#endif
