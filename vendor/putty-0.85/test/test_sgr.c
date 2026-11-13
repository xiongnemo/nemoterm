/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main

static void check_rgb(Mock *mk, optionalrgb rgb, int r, int g, int b)
{
    IEQUAL(rgb.enabled, true);
    IEQUAL(rgb.r, r); IEQUAL(rgb.g, g); IEQUAL(rgb.b, b);
}

static void test_extended_colours(Mock *mk)
{
    static const char *forms[] = {
        "38;2;17;34;51;48;2;68;85;102",
        "38:2:17:34:51;48:2:68:85:102",
        "38:2::17:34:51;48:2:0:68:85:102",
        "38;2::17:34:51;48;2:68:85:102"
    };
    for (size_t i = 0; i < lenof(forms); i++) {
        reset(mk); test_context(mk, "RGB form %s", forms[i]);
        char sequence[128];
        snprintf(sequence, sizeof(sequence), "\033[%smA", forms[i]);
        term_data_fragmented(mk->term, sequence);
        termchar tc = get_termchar(mk->term, 0, 0);
        check_rgb(mk, tc.truecolour.fg, 17, 34, 51);
        check_rgb(mk, tc.truecolour.bg, 68, 85, 102);
        IEQUAL(tc.attr & (ATTR_BOLD | ATTR_DIM | ATTR_ITALIC | ATTR_BLINK), 0);
    }
    reset(mk); test_context(mk, "indexed colours, independent underline colour");
    term_data_fragmented(mk->term, "\033[38:5:123;48;5;234;58:5:5;4:3mX");
    termchar tc = get_termchar(mk->term, 0, 0);
    IEQUAL(tc.attr & ATTR_FGMASK, 123);
    IEQUAL((tc.attr & ATTR_BGMASK) >> ATTR_BGSHIFT, 234);
    IEQUAL(tc.truecolour.fg.enabled, false); IEQUAL(tc.truecolour.bg.enabled, false);
    IEQUAL(tc.truecolour.decoration, UINT32_C(0x0d000005));
    term_data_fragmented(mk->term, "\033[58;2;12;34;56mY\033[59mZ");
    IEQUAL(get_termchar(mk->term, 1, 0).truecolour.decoration, UINT32_C(0x0e0c2238));
    IEQUAL(get_termchar(mk->term, 2, 0).truecolour.decoration, UINT32_C(0x0c000000));
}

static void test_styles(Mock *mk)
{
    for (unsigned style = 0; style <= 5; style++) {
        reset(mk); test_context(mk, "underline style %u", style);
        char sequence[48];
        snprintf(sequence, sizeof(sequence), "\033[4:%umX\033[24mY", style);
        term_data_fragmented(mk->term, sequence);
        termchar tc = get_termchar(mk->term, 0, 0);
        IEQUAL(!!(tc.attr & ATTR_UNDER), style != 0);
        IEQUAL(UNDER_STYLE(tc.truecolour), style);
        tc = get_termchar(mk->term, 1, 0);
        IEQUAL(tc.attr & ATTR_UNDER, 0); IEQUAL(tc.truecolour.decoration, 0);
    }
    reset(mk); test_context(mk, "italic conceal resets and double underline");
    term_data_fragmented(mk->term,
        "\033[3;8;21;58:2::255:0:0mA\033[23;28;24mB\033[0mC");
    termchar tc = get_termchar(mk->term, 0, 0);
    IEQUAL(tc.attr & (ATTR_ITALIC | ATTR_CONCEAL | ATTR_UNDER),
           ATTR_ITALIC | ATTR_CONCEAL);
    IEQUAL(!!(tc.truecolour.decoration & UNDER_DOUBLE_LEGACY), true);
    IEQUAL(UNDER_STYLE(tc.truecolour), 2);
    tc = get_termchar(mk->term, 1, 0);
    IEQUAL(tc.attr & (ATTR_ITALIC | ATTR_CONCEAL | ATTR_UNDER), 0);
    IEQUAL(tc.truecolour.decoration, UINT32_C(0x02ff0000));
    IEQUAL(get_termchar(mk->term, 2, 0).truecolour.decoration, 0);
    reset(mk); test_context(mk, "VT52 underline overrides previous modern style");
    term_data_fragmented(mk->term, "\033[4:3m\033[?2l\033SA\033WB");
    IEQUAL(UNDER_STYLE(get_termchar(mk->term, 0, 0).truecolour), 1);
    IEQUAL(UNDER_STYLE(get_termchar(mk->term, 1, 0).truecolour), 0);
    IEQUAL(get_termchar(mk->term, 1, 0).attr & ATTR_UNDER, 0);
    term_data_fragmented(mk->term, "\033<");
    IEQUAL(mk->term->vt52_mode, false);
}

