/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main
#include "test_clock.h"

#define LINK_A "\033]8;id=a;https://example.com/a\033\\"
#define LINK_B "\033]8;id=b;https://example.com/b\033\\"
#define LINK_END "\033]8;;\033\\"

static uint32_t parse(NemoHyperlinks **links, const char *s)
{
    return nemo_hyperlink_parse(links, s, strlen(s));
}

static void test_registry(Mock *mk)
{
    test_context(mk, "URI validation, explicit grouping and bounded storage");
    NemoHyperlinks *links = NULL;
    IEQUAL(nemo_hyperlink_memory(links), 0);
    IEQUAL(parse(&links, ";"), 0);
    IEQUAL(nemo_hyperlink_memory(links), 0);
    uint32_t a = parse(&links, "id=a;https://example.com/a?x=1&y=%22q%22#part");
    IEQUAL(a != 0, true);
    IEQUAL(parse(&links, "future=value:id=a;https://example.com/a?x=1&y=%22q%22#part"), a);
    uint32_t b = parse(&links, "id=a;https://example.com/b");
    IEQUAL(b != a && b != 0, true);
    uint32_t c = parse(&links, ";https://example.com/b");
    IEQUAL(c > b, true);
    IEQUAL(parse(&links, "id=;https://example.com/b") > c, true);
    const char *bad[] = {
        "missing separator", ";relative/path", ";//host/path", ";1bad:uri",
        ";https://host/a b", ";https://host/\"x\"", ";https://host/<x>",
        ";https://host/\\x", ";https://host/%", ";https://host/%0",
        ";https://host/%xz", ";https://host/\177", ";https://host/\xc3\xa9",
        "id=one:id=two;https://host/", "id=\t;https://host/"
    };
    size_t before = nemo_hyperlink_memory(links);
    for (size_t i = 0; i < lenof(bad); i++) IEQUAL(parse(&links, bad[i]), 0);
    static const char nul[] = ";https://host/\0hidden";
    IEQUAL(nemo_hyperlink_parse(&links, nul, sizeof(nul)-1), 0);
    IEQUAL(nemo_hyperlink_memory(links), before);
    char uri[NEMO_LINK_URI_MAX + 2];
    memset(uri, 'x', sizeof(uri)); memcpy(uri, "https://host/", 13);
    uri[NEMO_LINK_URI_MAX] = 0;
    char payload[NEMO_LINK_OSC_MAX + 2];
    snprintf(payload, sizeof(payload), ";%s", uri);
    IEQUAL(parse(&links, payload) != 0, true);
    uri[NEMO_LINK_URI_MAX] = 'x'; uri[NEMO_LINK_URI_MAX+1] = 0;
    snprintf(payload, sizeof(payload), ";%s", uri);
    IEQUAL(parse(&links, payload), 0);
    memset(payload, 'i', sizeof(payload)); memcpy(payload, "id=", 3);
    strcpy(payload + 3 + NEMO_LINK_ID_MAX, ";https://host/");
    IEQUAL(parse(&links, payload) != 0, true);
    payload[3 + NEMO_LINK_ID_MAX] = 'i';
    strcpy(payload + 4 + NEMO_LINK_ID_MAX, ";https://host/");
    IEQUAL(parse(&links, payload), 0);

    uint32_t previous = 0;
    for (unsigned i = 0; i < 3000; i++) {
        uint32_t handle = parse(&links, ";https://host/short");
        IEQUAL(handle > previous, true);
        SEQUAL(nemo_hyperlink_lookup(links, handle), "https://host/short");
        IEQUAL(nemo_hyperlink_memory(links) <= NEMO_LINK_BUDGET, true);
        IEQUAL(nemo_hyperlink_count(links) <= NEMO_LINK_COUNT_MAX, true);
        previous = handle;
    }
    IEQUAL(nemo_hyperlink_count(links), NEMO_LINK_COUNT_MAX);
    IEQUAL(nemo_hyperlink_lookup(links, a) == NULL, true);
    uri[NEMO_LINK_URI_MAX] = 0;
    snprintf(payload, sizeof(payload), ";%s", uri);
    for (unsigned i = 0; i < 3000; i++) {
        uint32_t handle = parse(&links, payload);
        IEQUAL(handle > previous, true);
        SEQUAL(nemo_hyperlink_lookup(links, handle), uri);
        IEQUAL(nemo_hyperlink_memory(links) <= NEMO_LINK_BUDGET, true);
        previous = handle;
    }
    IEQUAL(nemo_hyperlink_count(links) < NEMO_LINK_COUNT_MAX, true);
    IEQUAL(parse(&links, "id=a;https://example.com/a?x=1&y=%22q%22#part") > previous, true);
    IEQUAL(nemo_hyperlink_lookup(links, a) == NULL, true);
    nemo_hyperlink_free(links);
}

