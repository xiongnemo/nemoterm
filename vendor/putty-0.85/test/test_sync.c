/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main

#include "test_clock.h"

typedef struct FrameProbe {
    bool allow_begin, active;
    unsigned begins, ends, draws, draws_during_sync;
    wchar_t cells[8][20];
} FrameProbe;

static FrameProbe frame;

static bool sync_setup_draw(TermWin *win)
{
    Mock *mk = container_of(win, Mock, tw);
    return mk->term && mk->term->rows > 0 && mk->term->cols > 0;
}

static void sync_draw_text(TermWin *win, int x, int y, wchar_t *text, int len,
                           unsigned long attrs, int lattrs, truecolour tc)
{
    frame.draws++;
    if (frame.active)
        frame.draws_during_sync++;
    if (y < 0 || y >= (int)lenof(frame.cells))
        return;
    /* Test frames contain plain ASCII, so glyph and cell indices coincide. */
    for (int i = 0; i < len; i++)
        if (x + i >= 0 && x + i < (int)lenof(frame.cells[0]))
            /* PuTTY can hand its Windows renderer an ACP/OEM direct-font
             * marker. Both encodings map these ASCII bytes identically. */
            frame.cells[y][x + i] = DIRECT_FONT(text[i]) ?
                text[i] & 0xff : text[i];
}

static void sync_draw_cursor(TermWin *win, int x, int y, wchar_t *text, int len,
                             unsigned long attrs, int lattrs, truecolour tc)
{
    if (frame.active)
        frame.draws_during_sync++;
}

static int sync_char_width(TermWin *win, int character) { return 1; }
static void sync_draw_trust_sigil(TermWin *win, int x, int y) {}
static void sync_free_draw(TermWin *win) {}
static void sync_set_cursor(TermWin *win, int x, int y) {}
static void sync_refresh(TermWin *win) {}

static bool sync_set_update(TermWin *win, bool enabled)
{
    if (enabled) {
        frame.begins++;
        if (!frame.allow_begin)
            return false;
        frame.active = true;
    } else {
        frame.ends++;
        frame.active = false;
    }
    return true;
}

static void sync_reset(Mock *mk, const char *context)
{
    term_end_synchronized_update(mk->term);
    frame.allow_begin = true;
    reset(mk);
    term_size(mk->term, 4, 12, 0);
    term_data_fragmented(mk->term, "\033[?25l\033#5");
    term_update(mk->term);
    frame.begins = frame.ends = frame.draws = frame.draws_during_sync = 0;
    test_context(mk, "%s", context);
}

static void check_visible_word(Mock *mk, const wchar_t *word)
{
    for (size_t i = 0; word[i]; i++)
        IEQUAL(frame.cells[0][i], word[i]);
}

static void sync_query(Mock *mk, const char *expected)
{
    term_data_fragmented(mk->term, "\033[?2026$p");
    IEQUAL(mk->to_backend->len, strlen(expected));
    SEQUAL(mk->to_backend->s, expected);
    strbuf_clear(mk->to_backend);
}

