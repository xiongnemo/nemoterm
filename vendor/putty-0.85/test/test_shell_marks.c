/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main

static bool mark(NemoShellMarks *m, unsigned osc, const char *s, int x, int y)
{ return nemo_shell_marks_update(m, osc, s, strlen(s), x, y); }

static void shell_setup(Mock *mk, const char *name, int rows, int cols, int history)
{
    reset(mk); test_context(mk, "%s", name);
    mk->ucsdata->line_codepage = CP_UTF8;
    term_clrsb(mk->term);
    term_size(mk->term, rows, cols, history);
    term_data_fragmented(mk->term, "\033[2J\033[H\033%G");
}

static void copy_range(Mock *mk, bool output, const wchar_t *expected)
{
    IEQUAL(term_shell_mark_select(mk->term, output), true);
    int clip = CLIP_LOCAL+1;
    mk->clipboard_writes = 0;
    term_request_copy(mk->term, &clip, 1);
    check_clipboard(mk, expected);
}

static void test_protocol(Mock *mk)
{
    test_context(mk, "bounded shell state, duplicates and missing events");
    NemoShellMarks m = {0}; NemoShellPoint a, b;
    IEQUAL(nemo_shell_marks_memory(&m), 0);
    IEQUAL(mark(&m, 133, "D;0", 0, 0), true); IEQUAL(m.count, 0);
    mark(&m, 133, "A", 0, 0); uint64_t id = m.active_id;
    mark(&m, 133, "B", 2, 0); mark(&m, 133, "A", 0, 0);
    IEQUAL(m.count, 1); IEQUAL(m.active_id == id, true);
    IEQUAL(m.commands[0].point[1].valid, false);
    mark(&m, 133, "B;ignored", 2, 0); mark(&m, 133, "C", 8, 0);
    mark(&m, 133, "C", 0, 2); IEQUAL(m.commands[0].point[2].x, 8);
    IEQUAL(nemo_shell_marks_range(&m.commands[0], false, 0, 10, &a, &b), true);
    IEQUAL(a.x, 2); IEQUAL(b.x, 8);
    IEQUAL(nemo_shell_marks_range(&m.commands[0], true, 0, 10, &a, &b), false);
    mark(&m, 133, "D;-9223372036854775808", 0, 3);
    IEQUAL(m.commands[0].exit_known, true);
    IEQUAL(m.commands[0].exit_code == INT64_MIN, true);
    IEQUAL(nemo_shell_marks_range(&m.commands[0], true, 0, 10, &a, &b), true);
    mark(&m, 633, "E;echo\\x3b\\\\\\xE4\\xB8\\xAD;untrusted-nonce", 0, 4);
    mark(&m, 633, "A", 0, 4);
    SEQUAL(m.commands[1].text, "echo;\\\xe4\xb8\xad");
    mark(&m, 633, "B", 2, 4); mark(&m, 633, "C", 6, 4);
    mark(&m, 633, "A", 0, 5);
    IEQUAL(m.commands[1].finished, true); IEQUAL(m.commands[1].exit_known, false);
    IEQUAL(mark(&m, 633, "P;IsWindows=True", 0, 5), true); IEQUAL(m.is_windows, true);
    IEQUAL(mark(&m, 633, "P;HasRichCommandDetection=True", 0, 5), true);
    IEQUAL(m.rich_detection, true);
    IEQUAL(mark(&m, 633, "P;IsWindows=False", 0, 5), true); IEQUAL(m.is_windows, false);
    id = m.active_id;
    mark(&m, 1337, "SetMark", 0, 6); IEQUAL(m.active_id == id, true);
    IEQUAL(nemo_shell_marks_range(&m.commands[m.count-1], true, 0, 10, &a, &b), false);
    mark(&m, 633, "D;9223372036854775808", 0, 7);
    IEQUAL(nemo_shell_marks_lookup(&m, id)->exit_known, false);
    nemo_shell_marks_clear(&m); IEQUAL(nemo_shell_marks_memory(&m), 0);

    const char *codes[] = {"D", "D;", "D;bad", "D;0", "D;+42", "D;-42", "D;9223372036854775807"};
    for (size_t i = 0; i < lenof(codes); i++) {
        mark(&m, 133, "C", 0, 0); mark(&m, 133, codes[i], 2, 0);
        IEQUAL(m.commands[m.count-1].finished, true);
        IEQUAL(m.commands[m.count-1].exit_known, i >= 3);
    }
    nemo_shell_marks_clear(&m);
}

