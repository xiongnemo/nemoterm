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
 *   black, white, red, green, blue, yellow, magenta, cyan.
 *
 * rgb: components are scaled to 16 bits, then reduced to their high 8
 * bits. Legacy # components are high-aligned, not scaled: #fff gives
 * (240,240,240), while rgb:f/f/f gives (255,255,255). This follows Xlib
 * colour-string semantics, rather than CSS shorthand semantics.
 *
 * Other names, whitespace, alpha, and Xcms colour spaces are rejected.
 * In particular rgbi: specifies linear light intensity, whose conversion
 * to device RGB requires an Xcms device profile. It is deliberately not
 * treated as a synonym for rgb: with fractional components.
 *
 * No allocation or locale dependency; at most 18 input bytes examined.
 * Returns false on an invalid slice or NULL argument, leaving *out alone.
 */
bool nemo_colour_parse(const char *text, size_t len, NemoColour *out);

#endif
