/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main
#include "../../../tests/special_keys_reference.h"
#include "../../../tests/extended_keys_reference.h"
#include "../../../tests/legacy_modifiers_reference.h"

static void test_legacy_reference(Mock *mk, bool fragmented)
{
    for (size_t i = 0; i < lenof(legacy_modifiers_reference); i++) {
        const struct legacy_modifier_reference *r = &legacy_modifiers_reference[i];
        if (r->reset) {
            reset(mk);
            conf_set_int(mk->conf, CONF_funky_type, r->profile);
            term_reconfig(mk->term, mk->conf);
        }
        test_context(mk, "legacy modifiers %s step %u (%s)", r->name,
                     (unsigned)i, fragmented ? "bytes" : "whole");
        strbuf_clear(mk->to_backend);
        if (fragmented) term_data_fragmented(mk->term, r->sequence);
        else term_data(mk->term, r->sequence, strlen(r->sequence));
        for (unsigned j = 0; j < r->count; j++) {
            const struct legacy_modifier_event *e = &r->events[j];
            if (!e->down) continue;
            char output[NEMO_MOK_ENCODED_MAX];
            int n = term_format_xterm_extended_key(mk->term, e->resource,
                e->codepoint, e->mods, output, sizeof(output));
            bool consumed = false;
            if (n < 0) {
                if (e->kind == 1)
                    n = format_arrow_key(output, mk->term, e->code,
                        e->mods & 1, e->mods & 4, e->mods & 2, &consumed);
                else if (e->kind == 2) {
                    if (term_send_udk(mk->term, e->code, e->mods & 1, e->mods & 4)) continue;
                    n = format_function_key(output, mk->term, e->code,
                        e->mods & 1, e->mods & 4, e->mods & 2, &consumed);
                } else if (e->kind == 3)
                    n = format_small_keypad_key(output, mk->term, e->code,
                        e->mods & 1, e->mods & 4, e->mods & 2, &consumed);
                else n = term_format_xterm_legacy_key(mk->term, e->resource,
                    e->codepoint, e->mods, e->state & 16, output, sizeof(output));
                if (e->kind && n > 0 && (e->mods & 2) && !consumed)
                    put_byte(mk->to_backend, '\033');
            }
            if (n > 0) put_data(mk->to_backend, output, n);
        }
        SEQUAL(mk->to_backend->s, r->reply);
    }
    printf("Legacy modifier reference: %zu unchanged steps (%s)\n",
           lenof(legacy_modifiers_reference), fragmented ? "bytes" : "whole");
    conf_set_int(mk->conf, CONF_funky_type, FUNKY_XTERM_216);
    term_reconfig(mk->term, mk->conf);
    reset(mk);
}

static void test_extended_reference(Mock *mk, bool fragmented)
{
    unsigned matched = 0, fallback = 0;
    for (size_t i = 0; i < lenof(extended_keys_reference); i++) {
        const struct extended_key_reference *r = &extended_keys_reference[i];
        if (r->reset) reset(mk);
        test_context(mk, "extended resource %s step %u (%s)", r->name,
                     (unsigned)i, fragmented ? "bytes" : "whole");
        strbuf_clear(mk->to_backend);
        if (fragmented) term_data_fragmented(mk->term, r->sequence);
        else term_data(mk->term, r->sequence, strlen(r->sequence));
        SEQUAL(mk->to_backend->s, r->before);
        for (unsigned j = 0; j < r->count; j++) {
            const struct extended_key_event *e = &r->events[j];
            if (!e->down) continue; /* This protocol has no key releases. */
            char output[NEMO_MOK_ENCODED_MAX];
            int n = term_format_xterm_extended_key(mk->term, e->resource,
                e->codepoint, e->mods, output, sizeof(output));
            if (n > 0) put_data(mk->to_backend, output, n);
        }
        if (r->core) { SEQUAL(mk->to_backend->s, r->reply); matched++; }
        else { SEQUAL(mk->to_backend->s, r->before); fallback++; }
    }
    IEQUAL(matched, 283); IEQUAL(fallback, 26);
    printf("Extended resource reference: %u unchanged steps (%s); %u legacy observations excluded\n",
           matched, fragmented ? "bytes" : "whole", fallback);
    reset(mk);
}

