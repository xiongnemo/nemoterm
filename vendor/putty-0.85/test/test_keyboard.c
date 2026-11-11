/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main

static void reply(Mock *mk, const char *sequence, const char *expected)
{
    test_context(mk, "keyboard negotiation %s", sequence);
    term_data_fragmented(mk->term, sequence);
    SEQUAL(mk->to_backend->s, expected);
    strbuf_clear(mk->to_backend);
}

static void test_negotiation(Mock *mk)
{
    reset(mk);
    reply(mk, "\033[?u", "\033[?0u");
    reply(mk, "\033[>1u\033[?u\033[>31u\033[?u\033[<u\033[?u", "\033[?1u\033[?31u\033[?1u");
    reply(mk, "\033[=6;2u\033[?u\033[=2;3u\033[?u", "\033[?7u\033[?5u");
    reply(mk, "\033[=8u\033[?u\033[=16;2u\033[?u", "\033[?8u\033[?24u");
    reply(mk, "\033[=31;0u\033[=0;4u\033[?u\033[<0u\033[?u", "\033[?24u\033[?24u");
    reply(mk, "\033[>u\033[?u\033[<2u\033[?u", "\033[?0u\033[?0u");
    reply(mk, "\033[=4294967295u\033[?u", "\033[?31u");
    reply(mk, "\033[?0u\033[?;u\033[=1;1;1u\033[>3;2u\033[<1;2u\033[>1:2u\033[?u", "\033[?31u");
    reply(mk, "\033[>1\030\033[>3\032\033[?u", "\033[?31u");
    reply(mk, "\033[>1;", "");
    for (int i = 0; i < 10000; i++) term_data(mk->term, ";", 1);
    reply(mk, "u\033[?u", "\033[?31u");
    reply(mk, "\033[=1u\033[?1049h\033[?u\033[>3u\033[?u\033[?1049l\033[?u", "\033[?0u\033[?3u\033[?1u");
    reply(mk, "\033[?1049h\033[?u\033[<u\033[?u\033[?1049l", "\033[?3u\033[?0u");
    term_size(mk->term, 40, 100, 100);
    reply(mk, "\033[s\033[=8u\033[u\033[?u", "\033[?8u");
    reply(mk, "\033[?1049h\033[=31u\033c\033[?u\033[?1049h\033[?u", "\033[?0u\033[?0u");
    reset(mk);
    for (unsigned i = 0; i < 10000; i++) {
        char input[32]; sprintf(input, "\033[>%uu", i);
        term_data_fragmented(mk->term, input);
    }
    IEQUAL(mk->term->keyboard[0].count, NEMO_KEY_STACK_MAX);
    for (unsigned i = 0; i < NEMO_KEY_STACK_MAX; i++) {
        char expected[32]; sprintf(expected, "\033[?%uu", (9999-i)&31);
        reply(mk, "\033[?u\033[<u", expected);
    }
    reply(mk, "\033[?u\033[<4294967295u\033[?u", "\033[?0u\033[?0u");
    IEQUAL(sizeof(mk->term->keyboard), 66);
}

static void encoded(Mock *mk, unsigned flags, NemoKeyEvent event, const char *expected)
{
    char buf[NEMO_KEY_ENCODED_MAX+1];
    memset(buf, 0x5a, sizeof(buf));
    int n = nemo_keyboard_encode(flags, &event, buf, NEMO_KEY_ENCODED_MAX);
    test_context(mk, "flags %u key %u mods %u event %u", flags, event.key, event.modifiers, event.type);
    IEQUAL(n, (int)strlen(expected));
    if (n >= 0 && n <= NEMO_KEY_ENCODED_MAX) { buf[n] = 0; SEQUAL(buf, expected); }
}

