/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main

static void erase_setup(Mock *mk, const char *name)
{
    reset(mk);
    test_context(mk, "%s", name);
    mk->ucsdata->line_codepage = CP_UTF8;
    term_size(mk->term, 8, 12, 100);
}

static void erase_row_text(Mock *mk, int row, const char *expected)
{
    for (int x = 0; expected[x]; x++)
        IEQUAL(get_termchar(mk->term, x, row).chr & ~CSET_MASK,
               (unsigned char)expected[x]);
}

static void erase_reply(Mock *mk, const char *sequence, const char *expected)
{
    strbuf_clear(mk->to_backend);
    term_data_fragmented(mk->term, sequence);
    SEQUAL(mk->to_backend->s, expected);
}

static void test_protection_lifecycle(Mock *mk)
{
    erase_setup(mk, "protection is independent of SGR, queried and cursor-saved");
    Terminal *t = mk->term;
    erase_reply(mk, "\033P$q\"q\033\\\033[1\"q\033P$q\"q\033\\"
        "\033[2\"q\033P$q\"q\033\\\033[1;2\"q\033[999\"q\033[0:0\"q\033P$q\"q\033\\",
        "\033P1$r0\"q\033\\\033P1$r1\"q\033\\\033P1$r0\"q\033\\\033P1$r1\"q\033\\");
    term_data_fragmented(t, "A\033[0mB\033[4:3;58;2;1;2;3mC\033[59;24mD");
    for (int x=0; x<4; x++)
        IEQUAL(!!(get_termchar(t,x,0).truecolour.decoration & CELL_PROTECTED), true);
    IEQUAL(UNDER_STYLE(get_termchar(t,2,0).truecolour), 3);
    IEQUAL(get_termchar(t,3,0).truecolour.decoration, CELL_PROTECTED);
    erase_reply(mk,"\0337\033[0\"q\0338\033P$q\"q\033\\", "\033P1$r1\"q\033\\");
    term_data_fragmented(t,"\033[?1049h\033[0\"q\033[?1049l");
    IEQUAL(!!(t->curr_truecolour.decoration & CELL_PROTECTED), true);
    term_data_fragmented(t,"\033[!p");
    erase_row_text(mk,0,"ABCD"); /* soft reset changes current state, not old cells */
    IEQUAL(t->curr_truecolour.decoration & CELL_PROTECTED, 0);
    IEQUAL(t->dec_protection, false);
    term_data_fragmented(t,"\033[?2K");
    erase_row_text(mk,0,"    "); /* the reset also ends the DEC protection family */
    term_data_fragmented(t,"\033c");
    erase_row_text(mk,0,"    ");
    IEQUAL(get_termchar(t,0,0).truecolour.decoration & CELL_PROTECTED, 0);
}

static void test_line_and_display(Mock *mk)
{
    for (int display=0; display<2; display++) for (int mode=0; mode<3; mode++) {
        erase_setup(mk,"selective erase ranges include cursor and ignore margins");
        Terminal *t=mk->term;
        for (int row=0;row<4;row++) {
            char seq[96];
            snprintf(seq,sizeof(seq),"\033[%d;1HA\033[1\"qB\033[0\"qC\033[1\"qD\033[0\"qEF",row+1);
            term_data_fragmented(t,seq);
        }
        char seq[48];
        snprintf(seq,sizeof(seq),"\033[3;5r\033[2;3H\033[?%d%c",mode,display?'J':'K');
        term_data_fragmented(t,seq);
        for(int row=0;row<4;row++) for(int x=0;x<6;x++) {
            bool in_range=(display || row==1) &&
                (mode==2 || (mode==0 && (row>1 || (row==1 && x>=2))) ||
                 (mode==1 && (row<1 || (row==1 && x<=2))));
            bool protected=x==1 || x==3;
            IEQUAL(get_termchar(t,x,row).chr & ~CSET_MASK,
                   in_range && !protected ? ' ' : 'A'+x);
            IEQUAL(!!(get_termchar(t,x,row).truecolour.decoration & CELL_PROTECTED), protected);
        }
        IEQUAL(t->curs.x,2); IEQUAL(t->curs.y,1);
        IEQUAL(count234(t->scrollback),0);
    }
    static const char *ordinary[]={"\033[2K","\033[2J","\033[H\033[6X"};
    for(size_t i=0;i<lenof(ordinary);i++) {
        erase_setup(mk,"ordinary erases ignore protection");
        term_data_fragmented(mk->term,"\033[1\"qABCDEF");
        term_data_fragmented(mk->term,ordinary[i]);
        erase_row_text(mk,0,"      ");
        IEQUAL(get_termchar(mk->term,0,0).truecolour.decoration & CELL_PROTECTED,0);
    }
}

