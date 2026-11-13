/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main
#include "terminal/nemo_window_size.h"
#include "window_resize_cases.h"
#include "../../../tests/graphics_query_oracle_cases.h"
#include "../../../tests/dec_status_oracle_cases.h"
#include "../../../tests/checksum_oracle_cases.h"

static void response(Mock *mk, const char *expected)
{
    size_t len = strlen(expected);
    if (len != mk->to_backend->len || memcmp(expected, mk->to_backend->s, len)) {
        report_fail(mk, __FILE__, __LINE__, "query reply differs: %zu expected, %zu actual bytes",
                    len, mk->to_backend->len);
        printf(" actual hex:");
        for (size_t i = 0; i < mk->to_backend->len; i++)
            printf(" %02X", (unsigned char)mk->to_backend->s[i]);
        putchar('\n');
    }
    strbuf_clear(mk->to_backend);
}

static void test_graphics_queries(Mock *mk)
{
    for (size_t i = 0; i < lenof(graphics_query_oracle); i++) {
        reset(mk);
        test_context(mk, "XTSMGRAPHICS %s", graphics_query_oracle[i].name);
        strbuf_clear(mk->to_backend);
        term_data_fragmented(mk->term, graphics_query_oracle[i].sequence);
        response(mk, graphics_query_oracle[i].reply);
    }
    reset(mk);
    test_context(mk, "graphics queries report the implemented limits and defaults");
    term_data_fragmented(mk->term, "\033[?1;2;0S\033[?1;4;0S\033[?2;4;0S"
        "\033[?1;3;257S\033[?1;3;1024S\033[?1;1;0S\033[?;1;0S");
    response(mk, "\033[?1;0;256S\033[?1;0;256S\033[?2;0;8192;8192S"
        "\033[?1;3S\033[?1;3S\033[?1;0;256S\033[?0;1S");
    test_context(mk, "graphics viewport follows cell metrics and grid size");
    term_size(mk->term, 24, 80, 0);
    term_set_cell_size(mk->term, 8, 16);
    term_data_fragmented(mk->term, "\033[?2;1;0S");
    response(mk, "\033[?2;0;640;384S");
    term_size(mk->term, 31, 100, 0);
    term_set_cell_size(mk->term, 11, 20);
    term_data_fragmented(mk->term, "\033[?2;1;0S");
    response(mk, "\033[?2;0;1100;620S");
    term_set_cell_size(mk->term, INT_MAX, INT_MAX);
    term_data_fragmented(mk->term, "\033[?2;1;0S");
    response(mk, "\033[?2;0;8192;8192S");
    term_set_cell_size(mk->term, 8, 16);
}

static void test_dec_status(Mock *mk)
{
    /* The independent reference and native fixture both use UTF-8. */
    mk->ucsdata->line_codepage = CP_UTF8;
    for (size_t i = 0; i < lenof(dec_status_oracle); i++) {
        reset(mk);
        test_context(mk, "DEC status %s", dec_status_oracle[i].name);
        term_data_fragmented(mk->term, dec_status_oracle[i].sequence);
        response(mk, dec_status_oracle[i].reply);
    }
    reset(mk);
    test_context(mk, "DEC status truthful unsupported devices and empty checksum id");
    term_data_fragmented(mk->term, "\033[65;1\"p\033[?25n\033[?55n\033[?56n\033[?63;;9n");
    response(mk, "\033[?23n\033[?53n\033[?57;0n\033P0!~0000\033\\");
    test_context(mk, "printer configuration does not probe or start a print job");
    conf_set_str(mk->conf, CONF_printer, "Nemoterm test printer - do not open");
    term_reconfig(mk->term, mk->conf);
    term_data_fragmented(mk->term, "\033[?15n");
    response(mk, "\033[?11n");
    IEQUAL(mk->term->printing, false);
    IEQUAL(mk->term->print_job == NULL, true);
    conf_set_str(mk->conf, CONF_printer, "");
    term_reconfig(mk->term, mk->conf);
    term_data_fragmented(mk->term, "\033[?15n");
    response(mk, "\033[?13n");
    test_context(mk, "internal cursor synchronization remains absolute under DECOM");
    term_data_fragmented(mk->term, "\033[3;20r\033[?69h\033[11;70s\033[?6h"
        "\033[5;7H\033[?9001;42n\033[6n\033[?6n");
    response(mk, "\033[?9001;42;7;17R\033[5;7R\033[?5;7;1R");
    term_data_fragmented(mk->term, "\033[?9001n\033[?9001;0n\033[?9001;65536n"
        "\033[9001;42n\033[?9001;42;1n\033[?9001;42:1n");
    response(mk, "");
    term_data_fragmented(mk->term, "\033[61;1\"p\033[?9001;65535n");
    response(mk, "\033[?9001;65535;7;17R");
}