static void test_encoding(Mock *mk)
{
    uint32_t lower[] = {'a'}, upper[] = {'A'}, unicode[] = {0x4e2d,0x301,0x1f600};
    NemoKeyEvent a = {.key='a', .shifted='A', .base='a', .type=1, .text=lower, .text_len=1};
    char buffer[NEMO_KEY_ENCODED_MAX];
    IEQUAL(nemo_keyboard_encode(0, &a, buffer, sizeof(buffer)), -1);
    encoded(mk, 1, a, "a");
    a.modifiers = 1; a.text = upper;
    encoded(mk, 1, a, "A");
    encoded(mk, 31, a, "\033[97:65;2;65u");
    a.type = 2; encoded(mk, 31, a, "\033[97:65;2:2;65u");
    a.type = 3; encoded(mk, 31, a, "\033[97:65;2:3u");
    encoded(mk, 1, a, "");
    a.type = 1; a.text_len = 0; a.modifiers = 4;
    encoded(mk, 1, a, "\033[97;5u");
    encoded(mk, 2, a, "\001");
    a.modifiers = 196; encoded(mk, 2, a, "\001");
    a.modifiers = 5; encoded(mk, 2, a, "\033[97;6u");
    a.modifiers = 7; encoded(mk, 2, a, "\033[97;8u");
    a.modifiers = 3; encoded(mk, 6, a, "\033A");
    a.modifiers = 195; encoded(mk, 6, a, "\033A");
    a.modifiers = 4;
    a.type = 2; encoded(mk, 2, a, "\033[97;5:2u");
    a.type = 3; encoded(mk, 2, a, "\033[97;5:3u");
    a.type = 1; a.modifiers = 6;
    encoded(mk, 1, a, "\033[97;7u");
    a.modifiers = 255;
    encoded(mk, 31, a, "\033[97:65;256u");
    a.key = 0x444; a.base = 'a'; a.shifted = 0; a.modifiers = 4;
    encoded(mk, 5, a, "\033[1092::97;5u");
    a = (NemoKeyEvent){.type=1, .text=unicode, .text_len=3};
    encoded(mk, 24, a, "\033[0;1;20013:769:128512u");
    encoded(mk, 1, a, "\xe4\xb8\xad\xcc\x81\xf0\x9f\x98\x80");
    encoded(mk, 2, (NemoKeyEvent){.key='~', .type=1, .modifiers=4}, "\036");
    encoded(mk, 2, (NemoKeyEvent){.key=27, .type=1, .modifiers=192}, "\033");
    static const struct { uint32_t key; const char *value; } functions[] = {
        {27,"\033[27u"}, {NK_INSERT,"\033[2~"}, {NK_DELETE,"\033[3~"},
        {NK_UP,"\033[A"}, {NK_DOWN,"\033[B"}, {NK_RIGHT,"\033[C"}, {NK_LEFT,"\033[D"},
        {NK_HOME,"\033[H"}, {NK_END,"\033[F"}, {NK_PAGE_UP,"\033[5~"}, {NK_PAGE_DOWN,"\033[6~"},
        {NK_F1,"\033[P"}, {NK_F1+1,"\033[Q"}, {NK_F1+2,"\033[13~"}, {NK_F1+3,"\033[S"},
        {NK_F1+4,"\033[15~"}, {NK_F1+11,"\033[24~"}, {NK_F1+12,"\033[57376u"},
        {NK_F35,"\033[57398u"}, {NK_KP_0,"\033[57399u"}, {NK_KP_9,"\033[57408u"},
        {NK_KP_ENTER,"\033[57414u"}, {NK_KP_BEGIN,"\033[E"}, {NK_MEDIA_NEXT,"\033[57435u"},
        {NK_RIGHT_CONTROL,"\033[57448u"},
    };
    for (size_t i = 0; i < lenof(functions); i++) {
        a = (NemoKeyEvent){.key=functions[i].key, .type=1};
        encoded(mk, 31, a, functions[i].value);
    }
    for (unsigned key = 9; key <= 127; key += key == 9 ? 4 : 114) {
        a = (NemoKeyEvent){.key=key, .type=1, .modifiers=192};
        char plain[2] = {(char)key, 0};
        encoded(mk, 3, a, plain);
        a.type = 3; encoded(mk, 3, a, "");
        a.modifiers = 4; a.type = 1;
        char wanted[32]; sprintf(wanted, "\033[%u;5u", key);
        encoded(mk, 3, a, wanted);
    }
    a = (NemoKeyEvent){.key=NK_LEFT_CONTROL, .type=1, .modifiers=4};
    encoded(mk, 1, a, ""); encoded(mk, 31, a, "\033[57442;5u");
    a.type = 3; a.modifiers = 0; encoded(mk, 31, a, "\033[57442;1:3u");
    a = (NemoKeyEvent){.key=NK_UP, .type=3, .modifiers=5};
    encoded(mk, 3, a, "\033[1;6:3A");
}

static void test_encoding_bounds(Mock *mk)
{
    uint32_t text[NEMO_KEY_TEXT_MAX];
    for (size_t i = 0; i < lenof(text); i++) text[i] = 0x10ffff-i;
    NemoKeyEvent e = {.key=0x10ffff, .shifted=0x10fffe, .base=0x10fffd,
        .modifiers=255, .type=2, .text=text, .text_len=lenof(text)};
    unsigned char buffer[NEMO_KEY_ENCODED_MAX+2];
    for (size_t capacity = 0; capacity <= NEMO_KEY_ENCODED_MAX; capacity++) {
        memset(buffer, 0x5a, sizeof(buffer));
        int n = nemo_keyboard_encode(31, &e, (char *)buffer+1, capacity);
        IEQUAL(buffer[0], 0x5a); IEQUAL(buffer[capacity+1], 0x5a);
        IEQUAL(n >= 0 && (size_t)n <= capacity, true);
    }
    char result[NEMO_KEY_ENCODED_MAX];
    IEQUAL(nemo_keyboard_encode(31, &e, result, sizeof(result)) > 0, true);
    e.text_len++; IEQUAL(nemo_keyboard_encode(31, &e, result, sizeof(result)), 0);
    e.text_len--; text[3] = 0x9b;
    IEQUAL(nemo_keyboard_encode(31, &e, result, sizeof(result)), 0);
    e.text_len = 0; e.key = 0xd800;
    IEQUAL(nemo_keyboard_encode(31, &e, result, sizeof(result)), 0);
}

#ifdef _WINDOWS
#include "test_keyboard_win.c"
#endif

int main(void)
{
    Mock *mk = mock_new();
    mk->term = term_init(mk->conf, mk->ucsdata, &mk->tw);
    mk->ldisc = ldisc_create(mk->conf, mk->term, &mk->backend, &mk->seat);
    test_negotiation(mk);
    test_encoding(mk);
    test_encoding_bounds(mk);
#ifdef _WINDOWS
    test_windows_keyboard(mk);
#endif
    bool failed = mk->any_test_failed;
    mock_free(mk);
    puts(failed ? "Keyboard protocol suite FAILED" : "Keyboard protocol suite passed");
    return failed ? 1 : 0;
}
