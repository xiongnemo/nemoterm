/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main

static void check_colour(Mock *mk, unsigned index, unsigned r, unsigned g, unsigned b)
{
    IEQUAL(mk->term->palette[index].r, r);
    IEQUAL(mk->term->palette[index].g, g);
    IEQUAL(mk->term->palette[index].b, b);
}

static void reply(Mock *mk, const char *expected)
{
    SEQUAL(mk->to_backend->s, expected);
    strbuf_clear(mk->to_backend);
}

int main(void)
{
    Mock *mk = mock_new();
    mk->term = term_init(mk->conf, mk->ucsdata, &mk->tw);
    mk->ldisc = ldisc_create(mk->conf, mk->term, &mk->backend, &mk->seat);
    reset(mk);
    rgb original1 = mk->term->palette[1], original2 = mk->term->palette[2];
    rgb originalfg = mk->term->palette[OSC4_COLOUR_fg];
    rgb originalbg = mk->term->palette[OSC4_COLOUR_bg];
    rgb originalcursor = mk->term->palette[OSC4_COLOUR_cursor_bg];
    test_context(mk, "multi-set/query with BEL and ST, fragmented input");
    term_data_fragmented(mk->term,
        "\033]4;1;rgb:f/80/800;2;#123456;1;?;2;?\007");
    reply(mk, "\033]4;1;rgb:ffff/8080/8080\007"
              "\033]4;2;rgb:1212/3434/5656\007");
    term_data_fragmented(mk->term, "\033]4;2;?\033\\");
    reply(mk, "\033]4;2;rgb:1212/3434/5656\033\\");
    check_colour(mk, 1, 255, 128, 128);

    test_context(mk, "dynamic colours, chained queries, selective resets");
    term_data_fragmented(mk->term,
        "\033]10;#aabbcc;rgb:1/2/3;red\033\\\033]10;?;?;?\007");
    reply(mk, "\033]10;rgb:aaaa/bbbb/cccc\007"
              "\033]11;rgb:1111/2222/3333\007"
              "\033]12;rgb:ffff/0000/0000\007");
    term_data_fragmented(mk->term, "\033]104;1\007");
    check_colour(mk, 1, original1.r, original1.g, original1.b);
    check_colour(mk, 2, 0x12, 0x34, 0x56);
    check_colour(mk, OSC4_COLOUR_fg, 0xaa, 0xbb, 0xcc);
    term_data_fragmented(mk->term, "\033]104\033\\");
    check_colour(mk, 2, original2.r, original2.g, original2.b);
    check_colour(mk, OSC4_COLOUR_bg, 17, 34, 51);
    term_data_fragmented(mk->term, "\033]110\007\033]111\033\\\033]112\007");
    check_colour(mk, OSC4_COLOUR_fg, originalfg.r, originalfg.g, originalfg.b);
    check_colour(mk, OSC4_COLOUR_bg, originalbg.r, originalbg.g, originalbg.b);
    check_colour(mk, OSC4_COLOUR_cursor_bg,
                 originalcursor.r, originalcursor.g, originalcursor.b);

    test_context(mk, "invalid entries do not alias private PuTTY colour slots");
    term_data_fragmented(mk->term,
        "\033]4;256;red;42949672960;blue;-1;white;1;invalid;2;#fff\007"
        "\033]4;256;?;99999999999999999999;?\007");
    reply(mk, "");
    check_colour(mk, OSC4_COLOUR_fg, originalfg.r, originalfg.g, originalfg.b);
    check_colour(mk, 1, original1.r, original1.g, original1.b);
    check_colour(mk, 2, 240, 240, 240);

    test_context(mk, "overlong colour payload is rejected as a whole");
    strbuf *longosc = strbuf_new();
    put_dataz(longosc, "\033]4;1;red;");
    for (unsigned i = 0; i < OSC_STR_MAX; i++) put_byte(longosc, '0');
    put_dataz(longosc, ";blue\007");
    term_data_fragmented(mk->term, longosc->s);
    strbuf_free(longosc);
    check_colour(mk, 1, original1.r, original1.g, original1.b);
    term_data_fragmented(mk->term, "\033]4;1;blue\007");
    check_colour(mk, 1, 0, 0, 255);

    test_context(mk, "CAN and SUB abort palette modifications and queries");
    term_data_fragmented(mk->term, "\033]4;1;red\030\033]4;1;?\032");
    check_colour(mk, 1, 0, 0, 255);
    reply(mk, "");
    term_data_fragmented(mk->term, "\033%G\033]4;1;?\302\234");
    reply(mk, "\033]4;1;rgb:0000/0000/ffff\033\\");

    bool failed = mk->any_test_failed;
    mock_free(mk);
    puts(failed ? "OSC colour suite FAILED!" : "OSC colour suite passed");
    return failed ? 1 : 0;
}
