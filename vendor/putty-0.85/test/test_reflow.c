/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main

static void reflow_setup(Mock *mk, const char *name, int rows, int cols)
{
    reset(mk);
    test_context(mk, "%s", name);
    mk->ucsdata->line_codepage = CP_UTF8;
    term_size(mk->term, rows, cols, 2000);
}

static void row(Mock *mk, int y, const char *text, bool wrapped)
{
    termline *line = term_get_line(mk->term, y);
    for (int x = 0; text[x]; x++)
        IEQUAL(line->chars[x].chr & ~CSET_MASK, (unsigned char)text[x]);
    IEQUAL(!!(line->lattr & LATTR_WRAPPED), wrapped);
    term_release_line(line);
}

static void test_text_and_cursor(Mock *mk)
{
    reflow_setup(mk, "soft wraps join; hard breaks and delayed wrap survive", 8, 8);
    term_data_fragmented(mk->term, "abcdefghijklmno\r\nHARD\r\n12345678\0337");
    term_size(mk->term, 8, 4, 2000);
    row(mk, 0, "abcd", true); row(mk, 1, "efgh", true);
    row(mk, 2, "ijkl", true); row(mk, 3, "mno", false);
    row(mk, 4, "HARD", false);
    row(mk, 5, "1234", true); row(mk, 6, "5678", false);
    IEQUAL(mk->term->curs.x, 3); IEQUAL(mk->term->curs.y, 6);
    IEQUAL(mk->term->wrapnext, true);
    term_size(mk->term, 8, 16, 2000);
    row(mk, 0, "abcdefghijklmno", false); row(mk, 1, "HARD", false);
    row(mk, 2, "12345678", false);
    IEQUAL(mk->term->curs.x, 8); IEQUAL(mk->term->curs.y, 2);
    IEQUAL(mk->term->wrapnext, false);
    term_data_fragmented(mk->term, "\033[H\0338Z");
    row(mk, 2, "12345678Z", false);

    reflow_setup(mk, "cursor on unpainted blank column remains addressable", 6, 12);
    term_data_fragmented(mk->term, "a\033[3;10H\0337");
    term_size(mk->term, 8, 4, 2000);
    IEQUAL(mk->term->curs.y, 4); IEQUAL(mk->term->curs.x, 1);
    term_data_fragmented(mk->term, "X");
    row(mk, 4, " X", false);

    reflow_setup(mk, "top cursor stays visible when content below expands", 6, 12);
    term_data_fragmented(mk->term, "top\r\nabcdefghijkl\r\nmnopqrstuvwx\033[H");
    term_size(mk->term, 3, 4, 2000);
    IEQUAL(mk->term->curs.y, 0); IEQUAL(mk->term->curs.x, 0);
    row(mk, 0, "top", false); row(mk, 1, "abcd", true); row(mk, 2, "efgh", true);
}

static void test_unicode_attributes_selection(Mock *mk)
{
    reflow_setup(mk, "wide pairs, combining chains, colours and OSC8 move together", 8, 8);
    term_data_fragmented(mk->term,
        "ab\033[38;2;1;2;3;4:3;58;2;4;5;6m\033]8;;https://example.org/\033\\"
        "\xe4\xb8\xad" "e\xcc\x81Z\033]8;;\033\\\033[0m");
    termchar original = get_termchar(mk->term, 2, 0);
    for (int iteration = 0; iteration < 20; iteration++) {
        term_size(mk->term, 8, 3, 2000);
        row(mk, 0, "ab ", true);
        termline *line = term_get_line(mk->term, 0);
        IEQUAL(!!(line->lattr & LATTR_WRAPPED2), true);
        term_release_line(line);
        IEQUAL(get_termchar(mk->term, 0, 1).chr, 0x4e2d);
        IEQUAL(get_termchar(mk->term, 1, 1).chr, UCSWIDE);
        line = term_get_line(mk->term, 1);
        IEQUAL(line->chars[0].attr, original.attr);
        IEQUAL(line->chars[0].hyperlink, original.hyperlink);
        IEQUAL(memcmp(&line->chars[0].truecolour, &original.truecolour, sizeof(truecolour)), 0);
        IEQUAL(line->chars[2].chr & ~CSET_MASK, 'e');
        IEQUAL(line->chars[2].cc_next != 0, true);
        if (line->chars[2].cc_next)
            IEQUAL(line->chars[2 + line->chars[2].cc_next].chr, 0x301);
        term_release_line(line);
        term_data_fragmented(mk->term, "\033[?1003h\033[?1006h");
        strbuf_clear(mk->to_backend);
        term_mouse(mk->term, MBT_LEFT, MBT_SELECT, MA_CLICK, 0, 0, true, false, false);
        term_mouse(mk->term, MBT_LEFT, MBT_SELECT, MA_DRAG, 0, 2, true, false, false);
        term_mouse(mk->term, MBT_LEFT, MBT_SELECT, MA_RELEASE, 0, 2, true, false, false);
        int clip = CLIP_LOCAL+1;
        mk->clipboard_writes = 0;
        term_request_copy(mk->term, &clip, 1);
        check_clipboard(mk, L"ab\x4e2d" L"e\x301Z");
        IEQUAL(mk->to_backend->len, 0);
        term_size(mk->term, 8, 8, 2000);
        IEQUAL(get_termchar(mk->term, 2, 0).chr, 0x4e2d);
        IEQUAL(get_termchar(mk->term, 5, 0).chr & ~CSET_MASK, 'Z');
    }
    term_size(mk->term, 8, 1, 2000);
    IEQUAL(get_termchar(mk->term, 0, 2).chr, 0x4e2d);
    term_size(mk->term, 8, 8, 2000);
    IEQUAL(get_termchar(mk->term, 2, 0).chr, 0x4e2d);
    IEQUAL(get_termchar(mk->term, 3, 0).chr, UCSWIDE);

    reflow_setup(mk, "trailing styled spaces survive hard-line trimming", 6, 8);
    term_data_fragmented(mk->term, "x\033[41m   \033[0m\r\nnext");
    termchar space = get_termchar(mk->term, 3, 0);
    term_size(mk->term, 6, 2, 2000);
    IEQUAL(get_termchar(mk->term, 1, 1).attr, space.attr);
    term_size(mk->term, 6, 8, 2000);
    IEQUAL(get_termchar(mk->term, 3, 0).attr, space.attr);
    row(mk, 1, "next", false);
}

