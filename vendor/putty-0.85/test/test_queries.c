/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main

static void response(Mock *mk, const char *expected)
{
    size_t len = strlen(expected);
    if (len != mk->to_backend->len || memcmp(expected, mk->to_backend->s, len))
        report_fail(mk, __FILE__, __LINE__, "query reply differs: %zu expected, %zu actual bytes",
                    len, mk->to_backend->len);
    strbuf_clear(mk->to_backend);
}

static void test_cursor(Mock *mk)
{
    reset(mk);
    for (unsigned style = 0; style <= 6; style++) {
        test_context(mk, "DECSCUSR %u", style);
        char command[40], expected[40];
        unsigned actual = style ? style : 1;
        snprintf(command, sizeof(command), "\033[%u q\033P$q q\033\\", style);
        snprintf(expected, sizeof(expected), "\033P1$r%u q\033\\", actual);
        term_data_fragmented(mk->term, command);
        response(mk, expected);
        IEQUAL(mk->term->cursor_type, (actual-1)/2);
        IEQUAL(mk->term->blink_cur, (actual&1) != 0);
    }
    term_data_fragmented(mk->term, "\033[ q\033P$q q\033\\");
    response(mk, "\033P1$r1 q\033\\");
    term_data_fragmented(mk->term, "\033[6 q\033[8 q\033[99999999999999 q"
                         "\033[1;2 q\033[1:2 q\033P$q q\033\\");
    response(mk, "\033P1$r6 q\033\\");
    term_data_fragmented(mk->term, "\033[?12h\033P$q q\033\\\033[?12$p");
    response(mk, "\033P1$r5 q\033\\\033[?12;1$y");
    term_data_fragmented(mk->term, "\033[?12l\033P$q q\033\\\033[?12$p");
    response(mk, "\033P1$r6 q\033\\\033[?12;2$y");
    IEQUAL(mk->term->cblink_pending, false);
    IEQUAL(mk->term->cblinker, true);
    term_data_fragmented(mk->term, "\033[34l\033P$q q\033\\\033[6 q\033P$q q\033\\");
    response(mk, "\033P1$r2 q\033\\\033P1$r6 q\033\\");
    conf_set_bool(mk->conf, CONF_crhaslf, !conf_get_bool(mk->conf, CONF_crhaslf));
    term_reconfig(mk->term, mk->conf);
    term_data_fragmented(mk->term, "\033P$q q\033\\");
    response(mk, "\033P1$r6 q\033\\");

    conf_set_int(mk->conf, CONF_cursor_type, CURSOR_UNDERLINE);
    conf_set_bool(mk->conf, CONF_blink_cur, false);
    term_reconfig(mk->term, mk->conf);
    term_data_fragmented(mk->term, "\033[1 q\033[7 q\033P$q q\033\\");
    response(mk, "\033P1$r4 q\033\\");
    term_data_fragmented(mk->term, "\033[6 q\033c\033P$q q\033\\");
    response(mk, "\033P1$r4 q\033\\");
    term_data_fragmented(mk->term, "\033[6 q\033[?1049h\033P$q q\033\\"
                         "\033[?1049l\033P$q q\033\\");
    response(mk, "\033P1$r6 q\033\\\033P1$r6 q\033\\");
}