static void test_styles_and_rectangles(Mock *mk)
{
    erase_setup(mk,"selective rectangles preserve styles; ordinary rectangles use xterm rendition");
    Terminal *t=mk->term;
    term_data_fragmented(t,"\033[31;44;1;4:3;58;2;1;2;3mA\033[1\"qB\033[0\"qC"
        "\033]8;;https://example.org/erased\033\\D\033]8;;\033\\"
        "\033[32;45;3m\033[1;1;1;4${");
    erase_row_text(mk,0," B  ");
    termchar a=get_termchar(t,0,0), b=get_termchar(t,1,0);
    IEQUAL(a.attr & (ATTR_BOLD|ATTR_UNDER),ATTR_BOLD|ATTR_UNDER);
    IEQUAL(a.attr & ATTR_FGMASK,1); IEQUAL((a.attr & ATTR_BGMASK)>>ATTR_BGSHIFT,4);
    IEQUAL(UNDER_STYLE(a.truecolour),3);
    IEQUAL(a.truecolour.decoration & UNDER_COLOUR_MASK,UNDER_RGB|0x010203);
    IEQUAL(!!(b.truecolour.decoration & CELL_PROTECTED),true);
    IEQUAL(get_termchar(t,3,0).hyperlink,0);
    term_data_fragmented(t,"\033[1;1;1;4$z");
    erase_row_text(mk,0,"    ");
    a=get_termchar(t,0,0);
    IEQUAL(a.attr & (ATTR_BOLD|ATTR_UNDER|ATTR_ITALIC),ATTR_BOLD|ATTR_UNDER|ATTR_ITALIC);
    IEQUAL(a.attr & ATTR_FGMASK,2); IEQUAL((a.attr & ATTR_BGMASK)>>ATTR_BGSHIFT,5);
    IEQUAL(get_termchar(t,1,0).truecolour.decoration & CELL_PROTECTED,0);
    term_data_fragmented(t,"\033[0m\033[1;1;1;4$z");
    a=get_termchar(t,0,0);
    IEQUAL(a.attr & (ATTR_BOLD|ATTR_UNDER|ATTR_ITALIC),0);
    IEQUAL(a.attr & ATTR_FGMASK,2); IEQUAL((a.attr & ATTR_BGMASK)>>ATTR_BGSHIFT,5);

    erase_setup(mk,"selective line erasure uses background erase colour without SGR styles");
    term_data_fragmented(t,"\033[31;44;1;4mABC\033[32;45m\033[?2K");
    a=get_termchar(t,0,0);
    IEQUAL(a.attr & (ATTR_BOLD|ATTR_UNDER),0);
    IEQUAL(a.attr & ATTR_FGMASK,10); IEQUAL((a.attr & ATTR_BGMASK)>>ATTR_BGSHIFT,5);

    for (int defaults=0;defaults<2;defaults++) {
        erase_setup(mk,"rectangle origin defaults and clipping");
        term_data_fragmented(t,"111111\033[2;1H222222\033[3;1H333333\033[4;1H444444"
            "\033[5;1H555555\033[3;5r\033[?6h");
        term_data_fragmented(t,defaults?"\033[${":"\033[1;2;2;4${");
        erase_row_text(mk,0,"111111");erase_row_text(mk,1,"222222");
        erase_row_text(mk,2,defaults?"      ":"3   33");
        erase_row_text(mk,3,defaults?"      ":"4   44");
        erase_row_text(mk,4,defaults?"      ":"555555");
        IEQUAL(t->curs.x,0);IEQUAL(t->curs.y,2);
    }
    erase_setup(mk,"inverted and oversized rectangles are bounded");
    term_data_fragmented(t,"ABCDEF\033[1;12HZ\033[1;5;1;2${");
    erase_row_text(mk,0,"ABCDEF");
    term_data_fragmented(t,"\033[1;4294967295;1;4294967295${");
    IEQUAL(get_termchar(t,11,0).chr & ~CSET_MASK,' ');
    term_data_fragmented(t,"\033[1;1H\033#6ABC\033[1;1;1;2${");
    IEQUAL(get_lineattr(t,0)&LATTR_MODE,LATTR_WIDE);
    erase_row_text(mk,0,"  C");
}

static void test_wide_combining_and_wrap(Mock *mk)
{
    erase_setup(mk,"protected wide glyph survives half-cell erase boundary");
    Terminal *t=mk->term;
    term_data_fragmented(t,"\033[1\"q\xe4\xb8\xad\033[0\"q\xe6\x96\x87XYZ\033[1;2H\033[?K");
    IEQUAL(get_termchar(t,0,0).chr,0x4e2d);IEQUAL(get_termchar(t,1,0).chr,UCSWIDE);
    for(int x=2;x<7;x++) IEQUAL(get_termchar(t,x,0).chr & ~CSET_MASK,' ');
    erase_setup(mk,"unprotected half-wide erasure clears whole glyph, including combining chain");
    term_data_fragmented(t,"\xe4\xb8\xad\xcc\x81\033[1\"q\xe6\x96\x87\033[0\"qXYZ"
        "\033[1;2;1;3${");
    erase_row_text(mk,0,"  ");IEQUAL(get_termchar(t,0,0).cc_next,0);
    IEQUAL(get_termchar(t,2,0).chr,0x6587);IEQUAL(get_termchar(t,3,0).chr,UCSWIDE);
    for(int rectangle=0;rectangle<2;rectangle++) {
        erase_setup(mk,"selective line resets pending wrap; rectangles preserve it");
        term_data_fragmented(t,"\033[1;12HX");
        term_data_fragmented(t,rectangle?"\033[1;1;1;3${Z":"\033[?KZ");
        IEQUAL(t->curs.y,rectangle?1:0);
        IEQUAL(t->curs.x,rectangle?1:11);
        IEQUAL(get_termchar(t,rectangle?0:11,rectangle?1:0).chr & ~CSET_MASK,'Z');
    }
}