static void test_history_and_alternate(Mock *mk)
{
    reflow_setup(mk, "width-only resize does not resurrect history after clear", 4, 12);
    term_data_fragmented(mk->term, "old\r\nold\r\nold\r\nold\r\nold\033[2J\033[Hprompt");
    IEQUAL(count234(mk->term->scrollback) > 0, true);
    term_size(mk->term, 4, 8, 2000);
    row(mk, 0, "prompt", false);
    IEQUAL(mk->term->curs.y, 0);
    term_size(mk->term, 4, 16, 2000);
    row(mk, 0, "prompt", false);
    IEQUAL(mk->term->curs.y, 0);

    reflow_setup(mk, "history boundary joins soft wraps and keeps scrolled viewport", 3, 8);
    term_data_fragmented(mk->term, "abcdefghijklmnopqrstuvwxyz0123456789");
    IEQUAL(count234(mk->term->scrollback), 2);
    mk->term->disptop = -1;
    term_size(mk->term, 3, 4, 2000);
    IEQUAL(count234(mk->term->scrollback), 6);
    IEQUAL(mk->term->disptop, -4);
    row(mk, -6, "abcd", true); row(mk, -4, "ijkl", true);
    row(mk, 0, "yz01", true); row(mk, 2, "6789", false);
    term_size(mk->term, 3, 16, 2000);
    IEQUAL(count234(mk->term->scrollback), 0);
    row(mk, 0, "abcdefghijklmnop", true);
    row(mk, 1, "qrstuvwxyz012345", true); row(mk, 2, "6789", false);
    IEQUAL(mk->term->curs.x, 4); IEQUAL(mk->term->curs.y, 2);

    term_data_fragmented(mk->term, "\033[?1049h\033[2;2HGRID");
    term_size(mk->term, 3, 8, 2000);
    row(mk, 1, " GRID", false);
    IEQUAL(mk->term->curs.x, 5); IEQUAL(mk->term->curs.y, 1);
    term_data_fragmented(mk->term, "\033[?1049l");
    IEQUAL(mk->term->curs.x, 4); IEQUAL(mk->term->curs.y, 2);
    row(mk, 0, "qrstuvwx", true); row(mk, 2, "6789", false);
    term_size(mk->term, 3, 4, 0);
    IEQUAL(count234(mk->term->scrollback), 0);
    row(mk, 0, "yz01", true); row(mk, 2, "6789", false);
}

