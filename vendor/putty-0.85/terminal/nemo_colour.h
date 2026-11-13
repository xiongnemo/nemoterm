/* SPDX-License-Identifier: MIT
 * Bounded, allocation-free OSC colour parsing for NemoTerm.
 */
#ifndef NEMO_COLOUR_H
#define NEMO_COLOUR_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef struct NemoColour {
    uint8_t r, g, b;
} NemoColour;

/* Parse an exact byte slice, which need not be NUL-terminated.
 *
 * Supported XParseColor device-colour forms (ASCII case-insensitive):
 *   rgb:r/g/b   - each component independently has 1..4 hex digits;
 *   #rgb, #rrggbb, #rrrgggbbb, #rrrrggggbbbb;
 *   the pinned Xorg server 21.1.16 named-colour table, including its
 *   space-separated aliases and numbered variants (e.g. gray50, red1).
 *
 * rgb: components are scaled to 16 bits, then reduced to their high 8
 * bits. Legacy # components are high-aligned, not scaled: #fff gives
 * (240,240,240), while rgb:f/f/f gives (255,255,255). This follows Xlib
 * colour-string semantics, rather than CSS shorthand semantics.
 *
 * Unknown names, extra whitespace, alpha, and Xcms colour spaces are rejected.
 * Interior spaces are accepted only where present in the pinned table.
 * In particular rgbi: specifies linear light intensity, whose conversion
 * to device RGB requires an Xcms device profile. It is deliberately not
 * treated as a synonym for rgb: with fractional components.
 *
 * No allocation or locale dependency; names use a read-only binary search.
 * Input length is bounded by the longest name in the pinned table (22 bytes).
 * Returns false on an invalid slice or NULL argument, leaving *out alone.
 */
bool nemo_colour_parse(const char *text, size_t len, NemoColour *out);

#endif
