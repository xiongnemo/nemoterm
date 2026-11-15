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
