/* Included after the selection-colour mock helpers. No native UI/clipboard. */
#include "../../../tests/attribute_colour_cases.h"

static void attribute_conf(Conf *conf)
{
    for (int i = 0; i < 3; i++) {
        conf_set_int_int(conf, CONF_colours, CONF_COLOUR_fg*3+i, 255);
        conf_set_int_int(conf, CONF_colours, CONF_COLOUR_bg*3+i, 0);
    }
    conf_set_bool(conf, CONF_true_colour, true);
}

static bool test_attribute_colour_wire(void)
{
    bool failed = false;
    for (size_t i = 0; i < lenof(attribute_colour_cases); i++) {
        Mock *mk = mock_new();
        attribute_conf(mk->conf);
        mk->term = term_init(mk->conf, mk->ucsdata, &mk->tw);
        mk->ldisc = ldisc_create(mk->conf, mk->term, &mk->backend, &mk->seat);
        reset(mk);
        test_context(mk, "authored attribute colour: %s", attribute_colour_cases[i].name);
        term_data_fragmented(mk->term, attribute_colour_cases[i].sequence);
        reply(mk, attribute_colour_cases[i].reply);
        failed |= mk->any_test_failed;
        mock_free(mk);
    }
    return failed;
}

static bool test_attribute_colour_paint(void)
{
    Mock *mk = mock_new();
    attribute_conf(mk->conf);
    struct TermWinVtable vt = mock_termwin_vt;
    vt.setup_draw_ctx = selection_setup_draw;
    vt.draw_text = selection_draw_text;
    vt.free_draw_ctx = selection_free_draw;
    vt.set_cursor_pos = selection_set_cursor;
    vt.draw_trust_sigil = selection_draw_sigil;
    vt.char_width = selection_char_width;
    vt.set_synchronized_update = selection_sync;
    mk->tw.vt = &vt;
    mk->term = term_init(mk->conf, mk->ucsdata, &mk->tw);
    mk->ldisc = ldisc_create(mk->conf, mk->term, &mk->backend, &mk->seat);
    reset(mk);
    term_size(mk->term, 4, 12, 0);

    test_context(mk, "modes default off; special indices never alias defaults or cursor");
    IEQUAL(mk->term->attribute_colour_modes, 0);
    rgb saved[6];
    memcpy(saved, mk->term->palette+256, sizeof(saved));
    term_data_fragmented(mk->term,
        "\033]4;256;#112233;257;#445566;258;#778899;259;#aabbcc;260;#ddeeff\007");
    IEQUAL(memcmp(saved, mk->term->palette+256, sizeof(saved)), 0);
    IEQUAL(mk->term->palette_stack == NULL, true);
    for (unsigned i = 0; i < 5; i++) IEQUAL(mk->term->attribute_colours[i].enabled, true);

    static const unsigned sgr[] = {1, 4, 5, 7, 3};
    static const unsigned long flags[] = {ATTR_BOLD, ATTR_UNDER, ATTR_BLINK, ATTR_REVERSE, ATTR_ITALIC};
    static const unsigned colours[] = {0x112233, 0x445566, 0x778899, 0xaabbcc, 0xddeeff};
    for (unsigned i = 0; i < 5; i++) {
        char command[100];
        test_context(mk, "attribute mode %u uses colour and keeps stored SGR", i);
        sprintf(command, "\033]6;0;0;1;0;2;0;3;0;4;0;5;0\007\033]106;%u;1\007"
                "\033[?25l\033[1;1H\033[0;%umX", i, sgr[i]);
        term_data_fragmented(mk->term, command); term_update(mk->term);
        selection_check_display(mk, 0, i == 3 ? 0xffffff : colours[i], i == 3 ? colours[i] : 0);
        IEQUAL((mk->term->disptext[0]->chars[0].attr & flags[i]) != 0, false);
        termchar original = get_termchar(mk->term, 0, 0);
        IEQUAL((original.attr & flags[i]) != 0, true);
        IEQUAL(original.truecolour.fg.enabled, false);
        IEQUAL(original.truecolour.bg.enabled, false);
    }

    test_context(mk, "blink then bold then underline then italic priority");
    term_data_fragmented(mk->term, "\033]6;0;1;1;1;2;1;4;1\007"
        "\033[1;1H\033[0;1;3;4;5mX"); term_update(mk->term);
    selection_check_display(mk, 0, 0x778899, 0);
    term_data_fragmented(mk->term, "\033]6;2;0\007"); term_update(mk->term);
    selection_check_display(mk, 0, 0x112233, 0);
    term_data_fragmented(mk->term, "\033]6;0;0\007"); term_update(mk->term);
    selection_check_display(mk, 0, 0x445566, 0);
    term_data_fragmented(mk->term, "\033]6;1;0\007"); term_update(mk->term);
    selection_check_display(mk, 0, 0xddeeff, 0);

    test_context(mk, "explicit foreground survives until documented override mode 5");
    term_data_fragmented(mk->term,
        "\033]6;0;1;1;0;2;0;3;0;4;0\007\033[1;1H"
        "\033[0;1;38;2;18;52;86mX"); term_update(mk->term);
    selection_check_display(mk, 0, 0x123456, 0);
    term_data_fragmented(mk->term, "\033]106;5;1\007"); term_update(mk->term);
    selection_check_display(mk, 0, 0x112233, 0);
    term_data_fragmented(mk->term, "\033]6;5;0\007"); term_update(mk->term);
    selection_check_display(mk, 0, 0x123456, 0);
    term_data_fragmented(mk->term, "\033]4;1;#123456\007\033[1;1H\033[0;3;31mX"
        "\033]6;4;1\007"); term_update(mk->term);
    selection_check_display(mk, 0, 0x123456, 0);
    term_data_fragmented(mk->term, "\033]6;5;1\007"); term_update(mk->term);
    selection_check_display(mk, 0, 0xddeeff, 0);

    test_context(mk, "reverse mode replaces background without swapping explicit colours");
    term_data_fragmented(mk->term, "\033]6;0;0;3;1;4;0;5;0\007"
        "\033[1;1H\033[0;7;48;2;16;32;48mX"); term_update(mk->term);
    selection_check_display(mk, 0, 0xffffff, 0x102030);
    term_data_fragmented(mk->term, "\033]6;5;1\007"); term_update(mk->term);
    selection_check_display(mk, 0, 0xffffff, 0xaabbcc);
    term_data_fragmented(mk->term, "\033[?5h"); term_update(mk->term);
    selection_check_display(mk, 0, 0xaabbcc, 0xffffff);
    term_data_fragmented(mk->term, "\033[?5l\033]6;0;1;3;0;5;0\007");

    test_context(mk, "colour preferences can disable attribute overlays");
    term_data_fragmented(mk->term, "\033[1;1H\033[0;1mX"); term_update(mk->term);
    conf_set_bool(mk->conf, CONF_ansi_colour, false);
    term_reconfig(mk->term, mk->conf); term_update(mk->term);
    IEQUAL(mk->term->disptext[0]->chars[0].truecolour.fg.enabled, false);
    conf_set_bool(mk->conf, CONF_ansi_colour, true);
    term_reconfig(mk->term, mk->conf); term_update(mk->term);
    selection_check_display(mk, 0, 0x112233, 0);

    test_context(mk, "colour-mode updates repaint without modifying history cells");
    term_data_fragmented(mk->term, "\033[1;1H\033[0;1mX\033]6;5;0;4;0\007");
    term_update(mk->term);
    unsigned before = selection_draws;
    term_data_fragmented(mk->term, "\033[?2026h\033]5;0;red;0;?\007");
    reply(mk, "\033]5;0;rgb:ffff/0000/0000\007");
    term_update(mk->term); IEQUAL(selection_draws, before);
    selection_check_display(mk, 0, 0x112233, 0);
    term_data_fragmented(mk->term, "\033[?2026l"); term_update(mk->term);
    selection_check_display(mk, 0, 0xff0000, 0);

    test_context(mk, "selection overlays take precedence over attribute colours");
    term_data_fragmented(mk->term, "\033]17;#102030;;#405060\007");
    selection_select_row(mk);
    selection_check_display(mk, 0, 0x405060, 0x102030);
    mk->term->selstate = NO_SELECTION;
    term_invalidate(mk->term); term_update(mk->term);
    selection_check_display(mk, 0, 0xff0000, 0);

    test_context(mk, "palette restore leaves mode switches independent");
    term_data_fragmented(mk->term, "\033[1#P\033]6;0;0;1;1\007"
        "\033]5;0;blue\007\033[1#Q\033]5;0;?\007");
    reply(mk, "\033]5;0;rgb:ffff/0000/0000\007");
    IEQUAL(mk->term->attribute_colour_modes, 2);
    term_data_fragmented(mk->term, "\033c\033[!p\033[?1049h\033[?1049l");
    IEQUAL(mk->term->attribute_colour_modes, 2);
    term_data_fragmented(mk->term, "\033]105\007");
    IEQUAL(mk->term->attribute_colour_modes, 2);

    test_context(mk, "mode parser handles empty, missing, unknown and overflow fields");
    term_data_fragmented(mk->term, "\033]6;;1\007");
    IEQUAL(mk->term->attribute_colour_modes, 3);
    term_data_fragmented(mk->term, "\033]6;0;\007\033]106;0\007\033]6\007");
    IEQUAL(mk->term->attribute_colour_modes, 3);
    term_data_fragmented(mk->term, "\033]6;0;;1;0;9;1;4;4294967295\007");
    IEQUAL(mk->term->attribute_colour_modes, 16);
    term_data_fragmented(mk->term, "\033]6;4;4294967296\007\033]6;-1;0\007");
    IEQUAL(mk->term->attribute_colour_modes, 16);
    strbuf *overflow = strbuf_new();
    put_dataz(overflow, "\033]6;4;0;");
    for (unsigned i = 0; i < OSC_STR_MAX; i++) put_byte(overflow, '0');
    put_byte(overflow, '\007');
    term_data_fragmented(mk->term, overflow->s); strbuf_free(overflow);
    IEQUAL(mk->term->attribute_colour_modes, 16);
    const char binary[] = "\033]6;4;0\0;0;1\007";
    term_data(mk->term, binary, sizeof(binary)-1);
    IEQUAL(mk->term->attribute_colour_modes, 16);
    test_context(mk, "CAN and SUB discard attribute colour/mode writes");
    term_data_fragmented(mk->term, "\033]6;4;0\030\033]5;0;red\032");
    IEQUAL(mk->term->attribute_colour_modes, 16);
    IEQUAL(mk->term->attribute_colours[0].enabled, false);
    IEQUAL(mk->clipboard_writes, 0);

    bool failed = mk->any_test_failed;
    mock_free(mk);
    return failed;
}