static void test_invalid_groups(Mock *mk)
{
    static const char *invalid[] = {
        "38:2::1::3", "38:2:1:2", "38:2::1:2:256", "38:5:256",
        "38:5:", "38:2:1:2:3:4:5", "38;2;1;2", "38;5;9999999999999",
        "38;2;1:2;3;4", "48:5:999", "58:2::1:2:999", "1:2", "0:1"
    };
    for (size_t i = 0; i < lenof(invalid); i++) {
        reset(mk); test_context(mk, "invalid colour/group %s", invalid[i]);
        term_data_fragmented(mk->term, "\033[32;4:3m");
        unsigned long attr = mk->term->curr_attr;
        truecolour colour = mk->term->curr_truecolour;
        char sequence[128];
        snprintf(sequence, sizeof(sequence), "\033[%sm", invalid[i]);
        term_data_fragmented(mk->term, sequence);
        IEQUAL(mk->term->curr_attr, attr);
        IEQUAL(truecolour_equal(mk->term->curr_truecolour, colour), true);
    }
    reset(mk); test_context(mk, "unknown underline group is isolated");
    term_data_fragmented(mk->term, "\033[4:3m\033[4:7;31mX\033[4:;32mY");
    IEQUAL(UNDER_STYLE(get_termchar(mk->term, 0, 0).truecolour), 3);
    IEQUAL(UNDER_STYLE(get_termchar(mk->term, 1, 0).truecolour), 3);
    IEQUAL(get_termchar(mk->term, 1, 0).attr & ATTR_FGMASK, 2);
    reset(mk); test_context(mk, "subparameters cannot become cursor arguments");
    term_data_fragmented(mk->term, "\033[5:6H\033[2:3;5HX");
    IEQUAL(get_termchar(mk->term, 0, 0).chr & ~CSET_MASK, 'X');
    reset(mk); test_context(mk, "argument overflow rejects entire SGR");
    term_data_fragmented(mk->term, "\033[");
    for (int i = 0; i < 40; i++) term_data_fragmented(mk->term, "1;");
    term_data_fragmented(mk->term, "3mX\033[31mY");
    IEQUAL(get_termchar(mk->term, 0, 0).attr, ATTR_DEFAULT);
    IEQUAL(get_termchar(mk->term, 1, 0).attr & ATTR_FGMASK, 1);
    reset(mk); test_context(mk, "subparameter overflow and cancellation recover");
    term_data_fragmented(mk->term, "\033[4:3:1:1:1:1:1:1:1:1;31mX");
    IEQUAL(get_termchar(mk->term, 0, 0).attr, ATTR_DEFAULT);
    term_data_fragmented(mk->term, "\033[38:2::1:2\030Y\033[3mZ");
    IEQUAL(get_termchar(mk->term, 1, 0).attr, ATTR_DEFAULT);
    IEQUAL(get_termchar(mk->term, 2, 0).attr & ATTR_ITALIC, ATTR_ITALIC);
    term_data_fragmented(mk->term, "\033[0m\033[38:2::1\032W");
    IEQUAL(get_termchar(mk->term, 3, 0).chr & ~CSET_MASK, 'W');
    IEQUAL(get_termchar(mk->term, 3, 0).attr, ATTR_DEFAULT);
}

