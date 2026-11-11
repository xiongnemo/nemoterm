/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main

/* DECRQM is a single-Ps request. xterm ctlseqs defines response states
 * 0 unknown, 1 set, 2 reset, 3 permanently set, 4 permanently reset.
 * xterm's do_ansi_rqm/do_dec_rqm ignore parameters after the first. */
static void mode_response(Mock *mk, const char *file, int line,
                          const char *expected)
{
    size_t len = strlen(expected);
    if (mk->to_backend->len != len ||
        memcmp(mk->to_backend->s, expected, len)) {
        report_fail(mk, file, line, "DECRPM bytes differ (%zu actual, %zu expected)",
                    mk->to_backend->len, len);
        printf(" actual:");
        for (size_t i = 0; i < mk->to_backend->len; i++)
            printf(" %02x", (unsigned char)mk->to_backend->s[i]);
        printf("\n expect:");
        for (size_t i = 0; i < len; i++)
            printf(" %02x", (unsigned char)expected[i]);
        printf("\n");
    }
    strbuf_clear(mk->to_backend);
}

#define MODE_RESPONSE(s) mode_response(mk, __FILE__, __LINE__, s)

static bool mode_allow_synchronized_update(TermWin *win, bool enabled)
{
    return true;
}

static void mode_complete_resize(TermWin *win, int width, int height)
{
    Mock *mk = container_of(win, Mock, tw);
    term_resize_request_completed(mk->term);
}

typedef struct ModeCase {
    const char *name, *disable, *enable, *query, *reset_reply, *set_reply;
} ModeCase;

#define MODE_CASE(prefix, number, label) { \
    label, "\033[" prefix number "l", "\033[" prefix number "h", \
    "\033[" prefix number "$p", \
    "\033[" prefix number ";2$y", "\033[" prefix number ";1$y" \
}

static void test_switchable_modes(Mock *mk)
{
    static const ModeCase cases[] = {
        MODE_CASE("", "4", "ANSI IRM insertion"),
        MODE_CASE("", "12", "ANSI SRM send/receive, inverse of local echo"),
        MODE_CASE("", "20", "ANSI LNM newline"),
        MODE_CASE("", "34", "WYULCURM cursor style, inverse of big cursor"),
        MODE_CASE("?", "1", "DECCKM application cursor"),
        MODE_CASE("?", "3", "DECCOLM requested 80/132 columns"),
        MODE_CASE("?", "5", "DECSCNM reverse video"),
        MODE_CASE("?", "6", "DECOM origin"),
        MODE_CASE("?", "7", "DECAWM autowrap"),
        MODE_CASE("?", "8", "DECARM key repeat, inverse of repeat_off"),
        MODE_CASE("?", "12", "cursor blinking"),
        MODE_CASE("?", "25", "DECTCEM cursor visibility"),
        MODE_CASE("?", "47", "alternate screen mode 47"),
        MODE_CASE("?", "80", "DECSDM Sixel display mode"),
        MODE_CASE("?", "1004", "focus reporting"),
        MODE_CASE("?", "1007", "alternate scrolling"),
        MODE_CASE("?", "1047", "alternate screen mode 1047"),
        MODE_CASE("?", "1049", "alternate screen and cursor mode 1049"),
        MODE_CASE("?", "1070", "Sixel private palette"),
        MODE_CASE("?", "2004", "bracketed paste"),
        MODE_CASE("?", "2026", "synchronized output"),
        MODE_CASE("?", "8452", "Sixel cursor to graphic right"),
    };
    for (size_t i = 0; i < lenof(cases); i++) {
        const ModeCase *c = &cases[i];
        reset(mk);
        test_context(mk, "%s", c->name);
        term_data_fragmented(mk->term, c->disable);
        term_update(mk->term);
        term_data_fragmented(mk->term, c->query);
        mode_response(mk, __FILE__, __LINE__, c->reset_reply);
        term_data_fragmented(mk->term, c->enable);
        /* Real frontends complete DECCOLM's resize request before parsing
         * resumes. Service that request before sending the query. */
        term_update(mk->term);
        term_data_fragmented(mk->term, c->query);
        mode_response(mk, __FILE__, __LINE__, c->set_reply);
        /* Querying a mode must not change its state. */
        term_data_fragmented(mk->term, c->query);
        mode_response(mk, __FILE__, __LINE__, c->set_reply);
        term_data_fragmented(mk->term, c->disable);
        term_update(mk->term);
        term_data_fragmented(mk->term, c->query);
        mode_response(mk, __FILE__, __LINE__, c->reset_reply);
    }
    reset(mk);
    test_context(mk, "DECANM reports ANSI mode while CSI queries are available");
    term_data_fragmented(mk->term, "\033[?2h\033[?2$p");
    MODE_RESPONSE("\033[?2;1$y");
}

