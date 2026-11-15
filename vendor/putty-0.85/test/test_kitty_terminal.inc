/* SPDX-License-Identifier: MIT
 * Real byte parser, ldisc replies and lifecycle. The mock codec separates
 * terminal ownership/budget checks from native WIC and compositor validation. */
#include "kitty_compression_reference.h"
#include "kitty_feature_reference.h"
#include "kitty_query_error_reference.h"
static void kitty_reset(Mock *mk)
{
    reset(mk);
    term_set_cell_size(mk->term,8,16);
    term_data_fragmented(mk->term,"\033[3J");
    strbuf_clear(mk->to_backend);
}

static unsigned kitty_views(Terminal *term, int screen)
{
    return nemo_kitty_placements_count(term_kitty_placements(term,screen));
}

static unsigned kitty_images(Terminal *term, int screen)
{
    return nemo_kitty_cache_count(term_kitty_cache(term,screen));
}

static NemoKittyView kitty_first(Mock *mk, int screen)
{
    NemoKittyView v={0};
    IEQUAL(nemo_kitty_placement_view(nemo_kitty_placements_first(
        term_kitty_placements(mk->term,screen)),mk->term->cell_width,mk->term->cell_height,&v),true);
    return v;
}

static void kitty_reply_is(Mock *mk, const char *reply)
{
    SEQUAL(mk->to_backend->s,reply);
    strbuf_clear(mk->to_backend);
}

static bool kitty_mock_decode(TermWin *win, const void *data, size_t length,
                              NemoRaster *out, NemoRasterAdmission admit, void *ctx)
{
    static const unsigned char signature[]={137,80,78,71,13,10,26,10,'A'};
    if (length==sizeof(kitty_compression_png) && !memcmp(data,kitty_compression_png,length)) {
        size_t bytes=sizeof(kitty_compression_png_pixels);
        if (!admit(ctx,KITTY_COMPRESSION_PNG_WIDTH,KITTY_COMPRESSION_PNG_HEIGHT,bytes)) return false;
        out->pixels=malloc(bytes);
        if (!out->pixels) return false;
        memcpy(out->pixels,kitty_compression_png_pixels,bytes);
        out->width=KITTY_COMPRESSION_PNG_WIDTH; out->height=KITTY_COMPRESSION_PNG_HEIGHT;
        out->bytes=bytes; out->partial_alpha=true;
        return true;
    }
    if (length!=sizeof(signature) || memcmp(data,signature,sizeof(signature)))
        return inline_mock_decode(win,data,length,out,admit,ctx);
    size_t bytes=512u*512u*4u;
    if (!admit(ctx,512,512,bytes)) return false;
    out->pixels=malloc(bytes);
    if (!out->pixels) return false;
    out->width=out->height=512; out->bytes=bytes;
    for (unsigned i=0;i<512u*512u;i++) out->pixels[i]=0xff0000ff;
    return true;
}

static void kitty_check_budget(Mock *mk)
{
    size_t bytes=term_kitty_memory(mk->term)+mk->term->image_bytes+
        nemo_iterm_memory(mk->term->iterm_pending)+
        nemo_sixel_stats(mk->term->sixel_pending).allocated_bytes;
    IEQUAL(bytes<=NEMO_SIXEL_DEFAULT_BUDGET,true);
}

typedef struct KittyTerminalReference {
    const char *name;
    unsigned first, start_x, start_y, x, y, images, layers, history;
    const char *wire, *reply;
    double boxes[4][9];
} KittyTerminalReference;
#include "kitty_terminal_reference.h"

static void kitty_near(Mock *mk, double actual, double expected)
{
    double delta=actual-expected;
    if (!(delta >= -0.001 && delta <= 0.001))
        report_fail(mk,__FILE__,__LINE__,"image coordinate %.9f differs from upstream %.9f",actual,expected);
}