static void test_identity(Mock *mk)
{
    reset(mk);
    static const char *requests[] = { "c", ">c", "=c", ">q" };
    static const char *replies[] = {
        "\033[?62;4;22c", "\033[>0;136;0c", "\033P!|00000000\033\\",
        "\033P>|Nemoterm(PuTTY 0.85)\033\\"
    };
    static const char *arguments[] = {
        "", "0", "00", "0;9", ";9", "0;999999999999999999999999"
    };
    static const char *ignored[] = {
        "1", "2", "999", "1;0", "0:0", "999999999999999999999999"
    };
    for (size_t i = 0; i < lenof(requests); i++) {
        char prefix = strlen(requests[i]) == 2 ? requests[i][0] : 0;
        char final = requests[i][strlen(requests[i])-1];
        for (size_t j = 0; j < lenof(arguments)+lenof(ignored); j++) {
            const char *arg = j < lenof(arguments) ? arguments[j] :
                ignored[j-lenof(arguments)];
            test_context(mk, "identity %s argument %s", requests[i], arg);
            char sequence[100];
            snprintf(sequence, sizeof(sequence), "\033[%s%s%c",
                     prefix ? (prefix == '>' ? ">" : "=") : "", arg, final);
            term_data_fragmented(mk->term, sequence);
            response(mk, j < lenof(arguments) ? replies[i] : "");
            IEQUAL(mk->term->cursor_on, true);
            IEQUAL(mk->term->big_cursor, false);
            IEQUAL(mk->term->curs.x, 0);
            IEQUAL(mk->term->curs.y, 0);
        }
    }
    test_context(mk, "identity does not show a hidden cursor or change cells");
    term_data_fragmented(mk->term, "X\033[?25l\033[=c\033[=1c\033[=2c\033[>q");
    response(mk, "\033P!|00000000\033\\\033P>|Nemoterm(PuTTY 0.85)\033\\");
    IEQUAL(mk->term->cursor_on, false);
    IEQUAL(mk->term->curs.x, 1);
    IEQUAL(get_termchar(mk->term, 0, 0).chr, CSET_ASCII|'X');
    term_data_fragmented(mk->term, "\033[?25h\033[?1049h\033[=c\033[>q\033[?1049l");
    response(mk, "\033P!|00000000\033\\\033P>|Nemoterm(PuTTY 0.85)\033\\");
    IEQUAL(mk->term->cursor_on, true);

    test_context(mk, "explicit SCO cursor controls and suppressed identities");
    term_data_fragmented(mk->term, "\033[42\"p\033[=c");
    response(mk, "");
    IEQUAL(mk->term->cursor_on, false);
    term_data_fragmented(mk->term, "\033[=2c");
    IEQUAL(mk->term->cursor_on, true);
    IEQUAL(mk->term->big_cursor, true);
    term_data_fragmented(mk->term, "\033[=1c\033[c\033[>c\033[>q");
    response(mk, "");
    IEQUAL(mk->term->cursor_on, true);
    IEQUAL(mk->term->big_cursor, false);

    test_context(mk, "DA3 needs VT420; default mode restores modern query");
    term_data_fragmented(mk->term, "\033[41\"p\033[61\"p\033[=c"
                         "\033[62\"p\033[=c\033[64\"p\033[=c");
    response(mk, "\033P!|00000000\033\\");
    term_data_fragmented(mk->term, "\033[41\"p\033[=c");
    response(mk, "\033P!|00000000\033\\");

    test_context(mk, "cancelled identity requests do not reply; parser recovers");
    term_data_fragmented(mk->term, "\033[=0\030\033[>0\032\033[0\033[>q");
    response(mk, "\033P>|Nemoterm(PuTTY 0.85)\033\\");
    IEQUAL(mk->term->cursor_on, true);
}

static void test_state_strings(Mock *mk)
{
    reset(mk); test_context(mk, "SGR, margins and dimensions");
    term_data_fragmented(mk->term, "\033P$qm\033\\\033P$qr\033\\"
                         "\033P$q$|\033\\\033P$q*|\033\\");
    response(mk, "\033P1$r0m\033\\\033P1$r1;24r\033\\"
             "\033P1$r80$|\033\\\033P1$r24*|\033\\");
    term_data_fragmented(mk->term, "\033[3;20r\033P$qr\033\\");
    response(mk, "\033P1$r3;20r\033\\");
    term_size(mk->term, 30, 100, 0);
    term_data_fragmented(mk->term, "\033P$q$|\033\\\033P$q*|\033\\");
    response(mk, "\033P1$r100$|\033\\\033P1$r30*|\033\\");

    static const char *styles[] = {
        "0", "1;2;3;4:3;5;7;8;9;38:2::12:34:56;48:2::255:0:17;58:2::1:2:3",
        "4:2;31;104;58;5;7", "4:4;38;5;123;48;5;234", "4:5;97;40",
        "4;39;49", "4:0;58;5;255"
    };
    for (size_t i = 0; i < lenof(styles); i++) {
        reset(mk); test_context(mk, "SGR readback round trip %s", styles[i]);
        char sequence[200];
        snprintf(sequence, sizeof(sequence), "\033[0m\033[%sm\033P$qm\033\\", styles[i]);
        term_data_fragmented(mk->term, sequence);
        unsigned long attr = mk->term->curr_attr;
        truecolour tc = mk->term->curr_truecolour;
        IEQUAL(mk->to_backend->len >= 8 && mk->to_backend->len < 256, true);
        IEQUAL(memcmp(mk->to_backend->s, "\033P1$r", 5), 0);
        strbuf *restore = strbuf_new();
        put_dataz(restore, "\033[0m\033[");
        put_data(restore, mk->to_backend->s+5, mk->to_backend->len-7);
        strbuf_clear(mk->to_backend);
        term_data_fragmented(mk->term, restore->s);
        strbuf_free(restore);
        IEQUAL(mk->term->curr_attr, attr);
        IEQUAL(truecolour_equal(mk->term->curr_truecolour, tc), true);
    }
    term_data_fragmented(mk->term, "\033[0m\033[31;44m\033P$qm\033\\");
    response(mk, "\033P1$r0;31;44m\033\\");
}

