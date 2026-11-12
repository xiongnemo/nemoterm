/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main
#include "title_cases.h"
#include "title_mode_cases.h"

static Mock *title_mock(void)
{
    Mock *mk = mock_new();
    conf_set_int(mk->conf, CONF_remote_qtitle_action, TITLE_REAL);
    mk->ucsdata->line_codepage = CP_UTF8;
    mk->term = term_init(mk->conf, mk->ucsdata, &mk->tw);
    mk->ldisc = ldisc_create(mk->conf, mk->term, &mk->backend, &mk->seat);
    reset(mk);
    return mk;
}

static void response(Mock *mk, const char *expected)
{
    size_t n = strlen(expected);
    if (mk->to_backend->len != n || memcmp(mk->to_backend->s, expected, n))
        report_fail(mk, __FILE__, __LINE__, "title response differs: expected %zu bytes, got %zu",
                    n, mk->to_backend->len);
    strbuf_clear(mk->to_backend);
}

static void policies_and_encoding(Mock *mk)
{
    IEQUAL(mk->term->title_stack == NULL, true);
    term_data_fragmented(mk->term, "\033[23t\033[23;0;9t");
    IEQUAL(mk->term->title_stack == NULL, true); /* reads allocate nothing */
    mk->ucsdata->line_codepage = CP_ISO8859_1;
    term_data_fragmented(mk->term, "\033]0;caf\351\007\033[22t");
    SEQUAL(mk->term->window_title, "caf\351");
    mk->ucsdata->line_codepage = CP_UTF8;
    term_data_fragmented(mk->term, "\033]0;TOP\007");
    conf_set_bool(mk->conf, CONF_no_remote_wintitle, true);
    term_reconfig(mk->term, mk->conf);
    term_data_fragmented(mk->term, "\033[23t\033[22t\033]0;BLOCKED\007");
    SEQUAL(mk->term->window_title, "TOP");
    conf_set_bool(mk->conf, CONF_no_remote_wintitle, false);
    term_reconfig(mk->term, mk->conf);
    term_data_fragmented(mk->term, "\033[23t");
    SEQUAL(mk->term->window_title, "caf\351");
    IEQUAL(mk->term->wintitle_codepage, CP_ISO8859_1);
    IEQUAL(mk->term->icontitle_codepage, CP_ISO8859_1);
    term_update(mk->term);
    SEQUAL(mk->title->s, "caf\351");

    term_data_fragmented(mk->term, "\033]0;BASE\007\033[22t\033]1;\007"
                         "\033[22;1t\033]0;TOP\007\033[23;0t");
    SEQUAL(mk->term->icon_title, ""); /* explicit empty does not fall back */
    SEQUAL(mk->term->window_title, "BASE");
    term_data_fragmented(mk->term, "\033[23t");
    for (int policy = TITLE_NONE; policy <= TITLE_REAL; policy++) {
        conf_set_int(mk->conf, CONF_remote_qtitle_action, policy);
        term_reconfig(mk->term, mk->conf);
        term_data_fragmented(mk->term, "\033[20t\033[21t");
        response(mk, policy == TITLE_NONE ? "" : policy == TITLE_EMPTY ?
            "\033]L\033\\\033]l\033\\" : "\033]LBASE\033\\\033]lBASE\033\\");
    }
}

static void bounds_and_recovery(Mock *mk)
{
    term_data_fragmented(mk->term, "\033]0;BASE\007\033[22t");
    sfree(mk->term->window_title);
    mk->term->window_title = snewn(4098, char);
    memset(mk->term->window_title, 'X', 4097);
    mk->term->window_title[4097] = 0;
    term_data_fragmented(mk->term, "\033]1;PARTIAL\007\033[22t\033[23t");
    SEQUAL(mk->term->icon_title, "BASE");
    SEQUAL(mk->term->window_title, "BASE");

    for (unsigned i = 0; i < 20000; i++) {
        char command[80];
        sprintf(command, "\033]0;PUSH%u\007\033[22t", i);
        term_data_fragmented(mk->term, command);
    }
    for (unsigned i = 0; i < 20; i++) {
        char expected[40];
        sprintf(expected, "PUSH%u", i < 10 ? 19999-i : 19990);
        term_data_fragmented(mk->term, "\033[23t");
        SEQUAL(mk->term->window_title, expected);
    }
    term_data_fragmented(mk->term, "\033]0;BEFORE\007\033[22t\033]0;AFTER\007"
        "\033[23:1t\033[23;0\030Z\033[23;0\032Z");
    SEQUAL(mk->term->window_title, "AFTER");
    term_data_fragmented(mk->term, "\033[23t");
    SEQUAL(mk->term->window_title, "BEFORE");
    term_data_fragmented(mk->term, "\033[22;0;4294967295t\033]0;TOP\007"
                         "\033[23;0;4294967295t");
    SEQUAL(mk->term->window_title, "BEFORE");
}