static void test_checksums(Mock *mk)
{
    reset(mk);
    test_context(mk, "screen checksum access is disabled by default");
    term_data_fragmented(mk->term, "\033[64;1\"pA\033[23#y\033[7;1;1;1;1;1*y");
    response(mk, "");
    IEQUAL(mk->term->checksum_flags, 0);
    conf_set_bool(mk->conf, CONF_nemo_allow_checksum, true);
    conf_set_bool(mk->conf, CONF_crhaslf, false);
    conf_set_bool(mk->conf, CONF_lfhascr, false);
    conf_set_bool(mk->conf, CONF_utf8linedraw, true);
    term_reconfig(mk->term, mk->conf);
    mk->ucsdata->line_codepage = CP_UTF8;
    for (size_t i = 0; i < lenof(checksum_oracle); i++) {
        reset(mk);
        test_context(mk, "rectangle checksum %s", checksum_oracle[i].name);
        term_data_fragmented(mk->term, checksum_oracle[i].sequence);
        response(mk, checksum_oracle[i].reply);
    }
    for (size_t i = 0; i < lenof(checksum_direct); i++) {
        reset(mk);
        test_context(mk, "retained-cell checksum %s", checksum_direct[i].name);
        term_data_fragmented(mk->term, checksum_direct[i].sequence);
        response(mk, checksum_direct[i].reply);
    }
    reset(mk);
    test_context(mk, "checksums preserve pending wrap, selection and both buffers");
    term_data_fragmented(mk->term, "\033[1;80HZ\033[23#y");
    mk->term->selstate = SELECTED;
    mk->term->selstart = (pos){0, 79};
    mk->term->selend = (pos){1, 0};
    mk->term->disptop = -1;
    mk->term->grapheme_pending = true;
    term_data_fragmented(mk->term, "\033[7;1;1;80;1;80*y");
    response(mk, "\033P7!~005A\033\\");
    IEQUAL(mk->term->curs.x, 79); IEQUAL(mk->term->curs.y, 0);
    IEQUAL(mk->term->wrapnext, true);
    IEQUAL(mk->term->selstate, SELECTED);
    IEQUAL(mk->term->disptop, -1);
    IEQUAL(mk->term->grapheme_pending, true);
    mk->term->grapheme_pending = false;
    mk->term->disptop = 0;
    term_data_fragmented(mk->term, "X\033[?1049h\033[2J\033[H"
        "\033[7;1;1;1;1;1*y\033[?1049l\033[7;1;1;80;1;80*y");
    response(mk, "\033P7!~0020\033\\\033P7!~005A\033\\");
    IEQUAL(get_termchar(mk->term, 0, 1).chr, CSET_ASCII|'X');
    test_context(mk, "writing over a selected cell still invalidates it");
    term_data_fragmented(mk->term, "\033[1;80H");
    mk->term->selstate = SELECTED;
    mk->term->selstart = (pos){0, 79};
    mk->term->selend = (pos){1, 0};
    term_data_fragmented(mk->term, "Q");
    IEQUAL(mk->term->selstate, NO_SELECTION);
    test_context(mk, "checksums do not allocate or expose hidden retained columns");
    /* Shrinking can leave a longer retained physical row. Never checksum its
     * hidden tail; growing a sparse row must not resize its allocation here. */
    term_size(mk->term, 24, 40, 0);
    termline *sparse = index234(mk->term->screen, 23);
    int saved_cols = sparse->cols;
    sparse->cols = 5; /* Present only the initialized prefix to the reader. */
    termchar *before = sparse->chars;
    term_data_fragmented(mk->term, "\033[7;1;24;39;24;99999999999999999*y");
    response(mk, "\033P7!~0040\033\\");
    IEQUAL(sparse->cols, 5);
    IEQUAL(sparse->chars == before, true);
    sparse->cols = saved_cols;
    conf_set_bool(mk->conf, CONF_nemo_allow_checksum, false);
    term_reconfig(mk->term, mk->conf);
    test_context(mk, "revoking screen checksum access takes effect immediately");
    term_data_fragmented(mk->term, "\033[7;1;1;1;1;1*y");
    response(mk, "");
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
        "", "0", "00", "0;9", ";9", "0;999999999999999999999999",
        "0:0", "0:1", ":1", "0;1:2", "0:0:0", "1:0", "1;0:0"
    };
    static const char *ignored[] = {
        "1", "2", "999", "1;0", "999999999999999999999999999",
        "0:0:0:0:0:0:0:0:0:0"
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

static TermWindowGeometry geometry;
static bool mock_geometry(TermWin *tw, TermWindowGeometry *result)
{
    *result = geometry;
    return true;
}

static void test_geometry(Mock *mk)
{
    reset(mk); test_context(mk, "current geometry and independent XTerm shape");
    TermWinVtable vt = mock_termwin_vt;
    vt.get_geometry = mock_geometry;
    mk->tw.vt = &vt;
    geometry = (TermWindowGeometry) {
        .outer_x = 1, .outer_y = 1, .outer_width = 484, .outer_height = 316,
        .text_x = 2, .text_y = 2, .text_width = 480, .text_height = 312,
        .screen_width = 1024, .screen_height = 768,
        .cell_width = 6, .cell_height = 13,
    };
    /* Exact geometry query captured in independent XTerm run 43244992756. */
    term_data_fragmented(mk->term, "\033[11t\033[13t\033[13;2t\033[14t"
        "\033[14;2t\033[15t\033[16t\033[18t\033[19t");
    response(mk, "\033[1t\033[3;1;1t\033[3;2;2t\033[4;312;480t"
        "\033[4;316;484t\033[5;768;1024t\033[6;13;6t\033[8;24;80t\033[9;59;170t");
    /* Windows virtual-screen coordinates use XTerm's 16-bit wire encoding. */
    geometry.outer_x = -300; geometry.outer_y = -40;
    geometry.text_x = -298; geometry.text_y = -38;
    geometry.minimised = true;
    term_data_fragmented(mk->term, "\033[13t\033[13;2t\033[11t");
    response(mk, "\033[3;65236;65496t\033[3;65238;65498t\033[2t");
    term_data_fragmented(mk->term, "\033[13;0t\033[13;9t\033[14;0t\033[14;9t");
    response(mk, "\033[3;65236;65496t\033[3;65236;65496t\033[4;312;480t\033[4;312;480t");
    geometry.screen_width = 3840; geometry.screen_height = 2160;
    geometry.cell_width = 11; geometry.cell_height = 23;
    term_data_fragmented(mk->term, "\033[15;99t\033[16t\033[19t");
    response(mk, "\033[5;2160;3840t\033[6;23;11t\033[9;93;349t");
    geometry.cell_width = geometry.cell_height = 0;
    term_data_fragmented(mk->term, "\033[16t\033[19t\033[13:2t\033[14;2\030X\033[5n");
    response(mk, "\033[0n");
    mk->tw.vt = &mock_termwin_vt;
    term_notify_window_pos(mk->term, -3, -7);
    term_notify_window_size_pixels(mk->term, 800, 500);
    term_set_cell_size(mk->term, 8, 16);
    term_data_fragmented(mk->term, "\033[13t\033[14t\033[14;2t\033[15t\033[16t\033[19t");
    response(mk, "\033[3;65533;65529t\033[4;384;640t\033[4;500;800t\033[6;16;8t");
}

static unsigned model_resize_calls;
static bool model_defer_resize, model_deny_resize;
static int model_width, model_height;
static bool model_pixels;
static unsigned model_backend_calls;
static int model_backend_cols, model_backend_rows;

static void model_backend_size(Backend *be, int cols, int rows)
{
    model_backend_calls++;
    model_backend_cols = cols; model_backend_rows = rows;
}

static void finish_model_resize(Mock *mk)
{
    NemoWindowSize m = {
        .width = geometry.outer_width, .height = geometry.outer_height,
        .cols = mk->term->cols, .rows = mk->term->rows,
        .cell_width = 6, .cell_height = 13,
        .padding_width = 4, .padding_height = 4,
        .limit_width = 1024, .limit_height = 768,
    };
    int w, h;
    if (!model_deny_resize &&
        nemo_window_size(&m, model_width, model_height, model_pixels, &w, &h)) {
        geometry.outer_width = w; geometry.outer_height = h;
        geometry.text_width = w-4; geometry.text_height = h-4;
        term_size(mk->term, (h-4)/13, (w-4)/6, 0);
    }
    term_resize_request_completed(mk->term);
}

static void model_resize(TermWin *tw, int w, int h, bool pixels)
{
    Mock *mk = container_of(tw, Mock, tw);
    model_resize_calls++;
    model_width = w; model_height = h; model_pixels = pixels;
    if (!model_defer_resize) finish_model_resize(mk);
}

static void drain_model(Mock *mk)
{
    for (unsigned i = 0; i < 64; i++) {
        if (mk->term->win_resize_pending == WIN_RESIZE_NEED_SEND) term_update(mk->term);
        run_toplevel_callbacks();
        if (!bufchain_size(&mk->term->inbuf) &&
            mk->term->win_resize_pending == WIN_RESIZE_NO) return;
    }
    report_fail(mk, __FILE__, __LINE__, "resize response did not drain");
}

static void test_window_resize(Mock *mk)
{
    TermWinVtable vt = mock_termwin_vt;
    vt.get_geometry = mock_geometry;
    vt.request_window_resize = model_resize;
    mk->tw.vt = &vt;
    BackendVtable backend_vt = mock_backend_vt;
    backend_vt.size = model_backend_size;
    mk->backend.vt = &backend_vt;
    term_provide_backend(mk->term, &mk->backend);
    for (unsigned i = 0; i < lenof(window_resize_cases); i++) {
        reset(mk); test_context(mk, "independent resize: %s", window_resize_cases[i].name);
        geometry = (TermWindowGeometry) {
            .outer_width = 484, .outer_height = 316,
            .text_width = 480, .text_height = 312,
            .screen_width = 1024, .screen_height = 768,
            .cell_width = 6, .cell_height = 13,
        };
        term_data_fragmented(mk->term, window_resize_cases[i].sequence);
        drain_model(mk);
        /* Three documented frontend differences have an explicit expectation:
         * one complete cell minimum and immediately current geometry. Keep
         * the independent reply alongside it; never rewrite oracle evidence. */
        response(mk, window_resize_cases[i].adapted_reply ?
                 window_resize_cases[i].adapted_reply : window_resize_cases[i].reply);
    }
    reset(mk); test_context(mk, "resize completion orders following queries");
    model_defer_resize = true;
    term_data_fragmented(mk->term, "\033[8;30;90tZ\033[18t\033[5n");
    IEQUAL(mk->to_backend->len, 0);
    term_update(mk->term);
    IEQUAL(mk->term->win_resize_pending, WIN_RESIZE_AWAIT_REPLY);
    IEQUAL(mk->term->rows, 24); IEQUAL(mk->to_backend->len, 0);
    finish_model_resize(mk); model_defer_resize = false;
    drain_model(mk);
    response(mk, "\033[8;30;90t\033[0n");
    IEQUAL(get_termchar(mk->term, 0, 0).chr & ~CSET_MASK, 'Z');

    reset(mk); test_context(mk, "revoked permission and denied frontend recover parser");
    unsigned before = model_resize_calls;
    unsigned backend_before = model_backend_calls;
    term_data_fragmented(mk->term, "\033[4;210;482t\033[18t");
    mk->term->no_remote_resize = true;
    drain_model(mk);
    IEQUAL(model_resize_calls, before);
    IEQUAL(model_backend_calls, backend_before+1);
    IEQUAL(model_backend_cols, 80); IEQUAL(model_backend_rows, 24);
    response(mk, "\033[8;24;80t");
    term_data_fragmented(mk->term, "\033[8;0;0t\033[48t\033[18t");
    drain_model(mk);
    IEQUAL(model_resize_calls, before);
    IEQUAL(model_backend_calls, backend_before+3);
    response(mk, "\033[8;24;80t");
    mk->term->no_remote_resize = false;
    model_deny_resize = true;
    term_data_fragmented(mk->term, "\033[8;30;90t\033[18t");
    drain_model(mk); response(mk, "\033[8;24;80t");
    IEQUAL(model_backend_calls, backend_before+4);
    model_deny_resize = false;
    term_data_fragmented(mk->term, "\033[8;30;90t\033[18t");
    drain_model(mk); response(mk, "\033[8;30;90t");
    IEQUAL(model_backend_calls, backend_before+5);
    IEQUAL(model_backend_cols, 90); IEQUAL(model_backend_rows, 30);
    term_provide_backend(mk->term, NULL);
    mk->backend.vt = &mock_backend_vt;
    mk->tw.vt = &mock_termwin_vt;
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
    test_geometry(mk);
    test_window_resize(mk);
    test_graphics_queries(mk);
    test_dec_status(mk);
    test_checksums(mk);
    bool failed = mk->any_test_failed;
    mock_free(mk);
    puts(failed ? "Query suite FAILED" : "Query suite passed");
    return failed ? 1 : 0;
}
