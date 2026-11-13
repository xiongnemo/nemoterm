/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main
#include "../../../tests/tabulation_oracle_cases.h"
#include "../../../tests/double_size_oracle_cases.h"

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

static bool state_sync(TermWin *win, bool enabled) { return true; }

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
    IEQUAL(sizeof(t->saved_dec_modes),25*sizeof(int));
    state_reply(mk,"\033[?1r\033[?1$p","\033[?1;1$y");
}

int main(void)
{
    Mock *mk=mock_new();
    struct TermWinVtable vt=mock_termwin_vt;
    vt.set_synchronized_update=state_sync;
    mk->tw.vt=&vt;
    mk->term=term_init(mk->conf,mk->ucsdata,&mk->tw);
    mk->ldisc=ldisc_create(mk->conf,mk->term,&mk->backend,&mk->seat);
    test_soft_state(mk);
    test_soft_preservation(mk);
    test_soft_policy_and_palette(mk);
    test_saved_modes(mk);
    test_cursor_aliases_and_origin(mk);
    test_saved_extensions_and_recovery(mk);
    test_tabulation(mk);
    test_double_size(mk);
    bool failed=mk->any_test_failed;
    mock_free(mk);
    puts(failed ? "State control suite FAILED" : "State control suite passed");
    return failed ? 1 : 0;
}