static void test_fixed_rows(Mock *mk)
{
    reflow_setup(mk, "Sixel rows move vertically without splitting or resampling", 12, 12);
    term_data_fragmented(mk->term, "abcdefghijkl\r\n\033[?80l"
        "\033P0;1q\"1;1;16;32#1;2;100;0;0!16~\033\\\033[5;1HEND");
    NemoTermImage *im = mk->term->images;
    IEQUAL(im != NULL, true);
    if (!im) return;
    size_t bytes = mk->term->image_bytes;
    uint32_t before[16], after[16];
    term_image_read_row(im, 0, 0, before, 16);
    term_size(mk->term, 12, 4, 2000);
    IEQUAL(term_image_pixel_y(im, 0, mk->term->cell_height), 3*16);
    IEQUAL(term_image_pixel_y(im, 31, mk->term->cell_height), 3*16+31);
    IEQUAL(mk->term->image_bytes, bytes);
    term_image_read_row(im, 0, 0, after, 16);
    IEQUAL(memcmp(before, after, sizeof(before)), 0);
    row(mk, 6, "END", false);
    term_size(mk->term, 12, 12, 2000);
    IEQUAL(term_image_pixel_y(im, 0, mk->term->cell_height), 16);

    reflow_setup(mk, "DEC double-size lines retain grid and clipped tails", 8, 10);
    term_data_fragmented(mk->term, "abcdefghij\r\n\033#6WIDE\r\nplain");
    term_size(mk->term, 8, 3, 2000);
    termline *line = term_get_line(mk->term, 4);
    IEQUAL(line->lattr & LATTR_MODE, LATTR_WIDE);
    IEQUAL(line->chars[3].chr & ~CSET_MASK, 'E');
    term_release_line(line);
    term_size(mk->term, 8, 10, 2000);
    row(mk, 1, "WIDE", false); row(mk, 2, "plain", false);
}

static void test_large_history(Mock *mk)
{
    reflow_setup(mk, "long logical lines stream through bounded compressed history", 10, 80);
    term_size(mk->term, 10, 80, 12000);
    for (int i = 0; i < 10000; i++)
        term_data_fragmented(mk->term, "01234567890123456789012345678901234567890123456789012345678901234567890123456789");
    for (int i = 0; i < 6; i++) {
        term_size(mk->term, 10, i%2 ? 80 : 5, 12000);
        IEQUAL(count234(mk->term->scrollback) <= 12000, true);
        IEQUAL(count234(mk->term->screen), 10);
        IEQUAL(mk->term->curs.y, 9);
        int last = mk->term->curs.x - !mk->term->wrapnext;
        IEQUAL(last >= 0, true);
        if (last >= 0) IEQUAL(get_termchar(mk->term, last, 9).chr & ~CSET_MASK, '9');
    }
}

static void trim_copy_terminator(wchar_t *text)
{
    /* Copy All adds a final line terminator when the final hard line has
     * unused columns. It omits that terminator at the right margin. */
    size_t n = wcslen(text);
    while (n && (text[n-1] == '\r' || text[n-1] == '\n')) text[--n] = 0;
}

static void test_copy_roundtrip(Mock *mk)
{
    reflow_setup(mk, "copy of mixed paragraphs is invariant across many widths", 7, 19);
    for (int p = 0; p < 5; p++) {
        if (p) term_data_fragmented(mk->term, "\r\n");
        for (int j = 0; j < 13+p; j++)
            term_data_fragmented(mk->term, "ab\xe4\xb8\xad" "e\xcc\x81Z");
    }
    int clip = CLIP_LOCAL+1;
    term_copyall(mk->term, &clip, 1);
    trim_copy_terminator(mk->clipboard_text);
    size_t bytes = (wcslen(mk->clipboard_text)+1)*sizeof(wchar_t);
    wchar_t *expected = snewn(bytes / sizeof(wchar_t), wchar_t);
    memcpy(expected, mk->clipboard_text, bytes);
    for (int i = 0; i < 40; i++) {
        term_size(mk->term, 7+i%5, 1+(i*17)%43, 2000);
        term_copyall(mk->term, &clip, 1);
        trim_copy_terminator(mk->clipboard_text);
        if (wcscmp(mk->clipboard_text, expected)) {
            size_t at = 0;
            while (mk->clipboard_text[at] && expected[at] == mk->clipboard_text[at]) at++;
            printf("roundtrip %d cols=%d cursor=%d,%d wrap=%d length=%zu expected=%zu first=%zu actual=%x expected=%x\n",
                   i, mk->term->cols, mk->term->curs.y, mk->term->curs.x, mk->term->wrapnext,
                   wcslen(mk->clipboard_text), wcslen(expected), at, mk->clipboard_text[at], expected[at]);
        }
        IEQUAL(wcscmp(mk->clipboard_text, expected), 0);
    }
    sfree(expected);
}

int main(void)
{
    Mock *mk = mock_new();
    mk->term = term_init(mk->conf, mk->ucsdata, &mk->tw);
    mk->ldisc = ldisc_create(mk->conf, mk->term, &mk->backend, &mk->seat);
    test_text_and_cursor(mk);
    test_unicode_attributes_selection(mk);
    test_history_and_alternate(mk);
    test_fixed_rows(mk);
    test_copy_roundtrip(mk);
    test_large_history(mk);
    bool failed = mk->any_test_failed;
    mock_free(mk);
    puts(failed ? "Reflow suite FAILED" : "Reflow suite passed");
    return failed ? 1 : 0;
}