static void link_setup(Mock *mk, const char *context)
{
    reset(mk); test_context(mk, "%s", context);
    mk->ucsdata->line_codepage = CP_UTF8;
    term_data_fragmented(mk->term, "\033%G");
}

static void test_framing(Mock *mk)
{
    link_setup(mk, "OSC 8 state is independent from SGR; switching is not nesting");
    term_data_fragmented(mk->term, LINK_A "A\033[0m " LINK_B "B" LINK_END "C");
    uint32_t a = get_termchar(mk->term, 0, 0).hyperlink;
    uint32_t b = get_termchar(mk->term, 2, 0).hyperlink;
    IEQUAL(a != 0 && b != 0 && a != b, true);
    IEQUAL(get_termchar(mk->term, 1, 0).hyperlink, a);
    IEQUAL(get_termchar(mk->term, 3, 0).hyperlink, 0);
    SEQUAL(term_hyperlink_uri(mk->term, a), "https://example.com/a");
    term_data_fragmented(mk->term, "\033]8;id=a;https://example.com/a\aD");
    IEQUAL(get_termchar(mk->term, 4, 0).hyperlink, a);
    term_data_fragmented(mk->term, "\033]8;;\xc2\x9c" "E");
    IEQUAL(get_termchar(mk->term, 5, 0).hyperlink, 0);

    const char *cancels[] = {"\030", "\032", "\n", "\r", "\033[0m"};
    for (size_t i = 0; i < lenof(cancels); i++) {
        term_data_fragmented(mk->term, LINK_A "\033]8;;https://cancelled/");
        term_data_fragmented(mk->term, cancels[i]);
        IEQUAL(mk->term->curr_hyperlink, a);
    }
    term_data_fragmented(mk->term, "\033]8;;bad-relative-uri\a");
    IEQUAL(mk->term->curr_hyperlink, 0);
    term_data_fragmented(mk->term, "\033]8xid=a;https://example.com/a\a");
    IEQUAL(mk->term->curr_hyperlink, 0);
    term_data_fragmented(mk->term, LINK_A);
    static const char nul[] = "\033]8;;https://host/\0suffix\033\\";
    term_data(mk->term, nul, sizeof(nul)-1);
    IEQUAL(mk->term->curr_hyperlink, 0);

    char long_osc[NEMO_LINK_OSC_MAX + 100];
    memcpy(long_osc, "\033]8;id=", 7);
    memset(long_osc+7, 'i', NEMO_LINK_ID_MAX);
    strcpy(long_osc+7+NEMO_LINK_ID_MAX, ";https://host/");
    size_t n = strlen(long_osc);
    memset(long_osc+n, 'x', NEMO_LINK_URI_MAX-13);
    n += NEMO_LINK_URI_MAX-13;
    strcpy(long_osc+n, "\033\\");
    term_data_fragmented(mk->term, long_osc);
    IEQUAL(mk->term->curr_hyperlink != 0, true); /* more than old 2048 OSC cap */
    memcpy(long_osc, "\033]8;", 4);
    memset(long_osc+4, 'x', NEMO_LINK_OSC_MAX+1);
    strcpy(long_osc+5+NEMO_LINK_OSC_MAX, ";https://host/\033\\Z");
    term_data_fragmented(mk->term, long_osc);
    IEQUAL(mk->term->curr_hyperlink, 0);
    IEQUAL(mk->term->termstate, TOPLEVEL);
}

