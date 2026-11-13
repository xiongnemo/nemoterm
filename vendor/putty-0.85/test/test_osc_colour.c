/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main
#include "test_clock.h"
#include "../../../tests/palette_stack_oracle_cases.h"
#include "../../../tests/reset_palette_oracle_cases.h"
#include "../../../tests/x11_colour_cases.h"

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

#include "test_selection_colour.h"
#include "test_attribute_colour.h"

static void named_colour_protocol(Mock *mk)
{
    for (size_t i = 0; i < lenof(x11_colour_cases); i++) {
        char command[128], expected[80];
        const char *end = i % 2 ? "\007" : "\033\\";
        test_context(mk, "source-derived X11 colour %s", x11_colour_cases[i].name);
        sprintf(command, "\033]4;1;%s;1;?%s", x11_colour_cases[i].name, end);
        sprintf(expected, "\033]4;1;rgb:%04x/%04x/%04x%s",
                x11_colour_cases[i].r * 257, x11_colour_cases[i].g * 257,
                x11_colour_cases[i].b * 257, end);
        term_data_fragmented(mk->term, command);
        reply(mk, expected);
        check_colour(mk, 1, x11_colour_cases[i].r,
                     x11_colour_cases[i].g, x11_colour_cases[i].b);
    }
    test_context(mk, "named dynamic and selection colours, exact spaces, invalid names");
    term_data_fragmented(mk->term,
        "\033]10;gray50;LightGoldenrodYellow;light blue\007"
        "\033]17;WebGray\007\033]19;Red1\007"
        "\033]10;gray101\007\033]11;light  blue\007"
        "\033]17;web gray \007\033]19;red5\007"
        "\033]10;?;?;?\033\\\033]17;?\007\033]19;?\007");
    reply(mk, "\033]10;rgb:7f7f/7f7f/7f7f\033\\"
              "\033]11;rgb:fafa/fafa/d2d2\033\\"
              "\033]12;rgb:adad/d8d8/e6e6\033\\"
              "\033]17;rgb:8080/8080/8080\007"
              "\033]19;rgb:ffff/0000/0000\007");
}

static void stack_bounds_and_roundtrip(Mock *mk)
{
    test_context(mk, "empty stack reads and invalid writes allocate nothing");
    IEQUAL(mk->term->palette_stack == NULL, true);
    term_data_fragmented(mk->term, "\033[#Q\033[11#P\033[4294967295#P\033[#R");
    reply(mk, "\033[?0;0#Q");
    IEQUAL(mk->term->palette_stack == NULL, true);

    test_context(mk, "all 256 entries and all default colours survive stack restoration");
    rgb saved[OSC4_NCOLOURS];
    memcpy(saved, mk->term->palette, sizeof(saved));
    term_data_fragmented(mk->term, "\033[#P");
    for (unsigned i = 0; i < 256; i++) {
        char command[80];
        sprintf(command, "\033]4;%u;#%02x%02x%02x\007", i, i, 255-i, i/2);
        term_data_fragmented(mk->term, command);
    }
    term_data_fragmented(mk->term, "\033]10;#123456;#654321;#abcdef\007\033[#Q");
    for (unsigned i = 0; i < OSC4_NCOLOURS; i++)
        check_colour(mk, i, saved[i].r, saved[i].g, saved[i].b);
    term_update(mk->term);
    IEQUAL(mk->term->win_palette_pending, false);

    test_context(mk, "push overflow stays bounded and indexed slots survive pops");
    struct NemoPaletteStack *stack = mk->term->palette_stack;
    for (unsigned i = 0; i < 5000; i++) {
        term_data_fragmented(mk->term, "\033[#P");
        IEQUAL(mk->term->palette_stack == stack, true);
    }
    term_data_fragmented(mk->term, "\033[#R");
    reply(mk, "\033[?10;10#Q");
    for (unsigned i = 0; i < 5000; i++) term_data_fragmented(mk->term, "\033[#Q");
    term_data_fragmented(mk->term, "\033[#R\033]4;1;#123456\007\033[10#Q\033[#R");
    reply(mk, "\033[?0;10#Q\033[?9;10#Q");
    check_colour(mk, 1, saved[1].r, saved[1].g, saved[1].b);
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
        "\033]4;261;red;42949672960;blue;-1;white;1;invalid;2;#fff\007"
        "\033]4;261;?;99999999999999999999;?\007");
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
    failed |= test_selection_colour_wire();
    failed |= test_selection_colour_paint();
    failed |= test_attribute_colour_wire();
    failed |= test_attribute_colour_paint();
    failed |= test_attribute_colour_settings();
    for (size_t i = 0; i < lenof(reset_palette_oracle); i++) {
        mk = mock_new();
        /* The independent XTerm resource uses foreground for its default
         * cursor, unlike PuTTY's green default. All other defaults agree. */
        for (int component = 0; component < 3; component++)
            conf_set_int_int(mk->conf, CONF_colours,
                             CONF_COLOUR_cursor_bg*3+component, 187);
        mk->term = term_init(mk->conf, mk->ucsdata, &mk->tw);
        mk->ldisc = ldisc_create(mk->conf, mk->term, &mk->backend, &mk->seat);
        reset(mk);
        test_context(mk, "captured reset/reverse colour %s", reset_palette_oracle[i].name);
        term_data_fragmented(mk->term, reset_palette_oracle[i].sequence);
        reply(mk, reset_palette_oracle[i].reply);
        failed |= mk->any_test_failed;
        mock_free(mk);
    }
    for (size_t i = 0; i < lenof(palette_stack_oracle); i++) {
        mk = mock_new();
        conf_set_int(mk->conf, CONF_remote_qtitle_action, TITLE_REAL);
        mk->ucsdata->line_codepage = CP_UTF8;
        mk->term = term_init(mk->conf, mk->ucsdata, &mk->tw);
        mk->ldisc = ldisc_create(mk->conf, mk->term, &mk->backend, &mk->seat);
        reset(mk);
        test_context(mk, "palette/title stack %s", palette_stack_oracle[i].name);
        term_data_fragmented(mk->term, palette_stack_oracle[i].sequence);
        reply(mk, palette_stack_oracle[i].reply);
        failed |= mk->any_test_failed;
        mock_free(mk);
    }
    mk = mock_new();
    mk->term = term_init(mk->conf, mk->ucsdata, &mk->tw);
    mk->ldisc = ldisc_create(mk->conf, mk->term, &mk->backend, &mk->seat);
    reset(mk);
    stack_bounds_and_roundtrip(mk);
    named_colour_protocol(mk);
    failed |= mk->any_test_failed;
    mock_free(mk);
    puts(failed ? "OSC colour suite FAILED!" : "OSC colour suite passed");
    return failed ? 1 : 0;
}
