/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main
#include "../../../tests/tabulation_oracle_cases.h"
#include "../../../tests/double_size_oracle_cases.h"
#include "../../../tests/cursor_charset_cases.h"
#include "../../../tests/charset_reference.h"
#include "../../../tests/charset_parser_reference.h"
#include "../../../tests/charset_state_reference.h"
typedef struct { const char *name, *setup, *reply; size_t length; } CharsetInputCase;
#include "../../../tests/charset_input_reference.h"
#include "../../../tests/upss_input_reference.h"
#include "../../../tests/upss_reference.h"
#include "../../../tests/charset_checksum_reference.h"
#include "../../../tests/alignment_oracle_cases.h"

static void test_alignment(Mock *mk)
{
    for (size_t i = 0; i < lenof(alignment_oracle); i++) {
        reset(mk);
        term_size(mk->term, 24, 80, 200);
        test_context(mk, "alignment reference: %s", alignment_oracle[i].name);
        strbuf_clear(mk->to_backend);
        term_data_fragmented(mk->term, alignment_oracle[i].sequence);
        SEQUAL(mk->to_backend->s, alignment_oracle[i].reply);
    }

    reset(mk);
    test_context(mk, "alignment clears cell payloads and selection, but retains current RGB/protection");
    term_size(mk->term, 4, 8, 200);
    mk->ucsdata->line_codepage = CP_UTF8;
    term_data_fragmented(mk->term, "\033[38:2::1:2:3;48:2::4:5:6;1;4:3;53m"
                         "\033[1\"q\033]8;;https://example.invalid/alignment\033\\"
                         "\xe4\xb8\xad" "e\xcc\x81\033#6\033[2;1H\033#3");
    mk->term->selstate = SELECTED;
    mk->term->selstart = (pos){0, 0};
    mk->term->selend = (pos){2, 0};
    term_data_fragmented(mk->term, "\033#8");
    IEQUAL(mk->term->selstate, NO_SELECTION);
    for (int y = 0; y < 4; y++) {
        termline *line = term_get_line(mk->term, y);
        IEQUAL(line->lattr, LATTR_NORM);
        for (int x = 0; x < 8; x++) {
            termchar *ch = &line->chars[x];
            IEQUAL(ch->chr, 'E'); IEQUAL(ch->attr, ATTR_DEFAULT);
            IEQUAL(ch->cc_next, 0); IEQUAL(ch->hyperlink, 0);
            IEQUAL(ch->truecolour.decoration, 0);
            IEQUAL(ch->truecolour.fg.enabled, false);
            IEQUAL(ch->truecolour.bg.enabled, false);
        }
        term_release_line(line);
    }
    strbuf_clear(mk->to_backend);
    term_data_fragmented(mk->term, "\033P$qm\033\\\033P$q\"q\033\\Q");
    SEQUAL(mk->to_backend->s, "\033P1$r0;38:2::1:2:3;48:2::4:5:6m\033\\\033P1$r1\"q\033\\");
    termchar ch = get_termchar(mk->term, 0, 0);
    IEQUAL(ch.chr & ~CSET_MASK, 'Q');
    IEQUAL(ch.truecolour.fg.enabled, true); IEQUAL(ch.truecolour.fg.r, 1);
    IEQUAL(ch.truecolour.bg.enabled, true); IEQUAL(ch.truecolour.bg.b, 6);
    IEQUAL(ch.truecolour.decoration, CELL_PROTECTED);
    IEQUAL(ch.hyperlink != 0, true);

    reset(mk);
    test_context(mk, "alignment preserves text history and unrelated input/wrap/tab state");
    term_size(mk->term, 3, 8, 200);
    term_data_fragmented(mk->term, "HISTORY\r\nline2\r\nline3\r\n"
                         "\033[?1;69;2004h\033[?7l\033[4h\033[3g\033[1;4H\033H\033#8");
    IEQUAL(count234(mk->term->scrollback), 1);
    ch = get_termchar(mk->term, 0, -1);
    IEQUAL(ch.chr & ~CSET_MASK, 'H');
    IEQUAL(mk->term->lrmm, true); IEQUAL(mk->term->wrap, false);
    IEQUAL(mk->term->insert, true); IEQUAL(mk->term->app_cursor_keys, true);
    IEQUAL(mk->term->bracketed_paste, true); IEQUAL(mk->term->tabs[3], true);
    IEQUAL(mk->term->tabs[0], false);

    reset(mk);
    test_context(mk, "alignment one-cell grid and repeated payload replacement");
    term_size(mk->term, 1, 1, 0);
    for (int i = 0; i < 1000; i++) {
        term_data_fragmented(mk->term, "X\033#6\033#8");
        IEQUAL(mk->term->curs.x, 0); IEQUAL(mk->term->curs.y, 0);
        IEQUAL(mk->term->wrapnext, false);
        IEQUAL(get_termchar(mk->term, 0, 0).chr, 'E');
    }
}

