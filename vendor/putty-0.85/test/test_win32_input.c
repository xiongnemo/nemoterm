/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main

static void win32_reply(Mock *mk, const char *input, const char *expected)
{
    strbuf_clear(mk->to_backend);
    term_data_fragmented(mk->term, input);
    SEQUAL(mk->to_backend->s, expected);
}

static void test_win32_mode(Mock *mk)
{
    reset(mk);
    test_context(mk, "9001 global negotiation, queries, reset and held-key epochs");
    win32_reply(mk, "\033[?9001$p", "\033[?9001;4$y");
    conf_set_bool(mk->conf, CONF_nemo_win32_input, true);
    term_reconfig(mk->term, mk->conf);
    win32_reply(mk, "\033[?9001$p", "\033[?9001;2$y");
    unsigned epoch = mk->term->win32_input_epoch;
    win32_reply(mk, "\033[?9001h\033[?9001$p", "\033[?9001;1$y");
    IEQUAL(mk->term->win32_input_epoch, epoch+1);
    win32_reply(mk, "\033[?9001h\033[?1049h\033[?9001$p", "\033[?9001;1$y");
    IEQUAL(mk->term->win32_input_epoch, epoch+1);
    term_size(mk->term, 12, 40, 20);
    win32_reply(mk, "\033[?1049l\0337\033[?9001l\0338\033[?9001$p", "\033[?9001;2$y");
    IEQUAL(mk->term->win32_input_epoch, epoch+2);
    win32_reply(mk, "\033[?9001h\033c\033[?9001$p", "\033[?9001;2$y");
    const char *invalid[] = {"\033[9001h", "\033[>9001h", "\033[?9001\030h", "\033[?9001\032h"};
    for (size_t i = 0; i < lenof(invalid); i++) {
        win32_reply(mk, invalid[i], "");
        win32_reply(mk, "\033[?9001$p", "\033[?9001;2$y");
    }
    win32_reply(mk, "\033[?9001;1004h\033[?9001$p\033[?1004$p", "\033[?9001;1$y\033[?1004;1$y");
    term_reconfig(mk->term, mk->conf);
    win32_reply(mk, "\033[?9001$p", "\033[?9001;1$y");
    epoch = mk->term->win32_input_epoch;
    conf_set_bool(mk->conf, CONF_nemo_win32_input, false);
    term_reconfig(mk->term, mk->conf);
    win32_reply(mk, "\033[?9001$p", "\033[?9001;4$y");
    IEQUAL(mk->term->win32_input_epoch, epoch+1);
    conf_set_bool(mk->conf, CONF_nemo_win32_input, true);
    term_reconfig(mk->term, mk->conf);
    win32_reply(mk, "\033[?9001$p", "\033[?9001;1$y");
}

static void test_win32_encoder(Mock *mk)
{
    test_context(mk, "Win32 records preserve UTF16 units, repeat and control flags");
    NemoWin32Key key = {.vk=112, .scan=59, .down=true, .control=8, .repeat=1};
    char out[128];
    int n = nemo_win32_encode(&key, out, sizeof(out));
    out[n] = 0;
    SEQUAL(out, "\033[112;59;0;1;8;1_");
    key = (NemoWin32Key){.vk=65535, .scan=65535, .character=65535,
        .repeat=65535, .control=UINT32_MAX, .down=true};
    n = nemo_win32_encode(&key, out, sizeof(out));
    out[n] = 0;
    SEQUAL(out, "\033[65535;65535;65535;1;4294967295;65535_");
    IEQUAL(n < NEMO_WIN32_ENCODED_MAX, true);
    for (int size = 0; size < n; size++) {
        memset(out, 'X', sizeof(out));
        IEQUAL(nemo_win32_encode(&key, out, size), -1);
        for (size_t i = 0; i < sizeof(out); i++) IEQUAL(out[i], 'X');
    }
    memset(out, 'X', sizeof(out));
    IEQUAL(nemo_win32_encode(&key, out, n), n);
    IEQUAL(out[n], 'X');
    key = (NemoWin32Key){.character=0xd83d, .down=true, .repeat=1};
    n = nemo_win32_encode(&key, out, sizeof(out)); out[n] = 0;
    SEQUAL(out, "\033[0;0;55357;1;0;1_");
    key.character = 0xde00; key.down = false; key.repeat = 0;
    n = nemo_win32_encode(&key, out, sizeof(out)); out[n] = 0;
    SEQUAL(out, "\033[0;0;56832;0;0;0_");
}