static void test_special_reference(Mock *mk, bool fragmented)
{
    conf_set_int(mk->conf, CONF_funky_type, FUNKY_XTERM_216);
    conf_set_int(mk->conf, CONF_sharrow_type, SHARROW_BITMAP);
    term_reconfig(mk->term, mk->conf);
    for (size_t i = 0; i < lenof(special_keys_reference); i++) {
        const struct special_key_reference *r = &special_keys_reference[i];
        if (r->reset) reset(mk);
        test_context(mk, "special modifiers %s step %u (%s)", r->name,
                     (unsigned)i, fragmented ? "bytes" : "whole");
        strbuf_clear(mk->to_backend);
        if (fragmented) term_data_fragmented(mk->term, r->sequence);
        else term_data(mk->term, r->sequence, strlen(r->sequence));
        char output[64];
        bool consumed = false, shift = r->mods & 1, ctrl = r->mods & 4, alt = r->mods & 2;
        int n = 0;
        if (r->kind == 1)
            n = format_arrow_key(output, mk->term, r->key, shift, ctrl, alt, &consumed);
        else if (r->kind == 2)
            n = format_function_key(output, mk->term, r->key, shift, ctrl, alt, &consumed);
        else if (r->kind == 3)
            n = format_small_keypad_key(output, mk->term, r->key, shift, ctrl, alt, &consumed);
        if (r->kind && alt && !consumed) put_byte(mk->to_backend, '\033');
        put_data(mk->to_backend, output, n);
        SEQUAL(mk->to_backend->s, r->reply);
    }
    printf("Special modifier reference: %zu unchanged steps (%s)\n",
           lenof(special_keys_reference), fragmented ? "bytes" : "whole");
}

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
    IEQUAL(sizeof(mk->term->modify_keys), 12);
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

static void test_special_policy(Mock *mk)
{
    reset(mk);
    /* Preserve the documented reset-all contract, including resources that
     * the pinned XTerm currently leaves unchanged. This is not oracle parity. */
    mok_reply(mk, "\033[>1;3m\033[>2;4m\033[>1;1f\033[>2;1f\033[>m\033[>f"
              "\033[?1;2m\033[?1;2g", "\033[>1;2m\033[>2;2m\033[>1;0f\033[>2;0f");
    const char *invalid[] = {"\033[>1;5m", "\033[>2;4294967295m", "\033[>1;4;1m",
        "\033[>1;4:1:2m", "\033[>2:1;4m", "\033[>1;2f", "\033[>2;1:1f", "\033[>1;3\030"};
    for (size_t i = 0; i < lenof(invalid); i++) {
        mok_reply(mk, invalid[i], "");
        mok_reply(mk, "\033[?1;2m\033[>1;2g", "\033[>1;2m\033[>2;2m\033[>1;0f\033[>2;0f");
    }
    mok_reply(mk, "\033[>1;3m\033[>2;4m", "");
    term_reconfig(mk->term, mk->conf);
    term_size(mk->term, 40, 100, 100);
    mok_reply(mk, "\033[?1;2m", "\033[>1;3m\033[>2;4m");
    IEQUAL(sizeof(mk->term->special_modify_keys), 72);
    reset(mk);
}

