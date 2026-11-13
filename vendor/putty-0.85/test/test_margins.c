/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main
#include "../../../tests/margin_oracle_cases.h"
#include "../../../tests/horizontal_oracle_cases.h"
#include "../../../tests/reverse_wrap_oracle_cases.h"

static void test_reverse_wrap_oracle(Mock *mk)
{
    for (size_t i = 0; i < lenof(reverse_wrap_oracle); i++) {
        reset(mk); test_context(mk, "%s", reverse_wrap_oracle[i].name);
        mk->ucsdata->line_codepage = CP_UTF8;
        term_size(mk->term, 24, 80, 100);
        strbuf_clear(mk->to_backend);
        term_data_fragmented(mk->term, reverse_wrap_oracle[i].sequence);
        SEQUAL(mk->to_backend->s, reverse_wrap_oracle[i].reply);
        for (size_t j = 0; j < lenof(reverse_wrap_cells); j++) {
            int x = reverse_wrap_cells[j][1]-1, y = reverse_wrap_cells[j][0]-1;
            unsigned ch = get_termchar(mk->term, x, y).chr;
            if (ch == UCSWIDE) ch = 0;
            else if (DIRECT_CHAR(ch)) ch &= ~CSET_MASK;
            test_context(mk, "%s at %d,%d", reverse_wrap_oracle[i].name,y+1,x+1);
            IEQUAL(ch, reverse_wrap_oracle[i].cells[j]);
        }
    }
    for (size_t i = 0; i < lenof(reverse_wrap_direct); i++) {
        reset(mk); term_size(mk->term, 24, 80, 100);
        test_context(mk, "%s", reverse_wrap_direct[i].name);
        strbuf_clear(mk->to_backend);
        term_data_fragmented(mk->term, reverse_wrap_direct[i].sequence);
        SEQUAL(mk->to_backend->s, reverse_wrap_direct[i].reply);
    }
}

static void test_horizontal_oracle(Mock *mk)
{
    for (size_t i = 0; i < lenof(horizontal_oracle); i++) {
        reset(mk); test_context(mk, "%s", horizontal_oracle[i].name);
        mk->ucsdata->line_codepage = CP_UTF8;
        term_size(mk->term, 24, 80, 100);
        strbuf_clear(mk->to_backend);
        term_data_fragmented(mk->term, horizontal_oracle[i].sequence);
        SEQUAL(mk->to_backend->s, horizontal_oracle[i].reply);
        for (size_t j = 0; j < lenof(horizontal_cells); j++) {
            int x = horizontal_cells[j][1]-1, y = horizontal_cells[j][0]-1;
            unsigned ch = get_termchar(mk->term, x, y).chr;
            if (ch == UCSWIDE) ch = 0;
            else if (DIRECT_CHAR(ch)) ch &= ~CSET_MASK;
            test_context(mk, "%s at %d,%d", horizontal_oracle[i].name, y+1, x+1);
            IEQUAL(ch, horizontal_oracle[i].cells[j]);
        }
    }
}

static void test_margin_oracle(Mock *mk)
{
    for (size_t i=0; i<lenof(margin_oracle); i++) {
        reset(mk); test_context(mk,"%s",margin_oracle[i].name);
        mk->ucsdata->line_codepage=CP_UTF8;
        term_size(mk->term,24,80,100);
        strbuf_clear(mk->to_backend);
        term_data_fragmented(mk->term,margin_oracle[i].sequence);
        SEQUAL(mk->to_backend->s,margin_oracle[i].reply);
        for (int j=0; j<84; j++) {
            unsigned ch=get_termchar(mk->term,j%12,j/12).chr;
            if(ch==UCSWIDE)ch=0;
            else if(DIRECT_CHAR(ch))ch &= ~CSET_MASK;
            test_context(mk,"%s at %d,%d",margin_oracle[i].name,j/12+1,j%12+1);
            IEQUAL(ch,margin_oracle[i].chars[j]);
            if (margin_oracle[i].check_attrs)
                IEQUAL(get_termchar(mk->term,j%12,j/12).attr &
                    (ATTR_BOLD|ATTR_DIM|ATTR_ITALIC|ATTR_UNDER|ATTR_BLINK|ATTR_REVERSE|ATTR_CONCEAL|ATTR_STRIKE),
                    margin_oracle[i].attrs[j]);
        }
    }
}

