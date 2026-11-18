/* SPDX-License-Identifier: MIT
 * Independent compiled-upstream Unicode-image replay. All captured states stay
 * enabled; eight explicit xterm text-policy expectations are separately
 * generated from independent cursor/cell evidence. */
typedef struct KittyUnicodeReference {
    const char *name;
    unsigned first, columns, rows, resize_columns, resize_rows;
    int scroll;
    unsigned x,y,images,history,layers,error_prefix;
    const char *wire,*reply,*text[16];
    double boxes[16][9];
} KittyUnicodeReference;
#include "kitty_unicode_reference.h"

static void kitty_unicode_text(Mock *mk, unsigned y, const char *expected)
{
    termline *line=term_get_line(mk->term,y);
    strbuf *text=strbuf_new();
    for (int x=0;x<line->cols;x++) {
        const termchar *ch=&line->chars[x];
        if (ch->chr==UCSWIDE) continue;
        for (;;) {
            unsigned long scalar=ch->chr;
            if ((scalar&CSET_MASK)==CSET_ASCII) scalar&=0xff;
            put_utf8_char(text,scalar);
            if (!ch->cc_next) break;
            ch+=ch->cc_next;
        }
    }
    /* Upstream Line.__str__ omits blank tail cells. The generator verifies
     * none of these captured lines ends in an explicit literal space. */
    while (strbuf_chomp(text,' '));
    SEQUAL(text->s,expected);
    strbuf_free(text);term_release_line(line);
}

static void test_kitty_unicode_reference(Mock *parent)
{
    Mock *mk=NULL;TermWinVtable vt=mock_termwin_vt;vt.kitty_graphics=true;
    unsigned failed=0,policies=0;
    for (size_t i=0;i<lenof(kitty_unicode_reference);i++) {
        const KittyUnicodeReference *r=&kitty_unicode_reference[i];
        if (r->first) {
            if (mk) mock_free(mk);
            mk=mock_new();mk->tw.vt=&vt;mk->ucsdata->line_codepage=CP_UTF8;
            mk->term=term_init(mk->conf,mk->ucsdata,&mk->tw);
            mk->ldisc=ldisc_create(mk->conf,mk->term,&mk->backend,&mk->seat);
            term_size(mk->term,8,12,20);term_set_cell_size(mk->term,10,20);
            term_set_trust_status(mk->term,false);
        }
        bool policy=false;
        for (size_t p=0;p<lenof(kitty_unicode_xterm_policy);p++)
            if (!strcmp(r->name,kitty_unicode_xterm_policy[p].name)) {
                r=&kitty_unicode_xterm_policy[p];policy=true;policies++;break;
            }
        mk->any_test_failed=false;
        test_context(mk,"Kitty Unicode replay: %s",r->name);
        Terminal *t=mk->term;
        if (r->resize_rows) term_size(t,r->resize_rows,r->resize_columns,20);
        if (r->scroll) term_scroll(t,0,r->scroll);
        term_data_fragmented(t,r->wire);
        term_kitty_prepare(t);
        if (r->error_prefix) {
            size_t n=strlen(mk->to_backend->s);
            IEQUAL(strncmp(mk->to_backend->s,r->reply,r->error_prefix),0);
            IEQUAL(n>r->error_prefix+2,true);
            if (n>r->error_prefix+2) {
                SEQUAL(mk->to_backend->s+n-2,"\033\\");
                IEQUAL(memchr(mk->to_backend->s+r->error_prefix,'\033',n-r->error_prefix-2)==NULL,true);
            }
            strbuf_clear(mk->to_backend);
        } else kitty_reply_is(mk,r->reply);
        IEQUAL(t->cols,r->columns);IEQUAL(t->rows,r->rows);
        IEQUAL(t->curs.x,r->x);IEQUAL(t->curs.y,r->y);
        IEQUAL(-t->disptop,r->history);IEQUAL(kitty_images(t,t->alt_which),r->images);
        for (unsigned y=0;y<r->rows && y<(unsigned)t->rows;y++) kitty_unicode_text(mk,y,r->text[y]);
        unsigned visible=0;
        for (const NemoKittyPlacement *p=nemo_kitty_placements_first(term_kitty_placements(t,t->alt_which));
             p;p=nemo_kitty_placement_next(p)) {
            NemoKittyView v;if (!nemo_kitty_placement_view(p,10,20,&v)) continue;
            v.top+=r->history*20;v.bottom+=r->history*20;
            if (v.bottom<=0 || v.top>=r->rows*20) continue;
            if (visible<r->layers) {
                const NemoRaster *pixels=nemo_kitty_image_raster(v.image);
                double actual[]={v.left,v.top,v.right,v.bottom,
                    v.source_left/pixels->width,v.source_top/pixels->height,
                    v.source_right/pixels->width,v.source_bottom/pixels->height,v.z};
                for (unsigned j=0;j<lenof(actual);j++) kitty_near(mk,actual[j],r->boxes[visible][j]);
            }
            visible++;
        }
        IEQUAL(visible,r->layers);kitty_check_budget(mk);
        if (mk->any_test_failed) { failed++;printf("Kitty Unicode failed state: %s\n",r->name); }
        else if (policy) printf("Kitty Unicode xterm text policy matched: %s\n",r->name);
    }
    if (mk) mock_free(mk);
    parent->any_test_failed|=failed!=0;
    printf("Kitty Unicode replay: %u states; %u failed states; %u explicit xterm text-policy states\n",
           (unsigned)lenof(kitty_unicode_reference),failed,policies);
}

