/* Included by test_osc_colour.c: no windows or system clipboard are used. */
#include "../../../tests/selection_colour_cases.h"

static unsigned selection_draws;
static bool selection_setup_draw(TermWin *win)
{
    Mock *mk = container_of(win, Mock, tw);
    /* reset() powers on before the first term_size(). A real frontend has
     * no drawable grid at that point; do not paint the -1 size sentinel. */
    return mk->term && mk->term->rows > 0 && mk->term->cols > 0;
}
static void selection_draw_text(TermWin *win, int x, int y, wchar_t *text,
                                int len, unsigned long attr, int lattr,
                                truecolour tc) { selection_draws++; }
static void selection_free_draw(TermWin *win) {}
static void selection_set_cursor(TermWin *win, int x, int y) {}
static void selection_draw_sigil(TermWin *win, int x, int y) {}
static int selection_char_width(TermWin *win, int ch) { return 1; }
static bool selection_sync(TermWin *win, bool enabled) { return true; }

static void selection_check_rgb(Mock *mk, rgb colour, unsigned expected)
{
    IEQUAL(colour.r, (expected >> 16) & 255);
    IEQUAL(colour.g, (expected >> 8) & 255);
    IEQUAL(colour.b, expected & 255);
}

/* Resolve the display record, not the original screen cell. Tests use plain
 * text without dim/bold, for which the frontend applies exactly this swap. */
static void selection_check_display(Mock *mk, int x, unsigned fg, unsigned bg)
{
    termchar *ch = &mk->term->disptext[0]->chars[x];
    unsigned indices[] = {(ch->attr & ATTR_FGMASK) >> ATTR_FGSHIFT,
                          (ch->attr & ATTR_BGMASK) >> ATTR_BGSHIFT};
    optionalrgb overrides[] = {ch->truecolour.fg, ch->truecolour.bg};
    rgb colours[2];
    for (unsigned i = 0; i < 2; i++) {
        optionalrgb c = overrides[i];
        colours[i] = c.enabled ? (rgb){c.r, c.g, c.b} : mk->term->palette[indices[i]];
    }
    bool reverse = (ch->attr & ATTR_REVERSE) != 0;
    selection_check_rgb(mk, colours[reverse ? 1 : 0], fg);
    selection_check_rgb(mk, colours[reverse ? 0 : 1], bg);
}

static void selection_select_row(Mock *mk)
{
    mk->term->selstate = SELECTED;
    mk->term->seltype = LEXICOGRAPHIC;
    mk->term->selstart = (pos){0, 0};
    mk->term->selend = (pos){4, 0};
    term_invalidate(mk->term);
    term_update(mk->term);
}

static bool test_selection_colour_wire(void)
{
    bool failed = false;
    for (size_t i = 0; i < lenof(selection_colour_cases); i++) {
        Mock *mk = mock_new();
        mk->term = term_init(mk->conf, mk->ucsdata, &mk->tw);
        mk->ldisc = ldisc_create(mk->conf, mk->term, &mk->backend, &mk->seat);
        reset(mk);
        test_context(mk, "authored selection colour: %s", selection_colour_cases[i].name);
        term_data_fragmented(mk->term, selection_colour_cases[i].sequence);
        reply(mk, selection_colour_cases[i].reply);
        failed |= mk->any_test_failed;
        mock_free(mk);
    }
    return failed;
}

