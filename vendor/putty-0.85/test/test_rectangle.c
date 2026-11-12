/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main
#include "../../../tests/rectangle_oracle_cases.h"

static void rectangle_setup(Mock *mk, const char *name)
{
    reset(mk); test_context(mk, "%s", name);
    mk->ucsdata->line_codepage = CP_UTF8;
    term_size(mk->term, 24, 80, 100);
}

static void test_oracle(Mock *mk)
{
    const unsigned mask = ATTR_BOLD|ATTR_DIM|ATTR_ITALIC|ATTR_UNDER|
        ATTR_BLINK|ATTR_REVERSE|ATTR_CONCEAL|ATTR_STRIKE;
    for (size_t i=0; i<lenof(rectangle_oracle); i++) {
        rectangle_setup(mk, rectangle_oracle[i].name);
        term_data_fragmented(mk->term, rectangle_oracle[i].sequence);
        for (int j=0; j<60; j++) {
            termchar cell = get_termchar(mk->term,j%12,j/12);
            unsigned ch=cell.chr;
            if (ch==UCSWIDE) ch=0;
            else if (DIRECT_CHAR(ch) && (ch&CSET_MASK)==CSET_LINEDRW)
                ch=mk->ucsdata->unitab_xterm[ch&255];
            else if (DIRECT_CHAR(ch)) ch &= ~CSET_MASK;
            test_context(mk,"%s at %d,%d",rectangle_oracle[i].name,j/12+1,j%12+1);
            IEQUAL(ch,rectangle_oracle[i].chars[j]);
            IEQUAL(cell.attr&mask,rectangle_oracle[i].attrs[j]);
        }
    }
}

static void test_cells_and_lifetimes(Mock *mk)
{
    rectangle_setup(mk,"copy retains combining chains, colours, protection and hyperlink identity");
    Terminal *t=mk->term;
    term_data_fragmented(t,"\033[1\"q\033[3;4:3;38;2;1;2;3;58;2;4;5;6m"
        "\033]8;id=copy;https://example.org/rectangle\033\\A\xcc\x81\xe4\xb8\xad"
        "\033]8;;\033\\\033[0\"q\033[0m\033[1;1;1;3;1;2;2;1$v");
    termchar a=get_termchar(t,0,0),b=get_termchar(t,1,1);
    IEQUAL(b.chr,a.chr);IEQUAL(b.attr,a.attr);
    IEQUAL(b.hyperlink,a.hyperlink);IEQUAL(b.truecolour.decoration,a.truecolour.decoration);
    IEQUAL(b.truecolour.fg.enabled,true);IEQUAL(b.truecolour.fg.r,1);
    termline *line=term_get_line(t,1);
    IEQUAL(line->chars[1+line->chars[1].cc_next].chr,0x301);
    IEQUAL(line->chars[2].chr,0x4e2d);IEQUAL(line->chars[3].chr,UCSWIDE);
    term_release_line(line);
    term_data_fragmented(t,"\033[1;1HXXX"); /* copied combining list is independent */
    line=term_get_line(t,1);IEQUAL(line->chars[1+line->chars[1].cc_next].chr,0x301);term_release_line(line);
    term_data_fragmented(t,"\033[2;2H\033[?2K");IEQUAL(get_termchar(t,1,1).chr & ~CSET_MASK,'A');

    rectangle_setup(mk,"overlap copy of combining glyphs snapshots each row before mutation");
    term_data_fragmented(t,"A\xcc\x81" "B\xcc\x82" "C\xcc\x83\033[1;1;1;3;1;1;2;1$v");
    line=term_get_line(t,0);
    for(int x=1;x<4;x++) {
        IEQUAL(line->chars[x].chr & ~CSET_MASK,'A'+x-1);
        IEQUAL(line->chars[x+line->chars[x].cc_next].chr,0x300+x);
    }
    term_release_line(line);

    rectangle_setup(mk,"extent survives soft reset, alternate screens and resize; RIS resets it");
    strbuf_clear(mk->to_backend);
    term_data_fragmented(t,"\033[2*x\033[!p\033[?1049h\033[?1049l");
    term_size(t,12,40,100);
    term_data_fragmented(t,"\033P$q*x\033\\\033c\033P$q*x\033\\");
    SEQUAL(mk->to_backend->s,"\033P1$r2*x\033\\\033P1$r0*x\033\\");

    rectangle_setup(mk,"stream occupancy survives compressed history and reflow without per-cell growth");
    term_data_fragmented(t,"A B\033[2;1HC D");
    for(int i=0;i<30;i++) term_data_fragmented(t,"\r\n");
    IEQUAL(!!(get_termchar(t,1,-8).truecolour.decoration&CELL_UNDRAWN),false);
    IEQUAL(!!(get_termchar(t,3,-8).truecolour.decoration&CELL_UNDRAWN),true);
    term_size(t,12,40,100);term_size(t,24,80,100);

    rectangle_setup(mk,"attributes keep selection, text and links; fill and copy invalidate overwritten selection");
    term_data_fragmented(t,"\033]8;;https://example.org/a\033\\ABCD\033]8;;\033\\");
    term_mouse(t,MBT_LEFT,MBT_SELECT,MA_CLICK,0,0,true,false,false);
    term_mouse(t,MBT_LEFT,MBT_SELECT,MA_DRAG,3,0,true,false,false);
    term_mouse(t,MBT_LEFT,MBT_SELECT,MA_RELEASE,3,0,true,false,false);
    int selection=t->selstate;uint32_t link=get_termchar(t,0,0).hyperlink;
    term_data_fragmented(t,"\033[1;1;1;4;4;8$r");
    IEQUAL(t->selstate,selection);IEQUAL(get_termchar(t,0,0).hyperlink,link);
    term_data_fragmented(t,"\033[90;1;2;1;3$x");IEQUAL(t->selstate,NO_SELECTION);
    IEQUAL(get_termchar(t,1,0).hyperlink,0);
}

