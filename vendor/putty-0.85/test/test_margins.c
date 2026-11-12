/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main
#include "../../../tests/margin_oracle_cases.h"

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

int main(void)
{
    setvbuf(stdout,NULL,_IONBF,0);
    Mock *mk=mock_new();
    mk->term=term_init(mk->conf,mk->ucsdata,&mk->tw);
    mk->ldisc=ldisc_create(mk->conf,mk->term,&mk->backend,&mk->seat);
    test_margin_oracle(mk);test_wide_boundaries(mk);test_margin_state(mk);test_cell_lifetimes(mk);
    bool failed=mk->any_test_failed;mock_free(mk);
    puts(failed?"Margin suite FAILED":"Margin suite passed");
    return failed?1:0;
}