static void test_double_size(Mock *mk)
{
    static const int columns[] = {0, 1, 2, 37, 38, 39, 40, 78, 79};
    for (size_t i = 0; i < lenof(double_size_oracle); i++) {
        reset(mk);
        mk->ucsdata->line_codepage = CP_UTF8;
        term_size(mk->term, 24, 80, 0);
        test_context(mk, "double-size: %s", double_size_oracle[i].name);
        strbuf_clear(mk->to_backend);
        term_data_fragmented(mk->term, double_size_oracle[i].sequence);
        SEQUAL(mk->to_backend->s, double_size_oracle[i].reply);
        for (int y = 0; y < 3; y++) {
            termline *line = term_get_line(mk->term, y);
            for (size_t j = 0; j < lenof(columns); j++) {
                termchar *ch = &line->chars[columns[j]];
                unsigned scalar = ch->chr;
                if (scalar == UCSWIDE) scalar = 0;
                else if (DIRECT_CHAR(scalar)) scalar &= ~CSET_MASK;
                /* XTerm composes this fixture's e + acute to U+00E9;
                 * retaining its exact decomposed sequence is equivalent. */
                if (scalar == 'e' && ch->cc_next &&
                    (ch + ch->cc_next)->chr == 0x301) scalar = 0xe9;
                test_context(mk, "%s cell %d,%d", double_size_oracle[i].name, y+1, columns[j]+1);
                IEQUAL(scalar, double_size_oracle[i].cells[y*lenof(columns)+j]);
            }
            term_release_line(line);
        }
    }

    reset(mk);
    test_context(mk, "wrapped output uses the destination row's own width");
    term_size(mk->term, 3, 80, 0);
    term_data_fragmented(mk->term, "\033#6");
    for (int i = 0; i < 40; i++) term_data_fragmented(mk->term, "A");
    for (int i = 0; i < 80; i++) term_data_fragmented(mk->term, "B");
    IEQUAL(mk->term->curs.y, 1); IEQUAL(mk->term->curs.x, 79);
    IEQUAL(mk->term->wrapnext, true);
    for (int x = 0; x < 80; x++) IEQUAL(get_termchar(mk->term, x, 1).chr, CSET_ASCII|'B');
    term_data_fragmented(mk->term, "C");
    IEQUAL(mk->term->curs.y, 2); IEQUAL(mk->term->curs.x, 1);
}

static void test_tabulation(Mock *mk)
{
    for (size_t i = 0; i < lenof(tabulation_oracle); i++) {
        reset(mk);
        test_context(mk, "tabulation: %s", tabulation_oracle[i].name);
        term_size(mk->term, 24, 80, 0);
        strbuf_clear(mk->to_backend);
        term_data_fragmented(mk->term, tabulation_oracle[i].sequence);
        SEQUAL(mk->to_backend->s, tabulation_oracle[i].reply);
    }

    reset(mk);
    test_context(mk, "backward tabs stop at the origin's left margin");
    term_data_fragmented(mk->term, "\033[?69h\033[5;20s\033[?6h\033[999Z");
    IEQUAL(mk->term->curs.x, 4);

    reset(mk);
    test_context(mk, "tabulation rejects colon subparameters without changes");
    term_data_fragmented(mk->term, "\033[3g\033[1;5H\033H\033[1;10H"
                         "\033[2:3I\033[2:3Z\033[?5:1W");
    IEQUAL(mk->term->curs.x, 9);
    IEQUAL(mk->term->tabs[4], true);
    IEQUAL(mk->term->tabs[8], false);

    reset(mk);
    test_context(mk, "tab movement leaves text and attributes untouched");
    term_data_fragmented(mk->term, "\033[31;44;1mKEPT\033[1;1H\033[999I\033[999Z");
    for (int x = 0; x < 4; x++) {
        termchar ch = get_termchar(mk->term, x, 0);
        IEQUAL(ch.chr & ~CSET_MASK, "KEPT"[x]);
        IEQUAL(ch.attr & ATTR_BOLD, ATTR_BOLD);
        IEQUAL((ch.attr & ATTR_FGMASK) >> ATTR_FGSHIFT, 1);
        IEQUAL((ch.attr & ATTR_BGMASK) >> ATTR_BGSHIFT, 4);
    }

    reset(mk);
    test_context(mk, "one-column double-width line remains in bounds");
    term_size(mk->term, 1, 1, 0);
    term_data_fragmented(mk->term, "\033#6\t\033[I\033[Z\033[?5W");
    IEQUAL(mk->term->curs.x, 0);
    IEQUAL(mk->term->curs.y, 0);
}

static void state_reply(Mock *mk, const char *input, const char *expected)
{
    strbuf_clear(mk->to_backend);
    term_data_fragmented(mk->term, input);
    SEQUAL(mk->to_backend->s, expected);
}