static void modes_and_codepages(Mock *mk)
{
    /* Queries encode the stored title for the current protocol mode, even
     * after a codepage change. Do not use a font reverse map for UTF-8. */
    mk->ucsdata->line_codepage = CP_ISO8859_1;
    term_data_fragmented(mk->term, "\033]0;caf\351\007\033[>3t\033[21t");
    response(mk, "\033]lcaf\303\251\033\\");
    term_data_fragmented(mk->term, "\033[>3T\033[21t");
    response(mk, "\033]lcaf\351\033\\");
    term_data_fragmented(mk->term, "\033[>2t\033]0;caf\303\251\007\033[21t");
    IEQUAL(mk->term->wintitle_codepage, CP_UTF8);
    response(mk, "\033]lcaf\351\033\\");
    term_data_fragmented(mk->term, "\033[>3;1t\033[20t");
    response(mk, "\033]L636166C3A9\033\\");
    unsigned saved = mk->term->title_modes;
    term_reconfig(mk->term, mk->conf);
    IEQUAL(mk->term->title_modes, saved);
    for (int policy = TITLE_NONE; policy <= TITLE_EMPTY; policy++) {
        conf_set_int(mk->conf, CONF_remote_qtitle_action, policy);
        term_reconfig(mk->term, mk->conf);
        term_data_fragmented(mk->term, "\033[20t\033[21t");
        response(mk, policy == TITLE_NONE ? "" : "\033]L\033\\\033]l\033\\");
    }
    conf_set_int(mk->conf, CONF_remote_qtitle_action, TITLE_REAL);
    term_reconfig(mk->term, mk->conf);
    term_data_fragmented(mk->term, "\033[>0;1;2;3T");
    /* Locally configured titles also cannot inject a query terminator. */
    sfree(mk->term->window_title);
    mk->term->window_title = dupstr("A\033\\B");
    mk->term->wintitle_codepage = CP_UTF8;
    term_data_fragmented(mk->term, "\033[>3t\033[21t");
    response(mk, "\033]lA?\\B\033\\");
    term_data_fragmented(mk->term, "\033]0;BASE\007\033]0;A\302\030B\033\\\033[21t");
    response(mk, "\033]lBASE\033\\");
}

int main(void)
{
    bool failed = false;
    for (unsigned i = 0; i < lenof(title_mode_cases); i++) {
        Mock *mk = title_mock();
        test_context(mk, "%s", title_mode_cases[i].name);
        for (size_t j = 0; j < title_mode_cases[i].length; j++)
            term_data(mk->term, title_mode_cases[i].sequence+j, 1);
        response(mk, title_mode_cases[i].reply);
        failed |= mk->any_test_failed;
        mock_free(mk);
    }
    for (unsigned i = 0; i < lenof(title_cases); i++) {
        Mock *mk = title_mock();
        test_context(mk, "%s", title_cases[i].name);
        term_data_fragmented(mk->term, title_cases[i].sequence);
        response(mk, title_cases[i].reply);
        failed |= mk->any_test_failed;
        mock_free(mk);
    }
    Mock *mk = title_mock();
    policies_and_encoding(mk);
    failed |= mk->any_test_failed;
    mock_free(mk);
    mk = title_mock();
    bounds_and_recovery(mk);
    failed |= mk->any_test_failed;
    mock_free(mk);
    mk = title_mock();
    modes_and_codepages(mk);
    failed |= mk->any_test_failed;
    mock_free(mk);
    puts(failed ? "Title suite FAILED" : "Title suite passed");
    return failed ? 1 : 0;
}