static void test_cell_lifecycle(Mock *mk)
{
    link_setup(mk, "wide/combining cells, overwrite, ECH, ICH, DCH and DECALN");
    term_data_fragmented(mk->term, LINK_A "\xe4\xb8\xad" "e\xcc\x81 X" LINK_END);
    uint32_t a = get_termchar(mk->term, 0, 0).hyperlink;
    for (int x = 0; x < 5; x++) IEQUAL(get_termchar(mk->term, x, 0).hyperlink, a);
    IEQUAL(get_termchar(mk->term, 2, 0).cc_next != 0, true);
    term_data_fragmented(mk->term, "\033[1;2Hz");
    IEQUAL(get_termchar(mk->term, 0, 0).hyperlink, 0);
    IEQUAL(get_termchar(mk->term, 1, 0).hyperlink, 0);
    term_data_fragmented(mk->term, "\033[1;3H\033[@");
    IEQUAL(get_termchar(mk->term, 2, 0).hyperlink, 0);
    IEQUAL(get_termchar(mk->term, 3, 0).hyperlink, a);
    term_data_fragmented(mk->term, "\033[P");
    IEQUAL(get_termchar(mk->term, 2, 0).hyperlink, a);
    term_data_fragmented(mk->term, LINK_A "\033[2X");
    IEQUAL(get_termchar(mk->term, 2, 0).hyperlink, 0);
    IEQUAL(get_termchar(mk->term, 3, 0).hyperlink, 0);
    term_data_fragmented(mk->term, "\033#8");
    for (int x = 0; x < mk->term->cols; x++) IEQUAL(get_termchar(mk->term, x, 0).hyperlink, 0);

    link_setup(mk, "save/restore cursor and 1049 preserve attributes, RIS clears active");
    term_data_fragmented(mk->term, LINK_A "A\0337" LINK_B "B\0338C");
    a = get_termchar(mk->term, 0, 0).hyperlink;
    IEQUAL(get_termchar(mk->term, 1, 0).hyperlink, a);
    term_data_fragmented(mk->term, "\033[?1049h" LINK_B "\033[H" "B");
    uint32_t b = get_termchar(mk->term, 0, 0).hyperlink;
    IEQUAL(b != a && b != 0, true);
    term_data_fragmented(mk->term, "\033[?1049lD");
    IEQUAL(get_termchar(mk->term, 0, 0).hyperlink, a);
    IEQUAL(get_termchar(mk->term, 2, 0).hyperlink, a);
    term_data_fragmented(mk->term, "\033c");
    IEQUAL(mk->term->curr_hyperlink, 0);
    IEQUAL(mk->term->save_hyperlink, 0);
    IEQUAL(mk->term->alt_save_hyperlink, 0);
}

static void test_scrollback_and_resize(Mock *mk)
{
    link_setup(mk, "compressed history retains cells, colours, combining and links");
    term_size(mk->term, 3, 12, 20);
    term_data_fragmented(mk->term, LINK_A "\033[38;2;1;2;3;4:3mABC\xe4\xb8\xad" "e\xcc\x81" LINK_END "\r\n");
    uint32_t a = get_termchar(mk->term, 0, 0).hyperlink;
    term_data_fragmented(mk->term, "\r\n\r\n");
    IEQUAL(count234(mk->term->scrollback), 1);
    for (int x = 0; x < 6; x++) IEQUAL(get_termchar(mk->term, x, -1).hyperlink, a);
    IEQUAL(get_termchar(mk->term, 5, -1).cc_next != 0, true);
    IEQUAL(get_termchar(mk->term, 0, -1).truecolour.fg.b, 3);
    IEQUAL(UNDER_STYLE(get_termchar(mk->term, 0, -1).truecolour), 3);
    IEQUAL(get_termchar(mk->term, 6, -1).hyperlink, 0);

    link_setup(mk, "width clips/restores link cells; font changes keep cell ownership");
    term_size(mk->term, 3, 12, 20);
    term_data_fragmented(mk->term, LINK_A "abcdefghijkl" LINK_END);
    a = get_termchar(mk->term, 0, 0).hyperlink;
    for (unsigned i = 0; i < 100; i++) {
        term_size(mk->term, 3, 6, 20);
        IEQUAL(get_termchar(mk->term, 5, 0).hyperlink, a);
        term_size(mk->term, 3, 12, 20);
        IEQUAL(get_termchar(mk->term, 11, 0).hyperlink, a);
        term_set_cell_size(mk->term, 8 + i % 5, 16 + i % 7);
    }
    term_data_fragmented(mk->term, "\033[3;1H" LINK_B "bottom" LINK_END);
    uint32_t b = get_termchar(mk->term, 0, 2).hyperlink;
    term_size(mk->term, 2, 12, 20);
    IEQUAL(get_termchar(mk->term, 0, -1).hyperlink, a);
    IEQUAL(get_termchar(mk->term, 0, 1).hyperlink, b);
    term_size(mk->term, 3, 12, 20);
    IEQUAL(get_termchar(mk->term, 0, 0).hyperlink, a);
    IEQUAL(get_termchar(mk->term, 0, 2).hyperlink, b);
}

