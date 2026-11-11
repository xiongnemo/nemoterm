/* SPDX-License-Identifier: MIT */
#ifndef NEMO_KEYBOARD_H
#define NEMO_KEYBOARD_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

enum {
    NEMO_KEY_DISAMBIGUATE = 1, NEMO_KEY_EVENTS = 2,
    NEMO_KEY_ALTERNATES = 4, NEMO_KEY_ALL = 8, NEMO_KEY_TEXT = 16,
    NEMO_KEY_FLAGS = 31, NEMO_KEY_STACK_MAX = 32,
    NEMO_KEY_TEXT_MAX = 16, NEMO_KEY_ENCODED_MAX = 256,
    NEMO_KEY_SHIFT = 1, NEMO_KEY_ALT = 2, NEMO_KEY_CTRL = 4,
    NEMO_KEY_SUPER = 8, NEMO_KEY_CAPS = 64, NEMO_KEY_NUM = 128,
};

/* Internal logical key identities use the protocol's PUA order. The wire
 * representation of navigation and F1..F12 keys is selected by the encoder. */
enum {
    NK_INSERT = 57348, NK_DELETE, NK_LEFT, NK_RIGHT, NK_UP, NK_DOWN,
    NK_PAGE_UP, NK_PAGE_DOWN, NK_HOME, NK_END, NK_CAPS_LOCK, NK_SCROLL_LOCK,
    NK_NUM_LOCK, NK_PRINT_SCREEN, NK_PAUSE, NK_MENU, NK_F1,
    NK_F35 = NK_F1 + 34, NK_KP_0, NK_KP_9 = NK_KP_0 + 9,
    NK_KP_DECIMAL, NK_KP_DIVIDE, NK_KP_MULTIPLY, NK_KP_SUBTRACT, NK_KP_ADD,
    NK_KP_ENTER, NK_KP_EQUAL, NK_KP_SEPARATOR, NK_KP_LEFT, NK_KP_RIGHT,
    NK_KP_UP, NK_KP_DOWN, NK_KP_PAGE_UP, NK_KP_PAGE_DOWN, NK_KP_HOME,
    NK_KP_END, NK_KP_INSERT, NK_KP_DELETE, NK_KP_BEGIN,
    NK_MEDIA_PLAY, NK_MEDIA_PAUSE, NK_MEDIA_PLAY_PAUSE, NK_MEDIA_REVERSE,
    NK_MEDIA_STOP, NK_MEDIA_FORWARD, NK_MEDIA_REWIND, NK_MEDIA_NEXT,
    NK_MEDIA_PREVIOUS, NK_MEDIA_RECORD, NK_VOLUME_DOWN, NK_VOLUME_UP,
    NK_VOLUME_MUTE, NK_LEFT_SHIFT, NK_LEFT_CONTROL, NK_LEFT_ALT,
    NK_LEFT_SUPER, NK_LEFT_HYPER, NK_LEFT_META, NK_RIGHT_SHIFT,
    NK_RIGHT_CONTROL, NK_RIGHT_ALT, NK_RIGHT_SUPER, NK_RIGHT_HYPER,
    NK_RIGHT_META, NK_LEVEL3_SHIFT, NK_LEVEL5_SHIFT,
};

typedef struct NemoKeyboard {
    uint8_t count, stack[NEMO_KEY_STACK_MAX];
} NemoKeyboard;

typedef struct NemoKeyEvent {
    uint32_t key, shifted, base;
    unsigned modifiers, type; /* 1 press, 2 repeat, 3 release */
    const uint32_t *text;
    size_t text_len;
} NemoKeyEvent;

unsigned nemo_keyboard_flags(const NemoKeyboard *);
void nemo_keyboard_set(NemoKeyboard *, unsigned flags, unsigned mode);
void nemo_keyboard_push(NemoKeyboard *, unsigned flags);
void nemo_keyboard_pop(NemoKeyboard *, unsigned count);
/* -1 retains the existing legacy translator; 0 consumes without output.
 * Positive lengths are complete UTF-8/VT input, never a truncated sequence. */
int nemo_keyboard_encode(unsigned flags, const NemoKeyEvent *, char *, size_t);

#endif