static void margin_setup(Mock *mk, const char *name)
{
    reset(mk); test_context(mk,"%s",name);
    mk->ucsdata->line_codepage=CP_UTF8;
    term_size(mk->term,24,80,100);
}

static void test_wide_boundaries(Mock *mk)
{
    /* Deliberate difference from XTerm 412 scrollInMargins: do not repair
     * wide glyphs on rows outside the vertical scrolling region. */
    const unsigned left[]={'A',0x4e2d,0,'B','C','D','E','F','G','H','I','J'};
    const unsigned right[]={'A','B','C','D','E','F','G',0x4e2d,0,'H','I','J'};
    for (int side=0;side<2;side++) {
        margin_setup(mk,"wide glyphs crossing horizontal boundaries");
        for(int y=0;y<7;y++) {
            char *seq=dupprintf("\033[%d;1H%s",y+1,side?
                "ABCDEFG\xe4\xb8\xadHIJ":"A\xe4\xb8\xad" "BCDEFGHIJ");
            term_data_fragmented(mk->term,seq);sfree(seq);
        }
        term_data_fragmented(mk->term,"\033[?69h\033[3;8s\033[3;6r");
        term_data_fragmented(mk->term,side?"\033[T":"\033[S");
        for(int y=0;y<7;y++) for(int x=0;x<12;x++) {
            unsigned want=(side?right:left)[x],ch=get_termchar(mk->term,x,y).chr;
            if(y>=2&&y<=5) {
                if((side&&(x==7||x==8))||(!side&&(x==1||x==2)))want=' ';
                if(y==(side?2:5)&&x>=2&&x<=7)want=' ';
            }
            if(ch==UCSWIDE)ch=0;else if(DIRECT_CHAR(ch))ch &= ~CSET_MASK;
            test_context(mk,"wide-%s at %d,%d",side?"right":"left",y+1,x+1);
            IEQUAL(ch,want);
        }
    }
}

static void test_margin_state(Mock *mk)
{
    margin_setup(mk,"mode 69 saves the actual disabled boolean");
    Terminal *t=mk->term;
    strbuf_clear(mk->to_backend);
    term_data_fragmented(t,"\033[?69s\033[?69h\033[3;8s\033[?69r\033[?69$p\033P$qs\033\\");
    SEQUAL(mk->to_backend->s,"\033[?69;2$y\033P1$r1;80s\033\\");
    term_data_fragmented(t,"\033[?69h\033[3;8s\033[3;6r\033[?1049h");
    IEQUAL(t->marg_l,2);IEQUAL(t->marg_r,7);IEQUAL(t->marg_t,2);IEQUAL(t->marg_b,5);
    term_data_fragmented(t,"\033[4;12s\033[2;7r\033[?1049l");
    IEQUAL(t->marg_l,3);IEQUAL(t->marg_r,11);IEQUAL(t->marg_t,1);IEQUAL(t->marg_b,6);
    term_size(t,12,40,100);
    IEQUAL(t->lrmm,true);IEQUAL(t->marg_l,0);IEQUAL(t->marg_r,39);
    IEQUAL(t->marg_t,0);IEQUAL(t->marg_b,11);
    term_data_fragmented(t,"\033[3;8s\033[3;6r\033[!p");
    IEQUAL(t->lrmm,false);IEQUAL(t->marg_l,0);IEQUAL(t->marg_r,39);
    IEQUAL(t->marg_t,0);IEQUAL(t->marg_b,11);
    term_size(t,1,1,100);term_data_fragmented(t,"\033[?69h\033[1;1sXYZ\n\033[S\033[T\033[L\033[M");
    IEQUAL(t->curs.x,0);IEQUAL(t->curs.y,0);IEQUAL(t->marg_r,0);
    term_data_fragmented(t,"\033c");IEQUAL(t->lrmm,false);

    margin_setup(mk,"invalid parameters cannot mutate margins or leak parser state");
    term_data_fragmented(t,"\033[?69h\033[3;8s\033[4;5H");
    for(int i=0;i<1000;i++) term_data_fragmented(t,"\033[7;3s\033[5;5s\033[4:1;7s\033[99999999999999;1s\033[4;6\030");
    IEQUAL(t->marg_l,2);IEQUAL(t->marg_r,7);IEQUAL(t->curs.x,4);IEQUAL(t->curs.y,3);
    IEQUAL(t->termstate,TOPLEVEL);
}