static void test_tracking_queries(Mock *mk)
{
    static const char *queries =
        "\033[?9$p\033[?1000$p\033[?1002$p\033[?1003$p";
    static const struct {
        const char *modes, *replies;
    } cases[] = {
        { "\033[?9h", "\033[?9;1$y\033[?1000;2$y\033[?1002;2$y\033[?1003;2$y" },
        { "\033[?1000h", "\033[?9;2$y\033[?1000;1$y\033[?1002;2$y\033[?1003;2$y" },
        { "\033[?1002h", "\033[?9;2$y\033[?1000;2$y\033[?1002;1$y\033[?1003;2$y" },
        { "\033[?1003h", "\033[?9;2$y\033[?1000;2$y\033[?1002;2$y\033[?1003;1$y" },
        { "\033[?1000l", "\033[?9;2$y\033[?1000;2$y\033[?1002;2$y\033[?1003;2$y" },
    };
    reset(mk);
    test_context(mk, "tracking DECRQM follows last SET and unconditional RESET");
    for (size_t i = 0; i < lenof(cases); i++) {
        term_data_fragmented(mk->term, cases[i].modes);
        term_data_fragmented(mk->term, queries);
        mode_response(mk, __FILE__, __LINE__, cases[i].replies);
    }
}

static void test_encoding_queries(Mock *mk)
{
    static const char *queries =
        "\033[?1005$p\033[?1006$p\033[?1015$p\033[?1016$p";
    static const struct {
        const char *modes, *replies;
    } cases[] = {
        { "\033[?1005h", "\033[?1005;1$y\033[?1006;2$y\033[?1015;2$y\033[?1016;2$y" },
        { "\033[?1006h", "\033[?1005;2$y\033[?1006;1$y\033[?1015;2$y\033[?1016;2$y" },
        { "\033[?1015h", "\033[?1005;2$y\033[?1006;2$y\033[?1015;1$y\033[?1016;2$y" },
        { "\033[?1016h", "\033[?1005;2$y\033[?1006;2$y\033[?1015;2$y\033[?1016;1$y" },
        { "\033[?1006l", "\033[?1005;2$y\033[?1006;2$y\033[?1015;2$y\033[?1016;1$y" },
        { "\033[?1016l", "\033[?1005;2$y\033[?1006;2$y\033[?1015;2$y\033[?1016;2$y" },
    };
    reset(mk);
    test_context(mk, "encoding DECRQM follows last SET and matching RESET");
    for (size_t i = 0; i < lenof(cases); i++) {
        term_data_fragmented(mk->term, cases[i].modes);
        term_data_fragmented(mk->term, queries);
        mode_response(mk, __FILE__, __LINE__, cases[i].replies);
    }
    /* Encoding negotiation does not turn on tracking, and turning tracking
     * off does not discard the selected encoding. */
    term_data_fragmented(mk->term,
                         "\033[?1016h\033[?1000$p\033[?1000h"
                         "\033[?1000l\033[?1016$p");
    MODE_RESPONSE("\033[?1000;2$y\033[?1016;1$y");
}

static void test_alternate_screen_queries(Mock *mk)
{
    reset(mk);
    test_context(mk, "47/1047/1049 queries reflect the same current buffer");
    term_data_fragmented(mk->term,
                         "\033[?1049h\033[?47$p\033[?1047$p\033[?1049$p"
                         "\033[?47l\033[?47$p\033[?1047$p\033[?1049$p");
    MODE_RESPONSE("\033[?47;1$y\033[?1047;1$y\033[?1049;1$y"
                  "\033[?47;2$y\033[?1047;2$y\033[?1049;2$y");
}