static void test_clipped_navigation(Mock *mk)
{
    test_context(mk, "navigation falls back to retained command/output anchors");
    NemoShellMarks m = {0}; NemoShellPoint p;
    mark(&m, 133, "A", 0, 0); mark(&m, 133, "B", 2, 1);
    mark(&m, 633, "E;do-not-retain-cleared-command", 2, 1);
    mark(&m, 133, "C", 0, 2); mark(&m, 133, "D;0", 4, 3);
    nemo_shell_marks_rows(&m, 0, 7, -1);
    IEQUAL(m.commands[0].point[0].truncated, true);
    IEQUAL(m.commands[0].text == NULL, true); IEQUAL(m.text_bytes, 0);
    IEQUAL(nemo_shell_marks_neighbour(&m, -1, 0, 7, 0, 7, &p) == m.commands[0].id, true);
    IEQUAL(p.x, 2); IEQUAL(p.y, 0);
    nemo_shell_marks_rows(&m, 0, 7, -1);
    IEQUAL(nemo_shell_marks_neighbour(&m, -1, 0, 7, 0, 7, &p) == m.commands[0].id, true);
    IEQUAL(p.x, 0); IEQUAL(p.y, 0);
    nemo_shell_marks_rows(&m, INT_MIN+1, INT_MAX, 3);
    nemo_shell_marks_rows(&m, 0, 7, 0);
    IEQUAL(m.commands[0].point[0].y, -1);
    IEQUAL(m.commands[0].point[1].y, -1);
    nemo_shell_marks_clear(&m);
}

static void test_rejection_and_budgets(Mock *mk)
{
    test_context(mk, "malformed metadata is atomic; marks and text stay bounded");
    NemoShellMarks m = {0}; mark(&m, 633, "E;keep", 0, 0);
    const char *bad[] = {"", "AB", "Z", "E;\\", "E;\\xGG", "E;\\x00", "E;\xc0\xaf",
        "E;\xed\xa0\x80", "E;\xf4\x90\x80\x80", "E;\xe2\x82", "P;IsWindows=yes",
        "P;HasRichCommandDetection=False;extra", "P;Unknown=True"};
    for (size_t i = 0; i < lenof(bad); i++) {
        IEQUAL(mark(&m, 633, bad[i], 0, 0), false);
        IEQUAL(m.count, 1); SEQUAL(m.commands[0].text, "keep");
    }
    const char embedded[] = "E;bad\0hidden";
    IEQUAL(nemo_shell_marks_update(&m, 633, embedded, sizeof(embedded)-1, 0, 0), false);
    IEQUAL(mark(&m, 133, "A", -1, 0), false);
    IEQUAL(mark(&m, 1337, "SetMarkAnything", 0, 0), false);
    char *large = snewn(NEMO_SHELL_OSC_MAX+2, char);
    memset(large, 'x', NEMO_SHELL_OSC_MAX+1); large[NEMO_SHELL_OSC_MAX+1] = 0;
    IEQUAL(mark(&m, 633, large, 0, 0), false);
    memcpy(large, "E;", 2); large[NEMO_SHELL_TEXT_MAX+3] = 0;
    IEQUAL(mark(&m, 633, large, 0, 0), false);
    large[NEMO_SHELL_TEXT_MAX+2] = 0;
    for (int i = 0; i < 2000; i++) {
        mark(&m, 133, "A", 0, i); IEQUAL(mark(&m, 633, large, 1, i), true);
        mark(&m, 133, "D;0", 2, i);
        IEQUAL(m.text_bytes <= NEMO_SHELL_TEXT_BUDGET, true);
        IEQUAL(m.count <= NEMO_SHELL_MARK_MAX, true);
        IEQUAL(nemo_shell_marks_memory(&m) <= NEMO_SHELL_TEXT_BUDGET +
               NEMO_SHELL_MARK_MAX*sizeof(NemoShellCommand), true);
    }
    for (int i = 0; i < 1000; i++) mark(&m, 1337, "SetMark", 0, i);
    IEQUAL(m.count, NEMO_SHELL_MARK_MAX); IEQUAL(m.text_bytes, 0);
    uint64_t old = m.commands[0].id;
    mark(&m, 1337, "SetMark", 0, 1001);
    IEQUAL(nemo_shell_marks_lookup(&m, old) == NULL, true);
    m.next_id = UINT64_MAX; mark(&m, 133, "A", 0, 0);
    IEQUAL(m.count, 1); IEQUAL(m.active_id == 1, true);
    nemo_shell_marks_clear(&m); sfree(large);
}

