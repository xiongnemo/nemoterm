/* SPDX-License-Identifier: MIT */
#ifndef NEMO_CHARSET_H
#define NEMO_CHARSET_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* A descriptor and its mapping table are immutable static data. Aliases retain
 * their own wire designation for presentation-state round trips. */
typedef struct NemoCharset {
    const char *designation;
    const uint16_t *mapping;
    unsigned char minimum_level, maximum_level;
    unsigned char kind;
    bool national, size96;
} NemoCharset;

/* group is 1 for a 94-character designation, 3 for a 96-character introducer.
 * A NULL return means no supported designation at the requested level/mode;
 * the caller decides the terminal's unknown-designator recovery policy. */
const NemoCharset *nemo_charset_designate(unsigned group, unsigned level,
    bool national, const char *designation, size_t length);

/* Bounded stable-in-process handles for the parser's saved G0..G3 slots.
 * Zero is invalid; the introducer size is kept separately by the caller. */
unsigned nemo_charset_id(const NemoCharset *charset);
const NemoCharset *nemo_charset_by_id(unsigned id);

#define NEMO_CHARSET_NOCHAR UINT32_MAX
/* Maps one graphic byte, including explicit GR invocation. This does not parse
 * UTF-8, C0/C1 controls, or change GL/GR/SS/cursor state. The terminal parser must
 * perform those operations before calling it. No allocation or locale state. */
uint32_t nemo_charset_map(const NemoCharset *charset, unsigned byte,
                         unsigned level, bool national);

/* XTerm NRC selection-input conversion. It is always seven-bit, including
 * its fallback for unrepresentable characters. unicode_nrc enables UNI rules.
 * Keyboard layout/locale encoding is separate from selection conversion. */
unsigned nemo_charset_input(const NemoCharset *charset, uint32_t scalar,
                            bool unicode_nrc);
#endif