static void test_cursor_charsets(Mock *mk)
{
    Terminal *t = mk->term;
    int old_codepage = mk->ucsdata->line_codepage;
    bool old_linedraw = conf_get_bool(mk->conf, CONF_utf8linedraw);
    conf_set_bool(mk->conf, CONF_utf8linedraw, true);
    term_reconfig(t, mk->conf);
    mk->ucsdata->line_codepage = CP_UTF8;
    for (size_t i = 0; i < lenof(cursor_charset_cases); i++) {
        reset(mk);
        test_context(mk, "authored cursor charset: %s", cursor_charset_cases[i].name);
        state_reply(mk, cursor_charset_cases[i].sequence, cursor_charset_cases[i].reply);
        IEQUAL(mk->clipboard_writes, 0);
    }

    reset(mk);
    mk->ucsdata->line_codepage = CP_ISO8859_1;
    test_context(mk, "restored inactive banks and GR produce line-drawing cells");
    term_data_fragmented(t, "\033(0\033)0\033*0\033+0\033n\033|\0337"
                         "\033(B\033)B\033*B\033+B\017\033~\0338"
                         "\017q\016q\033nq\033oq\361");
    for (int x = 0; x < 5; x++)
        IEQUAL(get_termchar(t, x, 0).chr, CSET_LINEDRW|'q');
    IEQUAL(t->cset_gr, 3);
    IEQUAL(t->curs.x, 5);

    reset(mk);
    test_context(mk, "PuTTY SCO designations are retained in all saved banks");
    term_data_fragmented(t, "\033(U\033)U\033*U\033+U\0337"
                         "\033(B\033)B\033*B\033+B\0338");
    for (size_t i = 0; i < lenof(t->cset_attr); i++)
        IEQUAL(t->cset_attr[i], CSET_SCOACS);

    reset(mk);
    test_context(mk, "saved charset state obeys the current local prohibition");
    term_data_fragmented(t, "\033%G\033(0\033)0\033*0\033+0\033n\033|"
                         "\033[12m\0337\017\033}");
    conf_set_bool(mk->conf, CONF_no_remote_charset, true);
    term_reconfig(t, mk->conf);
    term_data_fragmented(t, "\0338");
    IEQUAL(t->cset, 0); IEQUAL(t->cset_gr, 2);
    IEQUAL(t->utf, false); IEQUAL(t->sco_acs, 0);
    for (size_t i = 0; i < lenof(t->cset_attr); i++)
        IEQUAL(t->cset_attr[i], CSET_ASCII);
    conf_set_bool(mk->conf, CONF_no_remote_charset, false);
    term_reconfig(t, mk->conf);
    term_data_fragmented(t, "\0338");
    IEQUAL(t->cset, 2); IEQUAL(t->cset_gr, 3);
    /* Encoding is global, not part of DECSC. Reconfiguration revoked it. */
    IEQUAL(t->utf, false); IEQUAL(t->sco_acs, 2);
    for (size_t i = 0; i < lenof(t->cset_attr); i++)
        IEQUAL(t->cset_attr[i], CSET_LINEDRW);

    conf_set_bool(mk->conf, CONF_utf8linedraw, old_linedraw);
    term_reconfig(t, mk->conf);
    mk->ucsdata->line_codepage = old_codepage;
    reset(mk);
}