static int mock_char_width(TermWin *tw, int chr) { return 1; }
static void mock_trust_sigil(TermWin *tw, int x, int y) {}
static bool mock_sync(TermWin *tw, bool enable) { return true; }

static void paint(Mock *mk)
{
    term_paint(mk->term, 0, 0, mk->term->cols-1, mk->term->rows-1, true);
}

static void test_rendered_frame(Mock *mk)
{
    link_setup(mk, "hit tests use displayed cells, including identical text replacements");
    term_data_fragmented(mk->term, LINK_A "same" LINK_END);
    uint32_t a = get_termchar(mk->term, 0, 0).hyperlink;
    IEQUAL(term_hyperlink_at(mk->term, 0, 0), 0);
    paint(mk);
    IEQUAL(term_hyperlink_at(mk->term, 0, 0), a);
    term_data_fragmented(mk->term, "\033[?2026h\033[H" LINK_B "same" LINK_END);
    IEQUAL(mk->term->synchronized_update, true);
    uint32_t b = get_termchar(mk->term, 0, 0).hyperlink;
    IEQUAL(b != a && b != 0, true);
    paint(mk);
    IEQUAL(term_hyperlink_at(mk->term, 0, 0), a);
    term_data_fragmented(mk->term, "\033[?2026l");
    paint(mk);
    IEQUAL(term_hyperlink_at(mk->term, 0, 0), b);
    term_data_fragmented(mk->term, "\033[?2026h\033[H" LINK_A "same" LINK_END);
    IEQUAL(term_hyperlink_at(mk->term, 0, 0), b);
    advance_test_clock(test_clock + TICKSPERSEC + 1);
    IEQUAL(mk->term->synchronized_update, false);
    paint(mk);
    IEQUAL(term_hyperlink_at(mk->term, 0, 0), a);
    term_data_fragmented(mk->term, "\033[Hsame");
    paint(mk);
    IEQUAL(term_hyperlink_at(mk->term, 0, 0), 0);
    IEQUAL(term_hyperlink_at(mk->term, -1, 0), 0);
    IEQUAL(term_hyperlink_at(mk->term, 80, 0), 0);
    IEQUAL(term_hyperlink_at(mk->term, 0, 24), 0);
    term_data_fragmented(mk->term, "\033[H\033#6" LINK_A "ab\xe4\xb8\xad" LINK_END);
    paint(mk);
    for (int x = 0; x < 8; x++) IEQUAL(term_hyperlink_at(mk->term, x, 0), a);
    IEQUAL(term_hyperlink_at(mk->term, 8, 0), 0);
    term_size(mk->term, 23, 79, 20);
    IEQUAL(term_hyperlink_at(mk->term, 0, 0), 0);
    paint(mk);
    IEQUAL(term_hyperlink_at(mk->term, 0, 0), a);

    link_setup(mk, "bidirectional display hit follows visible glyph, not logical index");
    term_data_fragmented(mk->term, LINK_A "\xd7\x90" LINK_B "\xd7\x91" LINK_END);
    paint(mk);
    bool found = false;
    for (int x = 0; x < mk->term->cols; x++) {
        termchar *cell = &mk->term->disptext[0]->chars[x];
        if (cell->chr == 0x5d0) { IEQUAL(term_hyperlink_at(mk->term, x, 0), a); found = true; }
        if (cell->chr == 0x5d1) IEQUAL(term_hyperlink_at(mk->term, x, 0), b);
    }
    IEQUAL(found, true);
}

