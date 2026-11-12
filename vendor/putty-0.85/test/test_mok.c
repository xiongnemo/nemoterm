/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main

static void mok_reply(Mock *mk, const char *sequence, const char *expected)
{
    test_context(mk, "modifyOtherKeys negotiation %s", sequence);
    strbuf_clear(mk->to_backend);
    term_data_fragmented(mk->term, sequence);
    SEQUAL(mk->to_backend->s, expected);
}

static void test_mok_negotiation(Mock *mk)
{
    reset(mk);
    mok_reply(mk, "\033[?4m\033[?4g\033[>4g", "\033[>4;0m\033[>4;0f\033[>4;0f");
    mok_reply(mk, "\033[>4;2m\033[>4;1f\033[?4m\033[?4g", "\033[>4;2m\033[>4;1f");
    mok_reply(mk, "\033[>4;3:5m\033P$q>4m\033\\\033P$q>4f\033\\",
              "\033P1$r>4;3:5m\033\\\033P1$r>4;1f\033\\");
    mok_reply(mk, "\033[?1049h\033[?4m\033[>4;1m\033[?1049l\033[?4m", "\033[>4;3m\033[>4;1m");
    term_size(mk->term, 40, 100, 100);
    mok_reply(mk, "\033[s\033[>4;2m\033[u\033[?4m", "\033[>4;2m");
    term_reconfig(mk->term, mk->conf);
    mok_reply(mk, "\033[?4m\033[>31u\033[?u\033[?4m\033[<u", "\033[>4;2m\033[?31u\033[>4;2m");
    mok_reply(mk, "\033[>4n\033[?4m\033P$q>4m\033\\", "\033[>4;65535m\033P1$r>4;65535m\033\\");
    mok_reply(mk, "\033[>4;65535m\033[?4m", "\033[>4;65535m");
    mok_reply(mk, "\033[>4m\033[>4f\033[?4m\033[?4g", "\033[>4;0m\033[>4;0f");
    mok_reply(mk, "\033[>4;2:4294967295m\033P$q>4m\033\\", "\033P1$r>4;2:4294967295m\033\\");
    mok_reply(mk, "\033[>4;2m\033P$q>4m\033\\", "\033P1$r>4;2m\033\\");
    const char *invalid[] = {
        "\033[>4;4m", "\033[>4;4294967295m", "\033[>4;2;1m", "\033[>4:1m",
        "\033[>4:1;2m", "\033[>4;2:1:2m", "\033[>4;0:1f", "\033[>4;2f",
        "\033[>4;0\030", "\033[>4;0\032", "\033[>4;0\033[0m", "\033[>3;0m",
    };
    for (size_t i = 0; i < lenof(invalid); i++) {
        mok_reply(mk, invalid[i], "");
        mok_reply(mk, "\033[?4m\033[?4g", "\033[>4;2m\033[>4;0f");
    }
    mok_reply(mk, "\033[>4;", "");
    for (unsigned i = 0; i < 10000; i++) term_data(mk->term, ";", 1);
    mok_reply(mk, "m\033[?4m", "\033[>4;2m");
    mok_reply(mk, "\033[>m\033[>f\033[?4m\033[?4g", "\033[>4;0m\033[>4;0f");
    conf_set_int(mk->conf, CONF_nemo_modify_other_keys, 3);
    conf_set_int(mk->conf, CONF_nemo_format_other_keys, 1);
    term_reconfig(mk->term, mk->conf);
    mok_reply(mk, "\033[?4m\033[?4g", "\033[>4;3m\033[>4;1f");
    mok_reply(mk, "\033[>4;0m\033[?4m\033[>4m\033[?4m", "\033[>4;0m\033[>4;3m");
    mok_reply(mk, "\033[>4;2:1m\033c\033[?4m\033[?4g\033P$q>4m\033\\",
              "\033[>4;3m\033[>4;1f\033P1$r>4;3m\033\\");
    conf_set_int(mk->conf, CONF_nemo_modify_other_keys, 0);
    conf_set_int(mk->conf, CONF_nemo_format_other_keys, 0);
    term_reconfig(mk->term, mk->conf);
    IEQUAL(sizeof(mk->term->modify_keys), 8);
}

