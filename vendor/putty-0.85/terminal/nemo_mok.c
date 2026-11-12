/* SPDX-License-Identifier: MIT
 * xterm modified-character keys, independently implemented from its control
 * specification and reference outputs. Alt/Meta retain ESC-prefix behavior
 * at level 1, matching the native frontend's existing default. */
#include "nemo_mok.h"
#include <stdio.h>
#include <string.h>

void nemo_mok_reset(NemoModifyKeys *state, int level, int format)
{
    *state = (NemoModifyKeys){.level=level >= 0 && level <= 3 ? level : 0,
                             .format=format == 1};
}

unsigned nemo_mok_xstate(unsigned mods)
{
    return (mods & NEMO_KEY_SHIFT ? 1 : 0) | (mods & NEMO_KEY_CAPS ? 2 : 0) |
        (mods & NEMO_KEY_CTRL ? 4 : 0) | (mods & NEMO_KEY_ALT ? 8 : 0) |
        (mods & NEMO_KEY_NUM ? 16 : 0) | (mods & NEMO_KEY_SUPER ? 64 : 0);
}

static int control(uint32_t key)
{
    if (key >= 64 && key <= 127) return key & 31;
    if (key == ' ' || key == '2') return 0;
    if (key >= '3' && key <= '7') return key-'3'+27;
    if (key == '8' || key == '?') return 127;
    if (key == '/') return 31;
    return -1;
}

static bool scalar(uint32_t key)
{ return key <= 0x10ffff && !(key >= 0xd800 && key <= 0xdfff); }

int nemo_mok_encode(const NemoModifyKeys *state, const NemoModifiedKey *key,
                    char *output, size_t capacity)
{
    if (state->level <= 0) return -1;
    if (!key || !output || !capacity || !scalar(key->key) || !scalar(key->factored_key) ||
        key->type < 1 || key->type > 3 || key->kind < NMK_TEXT || key->kind > NMK_ESCAPE) return 0;
    if (key->type == 3) return 0;
    if (key->kind == NMK_TEXT && (key->key < 32 || (key->key >= 127 && key->key <= 159))) return 0;
    unsigned mods = key->modifiers & 15, effective = mods;
    bool encode = state->level == 3;
    int alias = key->kind == NMK_TEXT && (mods & NEMO_KEY_CTRL) ? control(key->key) : -1;
    if (state->level == 1) {
        effective &= ~(NEMO_KEY_ALT | NEMO_KEY_SUPER);
        if ((mods & (NEMO_KEY_ALT | NEMO_KEY_SUPER)) &&
            (key->kind == NMK_TAB || key->kind == NMK_ENTER || alias >= 0))
            effective &= ~NEMO_KEY_CTRL;
        if (key->kind == NMK_ENTER) encode = effective != 0;
        else if (key->kind == NMK_TAB) encode = (effective & NEMO_KEY_CTRL) != 0;
        else if (key->kind == NMK_TEXT && alias < 0)
            encode = (effective & NEMO_KEY_CTRL) != 0;
    } else if (state->level == 2) {
        if (key->kind == NMK_BACKSPACE) encode = (mods & ~NEMO_KEY_CTRL) != 0;
        else if (key->kind != NMK_TEXT) encode = mods != 0;
        else encode = (mods & ~NEMO_KEY_SHIFT) ||
            ((mods & NEMO_KEY_SHIFT) && (key->key == ' ' || (key->key >= 64 && key->key <= 127)));
    }
    /* xterm suppresses a sole factored modifier. Combinations retain their
     * modifier parameter, but use the character looked up with the mask removed. */
    unsigned raw = nemo_mok_xstate(key->modifiers);
    if (raw && !(raw & (raw-1)) && (raw & state->ignore)) {
        effective = 0;
        if (state->level < 3) encode = false;
    }
    char buffer[NEMO_MOK_ENCODED_MAX];
    int length;
    if (encode) {
        uint32_t value = key->factored_key ? key->factored_key : key->key;
        length = state->format ? snprintf(buffer, sizeof(buffer), "\033[%u;%uu", value, effective+1) :
            snprintf(buffer, sizeof(buffer), "\033[27;%u;%u~", effective+1, value);
    } else if (alias >= 0) {
        length = 0;
        if (mods & (NEMO_KEY_ALT | NEMO_KEY_SUPER)) buffer[length++] = 27;
        buffer[length++] = alias;
    } else return -1;
    if (length < 0 || (size_t)length >= sizeof(buffer) || (size_t)length > capacity) {
        output[0] = 0; return 0;
    }
    memcpy(output, buffer, length);
    return length;
}