static void test_streams_and_reflow(Mock *mk)
{
    shell_setup(mk, "fragmented BEL/ST, Unicode ranges and repeated width reflow", 20, 8, 100);
    Terminal *t = mk->term;
    term_data_fragmented(t, "\033]133;A\a$ \033]133;B\033\\ab\xe4\xb8\xad" "e\xcc\x81"
        "\033]133;C\aXYZ\033]133;D;7\033\\");
    IEQUAL(t->shell_marks.count, 1); IEQUAL(t->shell_marks.commands[0].exit_code, 7);
    copy_range(mk, false, L"ab\x4e2d" L"e\x301"); copy_range(mk, true, L"XYZ");
    const int widths[] = {3, 1, 16, 4, 9, 8};
    for (int repeat = 0; repeat < 10; repeat++) for (size_t i = 0; i < lenof(widths); i++) {
        term_size(t, 20, widths[i], 100);
        copy_range(mk, false, L"ab\x4e2d" L"e\x301"); copy_range(mk, true, L"XYZ");
    }
    size_t count = t->shell_marks.count;
    term_data_fragmented(t, "\033]133;A\030\033]633;A\032\033P133;A\033\\\033_133;A\033\\");
    IEQUAL(t->shell_marks.count, count);
    char *large = snewn(NEMO_SHELL_OSC_MAX+32, char);
    strcpy(large, "\033]133;A;"); size_t prefix = strlen(large);
    memset(large+prefix, 'x', NEMO_SHELL_OSC_MAX+1);
    strcpy(large+prefix+NEMO_SHELL_OSC_MAX+1, "\a");
    term_data_fragmented(t, large); sfree(large);
    IEQUAL(t->shell_marks.count, count);
    term_data_fragmented(t, "\033]1337;SetMark\a"); IEQUAL(t->shell_marks.count, count+1);

    shell_setup(mk, "blank endpoints below cursor remain addressable during reflow", 8, 12, 100);
    term_data_fragmented(t, "\033[4;10H\033]133;A\a\033]133;B\a\033[4;12H\033]133;C\a\033[H");
    term_size(t, 12, 4, 100);
    IEQUAL(t->shell_marks.commands[0].point[1].x, 1);
    IEQUAL(t->shell_marks.commands[0].point[1].y, 5);
    IEQUAL(t->shell_marks.commands[0].point[2].x, 3);
    term_size(t, 12, 12, 100);
    IEQUAL(t->shell_marks.commands[0].point[1].x, 9);
    IEQUAL(t->shell_marks.commands[0].point[1].y, 3);
}

static void test_fixed_rows_and_height(Mock *mk)
{
    shell_setup(mk, "fixed double-width rows keep mark columns through narrow/restore", 16, 12, 100);
    Terminal *t = mk->term;
    term_data_fragmented(t, "abcdefghij\r\n\033#6\033]133;A\a$ \033]133;B\aab\033]133;C\aO\033]133;D;0\a");
    term_size(t, 16, 3, 100);
    IEQUAL(t->shell_marks.commands[0].point[1].x, 2);
    IEQUAL(t->shell_marks.commands[0].point[1].y, 4);
    IEQUAL(t->shell_marks.commands[0].point[2].x, 4);
    term_size(t, 16, 12, 100);
    copy_range(mk, false, L"ab"); copy_range(mk, true, L"O");

    shell_setup(mk, "height-only shrink and temporary history restore mark positions", 4, 12, 100);
    term_data_fragmented(t, "\033]133;A\a>\033]133;B\acmd\033]133;C\aout\033]133;D;0\a"
        "\r\nfiller\r\nfiller\r\nbottom");
    term_size(t, 2, 12, 100);
    IEQUAL(t->shell_marks.commands[0].point[0].y, -2);
    copy_range(mk, false, L"cmd"); copy_range(mk, true, L"out");
    term_size(t, 4, 12, 100);
    IEQUAL(t->shell_marks.commands[0].point[0].y, 0);
    copy_range(mk, false, L"cmd"); copy_range(mk, true, L"out");

    shell_setup(mk, "deleted bottom rows remove their bookmarks", 4, 12, 100);
    term_data_fragmented(t, "\033[4;1H\033]1337;SetMark\a\033[H");
    term_size(t, 2, 12, 100); IEQUAL(t->shell_marks.count, 0);
    term_size(t, 4, 12, 100); IEQUAL(t->shell_marks.count, 0);
}

