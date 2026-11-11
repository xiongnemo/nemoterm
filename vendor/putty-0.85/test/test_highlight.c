/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main
#include "test_clock.h"

static void bytes(Mock *mk, const char *s)
{
    size_t n = strlen(s);
    if (n != mk->to_backend->len || memcmp(s, mk->to_backend->s, n)) {
        report_fail(mk, __FILE__, __LINE__, "highlight bytes differ (%zu expected, %zu actual)", n, mk->to_backend->len);
        for (size_t i = 0; i < mk->to_backend->len; i++) printf("%02x ", (unsigned char)mk->to_backend->s[i]);
        puts("");
    }
    strbuf_clear(mk->to_backend);
}

static void mouse(Mock *mk, Mouse_Action a, int x, int y, bool shift)
{
    term_mouse_pixels(mk->term, MBT_LEFT, MBT_SELECT, a, x, y,
                      x*8+3, y*16+7, shift, false, false);
}

static void setup(Mock *mk, const char *context, int encoding)
{
    reset(mk); test_context(mk, "%s", context);
    term_set_cell_size(mk->term, 8, 16);
    char seq[64];
    snprintf(seq, sizeof(seq), "\033[?1001h\033[?%dh", encoding);
    term_data_fragmented(mk->term, seq);
}

static void start(Mock *mk)
{
    mouse(mk, MA_CLICK, 2, 3, false);
    IEQUAL(mk->term->mouse_highlight, HIGHLIGHT_WAIT);
    strbuf_clear(mk->to_backend);
    term_data_fragmented(mk->term, "\033[1;3;4;2;8T");
    IEQUAL(mk->term->mouse_highlight, HIGHLIGHT_ACTIVE);
}

static void test_coordinates(Mock *mk)
{
    static const struct {int encoding; const char *press, *simple, *reverse;} modes[] = {
        {0, "\033[M #$", "\033[t)$", "\033[T!$#$!$"},
        {1005, "\033[M #$", "\033[t)$", "\033[T!$#$!$"},
        {1006, "\033[<0;3;4M", "\033[<9;4t", "\033[<1;4;3;4;1;4T"},
        {1015, "\033[32;3;4M", "\033[9;4t", "\033[1;4;3;4;1;4T"},
        {1016, "\033[<0;20;56M", "\033[<9;4t", "\033[<1;4;3;4;1;4T"},
    };
    for (size_t i = 0; i < lenof(modes); i++) {
        setup(mk, "encoding, simple and reverse completion", modes[i].encoding);
        mouse(mk, MA_CLICK, 2, 3, false); bytes(mk, modes[i].press);
        mouse(mk, MA_DRAG, 4, 3, false); bytes(mk, "");
        term_data_fragmented(mk->term, "\033[1;3;4;2;8T");
        IEQUAL(mk->term->highlight_end.x, 4); /* queued motion survives handshake */
        mouse(mk, MA_DRAG, 8, 3, false); bytes(mk, "");
        IEQUAL(mk->term->highlight_start.x, 2);
        IEQUAL(mk->term->highlight_end.x, 8);
        IEQUAL(mk->term->selstate, NO_SELECTION);
        mouse(mk, MA_RELEASE, 8, 3, false); bytes(mk, modes[i].simple);
        IEQUAL(mk->term->mouse_highlight, HIGHLIGHT_OFF);
        IEQUAL(mk->term->mouse_buttons, 0);
        IEQUAL(mk->clipboard_writes, 0);
        start(mk);
        mouse(mk, MA_RELEASE, 0, 3, false); bytes(mk, modes[i].reverse);
    }
    setup(mk, "exclusive last row and clamped viewport endpoints", 1006);
    start(mk);
    mouse(mk, MA_DRAG, 500, 100, false);
    IEQUAL(mk->term->highlight_end.x, 80);
    IEQUAL(mk->term->highlight_end.y, 6);
    mouse(mk, MA_RELEASE, 500, 100, false); bytes(mk, "\033[<81;7t");
    start(mk); mouse(mk, MA_RELEASE, 2, 3, false); bytes(mk, "");
    setup(mk, "UTF8 large coordinates", 1005);
    term_size(mk->term, 24, 300, 0); start(mk);
    mouse(mk, MA_RELEASE, 250, 3, false); bytes(mk, "\033[t\xc4\x9b$");
    setup(mk, "legacy out of range is not truncated", 0);
    term_size(mk->term, 24, 300, 0); start(mk);
    mouse(mk, MA_RELEASE, 250, 3, false); bytes(mk, "");
}