static void test_cell_lifetimes(Mock *mk)
{
    margin_setup(mk,"partial scrolling retains combining, colour, protection and links");
    Terminal *t=mk->term;
    term_data_fragmented(t,"\033[4;4H\033[1\"q\033[3;4:3;38;2;1;2;3;58;2;4;5;6m"
        "\033]8;id=margin;https://example.org/margin\033\\A\xcc\x81\xe4\xb8\xad"
        "\033]8;;\033\\\033[0\"q\033[0m");
    termchar before=get_termchar(t,3,3);
    term_data_fragmented(t,"\033[?69h\033[3;8s\033[3;6r\033[S");
    termchar after=get_termchar(t,3,2);
    IEQUAL(after.chr,before.chr);IEQUAL(after.attr,before.attr);
    IEQUAL(after.hyperlink,before.hyperlink);IEQUAL(after.truecolour.decoration,before.truecolour.decoration);
    IEQUAL(after.truecolour.fg.r,1);IEQUAL(after.truecolour.fg.g,2);IEQUAL(after.truecolour.fg.b,3);
    termline *line=term_get_line(t,2);
    IEQUAL(line->chars[3+line->chars[3].cc_next].chr,0x301);
    IEQUAL(line->chars[4].chr,0x4e2d);IEQUAL(line->chars[5].chr,UCSWIDE);term_release_line(line);
    term_data_fragmented(t,"\033[4;4HXXX\033[3;4H\033[?2K");
    line=term_get_line(t,2);IEQUAL(line->chars[3+line->chars[3].cc_next].chr,0x301);term_release_line(line);
    IEQUAL(get_termchar(t,3,2).chr & ~CSET_MASK,'A');
    IEQUAL(count234(t->scrollback),0); /* Partial columns never become whole history lines. */
    term_data_fragmented(t,"\033[1;6r\033[999S");IEQUAL(count234(t->scrollback),0);
    term_data_fragmented(t,"\033[?69l\033[6;1H\n");IEQUAL(count234(t->scrollback),1);

    margin_setup(mk,"scroll invalidates only overlapping selections");
    term_data_fragmented(t,"\033[4;1HABCDEFGHIJKLMNOP\033[?69h\033[5;10s\033[3;6r");
    term_mouse(t,MBT_LEFT,MBT_SELECT,MA_CLICK,0,3,true,false,false);
    term_mouse(t,MBT_LEFT,MBT_SELECT,MA_DRAG,2,3,true,false,false);
    term_mouse(t,MBT_LEFT,MBT_SELECT,MA_RELEASE,2,3,true,false,false);
    int selection=t->selstate;
    term_data_fragmented(t,"\033[S");IEQUAL(t->selstate,selection);
    term_mouse(t,MBT_LEFT,MBT_SELECT,MA_CLICK,5,2,true,false,false);
    term_mouse(t,MBT_LEFT,MBT_SELECT,MA_DRAG,7,2,true,false,false);
    term_mouse(t,MBT_LEFT,MBT_SELECT,MA_RELEASE,7,2,true,false,false);
    term_data_fragmented(t,"\033[T");IEQUAL(t->selstate,NO_SELECTION);
}