static void test_style_lifetime(Mock *mk)
{
    reset(mk); test_context(mk, "style colour survives compressed history");
    term_size(mk->term, 4, 20, 100);
    mk->ucsdata->line_codepage = CP_UTF8;
    term_data_fragmented(mk->term, "\033[3;8;4:5;21;38:2::1:2:3;58:5:123m"
                                  "A\xe4\xb8\xad" "e\xcc\x81\033[0m");
    termchar original = get_termchar(mk->term, 0, 0);
    IEQUAL(UNDER_STYLE_RAW(original.truecolour), 5);
    IEQUAL(UNDER_STYLE(original.truecolour), 2);
    IEQUAL(!!(original.truecolour.decoration & UNDER_DOUBLE_LEGACY), true);
    term_data_fragmented(mk->term, "\r\none\r\ntwo\r\nthree\r\nfour");
    IEQUAL(count234(mk->term->scrollback), 1);
    termchar history = get_termchar(mk->term, 0, -1);
    IEQUAL(history.attr, original.attr);
    IEQUAL(truecolour_equal(history.truecolour, original.truecolour), true);
    IEQUAL(get_termchar(mk->term, 1, -1).chr, 0x4e2d);
    IEQUAL(get_termchar(mk->term, 2, -1).chr, UCSWIDE);
    term_size(mk->term, 3, 10, 100);
    term_size(mk->term, 4, 20, 100);
    history = get_termchar(mk->term, 0, -1);
    IEQUAL(history.attr, original.attr);
    IEQUAL(truecolour_equal(history.truecolour, original.truecolour), true);

    reset(mk); test_context(mk, "saved cursor, alternate screen and erase style");
    term_data_fragmented(mk->term, "\033[3;4:3;58:2::4:5:6m\0337"
                                  "\033[0m\0338A\033[?1049h\033[0mB\033[?1049lC");
    IEQUAL(get_termchar(mk->term, 0, 0).attr & ATTR_ITALIC, ATTR_ITALIC);
    IEQUAL(get_termchar(mk->term, 1, 0).truecolour.decoration, UINT32_C(0x0e040506));
    term_data_fragmented(mk->term, "\033[X");
    IEQUAL(get_termchar(mk->term, 2, 0).truecolour.decoration, 0);
    IEQUAL(get_termchar(mk->term, 2, 0).attr & (ATTR_ITALIC | ATTR_UNDER), 0);
    term_mouse(mk->term, MBT_LEFT, MBT_SELECT, MA_CLICK, 0, 0, true, false, false);
    term_mouse(mk->term, MBT_LEFT, MBT_SELECT, MA_DRAG, 1, 0, true, false, false);
    term_mouse(mk->term, MBT_LEFT, MBT_SELECT, MA_RELEASE, 1, 0, true, false, false);
    int clipboard = CLIP_LOCAL+1;
    term_request_copy(mk->term, &clipboard, 1);
    check_clipboard(mk, L"AC");
    term_data_fragmented(mk->term, "\033c");
    IEQUAL(mk->term->curr_truecolour.decoration, 0);
    IEQUAL(mk->term->curr_attr, ATTR_DEFAULT);
}

int main(void)
{
    Mock *mk = mock_new();
    mk->term = term_init(mk->conf, mk->ucsdata, &mk->tw);
    mk->ldisc = ldisc_create(mk->conf, mk->term, &mk->backend, &mk->seat);
    test_extended_colours(mk);
    test_styles(mk);
    test_invalid_groups(mk);
    test_style_lifetime(mk);
    bool failed = mk->any_test_failed;
    mock_free(mk);
    puts(failed ? "SGR suite FAILED" : "SGR suite passed");
    return failed ? 1 : 0;
}