static void test_content_and_multiclick(Mock *mk)
{
    setup(mk, "wide and combining characters are whole glyphs", 1006);
    term_data_fragmented(mk->term, "\033%G\033[4;1Hab\xe4\xb8\xad" "e\xcc\x81" "xyz");
    start(mk);
    mouse(mk, MA_DRAG, 3, 3, false); /* second cell of Chinese glyph */
    IEQUAL(mk->term->highlight_mouse.x, 2);
    mouse(mk, MA_RELEASE, 5, 3, false); bytes(mk, "\033[<6;4t");
    IEQUAL(get_termchar(mk->term, 3, 3).chr, UCSWIDE);
    setup(mk, "word/line expansion needs no second host handshake", 1006);
    term_data_fragmented(mk->term, "\033[4;1Hone two three");
    mouse(mk, MA_2CLK, 5, 3, false);
    IEQUAL(mk->term->highlight_start.x, 4);
    IEQUAL(mk->term->highlight_end.x, 7);
    bytes(mk, "");
    mouse(mk, MA_RELEASE, 5, 3, false); bytes(mk, "\033[<5;4;8;4;6;4T");
    mouse(mk, MA_3CLK, 5, 3, false);
    IEQUAL(mk->term->highlight_start.x, 0);
    IEQUAL(mk->term->highlight_end.x, 80);
    mouse(mk, MA_RELEASE, 5, 3, false); bytes(mk, "\033[<1;4;81;4;6;4T");
    IEQUAL(mk->clipboard_writes, 0);
    setup(mk, "word expansion follows wrapped rows", 1006);
    term_size(mk->term, 4, 10, 0);
    term_data_fragmented(mk->term, "abcdefghijkl");
    mouse(mk, MA_2CLK, 8, 0, false);
    IEQUAL(mk->term->highlight_start.x, 0);
    IEQUAL(mk->term->highlight_start.y, 0);
    IEQUAL(mk->term->highlight_end.x, 2);
    IEQUAL(mk->term->highlight_end.y, 1);
    mouse(mk, MA_RELEASE, 8, 0, false); bytes(mk, "\033[<1;1;3;2;9;1T");
    setup(mk, "double-width terminal line uses rendered viewport columns", 1006);
    term_data_fragmented(mk->term, "\033[4;1H\033#6abcdef");
    mouse(mk, MA_CLICK, 3, 3, false); strbuf_clear(mk->to_backend);
    term_data_fragmented(mk->term, "\033[1;4;4;1;25T");
    IEQUAL(mk->term->highlight_anchor.x, 2);
    mouse(mk, MA_RELEASE, 9, 3, false); bytes(mk, "\033[<9;4t");
}

static void test_cancellation(Mock *mk)
{
    setup(mk, "host abort, invalid range and stale handshake", 1006);
    mouse(mk, MA_CLICK, 2, 3, false); strbuf_clear(mk->to_backend);
    term_data_fragmented(mk->term, "\033[0T");
    IEQUAL(mk->term->mouse_highlight, HIGHLIGHT_OFF);
    mouse(mk, MA_RELEASE, 4, 3, false); bytes(mk, "\033[<0;5;4m");
    mouse(mk, MA_CLICK, 2, 3, false); strbuf_clear(mk->to_backend);
    term_data_fragmented(mk->term, "\033[1;3;4;10;3T");
    mouse(mk, MA_RELEASE, 4, 3, false); bytes(mk, "\033[<0;5;4m");
    term_data_fragmented(mk->term, "\033[1;3;4;1;25T");
    IEQUAL(mk->term->mouse_highlight, HIGHLIGHT_OFF);
    term_data_fragmented(mk->term, "\033[4;1HABCDEFGHIJKLMNOP");
    start(mk);
    mouse(mk, MA_DRAG, 8, 3, false);
    mouse(mk, MA_DRAG, 9, 3, true); bytes(mk, "\033[<9;4t");
    IEQUAL(mk->term->selstate, ABOUT_TO);
    mouse(mk, MA_DRAG, 12, 3, true);
    mouse(mk, MA_RELEASE, 12, 3, true); bytes(mk, "");
    IEQUAL(mk->term->selstate, SELECTED);
    int clipboard = CLIP_LOCAL+1;
    term_request_copy(mk->term, &clipboard, 1);
    check_clipboard(mk, L"JKLM");
    for (int kind = 0; kind < 8; kind++) {
        setup(mk, "lifecycle cancels highlight without stale pixels or duplicate replies", 1006);
        start(mk); mouse(mk, MA_DRAG, 8, 3, false);
        switch (kind) {
          case 0: term_mouse_cancel(mk->term); break;
          case 1: term_set_focus(mk->term, false); break;
          case 2: term_size(mk->term, 30, 100, 0); break;
          case 3: term_set_cell_size(mk->term, 9, 18); break;
          case 4: term_scroll(mk->term, -1, 0); break;
          case 5: term_data_fragmented(mk->term, "\033[?1049h"); break;
          case 6: term_reconfig(mk->term, mk->conf); break;
          case 7: term_data_fragmented(mk->term, "\033[?1005h"); break;
        }
        bytes(mk, "\033[<9;4t");
        IEQUAL(mk->term->mouse_highlight, HIGHLIGHT_OFF);
        mouse(mk, MA_RELEASE, 8, 3, false); bytes(mk, "");
    }
    setup(mk, "mode reset and RIS discard highlight", 1006);
    start(mk); term_data_fragmented(mk->term, "\033[?1000h");
    IEQUAL(mk->term->mouse_highlight, HIGHLIGHT_OFF); bytes(mk, "");
    term_data_fragmented(mk->term, "\033[?1001h"); start(mk);
    term_data_fragmented(mk->term, "\033c");
    IEQUAL(mk->term->mouse_highlight, HIGHLIGHT_OFF); bytes(mk, "");
}