static void test_horizontal_lifetimes(Mock *mk)
{
    margin_setup(mk, "horizontal edits retain full cell payloads");
    Terminal *t = mk->term;
    term_data_fragmented(t, "\033[4;4H\033[1\"q\033[3;4:3;38;2;1;2;3;58;2;4;5;6m"
        "\033]8;id=shift;https://example.org/shift\033\\A\xcc\x81\xe4\xb8\xad"
        "\033]8;;\033\\\033[0\"q\033[0m\033[?69h\033[3;10s\033[3;6r\033[4;4H");
    termchar before = get_termchar(t, 3, 3);
    term_data_fragmented(t, "\033[2 A");
    termchar after = get_termchar(t, 5, 3);
    IEQUAL(after.chr, before.chr); IEQUAL(after.attr, before.attr);
    IEQUAL(after.hyperlink, before.hyperlink);
    IEQUAL(memcmp(&after.truecolour, &before.truecolour, sizeof(after.truecolour)), 0);
    termline *line = term_get_line(t, 3);
    IEQUAL(line->chars[5+line->chars[5].cc_next].chr, 0x301);
    IEQUAL(line->chars[6].chr, 0x4e2d); IEQUAL(line->chars[7].chr, UCSWIDE);
    term_release_line(line);
    term_data_fragmented(t, "\033[2 @");
    after = get_termchar(t, 3, 3);
    IEQUAL(after.chr, before.chr); IEQUAL(after.hyperlink, before.hyperlink);
    IEQUAL(memcmp(&after.truecolour, &before.truecolour, sizeof(after.truecolour)), 0);
    IEQUAL(count234(t->scrollback), 0);

    margin_setup(mk, "horizontal shifts invalidate only intersecting selections");
    term_data_fragmented(t, "\033[4;1HABCDEFGHIJKLMNOP\033[?69h\033[5;10s\033[3;6r\033[4;5H");
    term_mouse(t, MBT_LEFT, MBT_SELECT, MA_CLICK, 0, 3, true, false, false);
    term_mouse(t, MBT_LEFT, MBT_SELECT, MA_DRAG, 2, 3, true, false, false);
    term_mouse(t, MBT_LEFT, MBT_SELECT, MA_RELEASE, 2, 3, true, false, false);
    int selection = t->selstate;
    IEQUAL(selection != NO_SELECTION, true);
    term_data_fragmented(t, "\033[2 A"); IEQUAL(t->selstate, selection);
    term_mouse(t, MBT_LEFT, MBT_SELECT, MA_CLICK, 5, 3, true, false, false);
    term_mouse(t, MBT_LEFT, MBT_SELECT, MA_DRAG, 7, 3, true, false, false);
    term_mouse(t, MBT_LEFT, MBT_SELECT, MA_RELEASE, 7, 3, true, false, false);
    term_data_fragmented(t, "\033[2 @"); IEQUAL(t->selstate, NO_SELECTION);

    margin_setup(mk, "wide cells split by lost columns are repaired");
    term_data_fragmented(t, "\033[3;7H\xe4\xb8\xad\033[?69h\033[3;8s\033[3;6r\033[3;3H\033[ A");
    IEQUAL(get_termchar(t, 7, 2).chr & ~CSET_MASK, ' ');
    term_data_fragmented(t, "\033[4;3H\xe4\xb8\xad\033[4;3H\033[ @");
    IEQUAL(get_termchar(t, 2, 3).chr & ~CSET_MASK, ' ');
    for (int i = 0; i < 200; i++)
        term_data_fragmented(t, "\033[99999999999999 A\033[99999999999999 @\033[99999999999999'}\033[99999999999999'~");
    IEQUAL(t->termstate, TOPLEVEL); IEQUAL(count234(t->scrollback), 0);
    term_size(t, 1, 1, 0);
    term_data_fragmented(t, "X\0336\0339\033[ A\033[ @\033['}\033['~\033[^");
    IEQUAL(t->curs.x, 0); IEQUAL(t->curs.y, 0);
}