static void test_kitty_terminal_reference(Mock *parent)
{
    Mock *mk=NULL;
    TermWinVtable vt=mock_termwin_vt;
    vt.kitty_graphics=true;
    for (size_t i=0;i<lenof(kitty_terminal_reference);i++) {
        const KittyTerminalReference *r=&kitty_terminal_reference[i];
        if (r->first) {
            if (mk) { parent->any_test_failed|=mk->any_test_failed; mock_free(mk); }
            mk=mock_new(); mk->tw.vt=&vt;
            mk->term=term_init(mk->conf,mk->ucsdata,&mk->tw);
            mk->ldisc=ldisc_create(mk->conf,mk->term,&mk->backend,&mk->seat);
            term_size(mk->term,8,12,20); term_set_cell_size(mk->term,10,20);
            term_set_trust_status(mk->term,false);
            char position[40]; sprintf(position,"\033[%u;%uH",r->start_y+1,r->start_x+1);
            term_data_fragmented(mk->term,position);
        }
        test_context(mk,"Kitty upstream terminal replay: %s",r->name);
        term_data_fragmented(mk->term,r->wire);
        kitty_reply_is(mk,r->reply);
        Terminal *t=mk->term;
        IEQUAL(t->curs.x,r->x); IEQUAL(t->curs.y,r->y);
        IEQUAL(kitty_images(t,t->alt_which),r->images);
        unsigned visible=0;
        for (const NemoKittyPlacement *p=nemo_kitty_placements_first(term_kitty_placements(t,t->alt_which));
             p;p=nemo_kitty_placement_next(p)) {
            NemoKittyView v;
            IEQUAL(nemo_kitty_placement_view(p,10,20,&v),true);
            v.top+=r->history*20; v.bottom+=r->history*20;
            if (v.right<=0 || v.bottom<=0 || v.left>=120 || v.top>=160) continue;
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
    }
    if (mk) { parent->any_test_failed|=mk->any_test_failed; mock_free(mk); }
    puts("Kitty upstream terminal replay: 101 states checked (6 APC inputs chunk-normalized)");
}

static void test_kitty_compression_reference(Mock *parent)
{
    Mock *mk=NULL;
    TermWinVtable vt=mock_termwin_vt;
    vt.kitty_graphics=true; vt.decode_image=kitty_mock_decode;
    for (size_t i=0;i<lenof(kitty_compression_reference);i++) {
        const KittyCompressionReference *r=&kitty_compression_reference[i];
        if (r->first) {
            if (mk) { parent->any_test_failed|=mk->any_test_failed; mock_free(mk); }
            mk=mock_new(); mk->tw.vt=&vt;
            mk->term=term_init(mk->conf,mk->ucsdata,&mk->tw);
            mk->ldisc=ldisc_create(mk->conf,mk->term,&mk->backend,&mk->seat);
            term_size(mk->term,8,12,20); term_set_cell_size(mk->term,10,20);
            term_set_trust_status(mk->term,false);
        }
        test_context(mk,"Kitty upstream compression replay: %s",r->name);
        term_data_fragmented(mk->term,r->wire);
        if (r->error_prefix) {
            IEQUAL(strncmp(mk->to_backend->s,r->reply,strlen(r->reply)),0);
            IEQUAL(strstr(mk->to_backend->s,"\033\\")!=NULL,true);
            strbuf_clear(mk->to_backend);
        } else kitty_reply_is(mk,r->reply);
        IEQUAL(mk->term->curs.x,r->x); IEQUAL(mk->term->curs.y,r->y);
        const NemoKittyImage *image=nemo_kitty_cache_peek(term_kitty_cache(mk->term,0),1,0);
        IEQUAL(image!=NULL,r->pixels!=NULL);
        if (image && r->pixels) {
            const NemoRaster *pixels=nemo_kitty_image_raster(image);
            IEQUAL(pixels->width,r->width); IEQUAL(pixels->height,r->height);
            if (pixels->width==r->width && pixels->height==r->height)
                IEQUAL(memcmp(pixels->pixels,r->pixels,(size_t)r->width*r->height*4),0);
        }
        kitty_check_budget(mk);
    }
    if (mk) { parent->any_test_failed|=mk->any_test_failed; mock_free(mk); }
    puts("Kitty upstream compression replay: 26 cases, 36 states and decoded pixels checked");
}

static void test_kitty_query_reference(Mock *parent, const KittyFeatureReference *reference,
                                      size_t length, bool error_control)
{
    Mock *mk=NULL;
    TermWinVtable vt=mock_termwin_vt;
    vt.kitty_graphics=true;
    for (size_t i=0;i<length;i++) {
        const KittyFeatureReference *r=&reference[i];
        if (r->first) {
            if (mk) { parent->any_test_failed|=mk->any_test_failed; mock_free(mk); }
            mk=mock_new(); mk->tw.vt=&vt;
            mk->term=term_init(mk->conf,mk->ucsdata,&mk->tw);
            mk->ldisc=ldisc_create(mk->conf,mk->term,&mk->backend,&mk->seat);
            term_size(mk->term,8,12,20); term_set_cell_size(mk->term,10,20);
            term_set_trust_status(mk->term,false);
        }
        test_context(mk,"Kitty upstream feature query: %s",r->name);
        Terminal *t=mk->term;
        size_t memory=term_kitty_memory(t);
        term_data_fragmented(t,r->wire);
        if (error_control && !strcmp(r->name,"continuation-invalid-base64/interleaved")) {
            /* Both terminals must return an error for the same upload ID.
             * The strict local base64 parser and upstream decoder use different
             * error codes/descriptions; preserve the original captured reply. */
            IEQUAL(strncmp(mk->to_backend->s,"\033_Gi=9;E",8),0);
            IEQUAL(strstr(mk->to_backend->s,"\033\\")!=NULL,true);
            strbuf_clear(mk->to_backend);
        } else kitty_reply_is(mk,r->reply);
        IEQUAL(t->curs.x,r->x); IEQUAL(t->curs.y,r->y);
        IEQUAL(kitty_images(t,0),r->images);
        unsigned count=0;
        for (const NemoKittyPlacement *p=nemo_kitty_placements_first(term_kitty_placements(t,0));
             p;p=nemo_kitty_placement_next(p)) {
            NemoKittyView v;
            IEQUAL(nemo_kitty_placement_view(p,10,20,&v),true);
            if (count<r->layers) {
                const NemoRaster *pixels=nemo_kitty_image_raster(v.image);
                double actual[]={v.left,v.top,v.right,v.bottom,
                    v.source_left/pixels->width,v.source_top/pixels->height,
                    v.source_right/pixels->width,v.source_bottom/pixels->height,v.z};
                for (unsigned j=0;j<lenof(actual);j++) kitty_near(mk,actual[j],r->boxes[count][j]);
            }
            count++;
        }
        IEQUAL(count,r->layers);
        if (strstr(r->wire,"a=q")) IEQUAL(term_kitty_memory(t),memory);
        kitty_check_budget(mk);
    }
    if (mk) { parent->any_test_failed|=mk->any_test_failed; mock_free(mk); }
}

static void test_kitty_terminal(Mock *mk)
{
    Terminal *t=mk->term;
    kitty_reset(mk);
    test_context(mk,"Kitty capability is disabled without a compositor");
    term_data_fragmented(t,"\033_Ga=q,i=1,f=24,s=1,v=1;/wAA\033\\Z");
    IEQUAL(t->kitty==NULL,true); kitty_reply_is(mk,"");
    IEQUAL(get_termchar(t,0,0).chr,'Z'|CSET_ASCII);

    TermWinVtable vt=mock_termwin_vt;
    vt.kitty_graphics=true; vt.decode_image=kitty_mock_decode;
    mk->tw.vt=&vt;
    kitty_reset(mk);
    test_context(mk,"Kitty feature discovery keeps an empty owner empty and obeys product limits");
    term_data_fragmented(t,"\033_Ga=q,i=31,e=T,s=8192,v=8193,S=2097152,c=8192,r=8193\033\\");
    kitty_reply_is(mk,"\033_Gi=31,e=T,s=8192,S=2097152,c=8192;OK\033\\");
    IEQUAL(term_kitty_cache(t,0)==NULL,true);
    IEQUAL(term_kitty_placements(t,0)==NULL,true);
    size_t query_memory=term_kitty_memory(t);
    for (unsigned i=0;i<1000;i++) {
        term_data_fragmented(t,"\033_Ga=q,i=31,e=T,S=2097153,C=1,U=1\033\\");
        kitty_reply_is(mk,"\033_Gi=31,e=T,C=1;OK\033\\");
        IEQUAL(term_kitty_memory(t),query_memory);
    }
    IEQUAL(term_kitty_cache(t,0)==NULL,true);
    IEQUAL(term_kitty_placements(t,0)==NULL,true);
    kitty_reset(mk);
    test_context(mk,"Kitty streaming decode, placement and quiet replies");
    term_data_fragmented(t,"\033[2;3H\033_Ga=T,i=11,p=5,f=32,s=1,v=1,C=1;/wAA/w==\033\\");
    IEQUAL(kitty_views(t,0),1); IEQUAL(kitty_images(t,0),1);
    kitty_reply_is(mk,"\033_Gi=11,p=5;OK\033\\");
    NemoKittyView v=kitty_first(mk,0);
    IEQUAL(v.left,16); IEQUAL(v.top,16); IEQUAL(v.right,17);
    IEQUAL(nemo_kitty_image_raster(v.image)->pixels[0],0xffff0000);
    IEQUAL(t->curs.x,2); IEQUAL(t->curs.y,1);
    term_data_fragmented(t,"\033_Ga=p,i=11,p=5,c=2,r=2,q=1\033\\");
    IEQUAL(kitty_views(t,0),1); IEQUAL(t->curs.x,4); IEQUAL(t->curs.y,2);
    kitty_reply_is(mk,"");
    term_data_fragmented(t,"\033_Ga=p,i=99,q=1\033\\");
    kitty_reply_is(mk,"\033_Gi=99;ENOENT:image not found\033\\");
    term_data_fragmented(t,"\033_Ga=p,i=99,q=2\033\\"); kitty_reply_is(mk,"");

    kitty_reset(mk);
    test_context(mk,"Kitty chunks, query isolation, explicit rejection and cancellation");
    term_data_fragmented(t,"\033_Ga=T,i=3,f=24,s=2,v=1,m=1;/wAA\033\\");
    IEQUAL(term_kitty_pending(t),true); IEQUAL(kitty_images(t,0),0); kitty_reply_is(mk,"");
    term_data_fragmented(t,"\033_Ga=q,e=t,i=8\033\\");
    kitty_reply_is(mk,"\033_Gi=8,e=t;OK\033\\");
    IEQUAL(term_kitty_pending(t),true);
    term_data_fragmented(t,"\033_Gm=0;AP8A\033\\");
    kitty_reply_is(mk,"\033_Gi=3;OK\033\\");
    IEQUAL(term_kitty_pending(t),false); IEQUAL(kitty_views(t,0),1);
    v=kitty_first(mk,0);
    IEQUAL(nemo_kitty_image_raster(v.image)->pixels[1],0xff00ff00);
    term_data_fragmented(t,"\033_Ga=q,i=9,t=f,f=24,s=1,v=1;L3RtcC94\033\\");
    kitty_reply_is(mk,"\033_Gi=9;ENOTSUP:image format or transport\033\\");
    IEQUAL(kitty_images(t,0),1);
    term_data_fragmented(t,"\033_Ga=T,i=4,f=24,s=2,v=1,m=1;/wAA\033\\\033_Gm=0;AP\030Q");
    IEQUAL(term_kitty_pending(t),false); IEQUAL(kitty_images(t,0),1);
    IEQUAL(get_termchar(t,1,0).chr,'Q'|CSET_ASCII);
    term_data_fragmented(t,"\033_Ga=T,i=5,f=24,s=1,v=1;/wAA\007\033\\");
    IEQUAL(kitty_images(t,0),1);
    IEQUAL(strstr(mk->to_backend->s,"EINVAL")!=NULL,true); strbuf_clear(mk->to_backend);
    term_data_fragmented(t,"\033_Ga=T,i=6,f=24,s=1,v=1;/wAA\033[H!");
    IEQUAL(kitty_images(t,0),1); IEQUAL(get_termchar(t,0,0).chr,'!'|CSET_ASCII);
    term_data_fragmented(t,"\033_Ga=T,i=7,f=24,s=1,v=1,C=1;/wAA\302\234");
    IEQUAL(kitty_images(t,0),2); kitty_reply_is(mk,"\033_Gi=7;OK\033\\");

    kitty_reset(mk);
    test_context(mk,"Kitty screen ownership, text erase and image delete are distinct");
    term_data_fragmented(t,"\033_Ga=T,i=1,f=24,s=1,v=1,C=1;/wAA\033\\");
    term_data_fragmented(t,"X\033[2K\033[H\033[J\033[1J");
    IEQUAL(kitty_views(t,0),1);
    term_data_fragmented(t,"\033[L");
    v=kitty_first(mk,0); IEQUAL(v.top,0);
    term_data_fragmented(t,"\033[M");
    v=kitty_first(mk,0); IEQUAL(v.top,0);
    term_data_fragmented(t,"\033[?1049h\033_Ga=T,i=1,f=24,s=1,v=1,C=1;AP8A\033\\");
    IEQUAL(kitty_views(t,0),1); IEQUAL(kitty_views(t,1),1);
    term_data_fragmented(t,"\033[?1049l\033_Ga=d,d=i,i=1\033\\");
    IEQUAL(kitty_views(t,0),0); IEQUAL(kitty_images(t,0),1);
    IEQUAL(kitty_views(t,1),1);
    term_data_fragmented(t,"\033_Ga=p,i=1,C=1\033\\\033[?47h\033[?47l");
    IEQUAL(kitty_views(t,1),1);
    term_data_fragmented(t,"\033[?1049h"); IEQUAL(kitty_images(t,1),0);
    term_data_fragmented(t,"\033[?1049l\033[2J"); IEQUAL(kitty_images(t,0),0);

    kitty_reset(mk);
    test_context(mk,"Kitty scrollback, RI, ED2, ED3 and hard reset");
    term_size(t,4,10,20);
    term_data_fragmented(t,"\033_Ga=T,i=1,f=24,s=1,v=1,C=1;/wAA\033\\\033[4;1H\n");
    v=kitty_first(mk,0); IEQUAL(v.top,-16);
    term_data_fragmented(t,"\033[H\033M"); v=kitty_first(mk,0); IEQUAL(v.top,-16);
    term_data_fragmented(t,"\033_Ga=T,i=2,f=24,s=1,v=1,C=1;AP8A\033\\\033[2J");
    IEQUAL(kitty_views(t,0),1); IEQUAL(kitty_images(t,0),1);
    term_data_fragmented(t,"\033c"); IEQUAL(kitty_views(t,0),1);
    term_data_fragmented(t,"\033[3J"); IEQUAL(kitty_views(t,0),0); IEQUAL(kitty_images(t,0),0);

    kitty_reset(mk);
    test_context(mk,"Kitty cursor wrap, font offset clamp, resize history recovery");
    term_size(t,4,10,20);
    term_data_fragmented(t,"\033[4;10H\033_Ga=T,i=1,f=24,s=1,v=1;/wAA\033\\");
    IEQUAL(t->curs.x,0); IEQUAL(t->curs.y,3); v=kitty_first(mk,0); IEQUAL(v.top,32);
    term_data_fragmented(t,"\033[H\033_Ga=p,i=1,p=1,X=7,Y=15,C=1\033\\");
    term_set_cell_size(t,4,8); term_set_cell_size(t,8,16);
    const NemoKittyPlacement *second=nemo_kitty_placement_next(nemo_kitty_placements_first(term_kitty_placements(t,0)));
    IEQUAL(nemo_kitty_placement_view(second,8,16,&v),true);
    IEQUAL(v.left,3); IEQUAL(v.top,7);
    term_data_fragmented(t,"\033[4;1H"); term_size(t,3,10,20);
    term_size(t,4,10,20); v=kitty_first(mk,0); IEQUAL(v.top,32);
    term_data_fragmented(t,"\033_Ga=p,i=1,r=4294967295\033\\");
    IEQUAL(strstr(mk->to_backend->s,"E2BIG")!=NULL,true);

    kitty_reset(mk);
    test_context(mk,"Kitty image budget is shared across screens, Sixel and iTerm");
    term_data_fragmented(t,"\033_Ga=T,i=1,f=100,C=1;iVBORw0KGgpB\033\\"
        "\033_Ga=T,i=2,f=100,C=1;iVBORw0KGgpB\033\\"
        "\033[?1049h\033_Ga=T,i=3,f=100,C=1;iVBORw0KGgpB\033\\");
    IEQUAL(kitty_images(t,0),2); IEQUAL(kitty_images(t,1),1); kitty_check_budget(mk);
    strbuf_clear(mk->to_backend);
    term_data_fragmented(t,"\033_Ga=q,i=99,f=100;iVBORw0KGgpB\033\\");
    kitty_reply_is(mk,"\033_Gi=99;E2BIG:image budget\033\\");
    IEQUAL(kitty_images(t,0),2); IEQUAL(kitty_images(t,1),1); kitty_check_budget(mk);
    term_data_fragmented(t,"\033_Ga=T,i=4,f=100,C=1;iVBORw0KGgpB\033\\");
    IEQUAL(kitty_images(t,0),2); IEQUAL(kitty_images(t,1),1); kitty_check_budget(mk);
    image_feed(mk); IEQUAL(image_count(t),1); kitty_check_budget(mk);
    term_data_fragmented(t,"\033]1337;File=inline=1:Ymln\033\\");
    kitty_check_budget(mk); IEQUAL(kitty_images(t,0),2); IEQUAL(kitty_images(t,1),1);
    term_data_fragmented(t,"\033c\033[3J");
    IEQUAL(kitty_images(t,0),0); IEQUAL(kitty_images(t,1),0); IEQUAL(image_count(t),0);
    IEQUAL(term_kitty_memory(t)<8192,true);
    mk->tw.vt=&mock_termwin_vt;
    test_kitty_terminal_reference(mk);
    test_kitty_compression_reference(mk);
    test_kitty_query_reference(mk,kitty_feature_reference,lenof(kitty_feature_reference),false);
    puts("Kitty upstream feature queries: 84 cases, 176 states (22 explicit capability subsets)");
    test_kitty_query_reference(mk,kitty_query_error_reference,lenof(kitty_query_error_reference),true);
    puts("Kitty upstream query errors: 54 cases, 216 states (one data-error envelope control)");
}