static void test_mok_encoding(Mock *mk)
{
    static const struct {
        int level, format; unsigned mask, mods; uint32_t key, factored;
        enum NemoModifiedKeyKind kind; const char *expected; int length;
    } cases[] = {
        {0,0,0,4,'a',0,NMK_TEXT,"",-1},
        {1,0,0,4,'a',0,NMK_TEXT,"\001",1},
        {1,0,0,5,'A',0,NMK_TEXT,"\001",1},
        {1,0,0,6,'a',0,NMK_TEXT,"\033\001",2},
        {1,0,0,2,'a',0,NMK_TEXT,"",-1},
        {1,0,0,1,'A',0,NMK_TEXT,"",-1},
        {1,0,0,4,'2',0,NMK_TEXT,"\0",1},
        {1,0,0,4,'`',0,NMK_TEXT,"\0",1},
        {1,0,0,4,'.',0,NMK_TEXT,"\033[27;5;46~",10},
        {1,0,0,6,'.',0,NMK_TEXT,"\033[27;5;46~",10},
        {1,0,0,5,'!',0,NMK_TEXT,"\033[27;6;33~",10},
        {1,0,0,1,9,0,NMK_TAB,"",-1},
        {1,0,0,4,9,0,NMK_TAB,"\033[27;5;9~",9},
        {1,0,0,1,13,0,NMK_ENTER,"\033[27;2;13~",10},
        {1,0,0,4,27,0,NMK_ESCAPE,"",-1},
        {2,0,0,1,'A',0,NMK_TEXT,"\033[27;2;65~",10},
        {2,0,0,1,'!',0,NMK_TEXT,"",-1},
        {2,0,0,1,'{',0,NMK_TEXT,"\033[27;2;123~",11},
        {2,0,0,5,'A',0,NMK_TEXT,"\033[27;6;65~",10},
        {2,0,0,6,'.',0,NMK_TEXT,"\033[27;7;46~",10},
        {2,0,0,1,' ',0,NMK_TEXT,"\033[27;2;32~",10},
        {2,0,0,1,9,0,NMK_TAB,"\033[27;2;9~",9},
        {2,0,0,4,8,0,NMK_BACKSPACE,"",-1},
        {2,0,0,5,8,0,NMK_BACKSPACE,"\033[27;6;8~",9},
        {2,0,0,4,27,0,NMK_ESCAPE,"\033[27;5;27~",10},
        {2,0,0,192,'A',0,NMK_TEXT,"",-1},
        {2,1,1,1,'A','a',NMK_TEXT,"",-1},
        {2,1,1,5,'A','a',NMK_TEXT,"\033[97;6u",7},
        {2,1,4,4,'a',0,NMK_TEXT,"\001",1},
        {2,1,8,2,'a',0,NMK_TEXT,"",-1},
        {3,0,0,0,'a',0,NMK_TEXT,"\033[27;1;97~",10},
        {3,1,1,1,'A','a',NMK_TEXT,"\033[97;1u",7},
        {3,1,5,5,'A','a',NMK_TEXT,"\033[97;6u",7},
        {3,1,0,192,'A',0,NMK_TEXT,"\033[65;1u",7},
        {3,1,0,0,0x1f600,0,NMK_TEXT,"\033[128512;1u",11},
        {2,1,0,4,0x444,0,NMK_TEXT,"\033[1092;5u",9},
    };
    for (size_t i = 0; i < lenof(cases); i++) {
        test_context(mk, "modifyOtherKeys encoding case %u", (unsigned)i);
        NemoModifyKeys mode = {.level=cases[i].level, .format=cases[i].format, .ignore=cases[i].mask};
        NemoModifiedKey key = {.key=cases[i].key, .factored_key=cases[i].factored,
            .modifiers=cases[i].mods, .kind=cases[i].kind, .type=1};
        char encoded[NEMO_MOK_ENCODED_MAX];
        int n = nemo_mok_encode(&mode, &key, encoded, sizeof(encoded));
        IEQUAL(n, cases[i].length);
        if (n > 0) IEQUAL(memcmp(encoded, cases[i].expected, n), 0);
        key.type = 2; IEQUAL(nemo_mok_encode(&mode, &key, encoded, sizeof(encoded)), n);
        key.type = 3; IEQUAL(nemo_mok_encode(&mode, &key, encoded, sizeof(encoded)), mode.level ? 0 : -1);
    }
    NemoModifyKeys mode = {.level=3};
    NemoModifiedKey key = {.key=0x10ffff, .modifiers=15, .type=1};
    for (size_t size = 0; size <= NEMO_MOK_ENCODED_MAX; size++) {
        unsigned char buffer[NEMO_MOK_ENCODED_MAX+2]; memset(buffer, 0x5a, sizeof(buffer));
        int n = nemo_mok_encode(&mode, &key, (char *)buffer+1, size);
        IEQUAL(buffer[0], 0x5a); IEQUAL(buffer[size+1], 0x5a);
        IEQUAL(n >= 0 && (size_t)n <= size, true);
    }
    char output[NEMO_MOK_ENCODED_MAX];
    key.key=0xd800; IEQUAL(nemo_mok_encode(&mode, &key, output, sizeof(output)), 0);
    key.key=0x110000; IEQUAL(nemo_mok_encode(&mode, &key, output, sizeof(output)), 0);
}

#ifdef _WINDOWS
#include "test_mok_win.c"
#endif

int main(void)
{
    Mock *mk = mock_new();
    mk->term = term_init(mk->conf, mk->ucsdata, &mk->tw);
    mk->ldisc = ldisc_create(mk->conf, mk->term, &mk->backend, &mk->seat);
    test_mok_negotiation(mk); test_mok_encoding(mk);
#ifdef _WINDOWS
    test_windows_mok(mk);
#endif
    bool failed = mk->any_test_failed;
    mock_free(mk);
    puts(failed ? "Modified keys suite FAILED" : "Modified keys suite passed");
    return failed ? 1 : 0;
}