static void test_reverse_wrap_lifetimes(Mock *mk)
{
    margin_setup(mk, "reverse motion preserves pixels, selection and retained cell payloads");
    Terminal *t = mk->term;
    IEQUAL(t->reverse_wrap, false); IEQUAL(t->reverse_wrap_extended, false);
    term_data_fragmented(t, "\033[2;80Hx\xcc\x81" "BC\033[8;4H"
        "\033P0;1q#1;2;100;0;0!24~\033\\\033[?45h");
    term_mouse(t, MBT_LEFT, MBT_SELECT, MA_CLICK, 0, 2, true, false, false);
    term_mouse(t, MBT_LEFT, MBT_SELECT, MA_DRAG, 1, 2, true, false, false);
    term_mouse(t, MBT_LEFT, MBT_SELECT, MA_RELEASE, 1, 2, true, false, false);
    int selected = t->selstate;
    IEQUAL(selected != NO_SELECTION, true);
    NemoTermImage *image = t->images;
    size_t bytes = t->image_bytes;
    for (int i = 0; i < 500; i++)
        term_data_fragmented(t, "\033[3;3H\033[3D\033[2C\b");
    IEQUAL(t->selstate, selected); IEQUAL(t->images == image, true);
    IEQUAL(t->image_bytes, bytes);
    termline *line = term_get_line(t, 1);
    IEQUAL(line->chars[79].chr & ~CSET_MASK, 'x');
    IEQUAL(line->chars[79+line->chars[79].cc_next].chr, 0x301);
    term_release_line(line);

    margin_setup(mk, "margin wrap does not join outside columns during copy or resize");
    term_data_fragmented(t, "\033[?69h\033[3;8s\033[3;6r\033[3;3HABCDEFGHIJKLM\033[?45h");
    IEQUAL(!!(get_lineattr(t,2) & LATTR_CURSOR_WRAPPED), true);
    IEQUAL(!!(get_lineattr(t,2) & LATTR_WRAPPED), false);
    int clip = CLIP_LOCAL;
    term_copyall(t, &clip, 1); /* mock clipboard, never the desktop clipboard */
#ifdef _WIN32
    IEQUAL(wcsstr(t->last_selected_text, L"ABCDEF\r\n  GHIJKL") != NULL, true);
#else
    IEQUAL(wcsstr(t->last_selected_text, L"ABCDEF\n  GHIJKL") != NULL, true);
#endif
    term_data_fragmented(t, "\033[?69l");
    term_size(t, 24, 100, 100);
    IEQUAL(get_termchar(t,2,2).chr & ~CSET_MASK, 'A');
    IEQUAL(get_termchar(t,2,3).chr & ~CSET_MASK, 'G');

    test_context(mk, "bounded reverse wrap for tiny grids and saturated counts");
    for (int rows = 1; rows <= 6; rows++) for (int cols = 1; cols <= 8; cols++) {
        reset(mk); term_size(t, rows, cols, 0);
        for (int i = 0; i < 60; i++) {
            term_data_fragmented(t, "\033[?45;1045h\033[99999999999999999D\b\0336");
            IEQUAL(t->curs.x >= 0 && t->curs.x < cols, true);
            IEQUAL(t->curs.y >= 0 && t->curs.y < rows, true);
        }
    }
}

int main(void)
{
    setvbuf(stdout,NULL,_IONBF,0);
    Mock *mk=mock_new();
    mk->term=term_init(mk->conf,mk->ucsdata,&mk->tw);
    mk->ldisc=ldisc_create(mk->conf,mk->term,&mk->backend,&mk->seat);
    test_margin_oracle(mk);test_wide_boundaries(mk);test_margin_state(mk);test_cell_lifetimes(mk);
    test_horizontal_oracle(mk);
    test_horizontal_lifetimes(mk);
    test_reverse_wrap_oracle(mk);
    test_reverse_wrap_lifetimes(mk);
    bool failed=mk->any_test_failed;mock_free(mk);
    puts(failed?"Margin suite FAILED":"Margin suite passed");
    return failed?1:0;
}
