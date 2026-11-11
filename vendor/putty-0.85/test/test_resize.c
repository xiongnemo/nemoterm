/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main

static const char *unicode_text = "A\xe4\xb8\xad" "e\xcc\x81Z";

static void check_unicode_cells(Mock *mk, int x, int y, bool check_tail)
{
    IEQUAL(get_termchar(mk->term, x, y).chr & ~CSET_MASK, 'A');
    IEQUAL(get_termchar(mk->term, x + 1, y).chr, 0x4e2d);
    IEQUAL(get_termchar(mk->term, x + 2, y).chr, UCSWIDE);
    IEQUAL(get_termchar(mk->term, x + 3, y).chr & ~CSET_MASK, 'e');
    termline *line = term_get_line(mk->term, y);
    int combining = line->chars[x + 3].cc_next;
    IEQUAL(combining != 0, true);
    if (combining && x + 3 + combining < line->size) {
        IEQUAL(line->chars[x + 3 + combining].chr, 0x301);
        IEQUAL(line->chars[x + 3 + combining].cc_next, 0);
    }
    term_release_line(line);
    if (check_tail)
        IEQUAL(get_termchar(mk->term, x + 4, y).chr & ~CSET_MASK, 'Z');
}

static void select_unicode(Mock *mk, int x, int y)
{
    int clipboard = CLIP_LOCAL + 1;
    term_mouse(mk->term, MBT_LEFT, MBT_SELECT, MA_CLICK, x, y, true, false, false);
    term_mouse(mk->term, MBT_LEFT, MBT_SELECT, MA_DRAG, x + 4, y, true, false, false);
    term_mouse(mk->term, MBT_LEFT, MBT_SELECT, MA_RELEASE, x + 4, y, true, false, false);
    IEQUAL(mk->term->selstate, SELECTED);
    mk->clipboard_writes = 0;
    term_request_copy(mk->term, &clipboard, 1);
    check_clipboard(mk, L"A\x4e2d" L"e\x0301Z");
}

static void test_unicode_width_resize(Mock *mk)
{
    reset(mk);
    test_context(mk, "resize retains CJK width and combining chains");
    mk->ucsdata->line_codepage = CP_UTF8;
    term_size(mk->term, 6, 10, 100);
    term_data_fragmented(mk->term, unicode_text);
    check_unicode_cells(mk, 0, 0, true);
    select_unicode(mk, 0, 0);
    term_size(mk->term, 3, 4, 100);
    IEQUAL(mk->term->rows, 3); IEQUAL(mk->term->cols, 4);
    IEQUAL(mk->term->curs.x, 3); IEQUAL(mk->term->curs.y, 0);
    IEQUAL(mk->term->selstate, NO_SELECTION);
    check_unicode_cells(mk, 0, 0, false);
    /* Existing PuTTY semantics are clipping, not reflow. Untouched tails
     * become visible again when enlarged. Clipboard contents survive. */
    term_size(mk->term, 6, 12, 100);
    check_unicode_cells(mk, 0, 0, true);
    IEQUAL(wcscmp(mk->clipboard_text, L"A\x4e2d" L"e\x0301Z"), 0);
    select_unicode(mk, 0, 0);
    /* Repeating width changes must preserve linked combining characters. */
    for (unsigned i = 0; i < 40; i++) {
        term_size(mk->term, 6, 4, 100);
        check_unicode_cells(mk, 0, 0, false);
        term_size(mk->term, 6, 12, 100);
        check_unicode_cells(mk, 0, 0, true);
    }
}

static void test_height_history_resize(Mock *mk)
{
    reset(mk);
    test_context(mk, "height shrink restores temporary scrollback on grow");
    mk->ucsdata->line_codepage = CP_UTF8;
    term_size(mk->term, 6, 10, 100);
    term_data_fragmented(mk->term, unicode_text);
    term_data_fragmented(mk->term, "\033[2;1Htwo\033[3;1Hthree\033[4;1Hfour"
                                  "\033[5;1Hfive\033[6;1Hsix");
    term_size(mk->term, 3, 6, 100);
    IEQUAL(mk->term->curs.y, 2);
    IEQUAL(mk->term->tempsblines, 3);
    IEQUAL(count234(mk->term->scrollback), 3);
    IEQUAL(get_termchar(mk->term, 0, 0).chr & ~CSET_MASK, 'f');
    term_size(mk->term, 6, 10, 100);
    IEQUAL(mk->term->curs.y, 5);
    IEQUAL(mk->term->tempsblines, 0);
    IEQUAL(count234(mk->term->scrollback), 0);
    check_unicode_cells(mk, 0, 0, true);
    IEQUAL(get_termchar(mk->term, 0, 5).chr & ~CSET_MASK, 's');
}

static void test_alternate_screen_resize(Mock *mk)
{
    reset(mk);
    test_context(mk, "main and alternate grids/cursors survive resize");
    mk->ucsdata->line_codepage = CP_UTF8;
    term_size(mk->term, 6, 12, 100);
    term_data_fragmented(mk->term, "\033[3;2H");
    term_data_fragmented(mk->term, unicode_text);
    term_data_fragmented(mk->term, "\033[?1049h\033[2;3H");
    term_data_fragmented(mk->term, unicode_text);
    IEQUAL(mk->term->curs.x, 7); IEQUAL(mk->term->curs.y, 1);
    term_size(mk->term, 4, 8, 100);
    IEQUAL(mk->term->alt_which, 1);
    IEQUAL(mk->term->curs.x, 7); IEQUAL(mk->term->curs.y, 1);
    check_unicode_cells(mk, 2, 1, true);
    term_size(mk->term, 6, 12, 100);
    IEQUAL(mk->term->curs.x, 7); IEQUAL(mk->term->curs.y, 1);
    check_unicode_cells(mk, 2, 1, true);
    term_data_fragmented(mk->term, "\033[?1049l");
    IEQUAL(mk->term->alt_which, 0);
    IEQUAL(mk->term->curs.x, 6); IEQUAL(mk->term->curs.y, 2);
    check_unicode_cells(mk, 1, 2, true);
    /* Preserve an inactive alternate grid too; mode 47 does not clear it. */
    term_size(mk->term, 5, 10, 100);
    term_data_fragmented(mk->term, "\033[?47h");
    check_unicode_cells(mk, 2, 1, true);
    IEQUAL(mk->term->curs.x, 7); IEQUAL(mk->term->curs.y, 1);
    /* Growing main history must not shift an unrelated alternate cursor. */
    term_data_fragmented(mk->term, "\033[?47l\033[5;1H");
    term_size(mk->term, 3, 10, 100);
    term_size(mk->term, 5, 10, 100);
    term_data_fragmented(mk->term, "\033[?47h");
    check_unicode_cells(mk, 2, 1, true);
    IEQUAL(mk->term->curs.x, 7); IEQUAL(mk->term->curs.y, 1);
}

int main(void)
{
    Mock *mk = mock_new();
    mk->term = term_init(mk->conf, mk->ucsdata, &mk->tw);
    mk->ldisc = ldisc_create(mk->conf, mk->term, &mk->backend, &mk->seat);
    test_unicode_width_resize(mk);
    test_height_history_resize(mk);
    test_alternate_screen_resize(mk);
    bool failed = mk->any_test_failed;
    mock_free(mk);
    puts(failed ? "Resize suite FAILED" : "Resize suite passed");
    return failed ? 1 : 0;
}