static void test_images_and_bounds(Mock *mk)
{
    rectangle_setup(mk,"attributes preserve Sixel; fill clears only its target pixels");
    Terminal *t=mk->term;
    term_data_fragmented(t,"\033[?80h\033P0;1q\"1;1;48;16#1;2;100;0;0!48~\033\\"
        "\033[2*x\033[1;1;1;6;7$r");
    uint32_t pixels[48];IEQUAL(t->images!=NULL,true);
    if(t->images) {
        term_image_read_row(t->images,0,0,pixels,48);
        for(int x=0;x<48;x++) IEQUAL(pixels[x],UINT32_C(0xffff0000));
        term_data_fragmented(t,"\033[90;1;2;1;3$x");
        term_image_read_row(t->images,0,0,pixels,48);
        for(int x=0;x<48;x++) IEQUAL(pixels[x],x>=8&&x<24?0:UINT32_C(0xffff0000));
    }
    rectangle_setup(mk,"malformed, cancelled and inverted rectangle operations leave bounded parser state");
    term_data_fragmented(t,"ABC\033[90;1:0;1;1;3$x\033[1;1;1;3;1:0$r"
        "\033[1;1;1;3;1;2;1:0;1$v\033[90;2;1;1;3$x\033[1;3;1;1;1;2;1;1$v");
    IEQUAL(get_termchar(t,0,0).chr & ~CSET_MASK,'A');IEQUAL(get_termchar(t,1,0).chr & ~CSET_MASK,'B');
    for(int i=0;i<1000;i++) term_data_fragmented(t,"\033[9999999999999;1;1;3;3$x\033[1;1;2;3;1;9999999999999;9999999999999;1$v");
    IEQUAL(t->termstate,TOPLEVEL);IEQUAL(t->image_bytes,0);
}

int main(void)
{
    Mock *mk=mock_new();mk->term=term_init(mk->conf,mk->ucsdata,&mk->tw);
    mk->ldisc=ldisc_create(mk->conf,mk->term,&mk->backend,&mk->seat);
    test_oracle(mk);test_cells_and_lifetimes(mk);test_images_and_bounds(mk);
    bool failed=mk->any_test_failed;mock_free(mk);
    puts(failed?"Rectangle editing suite FAILED":"Rectangle editing and independent XTerm oracle suite passed");
    return failed?1:0;
}