static void test_unknown_and_parameter_handling(Mock *mk)
{
    reset(mk);
    test_context(mk, "unsupported mode queries are explicitly unknown");
    term_data_fragmented(mk->term,
                         "\033[0$p\033[9999$p\033[2026$p"
                         "\033[?0$p\033[?4$p\033[?69$p"
                         "\033[?1001$p\033[?1048$p\033[?9001$p\033[?9999$p");
    MODE_RESPONSE("\033[0;0$y\033[9999;0$y\033[2026;0$y"
                  "\033[?0;0$y\033[?4;0$y\033[?69;0$y"
                  "\033[?1001;0$y\033[?1048;0$y\033[?9001;0$y\033[?9999;0$y");

    test_context(mk, "DECRQM ignores parameters after its first Ps");
    term_data_fragmented(mk->term,
                         "\033[4h\033[12l\033[4;12;20$p"
                         "\033[?1004h\033[?1004;1007;2026$p"
                         "\033[?9999;1004$p\033[9999;4$p");
    MODE_RESPONSE("\033[4;1$y\033[?1004;1$y\033[?9999;0$y\033[9999;0$y");
    term_data_fragmented(mk->term, "\033[$p\033[?$p\033[;4$p\033[?;1004$p");
    MODE_RESPONSE("\033[0;0$y\033[?0;0$y\033[0;0$y\033[?0;0$y");

    test_context(mk, "unknown query number is returned without signed truncation");
    term_data_fragmented(mk->term, "\033[?2147483647$p\033[2147483647$p");
    MODE_RESPONSE("\033[?2147483647;0$y\033[2147483647;0$y");
}

static void test_fragmented_query_and_recovery(Mock *mk)
{
    reset(mk);
    test_context(mk, "a fragmented DECRQM replies only after its final byte");
    term_data_fragmented(mk->term, "ABC\033[?2026l\033[?2026$");
    MODE_RESPONSE("");
    term_data_fragmented(mk->term, "p");
    MODE_RESPONSE("\033[?2026;2$y");
    IEQUAL(mk->term->curs.x, 3);
    IEQUAL(mk->term->curs.y, 0);
    IEQUAL(get_termchar(mk->term, 0, 0).chr, CSET_ASCII | 'A');
    IEQUAL(get_termchar(mk->term, 2, 0).chr, CSET_ASCII | 'C');

    test_context(mk, "cancelled DECRQM does not reply and parser recovers");
    term_data_fragmented(mk->term,
                         "\033[?2026$\030\033[?2026$p"
                         "\033[?2004$\032\033[?2004l\033[?2004$p");
    MODE_RESPONSE("\033[?2026;2$y\033[?2004;2$y");
    term_data_fragmented(mk->term,
                         "\033[?1004h\033[?1004$p\033[?1004l\033[?1004$p");
    MODE_RESPONSE("\033[?1004;1$y\033[?1004;2$y");
}

static void test_synchronized_mode_queries(Mock *mk)
{
    reset(mk);
    test_context(mk, "2026 queries remain live while synchronized output is active");
    term_data_fragmented(mk->term,
                         "\033[?2026$p\033[?2026h\033[?2026$p"
                         "\033[?2026h\033[?2026$p\033[?2026l\033[?2026$p");
    MODE_RESPONSE("\033[?2026;2$y\033[?2026;1$y"
                  "\033[?2026;1$y\033[?2026;2$y");
    /* SET is idempotent, not a nesting push; one RESET ends the frame. */
    term_data_fragmented(mk->term,
                         "\033[?1003;1016;1004;1007;2004;2026h\033c"
                         "\033[?1003$p\033[?1016$p\033[?1004$p"
                         "\033[?1007$p\033[?2004$p\033[?2026$p");
    MODE_RESPONSE("\033[?1003;2$y\033[?1016;2$y\033[?1004;2$y"
                  "\033[?1007;2$y\033[?2004;2$y\033[?2026;2$y");
}

int main(void)
{
    Mock *mk = mock_new();
    struct TermWinVtable vt = mock_termwin_vt;
    vt.set_synchronized_update = mode_allow_synchronized_update;
    vt.request_resize = mode_complete_resize;
    mk->tw.vt = &vt;
    mk->term = term_init(mk->conf, mk->ucsdata, &mk->tw);
    mk->ldisc = ldisc_create(mk->conf, mk->term, &mk->backend, &mk->seat);

    test_switchable_modes(mk);
    test_tracking_queries(mk);
    test_encoding_queries(mk);
    test_alternate_screen_queries(mk);
    test_unknown_and_parameter_handling(mk);
    test_fragmented_query_and_recovery(mk);
    test_synchronized_mode_queries(mk);

    bool failed = mk->any_test_failed;
    mock_free(mk);
    puts(failed ? "Mode test suite FAILED!" : "Mode test suite passed");
    return failed ? 1 : 0;
}