static void test_parse_and_input_continue(Mock *mk)
{
    sync_reset(mk, "2026 preserves the visible frame while parsing and input continue");
    term_data_fragmented(mk->term, "OLD");
    term_update(mk->term);
    check_visible_word(mk, L"OLD");
    term_data_fragmented(mk->term, "\033[?2026h");
    IEQUAL(frame.begins, 1);
    IEQUAL(frame.active, true);
    unsigned draws_before = frame.draws;
    term_data_fragmented(mk->term, "\rNEW");
    IEQUAL(get_termchar(mk->term, 0, 0).chr, CSET_ASCII | 'N');
    IEQUAL(get_termchar(mk->term, 2, 0).chr, CSET_ASCII | 'W');
    sync_query(mk, "\033[?2026;1$y");
    term_keyinput(mk->term, -1, "x", 1);
    SEQUAL(mk->to_backend->s, "x");
    strbuf_clear(mk->to_backend);
    term_update(mk->term);
    term_paint(mk->term, 0, 0, 11, 3, true);
    term_paint(mk->term, 0, 0, 11, 3, false);
    IEQUAL(frame.draws, draws_before);
    IEQUAL(frame.draws_during_sync, 0);
    check_visible_word(mk, L"OLD");
    sync_query(mk, "\033[?2026;1$y");

    term_data_fragmented(mk->term, "\033[?2026l");
    IEQUAL(frame.ends, 1);
    IEQUAL(frame.active, false);
    term_update(mk->term);
    check_visible_word(mk, L"NEW");
    IEQUAL(frame.draws > draws_before, true);
    sync_query(mk, "\033[?2026;2$y");
    term_end_synchronized_update(mk->term);
    term_data_fragmented(mk->term, "\033[?2026l");
    IEQUAL(frame.ends, 1);
}

static void test_deadline_and_repeated_set(Mock *mk)
{
    sync_reset(mk, "1000 ms hard deadline is not renewed by repeated SET");
    term_data_fragmented(mk->term, "OLD\033[?2026h");
    check_visible_word(mk, L"OLD");
    unsigned long started = test_clock;
    unsigned long deadline = mk->term->synchronized_update_deadline;
    IEQUAL(deadline - started, 1000);
    advance_test_clock(started + 400);
    term_data_fragmented(mk->term, "\033[?2026h\rNEW");
    IEQUAL(frame.begins, 1);
    IEQUAL(mk->term->synchronized_update_deadline, deadline);
    advance_test_clock(deadline - 1);
    IEQUAL(frame.active, true);
    IEQUAL(frame.ends, 0);
    IEQUAL(frame.draws_during_sync, 0);
    check_visible_word(mk, L"OLD");
    sync_query(mk, "\033[?2026;1$y");
    advance_test_clock(deadline);
    IEQUAL(frame.active, false);
    IEQUAL(frame.ends, 1);
    sync_query(mk, "\033[?2026;2$y");
    term_update(mk->term);
    check_visible_word(mk, L"NEW");
    advance_test_clock(deadline + 1100);
    IEQUAL(frame.ends, 1);
}

static void test_stale_timer_does_not_end_new_frame(Mock *mk)
{
    sync_reset(mk, "an old frame's timer cannot end a subsequent frame");
    term_data_fragmented(mk->term, "\033[?2026h");
    unsigned long old_deadline = mk->term->synchronized_update_deadline;
    term_data_fragmented(mk->term, "\033[?2026l");
    advance_test_clock(test_clock + 400);
    term_data_fragmented(mk->term, "\033[?2026h");
    unsigned long new_deadline = mk->term->synchronized_update_deadline;
    IEQUAL(new_deadline - old_deadline, 400);
    advance_test_clock(old_deadline);
    IEQUAL(frame.active, true);
    IEQUAL(frame.ends, 1);
    sync_query(mk, "\033[?2026;1$y");
    advance_test_clock(new_deadline);
    IEQUAL(frame.active, false);
    IEQUAL(frame.ends, 2);
    sync_query(mk, "\033[?2026;2$y");
}

