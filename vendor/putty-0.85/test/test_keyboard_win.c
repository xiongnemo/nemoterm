/* SPDX-License-Identifier: MIT
 * Included by test_keyboard.c on Windows. No physical input is generated and
 * no keyboard layout is activated: ToUnicodeEx receives a process-local HKL. */
#include "win-gui-seat.h"
#include "nemo_key_input.h"

static void native_key(Mock *mk, WinGuiSeat *wgs, HKL layout, unsigned vk,
                       unsigned scan, unsigned type, BYTE state[256],
                       const char *expected)
{
    LPARAM lp = 1 | ((scan & 255) << 16) | ((scan & 256) << 16);
    if (type != 1) lp |= 0x40000000u;
    if (type == 3) lp |= 0x80000000u;
    UINT message = type == 3 ? WM_KEYUP : WM_KEYDOWN;
    strbuf_clear(mk->to_backend);
    test_context(mk, "Windows key %u scan %u type %u", vk, scan, type);
    nemo_keyboard_prepare(wgs, message, vk, lp, state);
    IEQUAL(nemo_keyboard_input(wgs, message, vk, lp, state, layout), true);
    SEQUAL(mk->to_backend->s, expected);
}

static void test_windows_keyboard(Mock *mk)
{
    reset(mk);
    WinGuiSeat wgs = {.term=mk->term};
    BYTE state[256] = {0};
    HKL original = GetKeyboardLayout(0);
    HKL us = LoadKeyboardLayoutW(L"00000409", KLF_NOTELLSHELL);
    IEQUAL(us != NULL, true);
    if (!us) return;
    nemo_keyboard_set(&mk->term->keyboard[0], 31, 1);
    native_key(mk, &wgs, us, 'A', 0x1e, 1, state, "\033[97;1;97u");
    native_key(mk, &wgs, us, 'A', 0x1e, 2, state, "\033[97;1:2;97u");
    native_key(mk, &wgs, us, 'A', 0x1e, 3, state, "\033[97;1:3u");
    native_key(mk, &wgs, us, VK_SHIFT, 0x2a, 1, state, "\033[57441;2u");
    native_key(mk, &wgs, us, 'A', 0x1e, 1, state, "\033[97:65;2;65u");
    native_key(mk, &wgs, us, 'A', 0x1e, 3, state, "\033[97:65;2:3u");
    native_key(mk, &wgs, us, VK_SHIFT, 0x2a, 3, state, "\033[57441;1:3u");
    native_key(mk, &wgs, us, VK_CONTROL, 0x11d, 1, state, "\033[57448;5u");
    native_key(mk, &wgs, us, 'I', 0x17, 1, state, "\033[105;5u");
    native_key(mk, &wgs, us, 'I', 0x17, 3, state, "\033[105;5:3u");
    native_key(mk, &wgs, us, VK_CONTROL, 0x11d, 3, state, "\033[57448;1:3u");
    native_key(mk, &wgs, us, VK_UP, 0x148, 1, state, "\033[A");
    native_key(mk, &wgs, us, VK_UP, 0x148, 3, state, "\033[1;1:3A");
    native_key(mk, &wgs, us, VK_UP, 0x48, 1, state, "\033[57419u");
    native_key(mk, &wgs, us, VK_UP, 0x48, 3, state, "\033[57419;1:3u");
    native_key(mk, &wgs, us, VK_RETURN, 0x11c, 1, state, "\033[57414u");
    native_key(mk, &wgs, us, VK_RETURN, 0x11c, 3, state, "\033[57414;1:3u");
    state[VK_CAPITAL] = 1;
    native_key(mk, &wgs, us, 'A', 0x1e, 1, state, "\033[97;65;65u");
    native_key(mk, &wgs, us, 'A', 0x1e, 3, state, "\033[97;65:3u");
    state[VK_CAPITAL] = 0;
    nemo_keyboard_set(&mk->term->keyboard[0], 2, 1);
    native_key(mk, &wgs, us, VK_CONTROL, 0x1d, 1, state, "");
    native_key(mk, &wgs, us, 'A', 0x1e, 1, state, "\001");
    native_key(mk, &wgs, us, 'A', 0x1e, 3, state, "\033[97;5:3u");
    native_key(mk, &wgs, us, VK_CONTROL, 0x1d, 3, state, "");
    native_key(mk, &wgs, us, 'A', 0x1e, 1, state, "a");
    native_key(mk, &wgs, us, 'A', 0x1e, 3, state, "");

    state[VK_NUMLOCK] = 1;
    native_key(mk, &wgs, us, VK_NUMPAD1, 0x4f, 1, state, "1");
    native_key(mk, &wgs, us, VK_NUMPAD1, 0x4f, 3, state, "");
    native_key(mk, &wgs, us, VK_ADD, 0x4e, 1, state, "+");
    native_key(mk, &wgs, us, VK_ADD, 0x4e, 3, state, "");
    state[VK_NUMLOCK] = 0;

    nemo_keyboard_set(&mk->term->keyboard[0], 31, 1);
    wchar_t ime[] = {0x4e2d, 0xd83d, 0xde00, 0xd800, 'x', 0xdc00, 9, 0x9b};
    strbuf_clear(mk->to_backend);
    IEQUAL(nemo_keyboard_text(&wgs, ime, lenof(ime)), true);
    SEQUAL(mk->to_backend->s, "\033[0;1;20013:128512:120u");
    wchar_t long_text[34];
    for (size_t i = 0; i < lenof(long_text); i++) long_text[i] = 'a';
    long_text[15] = 0xd83d; long_text[16] = 0xde00;
    strbuf_clear(mk->to_backend);
    nemo_keyboard_text(&wgs, long_text, lenof(long_text));
    IEQUAL(strstr(mk->to_backend->s, "\033[0;1;128512:") != NULL, true);
    IEQUAL(strstr(mk->to_backend->s, "55357") == NULL, true);
    native_key(mk, &wgs, us, 'B', 0x30, 1, state, "\033[98;1;98u");
    strbuf_clear(mk->to_backend);
    nemo_keyboard_focus_lost(&wgs);
    SEQUAL(mk->to_backend->s, "\033[98;1:3u");
    native_key(mk, &wgs, us, 'B', 0x30, 3, state, "");
    /* A local shortcut calls prepare but skips input; its release is silent. */
    nemo_keyboard_prepare(&wgs, WM_KEYDOWN, 'C', 1 | (0x2e << 16), state);
    native_key(mk, &wgs, us, 'C', 0x2e, 3, state, "");

    HKL international = LoadKeyboardLayoutW(L"00020409", KLF_NOTELLSHELL);
    IEQUAL(international != NULL, true);
    if (international) {
        nemo_keyboard_set(&mk->term->keyboard[0], 1, 1);
        native_key(mk, &wgs, international, VK_OEM_7, 0x28, 1, state, "");
        native_key(mk, &wgs, international, VK_OEM_7, 0x28, 3, state, "");
        native_key(mk, &wgs, international, 'E', 0x12, 1, state, "\xc3\xa9");
        native_key(mk, &wgs, international, 'E', 0x12, 3, state, "");
        nemo_keyboard_set(&mk->term->keyboard[0], 31, 1);
        native_key(mk, &wgs, international, VK_OEM_7, 0x28, 1, state, "\033[39u");
        native_key(mk, &wgs, international, VK_OEM_7, 0x28, 3, state, "\033[39;1:3u");
        native_key(mk, &wgs, international, 'E', 0x12, 1, state, "\033[101;1;233u");
        native_key(mk, &wgs, international, 'E', 0x12, 3, state, "\033[101;1:3u");
        if (international != original) UnloadKeyboardLayout(international);
    }
    HKL german = LoadKeyboardLayoutW(L"00000407", KLF_NOTELLSHELL);
    IEQUAL(german != NULL, true);
    if (german) {
        native_key(mk, &wgs, german, VK_CONTROL, 0x1d, 1, state, "\033[57442;5u");
        native_key(mk, &wgs, german, VK_MENU, 0x138, 1, state, "\033[57449;7u");
        native_key(mk, &wgs, german, 'Q', 0x10, 1, state, "\033[113;1;64u");
        native_key(mk, &wgs, german, 'Q', 0x10, 3, state, "\033[113;7:3u");
        native_key(mk, &wgs, german, VK_MENU, 0x138, 3, state, "\033[57449;5:3u");
        native_key(mk, &wgs, german, VK_CONTROL, 0x1d, 3, state, "\033[57442;1:3u");
        if (german != original) UnloadKeyboardLayout(german);
    }
    HKL russian = LoadKeyboardLayoutW(L"00000419", KLF_NOTELLSHELL);
    IEQUAL(russian != NULL, true);
    if (russian) {
        native_key(mk, &wgs, russian, 'A', 0x1e, 1, state, "\033[1092::97;1;1092u");
        /* Release retains the physical press identity after a layout change. */
        native_key(mk, &wgs, us, 'Q', 0x1e, 3, state, "\033[1092::97;1:3u");
        if (russian != original) UnloadKeyboardLayout(russian);
    }
    IEQUAL(GetKeyboardLayout(0) == original, true);
    if (us != original) UnloadKeyboardLayout(us);
    nemo_keyboard_free(&wgs);
}