static void test_history_reset_and_alternate(Mock *mk)
{
    shell_setup(mk, "history clipping never resurrects discarded anchors", 3, 12, 3);
    Terminal *t = mk->term; NemoShellPoint a, b;
    term_data_fragmented(t, "\033]133;A\a$ \033]133;B\aecho\033]133;C\a");
    for (int i = 0; i < 10; i++) term_data_fragmented(t, "\r\nline");
    term_data_fragmented(t, "\033]133;D;0\a");
    IEQUAL(t->shell_marks.count, 1);
    IEQUAL(t->shell_marks.commands[0].point[2].truncated, true);
    IEQUAL(nemo_shell_marks_range(&t->shell_marks.commands[0], true, -3, 2, &a, &b), true);
    IEQUAL(a.y, -3); IEQUAL(a.x, 0); IEQUAL(a.truncated, true);
    term_clrsb(t);
    IEQUAL(t->shell_marks.commands[0].point[2].y, -1);
    term_size(t, 8, 6, 10);
    IEQUAL(t->shell_marks.commands[0].point[2].truncated, true);
    IEQUAL(t->shell_marks.commands[0].point[2].y < -count234(t->scrollback), true);
    for (int i = 0; i < 25; i++) term_data_fragmented(t, "\r\nnext");
    IEQUAL(t->shell_marks.count, 0);

    shell_setup(mk, "alternate screen isolated; soft reset preserves; RIS clears", 8, 12, 100);
    term_data_fragmented(t, "\033]633;A\a$ \033]633;B\aCOMMAND\033]633;C\aOUT\033]633;D;0\a");
    term_data_fragmented(t, "\033[?1049h\033]133;A\aBAD\033]133;D;1\a");
    IEQUAL(t->shell_marks.count, 1);
    IEQUAL(term_shell_mark_navigate(t, -1), false);
    IEQUAL(term_shell_mark_select(t, true), false);
    term_size(t, 10, 6, 100); term_data_fragmented(t, "\033[?1049l\033[!p");
    copy_range(mk, false, L"COMMAND"); copy_range(mk, true, L"OUT");
    term_data_fragmented(t, "\033c"); IEQUAL(t->shell_marks.count, 0);
    IEQUAL(nemo_shell_marks_memory(&t->shell_marks), 0);
}

static void test_scrolling_and_navigation(Mock *mk)
{
    shell_setup(mk, "prompt navigation, explicit selection and ordinary scroll reset", 8, 20, 100);
    Terminal *t = mk->term;
    term_data_fragmented(t, "\033]133;A\a>\033]133;B\aone\033]133;C\aONE\033]133;D;0\a\r\n"
        "\033]633;A\a>\033]633;B\atwo\033]633;C\aTWO\033]633;D;0\a\r\n"
        "\033]133;A\a>");
    IEQUAL(term_shell_mark_navigate(t, -1), true);
    IEQUAL(term_shell_mark_navigate(t, -1), true);
    copy_range(mk, false, L"two"); copy_range(mk, true, L"TWO");
    IEQUAL(term_shell_mark_navigate(t, -1), true); copy_range(mk, false, L"one");
    IEQUAL(term_shell_mark_navigate(t, -1), false);
    IEQUAL(term_shell_mark_navigate(t, 1), true); copy_range(mk, true, L"TWO");
    term_scroll(t, -1, 0); IEQUAL(t->shell_mark_selected, 0);
    copy_range(mk, false, L"two");

    shell_setup(mk, "partial vertical and horizontal scroll follows affected anchors", 8, 12, 100);
    term_data_fragmented(t, "\033[3;3H\033]1337;SetMark\a\033[3;10H\033]1337;SetMark\a"
        "\033[?69h\033[2;6s\033[2;6r\033[2;2H\033[S");
    IEQUAL(t->shell_marks.count, 2);
    IEQUAL(t->shell_marks.commands[0].point[0].y, 1);
    IEQUAL(t->shell_marks.commands[1].point[0].y, 2);
    term_data_fragmented(t, "\033[T");
    IEQUAL(t->shell_marks.commands[0].point[0].y, 2);
    term_data_fragmented(t, "\033[?69l\033[2;6r\033[2;1H\033[5M");
    IEQUAL(t->shell_marks.count, 0);

    shell_setup(mk, "progress and erased cells keep position anchors, not secret text copies", 8, 20, 100);
    term_data_fragmented(t, "\033]133;A\a\033]133;B\acmd\033]133;C\aold\033]133;D;0\a\r\033[3Cnew");
    copy_range(mk, true, L"new");
    term_data_fragmented(t, "\033[2J");
    IEQUAL(t->shell_marks.count, 1);
    IEQUAL(term_shell_mark_select(t, true), true);
    IEQUAL(wcsstr(t->last_selected_text, L"old") == NULL, true);
}

int main(void)
{
    Mock *mk = mock_new(); mk->term = term_init(mk->conf, mk->ucsdata, &mk->tw);
    mk->ldisc = ldisc_create(mk->conf, mk->term, &mk->backend, &mk->seat);
    test_protocol(mk); test_clipped_navigation(mk);
    test_rejection_and_budgets(mk); test_streams_and_reflow(mk);
    test_fixed_rows_and_height(mk);
    test_history_reset_and_alternate(mk); test_scrolling_and_navigation(mk);
    bool failed = mk->any_test_failed; mock_free(mk);
    puts(failed ? "Shell mark suite FAILED" : "Shell mark suite passed");
    return failed ? 1 : 0;
}