/* Rendering suppresses placeholder glyphs, but local selection must retain
 * their exact underlying scalars and combining marks. No system clipboard. */
static void test_kitty_unicode_selection(Mock *parent)
{
#ifdef PLATFORM_IS_UTF16
#define KITTY_COPY_PUA L"\xdbfb\xdeee"
#define KITTY_COPY_NL L"\r\n"
#else
#define KITTY_COPY_PUA L"\U0010eeee"
#define KITTY_COPY_NL L"\n"
#endif
    const wchar_t *linear=L"A" KITTY_COPY_PUA L"\u0305\u0305B" KITTY_COPY_NL L"C"
        KITTY_COPY_PUA L"\u030d\u0305D";
    const wchar_t *rectangle=KITTY_COPY_PUA L"\u0305\u0305" KITTY_COPY_NL
        KITTY_COPY_PUA L"\u030d\u0305";
    const int clipboard=CLIP_LOCAL+1;
    unsigned cases=0;
    for (unsigned flags=0;flags<16;flags++) {
        bool alternate=flags&1, mouse=flags&2, block=flags&4, cluster=flags&8;
        Mock *mk=mock_new();TermWinVtable vt=mock_termwin_vt;vt.kitty_graphics=true;
        mk->tw.vt=&vt;mk->ucsdata->line_codepage=CP_UTF8;
        mk->term=term_init(mk->conf,mk->ucsdata,&mk->tw);
        mk->ldisc=ldisc_create(mk->conf,mk->term,&mk->backend,&mk->seat);
        Terminal *t=mk->term;
        term_size(t,4,8,20);term_set_cell_size(t,8,16);
        term_set_trust_status(t,false);
        test_context(mk,"Kitty Unicode copy: alternate=%d mouse=%d rectangle=%d cluster=%d",
                     alternate,mouse,block,cluster);
        if (alternate) term_data_fragmented(t,"\033[?1049h");
        term_data_fragmented(t,cluster ? "\033[?2027h" : "\033[?2027l");
        term_data_fragmented(t,"\033_Ga=T,i=42,f=24,s=1,v=2,c=1,r=2,U=1,C=1;/wAA/wAA\033\\"
            "\033[38;2;0;0;42m\033[HA\xf4\x8e\xbb\xae\xcc\x85\xcc\x85" "B\r\nC"
            "\xf4\x8e\xbb\xae\xcc\x8d\xcc\x85" "D");
        if (mouse) term_data_fragmented(t,"\033[?1003;1006h");
        term_kitty_prepare(t);
        IEQUAL(kitty_images(t,alternate),1);
        IEQUAL(kitty_views(t,alternate)>1,true);
        strbuf_clear(mk->to_backend);
        for (unsigned repeat=0;repeat<2;repeat++) {
            term_mouse(t,MBT_LEFT,MBT_SELECT,MA_CLICK,block ? 1 : 0,0,true,block,false);
            term_mouse(t,MBT_LEFT,MBT_SELECT,MA_DRAG,block ? 1 : 2,1,true,block,false);
            term_mouse(t,MBT_LEFT,MBT_SELECT,MA_RELEASE,block ? 1 : 2,1,false,false,false);
            IEQUAL(t->selstate,SELECTED);
            IEQUAL(t->seltype,block ? RECTANGULAR : VISUAL_STREAM);
            IEQUAL(mk->to_backend->len,0);
            mk->clipboard_writes=0;
            term_request_copy(t,&clipboard,1);
            check_clipboard(mk,block ? rectangle : linear);
            term_kitty_prepare(t);kitty_check_budget(mk);cases++;
        }
        parent->any_test_failed|=mk->any_test_failed;mock_free(mk);
    }
    printf("Kitty Unicode selections: %u exact core copies checked\n",cases);
#undef KITTY_COPY_PUA
#undef KITTY_COPY_NL
}