static void test_iso2022_parser(Mock *mk)
{
    bool old_checksum = conf_get_bool(mk->conf, CONF_nemo_allow_checksum);
    conf_set_bool(mk->conf, CONF_nemo_allow_checksum, true);
    term_reconfig(mk->term, mk->conf);
    mk->ucsdata->line_codepage = CP_UTF8;
    IEQUAL(lenof(charset_reference), lenof(charset_parser_reference));
    for (unsigned fragmented = 0; fragmented < 2; fragmented++) {
        for (size_t i = 0; i < lenof(charset_checksum_reference); i++) {
            reset(mk);
            test_context(mk, "charset checksum %s / fragmented %u",
                         charset_checksum_reference[i].name, fragmented);
            strbuf *input = strbuf_new(), *expected = strbuf_new();
            put_dataz(input, charset_checksum_reference[i].setup);
            for (unsigned n = 0; n < 96; n++) {
                put_fmt(input, "\033[%u;%uH", n/48+1, n%48+1);
                put_byte(input, n+0x20+(charset_checksum_reference[i].right ? 0x80 : 0));
            }
            put_dataz(input, "\033[65;1\"p");
            for (unsigned mode = 0; mode < 2; mode++) {
                put_fmt(input, "\033[%u#y", mode ? 31 : 15);
                for (unsigned n = 0; n < 96; n++) {
                    unsigned row=n/48+1, col=n%48+1;
                    put_fmt(input, "\033[%u;1;%u;%u;%u;%u*y", n+1,row,col,row,col);
                    put_fmt(expected, "\033P%u!~%04X\033\\", n+1,
                            charset_checksum_reference[i].sums[mode][n]);
                }
            }
            put_dataz(input, "\033[?42l\033%G");
            if (fragmented) term_data_fragmented(mk->term, input->s);
            else term_data(mk->term, input->s, input->len);
            SEQUAL(mk->to_backend->s, expected->s);
            strbuf_free(input); strbuf_free(expected);
        }
        for (size_t i = 0; i < lenof(charset_checksum_lifetime); i++) {
            reset(mk);
            test_context(mk, "charset checksum lifetime %s / fragmented %u",
                         charset_checksum_lifetime[i].name, fragmented);
            if (fragmented) term_data_fragmented(mk->term, charset_checksum_lifetime[i].input);
            else term_data(mk->term, charset_checksum_lifetime[i].input,
                           strlen(charset_checksum_lifetime[i].input));
            const char *expected = charset_checksum_lifetime[i].reply;
            /* Preserve these four independently captured differences. XTerm
             * leaves old charSets behind on ICH/DCH and plain ASCII overwrite.
             * Our checksum follows the copied/overwritten glyph's own source.
             * REP retains our existing last-glyph/cluster lifetime across CUP. */
            static const struct { const char *name, *reply; } differences[] = {
                {"repeat", "\033P1501!~005D\033\\\033P1502!~005D\033\\\033P1503!~005D\033\\"
                    "\033P3101!~00DC\033\\\033P3102!~00DC\033\\\033P3103!~00DC\033\\"},
                {"insert", "\033P1501!~005B\033\\\033P1502!~0020\033\\\033P1503!~005C\033\\\033P1504!~005D\033\\"
                    "\033P3101!~00C4\033\\\033P3102!~0020\033\\\033P3103!~00D6\033\\\033P3104!~00DC\033\\"},
                {"delete", "\033P1501!~005B\033\\\033P1502!~005D\033\\\033P1503!~0020\033\\\033P1504!~0020\033\\"
                    "\033P3101!~00C4\033\\\033P3102!~00DC\033\\\033P3103!~0020\033\\\033P3104!~0020\033\\"},
                {"byte-nrc-overwrite", "\033P1501!~0023\033\\\033P3101!~0023\033\\"},
            };
            for (size_t d = 0; d < lenof(differences); d++) {
                if (strcmp(charset_checksum_lifetime[i].name, differences[d].name)) continue;
                IEQUAL(strcmp(expected, differences[d].reply) != 0, true);
                expected = differences[d].reply;
            }
            SEQUAL(mk->to_backend->s, expected);
        }
        for (size_t i = 0; i < lenof(charset_reference); i++) {
            reset(mk);
            test_context(mk, "ISO 2022 parser %s / fragmented %u",
                         charset_reference[i].name, fragmented);
            strbuf *input = strbuf_new(), *expected = strbuf_new();
            put_dataz(input, charset_parser_reference[i].setup);
            for (unsigned n = 0; n < 96; n++) {
                put_fmt(input, "\033[%u;%uH", n/48+1, n%48+1);
                put_byte(input, n+0x20+(charset_reference[i].right ? 0x80 : 0));
            }
            put_dataz(input, "\033[31#y");
            for (unsigned n = 0; n < 96; n++) {
                unsigned row=n/48+1, col=n%48+1;
                put_fmt(input, "\033[%u;1;%u;%u;%u;%u*y", n+1, row,col,row,col);
                put_fmt(expected, "\033P%u!~%04X\033\\", n+1, charset_reference[i].cells[n]);
            }
            put_dataz(input, "\033[1$w\033[?42$p\033[?42l\033%G");
            put_dataz(expected, charset_parser_reference[i].tail);
            if (fragmented) term_data_fragmented(mk->term, input->s);
            else term_data(mk->term, input->s, input->len);
            if (expected->len != mk->to_backend->len ||
                memcmp(expected->s, mk->to_backend->s, expected->len)) {
                size_t pos=0;
                while (pos < expected->len && pos < mk->to_backend->len &&
                       expected->s[pos] == mk->to_backend->s[pos]) pos++;
                report_fail(mk, __FILE__, __LINE__,
                    "reply differs at byte %zu, expected %.64s, actual %.64s (%zu/%zu bytes)",
                    pos, expected->s+pos, mk->to_backend->s+pos,
                    expected->len, mk->to_backend->len);
            }
            IEQUAL(mk->clipboard_writes, 0);
            strbuf_free(input); strbuf_free(expected);
        }
        for (size_t i = 0; i < lenof(charset_state_reference); i++) {
            reset(mk);
            test_context(mk, "ISO 2022 transition %s / fragmented %u",
                         charset_state_reference[i].name, fragmented);
            if (fragmented) term_data_fragmented(mk->term, charset_state_reference[i].input);
            else term_data(mk->term, charset_state_reference[i].input,
                           strlen(charset_state_reference[i].input));
            SEQUAL(mk->to_backend->s, charset_state_reference[i].reply);
        }
        for (size_t i = 0; i < lenof(upss_reference); i++) {
            reset(mk);
            test_context(mk, "UPSS %s / fragmented %u", upss_reference[i].name, fragmented);
            if (fragmented) term_data_fragmented(mk->term, upss_reference[i].input);
            else term_data(mk->term, upss_reference[i].input, strlen(upss_reference[i].input));
            SEQUAL(mk->to_backend->s, upss_reference[i].reply);
        }
    }
    reset(mk);
    test_context(mk, "UPSS requires its own explicit size after another DCS");
    term_data_fragmented(mk->term, "\033%G\033%@\033P1!uA\033\\"
        "\033P1$t1;1;1;@;@;@;0;2;@;BBBB\033\\\033P!uF\033\\\033[&u");
    SEQUAL(mk->to_backend->s, "\033P1!uA\033\\");
    test_context(mk, "local character-set policy blocks UPSS assignments");
    conf_set_bool(mk->conf, CONF_no_remote_charset, true);
    term_reconfig(mk->term, mk->conf);
    unsigned blocked_upss = mk->term->upss_id;
    term_data_fragmented(mk->term, "\033%@\033P1!uF\033\\");
    IEQUAL(mk->term->upss_id, blocked_upss);
    conf_set_bool(mk->conf, CONF_no_remote_charset, false);
    term_reconfig(mk->term, mk->conf);
    reset(mk);
    test_context(mk, "NRCS visible Unicode survives selection and rectangle fill");
    term_data_fragmented(mk->term, "\033%G\033[?42h\033(K[\\]"
                         "\033[91;2;1;2;3$x");
    for (int col=0; col<3; col++) IEQUAL(get_termchar(mk->term,col,1).chr,0x00c4);
    term_mouse(mk->term, MBT_LEFT, MBT_SELECT, MA_CLICK, 0,0,true,false,false);
    term_mouse(mk->term, MBT_LEFT, MBT_SELECT, MA_DRAG, 2,0,true,false,false);
    term_mouse(mk->term, MBT_LEFT, MBT_SELECT, MA_RELEASE, 2,0,false,false,false);
    int clipboard=CLIP_LOCAL+1;
    term_request_copy(mk->term,&clipboard,1);
    check_clipboard(mk,L"\x00c4\x00d6\x00dc");

    reset(mk);
    test_context(mk, "charset checksum metadata survives compressed history and reflow");
    term_size(mk->term, 2, 8, 200);
    term_data_fragmented(mk->term, "\033%G\033[?42h\033(K[\\]\r\nX\r\nY");
    IEQUAL(count234(mk->term->scrollback) > 0, true);
    for (unsigned pass = 0; pass < 2; pass++) {
        unsigned seen = 0;
        for (int y = -count234(mk->term->scrollback); y < mk->term->rows; y++) {
            termline *line = term_get_line(mk->term, y);
            for (int x = 0; x < line->cols; x++) {
                const termchar *ch = &line->chars[x];
                unsigned code = ch->chr == 0xc4 ? 0x5b : ch->chr == 0xd6 ? 0x5c : ch->chr == 0xdc ? 0x5d : 0;
                if (!code) continue;
                IEQUAL(!!(ch->truecolour.decoration & CELL_CHECKSUM_VALID), true);
                IEQUAL((ch->truecolour.decoration & CELL_CHECKSUM_VALUE) >> CELL_CHECKSUM_SHIFT, code);
                seen++;
            }
            term_release_line(line);
        }
        IEQUAL(seen, 3);
        term_size(mk->term, 4, 2, 200);
    }
    term_size(mk->term, 24, 80, 200);
    conf_set_bool(mk->conf, CONF_nemo_allow_checksum, old_checksum);
    term_reconfig(mk->term, mk->conf);
    reset(mk);
}