static void test_lifecycle_ends_frame(Mock *mk)
{
    sync_reset(mk, "resize ends a synchronized frame before changing dimensions");
    term_data_fragmented(mk->term, "OLD\033[?2026h\rNEW");
    term_size(mk->term, 5, 14, 0);
    IEQUAL(frame.ends, 1);
    IEQUAL(frame.active, false);
    IEQUAL(mk->term->rows, 5);
    IEQUAL(mk->term->cols, 14);
    sync_query(mk, "\033[?2026;2$y");
    term_update(mk->term);
    check_visible_word(mk, L"NEW");

    sync_reset(mk, "reconfiguration ends a synchronized frame");
    term_data_fragmented(mk->term, "OLD\033[?2026h\rNEW");
    term_reconfig(mk->term, mk->conf);
    IEQUAL(frame.ends, 1);
    IEQUAL(frame.active, false);
    sync_query(mk, "\033[?2026;2$y");
    term_update(mk->term);
    check_visible_word(mk, L"NEW");

    sync_reset(mk, "RIS releases the snapshot and resets synchronization");
    term_data_fragmented(mk->term, "OLD\033[?2026h\rNEW\033c");
    IEQUAL(frame.ends, 1);
    IEQUAL(frame.active, false);
    sync_query(mk, "\033[?2026;2$y");
    term_update(mk->term);
    check_visible_word(mk, L"   ");

    sync_reset(mk, "explicit shutdown helper releases a frame once");
    term_data_fragmented(mk->term, "OLD\033[?2026h\rNEW");
    term_end_synchronized_update(mk->term);
    term_end_synchronized_update(mk->term);
    IEQUAL(frame.ends, 1);
    IEQUAL(frame.active, false);
    sync_query(mk, "\033[?2026;2$y");
    term_update(mk->term);
    check_visible_word(mk, L"NEW");
}

static void test_frontend_capability_and_failure(Mock *mk,
                                                struct TermWinVtable *vt)
{
    sync_reset(mk, "failed frontend snapshot leaves output and mode usable");
    frame.allow_begin = false;
    term_data_fragmented(mk->term, "OLD\033[?2026h\rNEW");
    IEQUAL(frame.begins, 1);
    IEQUAL(frame.active, false);
    IEQUAL(frame.ends, 0);
    sync_query(mk, "\033[?2026;2$y");
    term_update(mk->term);
    check_visible_word(mk, L"NEW");
    term_data_fragmented(mk->term, "\033[?2026l");
    IEQUAL(frame.ends, 0);

    sync_reset(mk, "frontends without snapshot support report 2026 unknown");
    vt->set_synchronized_update = NULL;
    sync_query(mk, "\033[?2026;0$y");
    term_data_fragmented(mk->term, "OLD\033[?2026h\rNEW");
    IEQUAL(frame.begins, 0);
    sync_query(mk, "\033[?2026;0$y");
    term_update(mk->term);
    check_visible_word(mk, L"NEW");
    vt->set_synchronized_update = sync_set_update;
}

int main(void)
{
    Mock *mk = mock_new();
    struct TermWinVtable vt = mock_termwin_vt;
    vt.setup_draw_ctx = sync_setup_draw;
    vt.draw_text = sync_draw_text;
    vt.draw_cursor = sync_draw_cursor;
    vt.char_width = sync_char_width;
    vt.draw_trust_sigil = sync_draw_trust_sigil;
    vt.free_draw_ctx = sync_free_draw;
    vt.set_cursor_pos = sync_set_cursor;
    vt.refresh = sync_refresh;
    vt.set_synchronized_update = sync_set_update;
    mk->tw.vt = &vt;
    frame.allow_begin = true;
    mk->term = term_init(mk->conf, mk->ucsdata, &mk->tw);
    mk->ldisc = ldisc_create(mk->conf, mk->term, &mk->backend, &mk->seat);

    test_parse_and_input_continue(mk);
    test_deadline_and_repeated_set(mk);
    test_stale_timer_does_not_end_new_frame(mk);
    test_lifecycle_ends_frame(mk);
    test_frontend_capability_and_failure(mk, &vt);

    bool failed = mk->any_test_failed;
    mock_free(mk);
    for (size_t i = 0; i < lenof(test_timers); i++) {
        if (test_timers[i].active) {
            fputs("Live timer remained after terminal destruction\n", stderr);
            failed = true;
        }
    }
    puts(failed ? "Synchronized output test suite FAILED!" :
                 "Synchronized output test suite passed");
    return failed ? 1 : 0;
}