static void test_disabled_and_evicted(Mock *mk)
{
    link_setup(mk, "disabled parser/hit and evicted handles cannot alias fresh addresses");
    term_data_fragmented(mk->term, LINK_A "A" LINK_END);
    paint(mk);
    uint32_t a = term_hyperlink_at(mk->term, 0, 0);
    IEQUAL(a != 0, true);
    conf_set_bool(mk->conf, CONF_no_remote_hyperlinks, true);
    term_reconfig(mk->term, mk->conf);
    IEQUAL(term_hyperlink_at(mk->term, 0, 0), 0);
    size_t bytes = nemo_hyperlink_memory(mk->term->hyperlinks);
    term_data_fragmented(mk->term, LINK_B "B" LINK_END);
    IEQUAL(get_termchar(mk->term, 1, 0).hyperlink, 0);
    IEQUAL(nemo_hyperlink_memory(mk->term->hyperlinks), bytes);
    conf_set_bool(mk->conf, CONF_no_remote_hyperlinks, false);
    term_reconfig(mk->term, mk->conf);
    for (unsigned i = 0; i < NEMO_LINK_COUNT_MAX+1; i++)
        term_data_fragmented(mk->term, "\033]8;;https://host/new\033\\");
    IEQUAL(term_hyperlink_uri(mk->term, a) == NULL, true);
    IEQUAL(term_hyperlink_at(mk->term, 0, 0), 0);
    term_data_fragmented(mk->term, LINK_A);
    IEQUAL(mk->term->curr_hyperlink > a, true);
    IEQUAL(term_hyperlink_at(mk->term, 0, 0), 0);
}

static void test_plain_text_selection(Mock *mk)
{
    const int clipboard = CLIP_LOCAL + 1;
    const int modes[] = {1000, 1001, 1002, 1003};
    for (size_t i = 0; i < lenof(modes); i++) {
        link_setup(mk, "Shift selection copies the label without OSC 8 markup or URI");
        term_data_fragmented(mk->term, LINK_A "A\xe4\xb8\xad" "e\xcc\x81Z" LINK_END);
        paint(mk);
        char seq[40];
        snprintf(seq, sizeof(seq), "\033[?%dh\033[?1006h", modes[i]);
        term_data_fragmented(mk->term, seq);
        term_mouse(mk->term, MBT_LEFT, MBT_SELECT, MA_CLICK, 0, 0, true, false, false);
        term_mouse(mk->term, MBT_LEFT, MBT_SELECT, MA_DRAG, 4, 0, true, false, false);
        term_mouse(mk->term, MBT_LEFT, MBT_SELECT, MA_RELEASE, 4, 0, true, false, false);
        IEQUAL(mk->to_backend->len, 0);
        term_request_copy(mk->term, &clipboard, 1);
        check_clipboard(mk, L"A\x4e2d" L"e\x301Z");
        IEQUAL(get_termchar(mk->term, 0, 0).hyperlink != 0, true);
    }
}

int main(void)
{
    Mock *mk = mock_new();
    TermWinVtable vt = mock_termwin_vt;
    vt.char_width = mock_char_width;
    vt.draw_trust_sigil = mock_trust_sigil;
    vt.set_synchronized_update = mock_sync;
    mk->tw.vt = &vt;
    mk->term = term_init(mk->conf, mk->ucsdata, &mk->tw);
    mk->ldisc = ldisc_create(mk->conf, mk->term, &mk->backend, &mk->seat);
    test_registry(mk);
    test_framing(mk);
    test_cell_lifecycle(mk);
    test_scrollback_and_resize(mk);
    test_rendered_frame(mk);
    test_disabled_and_evicted(mk);
    test_plain_text_selection(mk);
    bool failed = mk->any_test_failed;
    mock_free(mk);
    puts(failed ? "Hyperlink test suite FAILED!" : "Hyperlink test suite passed");
    return failed ? 1 : 0;
}