static void test_dcs_recovery(Mock *mk)
{
    reset(mk); test_context(mk, "bounded query, cancellation and parser recovery");
    term_data_fragmented(mk->term, "\033P$q\033\\\033P$qunknown\033\\\033P$q\"p\033\\");
    response(mk, "\033P0$r\033\\\033P0$r\033\\\033P0$r\033\\");
    term_data_fragmented(mk->term, "\033P$q");
    for (int i = 0; i < 10000; i++) term_data(mk->term, "m", 1);
    IEQUAL(mk->term->dcs_query_len, 63);
    term_data_fragmented(mk->term, "\033\\A\033P$qm\033\\");
    response(mk, "\033P0$r\033\\\033P1$r0m\033\\");
    IEQUAL(get_termchar(mk->term, 0, 0).chr, CSET_ASCII|'A');
    term_data_fragmented(mk->term, "\033P$qm\030B\033P$qm\032C");
    response(mk, "");
    IEQUAL(get_termchar(mk->term, 1, 0).chr, CSET_ASCII|'B');
    IEQUAL(get_termchar(mk->term, 2, 0).chr, CSET_ASCII|'C');
    term_data_fragmented(mk->term, "\033P$qm\033[31m\033P$qm\033\\");
    response(mk, "\033P1$r0;31m\033\\");
    term_data_fragmented(mk->term, "\033P0$qm\033\\\033P$xq\033\\");
    response(mk, "");
    term_data_fragmented(mk->term, "\033P$qm\007\033\\");
    response(mk, "\033P1$r0;31m\033\\");
    term_data_fragmented(mk->term, "\033P$qm\x9c\033P$qm\xc2\x9c");
    response(mk, "\033P1$r0;31m\033\\\033P1$r0;31m\033\\");
    term_data_fragmented(mk->term, "\033P$qm");
    term_pwron(mk->term, true);
    term_data_fragmented(mk->term, "Z\033P$qm\033\\");
    response(mk, "\033P1$r0m\033\\");
    IEQUAL(mk->term->termstate, TOPLEVEL);
    term_data_fragmented(mk->term, "\033P0;1q#1;2;100;0;0#1~\033\\");
    IEQUAL(mk->term->images != NULL, true);
    size_t bytes = mk->term->image_bytes;
    term_data_fragmented(mk->term, "\033P$qm\033\\");
    response(mk, "\033P1$r0m\033\\");
    IEQUAL(mk->term->image_bytes, bytes);
}

int main(void)
{
    Mock *mk = mock_new();
    mk->term = term_init(mk->conf, mk->ucsdata, &mk->tw);
    mk->ldisc = ldisc_create(mk->conf, mk->term, &mk->backend, &mk->seat);
    test_identity(mk);
    test_cursor(mk);
    test_state_strings(mk);
    test_dcs_recovery(mk);
    bool failed = mk->any_test_failed;
    mock_free(mk);
    puts(failed ? "Query suite FAILED" : "Query suite passed");
    return failed ? 1 : 0;
}