static bool test_selection_colour_paint(void)
{
    Mock *mk = mock_new();
    for (int i = 0; i < 3; i++) {
        conf_set_int_int(mk->conf, CONF_colours, CONF_COLOUR_fg*3+i, 255);
        conf_set_int_int(mk->conf, CONF_colours, CONF_COLOUR_bg*3+i, 0);
    }
    conf_set_bool(mk->conf, CONF_true_colour, true);
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

    test_context(mk, "default selection queries are allocation-free and use configured colours");
    term_data_fragmented(mk->term, "\033]17;?\007\033]19;?\033\\");
    reply(mk, "\033]17;rgb:ffff/ffff/ffff\007\033]19;rgb:0000/0000/0000\033\\");
    IEQUAL(mk->term->palette_stack == NULL, true);
    IEQUAL(mk->term->selection_colours[0].enabled, false);
    IEQUAL(mk->term->selection_colours[1].enabled, false);
    term_data_fragmented(mk->term,
        "\033]10;red;blue\007\033]17;?\007\033]19;?\007");
    reply(mk, "\033]17;rgb:ffff/ffff/ffff\007\033]19;rgb:0000/0000/0000\007");

    test_context(mk, "display overrides preserve screen cells, styles and unselected text");
    term_data_fragmented(mk->term, "\033%G\033[?25l\033[1;1H"
        "\033[38;2;16;32;48;48;2;64;80;96mABCDE");
    termchar original = get_termchar(mk->term, 0, 0);
    selection_select_row(mk);
    selection_check_display(mk, 0, 0x405060, 0x102030);
    term_data_fragmented(mk->term, "\033]17;#112233\007\033]19;#445566\007");
    term_update(mk->term);
    selection_check_display(mk, 0, 0x445566, 0x112233);
    selection_check_display(mk, 4, 0x102030, 0x405060);
    termchar unchanged = get_termchar(mk->term, 0, 0);
    IEQUAL(unchanged.attr, original.attr);
    IEQUAL(truecolour_equal(unchanged.truecolour, original.truecolour), true);
    IEQUAL(unchanged.chr, original.chr);
    IEQUAL(mk->clipboard_writes, 0);

    test_context(mk, "partial reset restores only the specified selection component");
    term_data_fragmented(mk->term, "\033]117;ignored\007");
    term_update(mk->term);
    selection_check_display(mk, 0, 0x445566, 0x102030);
    IEQUAL(mk->term->selection_colours[0].enabled, false);
    IEQUAL(mk->term->selection_colours[1].enabled, true);
    term_data_fragmented(mk->term, "\033]119\033\\");
    term_update(mk->term);
    selection_check_display(mk, 0, 0x405060, 0x102030);

    test_context(mk, "palette pop restores unset selection components, not fixed fallback RGB");
    term_data_fragmented(mk->term, "\033[1#P\033]17;red;;blue\007\033[1#Q");
    term_update(mk->term);
    IEQUAL(mk->term->selection_colours[0].enabled, false);
    IEQUAL(mk->term->selection_colours[1].enabled, false);
    selection_check_display(mk, 0, 0x405060, 0x102030);

    test_context(mk, "SGR and screen reverse do not swap explicit displayed selection colours");
    term_data_fragmented(mk->term, "\033]17;#112233;;#445566\007\033[?5h");
    term_update(mk->term);
    selection_check_display(mk, 0, 0x445566, 0x112233);
    term_data_fragmented(mk->term, "\033[?5l\033[1;1H\033[7mABCDE");
    selection_select_row(mk);
    selection_check_display(mk, 0, 0x445566, 0x112233);
    term_data_fragmented(mk->term, "\033[1;1H\033[27mABCDE");
    selection_select_row(mk);

    test_context(mk, "2026 freezes selection colours while queries see pending changes");
    unsigned before = selection_draws;
    term_data_fragmented(mk->term, "\033[?2026h\033]17;red;;blue\007"
        "\033]17;?;;?\007");
    reply(mk, "\033]17;rgb:ffff/0000/0000\007\033]19;rgb:0000/0000/ffff\007");
    term_update(mk->term);
    IEQUAL(selection_draws, before);
    selection_check_display(mk, 0, 0x445566, 0x112233);
    term_data_fragmented(mk->term, "\033[?2026l");
    term_update(mk->term);
    IEQUAL(selection_draws > before, true);
    selection_check_display(mk, 0, 0x0000ff, 0xff0000);

    test_context(mk, "rectangular and application highlight selection share display colours");
    mk->term->seltype = RECTANGULAR;
    mk->term->selstart = (pos){1, 0};
    mk->term->selend = (pos){3, 1};
    term_invalidate(mk->term); term_update(mk->term);
    selection_check_display(mk, 0, 0x102030, 0x405060);
    selection_check_display(mk, 1, 0x0000ff, 0xff0000);
    mk->term->selstate = NO_SELECTION;
    mk->term->mouse_highlight = HIGHLIGHT_ACTIVE;
    mk->term->highlight_start = (pos){1, 0};
    mk->term->highlight_end = (pos){3, 0};
    term_invalidate(mk->term); term_update(mk->term);
    selection_check_display(mk, 1, 0x0000ff, 0xff0000);
    mk->term->mouse_highlight = HIGHLIGHT_OFF;

    test_context(mk, "resizing and repeated stack restoration preserve selection overrides");
    term_size(mk->term, 6, 20, 0);
    selection_select_row(mk);
    selection_check_display(mk, 0, 0x0000ff, 0xff0000);
    term_data_fragmented(mk->term, "\033[1#P");
    for (unsigned i = 0; i < 1000; i++)
        term_data_fragmented(mk->term, "\033]17;green;;white\007\033[1#Q");
    term_update(mk->term);
    selection_check_display(mk, 0, 0x0000ff, 0xff0000);

    test_context(mk, "overlong OSC cannot partially replace selection colours");
    strbuf *longosc = strbuf_new();
    put_dataz(longosc, "\033]17;blue;");
    for (unsigned i = 0; i < OSC_STR_MAX; i++) put_byte(longosc, 'x');
    put_dataz(longosc, ";red\007");
    term_data_fragmented(mk->term, longosc->s);
    strbuf_free(longosc);
    term_update(mk->term);
    selection_check_display(mk, 0, 0x0000ff, 0xff0000);

    test_context(mk, "configured colours apply live and are returned by queries");
    conf_set_bool(mk->conf, CONF_nemo_selection_bg_enabled, true);
    conf_set_bool(mk->conf, CONF_nemo_selection_fg_enabled, true);
    conf_set_int(mk->conf, CONF_nemo_selection_bg, 0x0a2030);
    conf_set_int(mk->conf, CONF_nemo_selection_fg, 0xfefdfc);
    term_reconfig(mk->term, mk->conf);
    term_update(mk->term);
    selection_check_display(mk, 0, 0xfefdfc, 0x0a2030);
    IEQUAL(mk->term->selection_colours[0].enabled, false);
    IEQUAL(mk->term->selection_colours[1].enabled, false);
    term_data_fragmented(mk->term, "\033]17;?;;?\007");
    reply(mk, "\033]17;rgb:0a0a/2020/3030\007\033]19;rgb:fefe/fdfd/fcfc\007");

    test_context(mk, "unrelated reconfiguration preserves application selection colours");
    term_data_fragmented(mk->term, "\033]17;#123456;;#654321\007");
    conf_set_bool(mk->conf, CONF_no_dbackspace, true);
    term_reconfig(mk->term, mk->conf);
    term_update(mk->term);
    selection_check_display(mk, 0, 0x654321, 0x123456);
    IEQUAL(mk->term->selection_colours[0].enabled, true);
    IEQUAL(mk->term->selection_colours[1].enabled, true);

    test_context(mk, "changing one configured colour leaves the other application override");
    conf_set_int(mk->conf, CONF_nemo_selection_bg, 0xabcdef);
    term_reconfig(mk->term, mk->conf);
    term_update(mk->term);
    selection_check_display(mk, 0, 0x654321, 0xabcdef);
    IEQUAL(mk->term->selection_colours[0].enabled, false);
    IEQUAL(mk->term->selection_colours[1].enabled, true);
    term_data_fragmented(mk->term, "\033]17;red;;blue\007\033]117\007\033]119\007");
    term_update(mk->term);
    selection_check_display(mk, 0, 0xfefdfc, 0xabcdef);

    test_context(mk, "stack default-state restoration follows the current local preferences");
    term_data_fragmented(mk->term, "\033[1#P\033]17;red;;blue\007");
    conf_set_int(mk->conf, CONF_nemo_selection_bg, 0x112244);
    conf_set_bool(mk->conf, CONF_nemo_selection_fg_enabled, false);
    term_reconfig(mk->term, mk->conf);
    term_data_fragmented(mk->term, "\033[1#Q");
    term_update(mk->term);
    selection_check_display(mk, 0, 0x405060, 0x112244);
    IEQUAL(mk->term->selection_defaults[1].enabled, false);

    test_context(mk, "malformed persisted RGB values fall back without overflow or aliasing");
    conf_set_int(mk->conf, CONF_nemo_selection_bg, -1);
    conf_set_int(mk->conf, CONF_nemo_selection_fg, 0x1000000);
    conf_set_bool(mk->conf, CONF_nemo_selection_fg_enabled, true);
    term_reconfig(mk->term, mk->conf);
    term_update(mk->term);
    selection_check_display(mk, 0, 0x000000, 0xffffff);
    term_data_fragmented(mk->term, "\033]17;?;;?\033\\");
    reply(mk, "\033]17;rgb:ffff/ffff/ffff\033\\\033]19;rgb:0000/0000/0000\033\\");
    IEQUAL(mk->clipboard_writes, 0);

    bool failed = mk->any_test_failed;
    mock_free(mk);
    return failed;
}