static void test_extended_policy(Mock *mk)
{
    reset(mk);
    mok_reply(mk, "\033[>3;4m\033[>6;4m\033[>7;4m\033[>3;1f\033[>6;1f\033[>7;1f"
              "\033[>m\033[>f\033[?3;6;7m\033[>3;6;7g",
              "\033[>3;0m\033[>6;0m\033[>7;0m\033[>3;0f\033[>6;0f\033[>7;0f");
    mok_reply(mk, "\033[>7;4m", "");
    char output[NEMO_MOK_ENCODED_MAX];
    int n = term_format_xterm_extended_key(mk->term, 7, 27, 4, output, sizeof(output));
    IEQUAL(n, sizeof("\033[27;5;27~")-1);
    IEQUAL(memcmp(output, "\033[27;5;27~", n), 0);
    for (size_t capacity = 0; capacity <= sizeof(output); capacity++) {
        unsigned char guarded[NEMO_MOK_ENCODED_MAX+2];
        memset(guarded, 0x5a, sizeof(guarded));
        int got = term_format_xterm_extended_key(mk->term, 7, 27, 4,
                                                 (char *)guarded+1, capacity);
        IEQUAL(got, capacity < (size_t)n ? 0 : n);
        IEQUAL(guarded[0], 0x5a); IEQUAL(guarded[capacity+1], 0x5a);
    }
    IEQUAL(term_format_xterm_extended_key(mk->term, 7, 0xd800, 0, output, sizeof(output)), 0);
    IEQUAL(term_format_xterm_extended_key(mk->term, 7, 0x110000, 0, output, sizeof(output)), 0);
    mk->term->c1_8bit = true;
    n = term_format_xterm_extended_key(mk->term, 7, 27, 4, output, sizeof(output));
    IEQUAL(n, sizeof("\23327;5;27~")-1);
    IEQUAL(memcmp(output, "\23327;5;27~", n), 0);
    reset(mk);
}

static void test_legacy_policy(Mock *mk)
{
    reset(mk);
    const unsigned values[] = {0, 1, 2, 4, 8, 15, 16, 255, 65535};
    for (size_t i = 0; i < lenof(values); i++) {
        char sequence[100], expected[100];
        sprintf(sequence, "\033[>0;%um\033[?0m\033P$q>0m\033\\", values[i]);
        sprintf(expected, "\033[>0;%um\033P1$r>0;%um\033\\", values[i], values[i]);
        mok_reply(mk, sequence, expected);
    }
    mok_reply(mk, "\033[>0;15:5m\033[>0;65535f\033P$q>0f\033\\", "\033P1$r>0;65535f\033\\");
    /* Applying a format status reply must restore format without changing the
     * modifier mask. XTerm 412's observed m suffix fails this round trip. */
    mok_reply(mk, "\033[>0;0f\033[>0;65535f\033[?0m\033[>0g",
              "\033[>0;15m\033[>0;65535f");
    const char *preserve[] = {"\033[?1049h\033[?1049l", "\0337\0338"};
    for (size_t i = 0; i < lenof(preserve); i++) {
        mok_reply(mk, preserve[i], "");
        mok_reply(mk, "\033P$q>0m\033\\\033[>0g", "\033P1$r>0;15:5m\033\\\033[>0;65535f");
    }
    term_size(mk->term, 40, 100, 100);
    term_reconfig(mk->term, mk->conf);
    mok_reply(mk, "\033P$q>0m\033\\", "\033P1$r>0;15:5m\033\\");
    mok_reply(mk, "\033[>0n\033[?0m\033P$q>0m\033\\",
              "\033[>0;65535m\033P1$r>0;65535m\033\\");
    const char *resets[] = {"\033c", "\033[!p", "\033[63;1\"p", "\033[>0m\033[>0f", "\033[>m\033[>f"};
    for (size_t i = 0; i < lenof(resets); i++) {
        mok_reply(mk, "\033[>0;15:5m\033[>0;1f", "");
        mok_reply(mk, resets[i], "");
        mok_reply(mk, "\033[?0m\033[>0g\033P$q>0m\033\\\033P$q>0f\033\\",
                  "\033[>0;0m\033[>0;0f\033P1$r>0;0m\033\\\033P1$r>0;0f\033\\");
    }
    reset(mk);
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
    test_special_reference(mk, false); test_special_reference(mk, true);
    test_special_policy(mk);
    test_extended_reference(mk, false); test_extended_reference(mk, true);
    test_extended_policy(mk);
    test_legacy_reference(mk, false); test_legacy_reference(mk, true);
    test_legacy_policy(mk);
#ifdef _WINDOWS
    test_windows_mok(mk);
    test_windows_special_priority(mk);
    test_windows_extended_reference(mk);
    test_windows_legacy_startup(mk);
#endif
    bool failed = mk->any_test_failed;
    mock_free(mk);
    puts(failed ? "Modified keys suite FAILED" : "Modified keys suite passed");
    return failed ? 1 : 0;
}
