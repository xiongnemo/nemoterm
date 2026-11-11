/* SPDX-License-Identifier: MIT
 * Independent implementation of https://sw.kovidgoyal.net/kitty/keyboard-protocol/
 */
#include "nemo_keyboard.h"
#include <string.h>

unsigned nemo_keyboard_flags(const NemoKeyboard *state)
{
    return state->count ? state->stack[state->count-1] : 0;
}

void nemo_keyboard_set(NemoKeyboard *state, unsigned flags, unsigned mode)
{
    if (mode < 1 || mode > 3) return;
    if (!state->count) state->count = 1;
    uint8_t *value = &state->stack[state->count-1];
    flags &= NEMO_KEY_FLAGS;
    if (mode == 1) *value = flags;
    else if (mode == 2) *value |= flags;
    else *value &= ~flags;
}

void nemo_keyboard_push(NemoKeyboard *state, unsigned flags)
{
    if (!state->count) state->stack[state->count++] = 0;
    if (state->count == NEMO_KEY_STACK_MAX) {
        memmove(state->stack, state->stack+1, NEMO_KEY_STACK_MAX-1);
        state->count--;
    }
    state->stack[state->count++] = flags & NEMO_KEY_FLAGS;
}

void nemo_keyboard_pop(NemoKeyboard *state, unsigned count)
{
    unsigned remain = count >= state->count ? 0 : state->count-count;
    memset(state->stack+remain, 0, state->count-remain);
    state->count = remain;
}

typedef struct KeyBuffer {
    char *data;
    size_t size, used;
    bool overflow;
} KeyBuffer;

static void byte(KeyBuffer *b, unsigned char value)
{
    if (b->used < b->size) b->data[b->used++] = value;
    else b->overflow = true;
}

static void number(KeyBuffer *b, uint32_t value)
{
    char digits[10];
    unsigned count = 0;
    do { digits[count++] = '0' + value%10; value /= 10; } while (value);
    while (count) byte(b, digits[--count]);
}

static bool scalar(uint32_t value)
{
    return value <= 0x10ffff && !(value >= 0xd800 && value <= 0xdfff);
}

static bool printable(uint32_t value)
{
    return scalar(value) && value >= 32 && !(value >= 127 && value <= 159);
}

static void utf8(KeyBuffer *b, uint32_t value)
{
    if (value < 128) byte(b, value);
    else {
        unsigned rest = value < 0x800 ? 1 : value < 0x10000 ? 2 : 3;
        byte(b, (rest == 1 ? 0xc0 : rest == 2 ? 0xe0 : 0xf0) | (value >> (6*rest)));
        while (rest) byte(b, 0x80 | ((value >> (6*--rest)) & 63));
    }
}

static unsigned legacy_control(unsigned key)
{
    if (key >= 'a' && key <= 'z') return key-'a'+1;
    if (key >= '[' && key <= '_') return key-'['+27;
    if (key >= '3' && key <= '7') return key-'3'+27;
    if (key == ' ' || key == '@' || key == '2') return 0;
    if (key == '/' || key == '?') return key == '/' ? 31 : 127;
    if (key == '8') return 127;
    return key;
}

static char functional(uint32_t key, uint32_t *wire)
{
    static const struct { uint32_t key, value; char final; } table[] = {
        {NK_INSERT,2,'~'}, {NK_DELETE,3,'~'}, {NK_LEFT,1,'D'}, {NK_RIGHT,1,'C'},
        {NK_UP,1,'A'}, {NK_DOWN,1,'B'}, {NK_PAGE_UP,5,'~'}, {NK_PAGE_DOWN,6,'~'},
        {NK_HOME,1,'H'}, {NK_END,1,'F'}, {NK_KP_BEGIN,1,'E'},
        {NK_F1,1,'P'}, {NK_F1+1,1,'Q'}, {NK_F1+2,13,'~'}, {NK_F1+3,1,'S'},
    };
    for (unsigned i = 0; i < sizeof(table)/sizeof(*table); i++)
        if (key == table[i].key) { *wire = table[i].value; return table[i].final; }
    if (key >= NK_F1+4 && key <= NK_F1+11) {
        static const unsigned codes[] = {15,17,18,19,20,21,23,24};
        *wire = codes[key-NK_F1-4]; return '~';
    }
    *wire = key;
    return 'u';
}