static bool state_sync(TermWin *win, bool enabled) { return true; }
static void state_bell(TermWin *win, int mode) { (void)win; (void)mode; }

static void test_iso2022_paste(Mock *mk)
{
    wchar_t text[2*lenof(charset_input_text)];
    size_t length=0;
    strbuf *utf8=strbuf_new();
    for (size_t i=0;i<lenof(charset_input_text);i++) {
        uint32_t scalar=charset_input_text[i];
        put_utf8_char(utf8,scalar);
#ifdef PLATFORM_IS_UTF16
        if (scalar>0xffff) {
            text[length++]=0xd800+((scalar-0x10000)>>10);
            text[length++]=0xdc00+((scalar-0x10000)&1023);
        } else
#endif
            text[length++]=scalar;
    }
    mk->ucsdata->line_codepage=CP_UTF8;
    IEQUAL(sizeof(upss_input_text),sizeof(charset_input_text));
    IEQUAL(!memcmp(upss_input_text,charset_input_text,sizeof(charset_input_text)),true);
    for (unsigned suite=0;suite<2;suite++) {
      const CharsetInputCase *cases=suite ? upss_input_reference : charset_input_reference;
      size_t count=suite ? lenof(upss_input_reference) : lenof(charset_input_reference);
      for (size_t i=0;i<count;i++) {
        reset(mk);
        test_context(mk,"ISO 2022 independent selection input: %s",cases[i].name);
        term_data_fragmented(mk->term,cases[i].setup);
        term_do_paste(mk->term,text,length);
        unsigned callbacks=0;
        while (mk->term->paste_len && callbacks++<10) run_toplevel_callbacks();
        IEQUAL(mk->term->paste_len,0);
        IEQUAL(mk->to_backend->len,cases[i].length);
        size_t common=min(mk->to_backend->len,cases[i].length);
        for (size_t n=0;n<common;n++) if (mk->to_backend->s[n]!=cases[i].reply[n]) {
            report_fail(mk,__FILE__,__LINE__,"selection byte %zu: %02x != %02x",n,
                (unsigned char)mk->to_backend->s[n],(unsigned char)cases[i].reply[n]);
            break;
        }
        strbuf_clear(mk->to_backend);
        /* NRC selection conversion must not replace configured Unicode typing. */
        term_keyinputw(mk->term,text,length);
        IEQUAL(mk->to_backend->len,utf8->len);
        IEQUAL(mk->to_backend->len==utf8->len && !memcmp(mk->to_backend->s,utf8->s,utf8->len),true);
      }
    }
    strbuf_free(utf8);
    reset(mk);
    test_context(mk,"configured byte keyboard input observes temporary UTF-8 override");
    mk->ucsdata->line_codepage=CP_ISO8859_1;
    term_data_fragmented(mk->term,"\033%G");
    term_keyinput(mk->term,CP_ISO8859_1,"\243",1);
    SEQUAL(mk->to_backend->s,"\302\243");
    mk->ucsdata->line_codepage=CP_UTF8;
    reset(mk);
}

