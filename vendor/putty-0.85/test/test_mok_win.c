/* SPDX-License-Identifier: MIT */
#include "win-gui-seat.h"
#include "nemo_key_input.h"

static void mok_native_key(Mock *mk, WinGuiSeat *wgs, HKL layout,
                           unsigned vk, unsigned scan, unsigned mods,
                           const char *expected, int length)
{
    BYTE state[256] = {0};
    if (mods & 1) state[VK_SHIFT] = state[VK_LSHIFT] = 0x80;
    if (mods & 4) state[VK_CONTROL] = state[VK_LCONTROL] = 0x80;
    if (mods & 2) state[VK_MENU] = state[VK_LMENU] = 0x80;
    if (mods & 64) state[VK_CAPITAL] = 1;
    if (mods & 128) state[VK_NUMLOCK] = 1;
    if (mods & 256) { state[VK_RMENU] = state[VK_MENU] = 0x80; state[VK_LMENU] = 0; }
    LPARAM lp = 1 | ((scan & 511) << 16);
    strbuf_clear(mk->to_backend);
    test_context(mk, "Windows MOK level %d key %u mods %u", mk->term->modify_keys.level, vk, mods);
    nemo_keyboard_prepare(wgs, WM_KEYDOWN, vk, lp, state);
    bool handled = nemo_keyboard_input(wgs, WM_KEYDOWN, vk, lp, state, layout);
    IEQUAL(handled, length >= 0);
    IEQUAL(mk->to_backend->len, length < 0 ? 0 : length);
    if (length > 0) IEQUAL(memcmp(mk->to_backend->s, expected, length), 0);
    if (!handled) {
        /* Perform the legacy translator's one stateful lookup, including a
         * dead-key press. No layout is activated and no OS input is injected. */
        wchar_t wide[16]; ToUnicodeEx(vk, scan & 255, state, wide, lenof(wide), 0, layout);
    }
    strbuf_clear(mk->to_backend);
    nemo_keyboard_prepare(wgs, WM_KEYUP, vk, lp | 0xc0000000u, state);
    nemo_keyboard_input(wgs, WM_KEYUP, vk, lp | 0xc0000000u, state, layout);
    IEQUAL(mk->to_backend->len, 0);
}

static void test_windows_mok(Mock *mk)
{
    reset(mk);
    WinGuiSeat wgs = {.term=mk->term, .conf=mk->conf};
    HKL original = GetKeyboardLayout(0), us = LoadKeyboardLayoutW(L"00000409", KLF_NOTELLSHELL);
    IEQUAL(us != NULL, true);
    if (!us) return;
#define KEY(vk,scan,mods,expected) mok_native_key(mk,&wgs,us,vk,scan,mods,expected,sizeof(expected)-1)
#define LEGACY(vk,scan,mods) mok_native_key(mk,&wgs,us,vk,scan,mods,"",-1)
    mok_reply(mk, "\033[>4;1m", "");
    KEY('A',0x1e,4,"\001"); KEY('A',0x1e,5,"\001");
    KEY('2',3,4,"\0"); KEY(VK_OEM_3,0x29,4,"\0");
    KEY(VK_OEM_PERIOD,0x34,4,"\033[27;5;46~");
    KEY(VK_OEM_PERIOD,0x34,6,"\033[27;5;46~");
    LEGACY('A',0x1e,1); LEGACY('A',0x1e,2);
    mok_reply(mk, "\033[>4;2m", "");
    KEY('A',0x1e,1,"\033[27;2;65~"); KEY('A',0x1e,4,"\033[27;5;97~");
    KEY('A',0x1e,5,"\033[27;6;65~"); KEY('A',0x1e,68,"\033[27;5;65~");
    KEY('A',0x1e,69,"\033[27;6;97~");
    KEY('1',2,5,"\033[27;6;33~"); LEGACY('1',2,1);
    KEY(VK_TAB,0x0f,1,"\033[27;2;9~");
    KEY(VK_RETURN,0x1c,4,"\033[27;5;13~");
    KEY(VK_BACK,0x0e,1,"\033[27;2;127~"); LEGACY(VK_BACK,0x0e,4);
    KEY(VK_ESCAPE,1,4,"\033[27;5;27~"); LEGACY(VK_UP,0x148,1);
    mok_reply(mk, "\033[>4;2:1m\033[>4;1f", "");
    LEGACY('A',0x1e,1); KEY('A',0x1e,5,"\033[97;6u");
    mok_reply(mk, "\033[>4;3m", "");
    KEY('A',0x1e,0,"\033[97;1u"); KEY(VK_BACK,0x0e,4,"\033[8;5u");
    LEGACY(VK_F1,0x3b,0); LEGACY(VK_NUMPAD1,0x4f,128);
    wchar_t text[] = {0x4e2d,0xd83d,0xde00,0x301};
    strbuf_clear(mk->to_backend);
    IEQUAL(nemo_keyboard_text(&wgs, text, lenof(text)), true);
    SEQUAL(mk->to_backend->s,"\033[20013;1u\033[128512;1u\033[769;1u");
    mok_reply(mk, "\033[>31u", "");
    /* The existing kitty suite checks releases; here verify encoding priority. */
    BYTE state[256] = {0}; LPARAM lp = 1 | (0x1e<<16);
    nemo_keyboard_prepare(&wgs, WM_KEYDOWN, 'A', lp, state);
    strbuf_clear(mk->to_backend);
    nemo_keyboard_input(&wgs, WM_KEYDOWN, 'A', lp, state, us);
    SEQUAL(mk->to_backend->s,"\033[97;1;97u");
    nemo_keyboard_focus_lost(&wgs);
    mok_reply(mk, "\033[<u", "");
    KEY('A',0x1e,0,"\033[97;1u");
    HKL intl=LoadKeyboardLayoutW(L"00020409",KLF_NOTELLSHELL);
    if (intl) {
        mok_native_key(mk,&wgs,intl,VK_OEM_7,0x28,0,"",-1);
        mok_native_key(mk,&wgs,intl,'E',0x12,0,"\033[233;1u",8);
        mok_native_key(mk,&wgs,intl,'E',0x12,0,"\033[101;1u",8);
        if (intl!=original) UnloadKeyboardLayout(intl);
    } else IEQUAL(intl!=NULL,true);
    HKL german=LoadKeyboardLayoutW(L"00000407",KLF_NOTELLSHELL);
    if (german) {
        mok_native_key(mk,&wgs,german,'Q',0x10,4|256,"\033[64;1u",7);
        mok_reply(mk,"\033[>4;2m","");
        mok_native_key(mk,&wgs,german,'Q',0x10,4|256,"",-1);
        if (german!=original) UnloadKeyboardLayout(german);
    } else IEQUAL(german!=NULL,true);
    HKL russian=LoadKeyboardLayoutW(L"00000419",KLF_NOTELLSHELL);
    if (russian) {
        mok_native_key(mk,&wgs,russian,'A',0x1e,4,"\033[1092;5u",9);
        if (russian!=original) UnloadKeyboardLayout(russian);
    } else IEQUAL(russian!=NULL,true);
    IEQUAL(GetKeyboardLayout(0)==original,true);
    if (us!=original) UnloadKeyboardLayout(us);
    nemo_keyboard_free(&wgs);
#undef KEY
#undef LEGACY
}