static bool test_attribute_colour_settings(void)
{
    Mock *mk = mock_new();
    attribute_conf(mk->conf);
    conf_set_int(mk->conf, CONF_nemo_attribute_custom, 31);
    conf_set_int(mk->conf, CONF_nemo_attribute_modes, 1);
    conf_set_int(mk->conf, CONF_nemo_attribute_bold, 0x112233);
    conf_set_int(mk->conf, CONF_nemo_attribute_underline, 0x445566);
    conf_set_int(mk->conf, CONF_nemo_attribute_blink, 0x778899);
    conf_set_int(mk->conf, CONF_nemo_attribute_reverse, 0xaabbcc);
    conf_set_int(mk->conf, CONF_nemo_attribute_italic, 0xddeeff);
    struct TermWinVtable vt = mock_termwin_vt;
    vt.setup_draw_ctx = selection_setup_draw;
    vt.draw_text = selection_draw_text;
    vt.free_draw_ctx = selection_free_draw;
    vt.set_cursor_pos = selection_set_cursor;
    vt.draw_trust_sigil = selection_draw_sigil;
    vt.char_width = selection_char_width;
    vt.set_synchronized_update = selection_sync;
    mk->tw.vt = &vt;
    mk->term = term_init(mk->conf, mk->ucsdata, &mk->tw);
    mk->ldisc = ldisc_create(mk->conf, mk->term, &mk->backend, &mk->seat);
    reset(mk); term_size(mk->term, 4, 12, 0);

    test_context(mk, "saved defaults and mode apply at startup and survive protocol resets");
    IEQUAL(mk->term->attribute_colour_modes, 1);
    term_data_fragmented(mk->term, "\033]5;0;?;1;?;2;?;3;?;4;?\007");
    reply(mk, "\033]5;0;rgb:1111/2222/3333\007\033]5;1;rgb:4444/5555/6666\007"
              "\033]5;2;rgb:7777/8888/9999\007\033]5;3;rgb:aaaa/bbbb/cccc\007"
              "\033]5;4;rgb:dddd/eeee/ffff\007");
    term_data_fragmented(mk->term, "\033[?25l\033[1;1H\033[1mX"); term_update(mk->term);
    selection_check_display(mk, 0, 0x112233, 0);
    term_data_fragmented(mk->term, "\033]5;0;red\007\033]105;0\007"); term_update(mk->term);
    selection_check_display(mk, 0, 0x112233, 0);

    test_context(mk, "unrelated preferences preserve application colours and modes");
    term_data_fragmented(mk->term, "\033]5;0;red;1;blue\007\033]6;1;1\007");
    conf_set_int(mk->conf, CONF_savelines, conf_get_int(mk->conf, CONF_savelines)+1);
    term_reconfig(mk->term, mk->conf); term_update(mk->term);
    selection_check_display(mk, 0, 0xff0000, 0);
    IEQUAL(mk->term->attribute_colour_modes, 3);
    IEQUAL(mk->term->attribute_colours[1].enabled, true);

    test_context(mk, "editing one local colour clears only that override");
    conf_set_int(mk->conf, CONF_nemo_attribute_bold, 0xabcdef);
    term_reconfig(mk->term, mk->conf); term_update(mk->term);
    selection_check_display(mk, 0, 0xabcdef, 0);
    IEQUAL(mk->term->attribute_colours[0].enabled, false);
    IEQUAL(mk->term->attribute_colours[1].enabled, true);
    IEQUAL(mk->term->attribute_colour_modes, 3);
    conf_set_int(mk->conf, CONF_nemo_attribute_modes, 16);
    term_reconfig(mk->term, mk->conf);
    IEQUAL(mk->term->attribute_colour_modes, 18); /* unchanged app underline survives */

    test_context(mk, "retained styles combine with their configured colours");
    conf_set_int(mk->conf, CONF_nemo_attribute_modes, 31);
    conf_set_int(mk->conf, CONF_nemo_attribute_keep_styles, 31);
    term_reconfig(mk->term, mk->conf);
    static const unsigned sgr[] = {1, 4, 5, 7, 3};
    static const unsigned long flags[] = {ATTR_BOLD, ATTR_UNDER, ATTR_BLINK, ATTR_REVERSE, ATTR_ITALIC};
    for (unsigned i = 0; i < 5; i++) {
        char command[60];
        sprintf(command, "\033[1;1H\033[0;%umX", sgr[i]);
        term_data_fragmented(mk->term, command);
        /* Real blink is consumed after colour resolution by do_paint. */
        mk->term->blink_is_real = false;
        term_update(mk->term);
        IEQUAL((mk->term->disptext[0]->chars[0].attr & flags[i]) != 0, true);
        if (i == 3) selection_check_display(mk, 0, 0xaabbcc, 0xffffff);
    }
    conf_set_int(mk->conf, CONF_nemo_attribute_keep_styles, 0);
    term_reconfig(mk->term, mk->conf); term_update(mk->term);
    IEQUAL((mk->term->disptext[0]->chars[0].attr & ATTR_ITALIC) != 0, false);
    IEQUAL(mk->term->attribute_colours[1].enabled, true);

    test_context(mk, "saved unset palette entry follows newer local default");
    term_data_fragmented(mk->term, "\033]105;0\007\033[1#P\033]5;0;red\007");
    conf_set_int(mk->conf, CONF_nemo_attribute_bold, 0x102030);
    term_reconfig(mk->term, mk->conf);
    term_data_fragmented(mk->term, "\033[1#Q\033]5;0;?\007");
    reply(mk, "\033]5;0;rgb:1010/2020/3030\007");
    IEQUAL(mk->term->attribute_colours[0].enabled, false);
    conf_set_int(mk->conf, CONF_nemo_attribute_custom, 30);
    term_reconfig(mk->term, mk->conf);
    term_data_fragmented(mk->term, "\033]10;red\007\033]5;0;?\007");
    reply(mk, "\033]5;0;rgb:ffff/ffff/ffff\007");
    conf_set_int(mk->conf, CONF_nemo_attribute_custom, 31);
    term_reconfig(mk->term, mk->conf);
    term_data_fragmented(mk->term, "\033]5;0;?\007");
    reply(mk, "\033]5;0;rgb:1010/2020/3030\007");

    test_context(mk, "invalid persisted masks and colours fall back without enabling modes");
    conf_set_int(mk->conf, CONF_nemo_attribute_modes, -1);
    conf_set_int(mk->conf, CONF_nemo_attribute_keep_styles, 32);
    conf_set_int(mk->conf, CONF_nemo_attribute_custom, -1);
    conf_set_int(mk->conf, CONF_nemo_attribute_bold, -1);
    term_reconfig(mk->term, mk->conf);
    IEQUAL(mk->term->attribute_colour_modes, 0);
    IEQUAL(mk->term->attribute_keep_styles, 0);
    IEQUAL(mk->term->attribute_defaults[0].enabled, false);
    conf_set_int(mk->conf, CONF_nemo_attribute_custom, 1);
    term_reconfig(mk->term, mk->conf);
    term_data_fragmented(mk->term, "\033]5;0;?\007");
    reply(mk, "\033]5;0;rgb:ffff/ffff/ffff\007");
    IEQUAL(mk->clipboard_writes, 0);
    bool failed = mk->any_test_failed;
    mock_free(mk);
    return failed;
}