static void test_soft_state(Mock *mk)
{
    reset(mk);
    test_context(mk, "DECSTR resets operating state and only the active saved cursor");
    Terminal *t=mk->term;
    term_data_fragmented(t, "\033[3;12r\033[?1;5;6;66;1003;1016;1004;1007;2004h"
        "\033[4h\033[12l\033[20h\033[?7;8;25l\033[6 q\033[>4;2m\033[>4;1f"
        "\033[5;9H\0337\033[1;2;3;4:3;9;38;2;1;2;3;58;2;4;5;6m\033[!p");
    IEQUAL(t->curs.x,8);IEQUAL(t->curs.y,6);
    IEQUAL(t->marg_t,0);IEQUAL(t->marg_b,23);
    IEQUAL(t->insert,false);IEQUAL(t->dec_om,false);
    IEQUAL(t->app_cursor_keys,false);IEQUAL(t->app_keypad_keys,false);
    IEQUAL(t->wrap,true);IEQUAL(t->cursor_on,true);
    IEQUAL(t->curr_attr,ATTR_DEFAULT);
    IEQUAL(t->curr_truecolour.fg.enabled,false);
    IEQUAL(t->curr_truecolour.bg.enabled,false);
    IEQUAL(t->curr_truecolour.decoration,0);
    IEQUAL(t->modify_keys.level,0);IEQUAL(t->modify_keys.format,0);
    IEQUAL(t->rvideo,true);IEQUAL(t->repeat_off,true);
    IEQUAL(t->srm_echo,true);IEQUAL(t->cr_lf_return,true);
    IEQUAL(t->xterm_mouse,3);IEQUAL(t->mouse_encoding,1016);
    IEQUAL(t->mouse_focus_reporting,true);IEQUAL(t->mouse_alternate_scroll,true);
    IEQUAL(t->bracketed_paste,true);
    state_reply(mk,"\033P$qm\033\\\033P$qr\033\\\033[6n\0338\033[6n",
        "\033P1$r0m\033\\\033P1$r1;24r\033\\\033[7;9R\033[1;1R");

    reset(mk);
    term_data_fragmented(t,"\033[5;6H\033[31m\033]8;;https://example.org/main\033\\\0337"
        "\033[?1049h\033[9;10H\033[32m\0337\033[!p");
    IEQUAL(t->alt_which,1);IEQUAL(t->curs.x,9);IEQUAL(t->curs.y,8);
    IEQUAL(t->curr_hyperlink,0);IEQUAL(t->save_hyperlink,0);
    state_reply(mk,"\033[6n\0338\033[6n\033[?1049l\033[6n",
        "\033[9;10R\033[1;1R\033[5;6R");
    IEQUAL((t->curr_attr & ATTR_FGMASK)>>ATTR_FGSHIFT,1);
    IEQUAL(t->curr_hyperlink!=0,true);
}

static void test_soft_preservation(Mock *mk)
{
    reset(mk);
    test_context(mk, "soft reset preserves text, history, images, viewport, tabs and transports");
    Terminal *t=mk->term;
    term_size(t,8,40,100);
    for (int i=0;i<80;i++) term_data_fragmented(t,"history line\r\n");
    term_data_fragmented(t,"\033[3g\033[1;5H\033H\033[1;1H"
        "\033]8;;https://example.org/kept\033\\\033[38;2;10;20;30mKEPT\033]8;;\033\\"
        "\033[2;1H\033P0;1q\"1;1;32;32#1;2;100;0;0!32~\033\\"
        "\033[?1003;1016;1004;2004;9001;80;8452h\033[?1070l\033[>31u\033%G");
    tree234 *screen=t->screen,*history=t->scrollback;
    NemoTermImage *images=t->images;
    termchar kept=get_termchar(t,0,0);
    int rows=count234(history);
    t->disptop=-3;
    term_data_fragmented(t,"\033[?2026h");
    unsigned long deadline=t->synchronized_update_deadline;
    unsigned epoch=t->win32_input_epoch;
    term_data_fragmented(t,"\033[!p");
    IEQUAL(t->screen==screen,true);IEQUAL(t->scrollback==history,true);
    IEQUAL(count234(history),rows);IEQUAL(t->images==images,true);
    IEQUAL(images!=NULL,true);IEQUAL(t->disptop,-3);
    termchar after=get_termchar(t,0,0);
    IEQUAL(after.chr,kept.chr);IEQUAL(after.attr,kept.attr);
    IEQUAL(after.truecolour.fg.r,kept.truecolour.fg.r);
    IEQUAL(after.hyperlink,kept.hyperlink);IEQUAL(after.hyperlink!=0,true);
    IEQUAL(t->tabs[4],true);IEQUAL(t->tabs[8],false);
    IEQUAL(t->utf,true);IEQUAL(t->xterm_mouse,3);IEQUAL(t->mouse_encoding,1016);
    IEQUAL(t->win32_input,true);IEQUAL(t->win32_input_epoch,epoch);
    IEQUAL(nemo_keyboard_flags(&t->keyboard[0]),31);
    IEQUAL(t->sixel_display_mode,true);IEQUAL(t->sixel_scrolls_right,true);
    IEQUAL(t->sixel_private_palette,false);
    IEQUAL(t->synchronized_update,true);IEQUAL(t->synchronized_update_deadline,deadline);
    term_data_fragmented(t,"\033[?2026l\033[1;1H\t");
    IEQUAL(t->curs.x,4);
    term_data_fragmented(t,"\033[!p\xe4\xb8\xad");
    IEQUAL(t->curs.x,6);

    reset(mk);
    term_data_fragmented(t,"\033[1;80HX\033[!pY");
    IEQUAL(t->curs.x,1);IEQUAL(t->curs.y,1);
    IEQUAL(get_termchar(t,79,0).chr,CSET_ASCII|'X');
    IEQUAL(get_termchar(t,0,1).chr,CSET_ASCII|'Y');
    term_data_fragmented(t,"\033(0q\033)0\016q\033[!pq");
    IEQUAL(t->cset,0);IEQUAL(t->cset_attr[0],CSET_ASCII);
    IEQUAL(t->cset_attr[1],CSET_ASCII);
    IEQUAL(get_termchar(t,3,1).chr,CSET_ASCII|'q');
}