static void test_history_reflow_selection(Mock *mk)
{
    erase_setup(mk,"protected cells and metadata survive compressed history and reflow");
    Terminal *t=mk->term;
    for(int i=0;i<20;i++) term_data_fragmented(t,"\033[1\"qPROTECT\033[0\"qtail\r\n");
    termchar old=get_termchar(t,0,-1);
    IEQUAL(!!(old.truecolour.decoration & CELL_PROTECTED),true);
    int history=count234(t->scrollback);
    term_data_fragmented(t,"\033[?2J");
    IEQUAL(count234(t->scrollback),history);
    IEQUAL(get_termchar(t,0,-1).truecolour.decoration,old.truecolour.decoration);
    term_size(t,8,6,100);
    int found=0;
    for(int y=-count234(t->scrollback);y<8;y++) {
        termline *line=term_get_line(t,y);
        for(int x=0;x<line->cols;x++) if(line->chars[x].truecolour.decoration&CELL_PROTECTED) found++;
        term_release_line(line);
    }
    IEQUAL(found,140);
    term_size(t,8,12,100);
    term_data_fragmented(t,"\033[?3J");IEQUAL(count234(t->scrollback),0);

    erase_setup(mk,"selective erasure retains a protected selection and removes erased links");
    term_data_fragmented(t,"\033[1\"q\033]8;;https://example.org/kept\033\\KEEP\033[0\"qgone");
    uint32_t link=get_termchar(t,0,0).hyperlink;
    term_mouse(t,MBT_LEFT,MBT_SELECT,MA_CLICK,0,0,true,false,false);
    term_mouse(t,MBT_LEFT,MBT_SELECT,MA_DRAG,3,0,true,false,false);
    term_mouse(t,MBT_LEFT,MBT_SELECT,MA_RELEASE,3,0,true,false,false);
    int selection=t->selstate;
    term_data_fragmented(t,"\033[?2K");
    IEQUAL(t->selstate,selection); IEQUAL(get_termchar(t,0,0).hyperlink,link);
    IEQUAL(get_termchar(t,4,0).hyperlink,0);
    erase_row_text(mk,0,"KEEP    ");
}

static void test_images_and_recovery(Mock *mk)
{
    erase_setup(mk,"Sixel pixels follow only the cells actually erased");
    Terminal *t=mk->term;
    term_data_fragmented(t,"\033[1\"q A \033[0\"q B \033[H\033[?80h"
        "\033P0;1q\"1;1;48;16#1;2;100;0;0!48~\033\\\033[?2K");
    uint32_t pixels[48];
    IEQUAL(t->images!=NULL,true);
    if(t->images) {
        IEQUAL(term_image_read_row(t->images,0,0,pixels,48),48);
        for(int x=0;x<48;x++) IEQUAL(pixels[x],x<24?UINT32_C(0xffff0000):0);
        term_data_fragmented(t,"\033[1;1;1;3$z");
        if(t->images) {
            term_image_read_row(t->images,0,0,pixels,48);
            for(int x=0;x<48;x++) IEQUAL(pixels[x],0);
        }
    }
    erase_setup(mk,"invalid and cancelled erases do not change cells");
    term_data_fragmented(t,"ABC\033[H\033[?4K\033[?999J\033[4K\033[4294967295J"
        "\033[?2:0K\033[1:0;1;1;3${\033[?2\030K\033[?2\032J");
    erase_row_text(mk,0,"KJC"); /* cancellation resumes ordinary printable input */
    term_data_fragmented(t,"\033[1\"q\033[?2;9K");
    erase_row_text(mk,0,"   ");
    for(int i=0;i<2000;i++) term_data_fragmented(t,"\033[99999999999999999;1;2;3${\033[1;12;1;1$z");
    IEQUAL(t->termstate,TOPLEVEL);IEQUAL(t->image_bytes,0);
}

int main(void)
{
    Mock *mk=mock_new();
    mk->term=term_init(mk->conf,mk->ucsdata,&mk->tw);
    mk->ldisc=ldisc_create(mk->conf,mk->term,&mk->backend,&mk->seat);
    test_protection_lifecycle(mk);test_line_and_display(mk);
    test_styles_and_rectangles(mk);test_wide_combining_and_wrap(mk);
    test_history_reflow_selection(mk);test_images_and_recovery(mk);
    bool failed=mk->any_test_failed;
    mock_free(mk);
    puts(failed?"Selective erase suite FAILED":"Selective erase suite passed");
    return failed?1:0;
}