static void test_timer_and_parser(Mock *mk)
{
    setup(mk, "one-second handshake deadline, old timer isolation", 1006);
    mouse(mk, MA_CLICK, 2, 3, false); bytes(mk, "\033[<0;3;4M");
    unsigned long first = mk->term->mouse_highlight_deadline;
    term_data_fragmented(mk->term, "\033[1;1Hlive");
    IEQUAL(get_termchar(mk->term, 0, 0).chr, CSET_ASCII|'l');
    advance_test_clock(first-1);
    IEQUAL(mk->term->mouse_highlight, HIGHLIGHT_WAIT);
    advance_test_clock(first);
    bytes(mk, "\033[<0;3;4m");
    IEQUAL(mk->term->mouse_highlight, HIGHLIGHT_OFF);
    term_data_fragmented(mk->term, "\033[1;3;4;1;25T");
    IEQUAL(mk->term->mouse_highlight, HIGHLIGHT_OFF);
    mouse(mk, MA_CLICK, 2, 3, false); strbuf_clear(mk->to_backend);
    unsigned long old = mk->term->mouse_highlight_deadline;
    advance_test_clock(old-100);
    mouse(mk, MA_RELEASE, 2, 3, false); bytes(mk, "\033[<0;3;4m");
    mouse(mk, MA_CLICK, 2, 3, false); strbuf_clear(mk->to_backend);
    unsigned long deadline = mk->term->mouse_highlight_deadline;
    advance_test_clock(old);
    IEQUAL(mk->term->mouse_highlight, HIGHLIGHT_WAIT);
    term_data_fragmented(mk->term, "\033[1;3;4;1;25T");
    advance_test_clock(deadline);
    IEQUAL(mk->term->mouse_highlight, HIGHLIGHT_ACTIVE);
    mouse(mk, MA_RELEASE, 8, 3, false); bytes(mk, "\033[<9;4t");
    term_data_fragmented(mk->term, "\033[?1001$p\033[?1000$p");
    bytes(mk, "\033[?1001;1$y\033[?1000;2$y");
    /* Unsolicited multi-parameter T must never become a scroll command. */
    term_data_fragmented(mk->term, "\033[1;1HX\033[4;1;2;3;4T\033[2;3T");
    IEQUAL(get_termchar(mk->term, 0, 0).chr, CSET_ASCII|'X');
    term_data_fragmented(mk->term, "\033[1T");
    IEQUAL(get_termchar(mk->term, 0, 1).chr, CSET_ASCII|'X');
}

static bool accept_sync(TermWin *win, bool enabled)
{
    return true;
}

static void test_sync_and_configuration(Mock *mk)
{
    setup(mk, "highlight motion releases synchronized presentation", 1006);
    start(mk);
    term_data_fragmented(mk->term, "\033[?2026h");
    IEQUAL(mk->term->synchronized_update, true);
    mouse(mk, MA_DRAG, 8, 3, false);
    IEQUAL(mk->term->synchronized_update, false);
    IEQUAL(mk->term->mouse_highlight, HIGHLIGHT_ACTIVE);
    conf_set_bool(mk->conf, CONF_no_mouse_rep, true);
    term_reconfig(mk->term, mk->conf); bytes(mk, "\033[<9;4t");
    term_data_fragmented(mk->term, "\033[?1001$p"); bytes(mk, "\033[?1001;4$y");
    mouse(mk, MA_CLICK, 2, 3, false);
    IEQUAL(mk->term->mouse_highlight, HIGHLIGHT_OFF);
    bytes(mk, "");
}

int main(void)
{
    Mock *mk = mock_new();
    struct TermWinVtable vt = mock_termwin_vt;
    vt.set_synchronized_update = accept_sync;
    mk->tw.vt = &vt;
    mk->term = term_init(mk->conf, mk->ucsdata, &mk->tw);
    mk->ldisc = ldisc_create(mk->conf, mk->term, &mk->backend, &mk->seat);
    test_coordinates(mk);
    test_content_and_multiclick(mk);
    test_cancellation(mk);
    test_timer_and_parser(mk);
    test_sync_and_configuration(mk);
    bool failed = mk->any_test_failed;
    mock_free(mk);
    for (size_t i = 0; i < lenof(test_timers); i++) if (test_timers[i].active) failed = true;
    puts(failed ? "Highlight suite FAILED" : "Highlight suite passed");
    return failed ? 1 : 0;
}