int nemo_keyboard_encode(unsigned flags, const NemoKeyEvent *e, char *out, size_t capacity)
{
    flags &= NEMO_KEY_FLAGS;
    if (!(flags & (NEMO_KEY_DISAMBIGUATE | NEMO_KEY_EVENTS | NEMO_KEY_ALL))) return -1;
    if (!e || !out || !capacity || !scalar(e->key) || !scalar(e->shifted) ||
        !scalar(e->base) || e->type < 1 || e->type > 3 ||
        e->text_len > NEMO_KEY_TEXT_MAX || (e->text_len && !e->text)) return 0;
    bool all = (flags & NEMO_KEY_ALL) != 0;
    bool events = (flags & NEMO_KEY_EVENTS) != 0;
    bool release = e->type == 3;
    unsigned mods = e->modifiers & 255;
    unsigned nonlocks = mods & 63;
    bool is_functional = (e->key && e->key < 32) || e->key == 127 ||
        (e->key >= NK_INSERT && e->key <= NK_LEVEL5_SHIFT);
    bool text_keypad = (e->key >= NK_KP_0 && e->key <= NK_KP_ADD) ||
        e->key == NK_KP_EQUAL || e->key == NK_KP_SEPARATOR;
    if (release && !events) return 0;
    if (e->key >= NK_LEFT_SHIFT && e->key <= NK_LEVEL5_SHIFT && !all) return 0;
    for (size_t i = 0; i < e->text_len; i++) if (!printable(e->text[i])) return 0;
    KeyBuffer b = {out, capacity, 0, false};
    /* Text remains text until report-all is requested. Lock modifiers must
     * not turn ordinary typing into escape sequences. */
    if (!all && (!is_functional || text_keypad) && e->text_len &&
        !(nonlocks & ~NEMO_KEY_SHIFT)) {
        if (!release) for (size_t i = 0; i < e->text_len; i++) utf8(&b, e->text[i]);
    } else if (!all && !nonlocks && (e->key == 13 || e->key == 9 || e->key == 127)) {
        if (!release) byte(&b, e->key);
    } else {
        uint32_t shifted = (flags & NEMO_KEY_ALTERNATES) && (mods & NEMO_KEY_SHIFT) ? e->shifted : 0;
        uint32_t base = (flags & NEMO_KEY_ALTERNATES) ? e->base : 0;
        if (shifted == e->key) shifted = 0;
        if (base == e->key) base = 0;
        if (is_functional) shifted = base = 0;
        bool extra_event = events && e->type != 1;
        bool classic = !(flags & (NEMO_KEY_DISAMBIGUATE | NEMO_KEY_ALL)) &&
            !extra_event && !shifted && !base;
        if (classic && e->key >= 32 && e->key < 127 && !(mods & ~7)) {
            uint32_t key = (mods & NEMO_KEY_SHIFT) && e->shifted ? e->shifted : e->key;
            if (mods & NEMO_KEY_ALT) byte(&b, 27);
            if (mods & NEMO_KEY_CTRL) {
                if (key >= 'A' && key <= 'Z') key += 'a'-'A';
                key = legacy_control(key);
            }
            utf8(&b, key);
        } else {
            uint32_t wire;
            char final = functional(e->key, &wire);
            bool associated = all && (flags & NEMO_KEY_TEXT) && !release && e->text_len;
            if (!e->key && !associated) return 0;
            /* ESC remains a legacy press until disambiguation is requested. */
            if (classic && !mods && e->key == 27) byte(&b, 27);
            else {
                bool fields = mods || extra_event || associated;
                byte(&b, 27); byte(&b, '[');
                if (wire != 1 || final == 'u' || fields || shifted || base) number(&b, wire);
                if (shifted || base) {
                    byte(&b, ':');
                    if (shifted) number(&b, shifted);
                    if (base) { byte(&b, ':'); number(&b, base); }
                }
                if (fields) {
                    byte(&b, ';'); number(&b, mods+1);
                    if (extra_event) { byte(&b, ':'); number(&b, e->type); }
                }
                if (associated) {
                    for (size_t i = 0; i < e->text_len; i++) {
                        byte(&b, i ? ':' : ';'); number(&b, e->text[i]);
                    }
                }
                byte(&b, final);
            }
        }
    }
    if (b.overflow) { out[0] = 0; return 0; }
    return (int)b.used;
}