static void test_soft_policy_and_palette(Mock *mk)
{
    reset(mk);
    test_context(mk,"soft reset restores configured defaults and indexed colours only");
    Terminal *t=mk->term;
    conf_set_bool(mk->conf,CONF_wrap_mode,false);
    conf_set_bool(mk->conf,CONF_app_cursor,true);
    conf_set_bool(mk->conf,CONF_app_keypad,true);
    conf_set_int(mk->conf,CONF_cursor_type,CURSOR_UNDERLINE);
    conf_set_bool(mk->conf,CONF_blink_cur,false);
    conf_set_int(mk->conf,CONF_nemo_modify_other_keys,3);
    conf_set_int(mk->conf,CONF_nemo_format_other_keys,1);
    term_reconfig(t,mk->conf);
    term_data_fragmented(t,"\033]4;1;#123456\007\033]10;#345678\007"
        "\033[?7h\033[?1;66l\033[6 q\033[>4;0m\033[!p");
    IEQUAL(t->wrap,false);IEQUAL(t->app_cursor_keys,true);IEQUAL(t->app_keypad_keys,true);
    IEQUAL(t->cursor_type,CURSOR_UNDERLINE);IEQUAL(t->blink_cur,false);
    IEQUAL(t->modify_keys.level,3);IEQUAL(t->modify_keys.format,1);
    IEQUAL(t->subpalettes[SUBPAL_SESSION].present[1],false);
    state_reply(mk,"\033]10;?\007","\033]10;rgb:3434/5656/7878\007");
    conf_set_bool(mk->conf,CONF_wrap_mode,true);
    conf_set_bool(mk->conf,CONF_app_cursor,false);
    conf_set_bool(mk->conf,CONF_app_keypad,false);
    conf_set_int(mk->conf,CONF_nemo_modify_other_keys,0);
    conf_set_int(mk->conf,CONF_nemo_format_other_keys,0);
    term_reconfig(t,mk->conf);
}

static void test_saved_modes(Mock *mk)
{
    reset(mk);
    test_context(mk,"private save cache is independent, shared by groups and retained across reset");
    memset(mk->term->saved_dec_modes,0,sizeof(mk->term->saved_dec_modes));
    state_reply(mk,"\033[?7r\033[?7$p","\033[?7;2$y");
    state_reply(mk,"\033[?1;7;25h\033[?1;7;25s\033[?1;7;25l\033[?1;25r"
        "\033[?1$p\033[?7$p\033[?25$p","\033[?1;1$y\033[?7;2$y\033[?25;1$y");
    state_reply(mk,"\033[?1l\033[?1s\033[?1h\033[?1r\033[?1$p","\033[?1;2$y");
    state_reply(mk,"\033[?1h\033[?1s\033[!p\033[?1r\033[?1$p"
        "\033c\033[?1r\033[?1$p","\033[?1;1$y\033[?1;1$y");
    state_reply(mk,"\033[?1003;1016h\033[?1000;1006s\033[?1002;1005h\033[?1001;1015r"
        "\033[?1003$p\033[?1016$p","\033[?1003;1$y\033[?1016;1$y");
    state_reply(mk,"\033[?9s\033[?1002h\033[?1000s\033[?9r\033[?1003$p"
        "\033[?1002r\033[?1002$p","\033[?1003;1$y\033[?1002;1$y");
    state_reply(mk,"\033[?1016s\033[?1005h\033[?1015s\033[?1006h\033[?1016r\033[?1005$p",
        "\033[?1005;1$y");
    state_reply(mk,"\033[?1005l\033[?1016s\033[?1006h\033[?1005r\033[?1006$p",
        "\033[?1006;2$y");

    static const unsigned modes[]={5,6,7,8,12,25,66,80,1004,1007,1070,2004,8452};
    for (size_t i=0;i<lenof(modes);i++) {
        char command[128],expected[32];unsigned m=modes[i];
        for (int initial=0;initial<2;initial++) {
            test_context(mk,"save mode %u initial %d",m,initial);
            snprintf(command,sizeof(command),"\033[?%u%c\033[?%us\033[?%u%c\033[?%ur\033[?%u$p",
                m,initial?'h':'l',m,m,initial?'l':'h',m,m);
            snprintf(expected,sizeof(expected),"\033[?%u;%d$y",m,initial?1:2);
            state_reply(mk,command,expected);
        }
    }
}

