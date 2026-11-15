/* SPDX-License-Identifier: MIT
 * Literal upstream replay through the real parser and graphics owner.
 * Includes virtual parents whose visibility follows Unicode image cells. */
typedef struct KittyRelativeReference {
    const char *name;
    unsigned first, x, y, images, history, layers, error_prefix;
    const char *wire, *reply;
    double boxes[12][9];
} KittyRelativeReference;
#include "kitty_relative_reference.h"

static void test_kitty_relative_reference(Mock *parent)
{
    Mock *mk=NULL;
    TermWinVtable vt=mock_termwin_vt;
    vt.kitty_graphics=true;
    unsigned failed=0;
    for (size_t i=0;i<lenof(kitty_relative_reference);i++) {
        const KittyRelativeReference *r=&kitty_relative_reference[i];
        if (r->first) {
            if (mk) mock_free(mk);
            mk=mock_new();mk->tw.vt=&vt;
            mk->ucsdata->line_codepage=CP_UTF8;
            mk->term=term_init(mk->conf,mk->ucsdata,&mk->tw);
            mk->ldisc=ldisc_create(mk->conf,mk->term,&mk->backend,&mk->seat);
            term_size(mk->term,8,12,20);term_set_cell_size(mk->term,10,20);
            term_set_trust_status(mk->term,false);
        }
        mk->any_test_failed=false;
        test_context(mk,"Kitty relative replay: %s",r->name);
        term_data_fragmented(mk->term,r->wire);
        term_kitty_prepare(mk->term);
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
        Terminal *t=mk->term;
        IEQUAL(t->curs.x,r->x);IEQUAL(t->curs.y,r->y);
        IEQUAL(kitty_images(t,t->alt_which),r->images);
        unsigned visible=0;
        for (const NemoKittyPlacement *p=nemo_kitty_placements_first(term_kitty_placements(t,t->alt_which));
             p;p=nemo_kitty_placement_next(p)) {
            NemoKittyView v;
            if (!nemo_kitty_placement_view(p,10,20,&v)) continue;
            v.top+=r->history*20;v.bottom+=r->history*20;
            /* The upstream raw layer list culls vertically, not horizontally.
             * This compares that model; the window compositor clips pixels. */
            if (v.bottom<=0 || v.top>=160) continue;
            if (visible<r->layers) {
                const NemoRaster *pixels=nemo_kitty_image_raster(v.image);
                double actual[]={v.left,v.top,v.right,v.bottom,
                    v.source_left/pixels->width,v.source_top/pixels->height,
                    v.source_right/pixels->width,v.source_bottom/pixels->height,v.z};
                for (unsigned j=0;j<lenof(actual);j++) kitty_near(mk,actual[j],r->boxes[visible][j]);
            }
            visible++;
        }
        IEQUAL(visible,r->layers);
        kitty_check_budget(mk);
        if (mk->any_test_failed) {
            failed++;
            printf("Kitty relative failed state: %s\n",r->name);
        }
    }
    if (mk) mock_free(mk);
    parent->any_test_failed|=failed!=0;
    printf("Kitty relative replay: %u states; %u failed states\n",
           (unsigned)lenof(kitty_relative_reference),failed);
}
