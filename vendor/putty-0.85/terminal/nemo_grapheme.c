/* SPDX-License-Identifier: MIT */
#include "nemo_grapheme.h"
#include <stddef.h>

enum {
    G_OTHER, G_CR, G_LF, G_CONTROL, G_EXTEND, G_ZWJ, G_RI,
    G_PREPEND, G_SPACING, G_L, G_V, G_T, G_LV, G_LVT
};
enum { I_NONE, I_CONSONANT, I_EXTEND, I_LINKER };
#include "nemo_grapheme_data.h"

static unsigned properties(uint32_t cp)
{
    unsigned hangul = cp >= 0xac00 && cp <= 0xd7a3 ?
        ((cp - 0xac00) % 28 ? G_LVT : G_LV) : 0;
    size_t lo = 0, hi = sizeof(nemo_grapheme_ranges) / sizeof(*nemo_grapheme_ranges);
    while (lo < hi) {
        size_t mid = lo + (hi-lo)/2;
        if (cp < nemo_grapheme_ranges[mid].first) hi = mid;
        else if (cp > nemo_grapheme_ranges[mid].last) lo = mid+1;
        else return nemo_grapheme_ranges[mid].value | hangul;
    }
    return hangul;
}

void nemo_grapheme_reset(NemoGraphemeState *state)
{
    *state = (NemoGraphemeState){0};
}

static bool control(unsigned g)
{
    return g == G_CR || g == G_LF || g == G_CONTROL;
}

bool nemo_grapheme_feed(NemoGraphemeState *s, uint32_t cp)
{
    /* The UTF decoder normally rejects these; make this API safe in isolation. */
    if (cp > 0x10ffff || (cp >= 0xd800 && cp <= 0xdfff)) {
        nemo_grapheme_reset(s);
        s->started = 1;
        s->previous = G_CONTROL;
        return true;
    }
    unsigned props = properties(cp), g = props & 15, prev = s->previous;
    unsigned incb = (props >> 4) & 3;
    bool ep = (props & 0x40) != 0, boundary;
    if (!s->started) boundary = true;                        /* GB1 */
    else if (prev == G_CR && g == G_LF) boundary = false;    /* GB3 */
    else if (control(prev) || control(g)) boundary = true;  /* GB4/5 */
    else if (prev == G_L && (g == G_L || g == G_V ||
                             g == G_LV || g == G_LVT)) boundary = false;
    else if ((prev == G_LV || prev == G_V) &&
             (g == G_V || g == G_T)) boundary = false;       /* GB6/7 */
    else if ((prev == G_LVT || prev == G_T) && g == G_T) boundary = false;
    else if (g == G_EXTEND || g == G_ZWJ ||
             g == G_SPACING || prev == G_PREPEND) boundary = false; /* GB9/a/b */
    else if (s->indic_linker && incb == I_CONSONANT) boundary = false; /* GB9c */
    else if (s->ep_zwj && ep) boundary = false;              /* GB11 */
    else if (prev == G_RI && g == G_RI && s->ri_odd) boundary = false;
    else boundary = true;                                  /* GB12/13/999 */

    /* Finite suffix state: no unbounded cluster-length or RI-run counter. */
    s->ri_odd = g == G_RI ? (prev == G_RI ? !s->ri_odd : 1) : 0;
    s->ep_zwj = g == G_ZWJ && s->ep_extend;
    s->ep_extend = ep || (g == G_EXTEND && s->ep_extend);
    /* Rev. 49 GB9c starts at any Linker, unlike Unicode 16/17's rule. */
    s->indic_linker = incb == I_LINKER || (incb == I_EXTEND && s->indic_linker);
    s->previous = (unsigned char)g;
    s->started = 1;
    return boundary;
}

unsigned nemo_grapheme_cell_width(NemoGraphemeWidth *s, uint32_t cp, int legacy)
{
    unsigned props = properties(cp);
    unsigned width = legacy >= 2 || (props & (0x80 | 0x200)) ||
        (cp == 0xfe0f && s->emoji_base) ? 2 : 1;
    if (s->cells < width) s->cells = (unsigned char)width;
    s->emoji_base = (props & 0x100) != 0;
    return s->cells;
}