static void test_cursor_aliases_and_origin(Mock *mk)
{
    reset(mk);
    test_context(mk,"1048 cursor alias, shared alternate slot and origin-relative CPR");
    state_reply(mk,"\033[5;6H\033[?1048s\033[1;2H\033[?1048r\033[6n","\033[5;6R");
    term_data_fragmented(mk->term,"MAIN\033[?47hALT\033[?1047s\033[?47l\033[?1049r");
    IEQUAL(mk->term->alt_which,1);
    IEQUAL(get_termchar(mk->term,0,0).chr,CSET_ASCII|'A');
    term_data_fragmented(mk->term,"\033[?47l");
    IEQUAL(get_termchar(mk->term,5,4).chr,CSET_ASCII|'M');
    state_reply(mk,"\033[3;12r\033[8;9H\033[?6h\033[6n\033[4;5H\033[6n\033[?6l\033[6n",
        "\033[1;1R\033[4;5R\033[1;1R");
    state_reply(mk,"\033[?6h\033[?6s\033[?6l\033[8;9H\033[?6r\033[6n","\033[1;1R");
    state_reply(mk,"\033[4;5H\0337\033[?6l\0338\033[?6$p\033[6n",
        "\033[?6;1$y\033[4;5R");
    state_reply(mk,"\033[?6l\033[8;20r\0338\033[6n","\033[1;5R");
}

static void test_saved_extensions_and_recovery(Mock *mk)
{
    reset(mk);
    test_context(mk,"saved modes respect local prohibitions and bounded fragmented parsing");
    Terminal *t=mk->term;
    conf_set_bool(mk->conf,CONF_nemo_win32_input,true);
    term_reconfig(t,mk->conf);
    state_reply(mk,"\033[?9001h\033[?9001s\033[?9001l\033[?9001r\033[?9001$p",
        "\033[?9001;1$y");
    state_reply(mk,"\033[?2026h\033[?2026s\033[?2026l\033[?2026r\033[?2026$p",
        "\033[?2026;1$y");
    term_data_fragmented(t,"\033[?2026l\033[?1003;66;2004h\033[?1003;66;2004s");
    conf_set_bool(mk->conf,CONF_no_mouse_rep,true);
    conf_set_bool(mk->conf,CONF_no_applic_k,true);
    conf_set_bool(mk->conf,CONF_no_bracketed_paste,true);
    conf_set_bool(mk->conf,CONF_nemo_win32_input,false);
    term_reconfig(t,mk->conf);
    state_reply(mk,"\033[?1003;66;2004;9001l\033[?1003;66;2004;9001r"
        "\033[?1003$p\033[?66$p\033[?2004$p\033[?9001$p",
        "\033[?1003;4$y\033[?66;4$y\033[?2004;4$y\033[?9001;4$y");
    IEQUAL(t->xterm_mouse,0);IEQUAL(t->app_keypad_keys,false);
    IEQUAL(t->bracketed_paste,false);IEQUAL(t->win32_input,false);
    conf_set_bool(mk->conf,CONF_no_mouse_rep,false);
    conf_set_bool(mk->conf,CONF_no_applic_k,false);
    conf_set_bool(mk->conf,CONF_no_bracketed_paste,false);
    term_reconfig(t,mk->conf);
    state_reply(mk,"\033[?1h\033[?1s\033[?1l\033[?1\030r\033[?1$p"
        "\033[?1:2r\033[?1$p\033[?1r\033[?1$p",
        "\033[?1;2$y\033[?1;2$y\033[?1;1$y");
    state_reply(mk,"\033[?1h\033[!\032p\033[?1$p\033[!1:2p\033[?1$p"
        "\033[123!p\033[?1$p","\033[?1;1$y\033[?1;1$y\033[?1;2$y");
    for (int i=0;i<20000;i++) term_data_fragmented(t,"\033[?4294967295;99999s\033[?4294967295;99999r");
    IEQUAL(sizeof(t->saved_dec_modes),26*sizeof(int));
    state_reply(mk,"\033[?1r\033[?1$p","\033[?1;1$y");
}

#include "test_bell.inc"

int main(void)
{
    Mock *mk=mock_new();
    struct TermWinVtable vt=mock_termwin_vt;
    vt.set_synchronized_update=state_sync;
    vt.bell=state_bell;
    mk->tw.vt=&vt;
    mk->term=term_init(mk->conf,mk->ucsdata,&mk->tw);
    mk->ldisc=ldisc_create(mk->conf,mk->term,&mk->backend,&mk->seat);
    /* This fixture runs the event loop; the synchronous parser matrices below
     * intentionally accumulate update callbacks until mock_free. */
    test_iso2022_paste(mk);
    test_soft_state(mk);
    test_soft_preservation(mk);
    test_soft_policy_and_palette(mk);
    test_saved_modes(mk);
    test_cursor_aliases_and_origin(mk);
    test_cursor_charsets(mk);
    test_iso2022_parser(mk);
    test_saved_extensions_and_recovery(mk);
    test_tabulation(mk);
    test_double_size(mk);
    test_alignment(mk);
    test_bell_policy(mk);
    bool failed=mk->any_test_failed;
    mock_free(mk);
    puts(failed ? "State control suite FAILED" : "State control suite passed");
    return failed ? 1 : 0;
}