#ifdef _WIN32
#include "win-gui-seat.h"
#include "nemo_key_input.h"

static void raw_key(Mock *mk, WinGuiSeat *wgs, HKL layout, unsigned vk,
                    unsigned scan, bool down, unsigned repeat, BYTE state[256],
                    const char *expected)
{
    LPARAM lp = repeat | ((scan & 255) << 16) | ((scan & 256) << 16);
    if (!down) lp |= 0xc0000000u;
    UINT message = down ? WM_KEYDOWN : WM_KEYUP;
    strbuf_clear(mk->to_backend);
    test_context(mk, "Win32 key %u scan %u down %d repeat %u", vk, scan, down, repeat);
    nemo_keyboard_prepare(wgs, message, vk, lp, state);
    IEQUAL(nemo_keyboard_input(wgs, message, vk, lp, state, layout), true);
    SEQUAL(mk->to_backend->s, expected);
}

static void test_win32_windows(Mock *mk)
{
    reset(mk);
    WinGuiSeat wgs = {.term=mk->term};
    BYTE state[256] = {0};
    HKL original = GetKeyboardLayout(0);
    HKL us = LoadKeyboardLayoutW(L"00000409", KLF_NOTELLSHELL);
    IEQUAL(us != NULL, true);
    if (!us) return;
    term_data_fragmented(mk->term, "\033[?9001h");
    IEQUAL(nemo_win32_input_active(&wgs), true);
    raw_key(mk,&wgs,us,'A',30,true,3,state,"\033[65;30;97;1;0;3_");
    raw_key(mk,&wgs,us,'A',30,false,1,state,"\033[65;30;97;0;0;1_");
    raw_key(mk,&wgs,us,VK_SHIFT,42,true,1,state,"\033[16;42;0;1;16;1_");
    raw_key(mk,&wgs,us,VK_RETURN,28,true,1,state,"\033[13;28;13;1;16;1_");
    raw_key(mk,&wgs,us,VK_RETURN,28,false,1,state,"\033[13;28;13;0;16;1_");
    raw_key(mk,&wgs,us,VK_SHIFT,42,false,1,state,"\033[16;42;0;0;0;1_");
    raw_key(mk,&wgs,us,VK_CONTROL,29,true,1,state,"\033[17;29;0;1;8;1_");
    raw_key(mk,&wgs,us,VK_SPACE,57,true,1,state,"\033[32;57;32;1;8;1_");
    raw_key(mk,&wgs,us,VK_SPACE,57,false,1,state,"\033[32;57;32;0;8;1_");
    raw_key(mk,&wgs,us,'C',46,true,1,state,"\033[67;46;3;1;8;1_");
    raw_key(mk,&wgs,us,'C',46,false,1,state,"\033[67;46;3;0;8;1_");
    raw_key(mk,&wgs,us,VK_CONTROL,29,false,1,state,"\033[17;29;0;0;0;1_");
    raw_key(mk,&wgs,us,VK_CONTROL,285,true,1,state,"\033[17;29;0;1;260;1_");
    raw_key(mk,&wgs,us,VK_CONTROL,285,false,1,state,"\033[17;29;0;0;256;1_");
    raw_key(mk,&wgs,us,VK_RETURN,284,true,1,state,"\033[13;28;13;1;256;1_");
    raw_key(mk,&wgs,us,VK_RETURN,284,false,1,state,"\033[13;28;13;0;256;1_");
    state[VK_CAPITAL] = state[VK_NUMLOCK] = state[VK_SCROLL] = 1;
    raw_key(mk,&wgs,us,'A',30,true,1,state,"\033[65;30;65;1;224;1_");
    raw_key(mk,&wgs,us,'A',30,false,1,state,"\033[65;30;65;0;224;1_");
    state[VK_CAPITAL] = state[VK_NUMLOCK] = state[VK_SCROLL] = 0;
    wchar_t text[] = {0x4e2d, 0xd83d, 0xde00, 9};
    strbuf_clear(mk->to_backend);
    IEQUAL(nemo_keyboard_text(&wgs, text, lenof(text)), true);
    SEQUAL(mk->to_backend->s,"\033[0;0;20013;1;0;1_\033[0;0;55357;1;0;1_\033[0;0;56832;1;0;1_\033[0;0;9;1;0;1_");
    raw_key(mk,&wgs,us,'B',48,true,1,state,"\033[66;48;98;1;0;1_");
    strbuf_clear(mk->to_backend); nemo_keyboard_focus_lost(&wgs);
    SEQUAL(mk->to_backend->s,"\033[66;48;98;0;0;1_");
    raw_key(mk,&wgs,us,'B',48,false,1,state,"");
    nemo_keyboard_prepare(&wgs,WM_KEYDOWN,'C',1|(46<<16),state);
    raw_key(mk,&wgs,us,'C',46,false,1,state,""); /* locally consumed shortcut */
    raw_key(mk,&wgs,us,'B',48,true,1,state,"\033[66;48;98;1;0;1_");
    term_data_fragmented(mk->term,"\033[?9001l\033[?9001h");
    raw_key(mk,&wgs,us,'B',48,false,1,state,"");
    term_data_fragmented(mk->term,"\033[=1u");
    IEQUAL(nemo_win32_input_active(&wgs),false);
    raw_key(mk,&wgs,us,'A',30,true,1,state,"a");
    raw_key(mk,&wgs,us,'A',30,false,1,state,"");
    term_data_fragmented(mk->term,"\033[=0u\033[>4;3m");
    IEQUAL(nemo_win32_input_active(&wgs),false);
    raw_key(mk,&wgs,us,'A',30,true,1,state,"\033[27;1;97~");
    term_data_fragmented(mk->term,"\033[>4;0m");
    raw_key(mk,&wgs,us,'A',30,false,1,state,"");

    HKL international = LoadKeyboardLayoutW(L"00020409", KLF_NOTELLSHELL);
    IEQUAL(international != NULL,true);
    if (international) {
        raw_key(mk,&wgs,international,VK_OEM_7,40,true,1,state,"\033[222;40;0;1;0;1_");
        raw_key(mk,&wgs,international,VK_OEM_7,40,false,1,state,"\033[222;40;0;0;0;1_");
        raw_key(mk,&wgs,international,'E',18,true,1,state,"\033[69;18;233;1;0;1_");
        raw_key(mk,&wgs,international,'E',18,false,1,state,"\033[69;18;101;0;0;1_");
        if (international != original) UnloadKeyboardLayout(international);
    }
    HKL german = LoadKeyboardLayoutW(L"00000407", KLF_NOTELLSHELL);
    IEQUAL(german != NULL,true);
    if (german) {
        raw_key(mk,&wgs,german,VK_CONTROL,29,true,1,state,"\033[17;29;0;1;8;1_");
        raw_key(mk,&wgs,german,VK_MENU,312,true,1,state,"\033[18;56;0;1;265;1_");
        raw_key(mk,&wgs,german,'Q',16,true,1,state,"\033[81;16;64;1;9;1_");
        raw_key(mk,&wgs,german,'Q',16,false,1,state,"\033[81;16;64;0;9;1_");
        raw_key(mk,&wgs,german,VK_MENU,312,false,1,state,"\033[18;56;0;0;264;1_");
        raw_key(mk,&wgs,german,VK_CONTROL,29,false,1,state,"\033[17;29;0;0;0;1_");
        if (german != original) UnloadKeyboardLayout(german);
    }
    nemo_keyboard_free(&wgs);
    IEQUAL(GetKeyboardLayout(0)==original,true);
    if (us != original) UnloadKeyboardLayout(us);
}
#endif

int main(void)
{
    Mock *mk=mock_new();
    mk->term=term_init(mk->conf,mk->ucsdata,&mk->tw);
    mk->ldisc=ldisc_create(mk->conf,mk->term,&mk->backend,&mk->seat);
    test_win32_mode(mk);
    test_win32_encoder(mk);
#ifdef _WIN32
    test_win32_windows(mk);
#endif
    bool failed=mk->any_test_failed;
    mock_free(mk);
    puts(failed ? "Win32 input suite FAILED" : "Win32 input suite passed");
    return failed ? 1 : 0;
}
