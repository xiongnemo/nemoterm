/* SPDX-License-Identifier: MIT
 * Included by terminal.c: byte framing and terminal ownership, independent
 * of the native compositor. No filesystem or shared-memory transport. */
typedef struct NemoKittyScreen {
    Terminal *term;
    NemoKittyCache *cache;
    NemoKittyPlacements *placements;
} NemoKittyScreen;

struct NemoTermKitty {
    NemoKitty *input;
    NemoKittyScreen screen[2];
};

const NemoKittyCache *term_kitty_cache(const Terminal *term, int screen)
{
    return term && term->kitty && screen>=0 && screen<2 ?
        term->kitty->screen[screen].cache : NULL;
}

const NemoKittyPlacements *term_kitty_placements(const Terminal *term, int screen)
{
    return term && term->kitty && screen>=0 && screen<2 ?
        term->kitty->screen[screen].placements : NULL;
}

size_t term_kitty_memory(const Terminal *term)
{
    if (!term || !term->kitty) return 0;
    size_t bytes=sizeof(*term->kitty)+nemo_kitty_memory(term->kitty->input);
    for (int i=0;i<2;i++)
        bytes+=nemo_kitty_cache_memory(term->kitty->screen[i].cache)+
            nemo_kitty_placements_memory(term->kitty->screen[i].placements);
    return bytes;
}

bool term_kitty_pending(const Terminal *term)
{
    return term && term->kitty && nemo_kitty_pending(term->kitty->input);
}

/* All callbacks count the two screens, transport, decoded pixels, placement
 * metadata and both other protocols, replacing the calling owner's accounting
 * with its proposed current value. Queries and metadata never evict images. */
static bool nemo_kitty_admit(Terminal *term, size_t owned, size_t current,
                             size_t extra, bool evict)
{
    size_t other=nemo_image_pending(term)-owned;
    const size_t budget=NEMO_SIXEL_DEFAULT_BUDGET;
    if (other>budget || current>budget-other || extra>budget-other-current)
        return false;
    current+=other;
    if (evict) return nemo_image_admit(term,current,extra);
    return term->image_bytes<=budget-current-extra;
}

static bool nemo_kitty_input_admit(void *ctx, size_t current, size_t extra)
{
    Terminal *term=ctx;
    return nemo_kitty_admit(term,nemo_kitty_memory(term->kitty->input),current,extra,false);
}

static bool nemo_kitty_pixels_admit(void *ctx, size_t current, size_t extra, bool evict)
{
    NemoKittyScreen *s=ctx;
    /* Cache construction is metadata-only and may be triggered by a query. */
    return nemo_kitty_admit(s->term,nemo_kitty_cache_memory(s->cache),current,extra,evict && s->cache);
}

static bool nemo_kitty_views_admit(void *ctx, size_t current, size_t extra)
{
    NemoKittyScreen *s=ctx;
    return nemo_kitty_admit(s->term,nemo_kitty_placements_memory(s->placements),current,extra,false);
}

static bool nemo_kitty_png_decode(void *ctx, const void *data, size_t length,
                                 NemoRaster *out, NemoRasterAdmission admit, void *actx)
{
    Terminal *term=((NemoKittyScreen *)ctx)->term;
    return term->win->vt->decode_image &&
        term->win->vt->decode_image(term->win,data,length,out,admit,actx);
}

static void nemo_kitty_removed(void *ctx, const NemoKittyImage *image)
{
    NemoKittyScreen *s=ctx;
    nemo_kitty_placements_image_removed(s->placements,image);
    term_invalidate(s->term);
}

static bool nemo_kitty_start(Terminal *term)
{
    if (!term->win->vt->kitty_graphics) return false;
    if (!term->kitty) {
        if (!nemo_kitty_admit(term,0,0,sizeof(*term->kitty),false)) return false;
        term->kitty=calloc(1,sizeof(*term->kitty));
        if (!term->kitty) return false;
        for (int i=0;i<2;i++) term->kitty->screen[i].term=term;
    }
    if (!term->kitty->input)
        term->kitty->input=nemo_kitty_new(NEMO_SIXEL_DEFAULT_BUDGET,nemo_kitty_input_admit,term);
    return nemo_kitty_begin(term->kitty->input);
}

static bool nemo_kitty_screen_ready(NemoKittyScreen *s)
{
    if (!s->cache)
        s->cache=nemo_kitty_cache_new(NEMO_SIXEL_DEFAULT_BUDGET,nemo_kitty_pixels_admit,
                                     nemo_kitty_png_decode,nemo_kitty_removed,s);
    if (s->cache && !s->placements)
        s->placements=nemo_kitty_placements_new(s->cache,NEMO_SIXEL_DEFAULT_BUDGET,
                                               nemo_kitty_views_admit,s);
    return s->cache && s->placements;
}

static void nemo_kitty_cancel_input(Terminal *term)
{
    if (term->kitty) nemo_kitty_cancel(term->kitty->input);
    term->kitty_apc=false;
    if (term->termstate>=NEMO_APC_START && term->termstate<=NEMO_APC_MAYBE_ST_UTF8)
        term->termstate=NEMO_APC_DROP;
}

static void nemo_kitty_free_terminal(Terminal *term)
{
    if (!term->kitty) return;
    for (int i=0;i<2;i++) {
        NemoKittyScreen *s=&term->kitty->screen[i];
        nemo_kitty_placements_free(s->placements);
        s->placements=NULL;
        nemo_kitty_cache_free(s->cache);
    }
    nemo_kitty_free(term->kitty->input);
    free(term->kitty);
    term->kitty=NULL;
}

static void nemo_kitty_clear_screen(Terminal *term, int screen, bool history)
{
    if (!term->kitty) return;
    NemoKittyScreen *s=&term->kitty->screen[screen];
    if (history) nemo_kitty_cache_clear(s->cache);
    else {
        NemoKittyCommand c={0};
        c.present=UINT64_C(1)<<('d'-'a'+26);
        c.values['d'-'a'+26]='A';
        unsigned deleted=0;
        nemo_kitty_placements_delete(s->placements,&c,0,0,term->cols,term->rows,
                                     term->cell_width,term->cell_height,&deleted);
        /* ED2/RIS also discard data that has no remaining placement. */
        nemo_kitty_cache_prune_range(s->cache,1,UINT32_MAX);
    }
    term_invalidate(term);
}

static void nemo_kitty_rescale(Terminal *term)
{
    nemo_kitty_cancel_input(term);
    if (term->kitty)
        for (int i=0;i<2;i++)
            nemo_kitty_placements_rescale(term->kitty->screen[i].placements,
                                          term->cell_width,term->cell_height);
}

static void nemo_kitty_rows(Terminal *term, int screen, int delta, int first)
{
    if (term->kitty)
        nemo_kitty_placements_rows(term->kitty->screen[screen].placements,
                                   delta,first,term->cell_width,term->cell_height);
}

static void nemo_scroll_page(Terminal *term, int top, int bottom, int lines, bool sb)
{
    /* Kitty overlays move with page/index scrolling, not IL/DL text editing.
     * Horizontal subregions leave overlays in place; they do not slice pixels. */
    if (term->kitty && !term->marg_l && term->marg_r==term->cols-1) {
        int count=max(top-bottom-1,min(lines,bottom-top+1));
        nemo_kitty_placements_scroll(term->kitty->screen[term->alt_which].placements,
            top,bottom,count,top!=0 || bottom!=term->rows-1,
            term->alt_which ? 0 : term->savelines,term->cell_width,term->cell_height);
    }
    scroll(term,top,bottom,lines,sb);
}

static void nemo_kitty_reply(Terminal *term, const NemoKittyCommand *c,
                            uint32_t id, uint32_t number, const char *status)
{
    unsigned quiet=nemo_kitty_get(c,'q');
    if (!term->ldisc || (!id && !number) || quiet>1 ||
        (quiet && !strcmp(status,"OK")) || nemo_kitty_get(c,'a')=='d') return;
    char reply[192];
    int n=sprintf(reply,"\033_G");
    if (id) n+=sprintf(reply+n,"i=%u",id);
    if (number) n+=sprintf(reply+n,",I=%u",number);
    unsigned placement=nemo_kitty_get(c,'p');
    if (placement) n+=sprintf(reply+n,",p=%u",placement);
    n+=sprintf(reply+n,";%s\033\\",status);
    nemo_protocol_send(term,reply,n);
}

static void nemo_kitty_feature_reply(Terminal *term, const NemoKittyCommand *c,
                                     bool malformed)
{
    unsigned id=nemo_kitty_get(c,'i'), number=nemo_kitty_get(c,'I');
    unsigned quiet=nemo_kitty_get(c,'q');
    if (!term->ldisc || !id || quiet>1) return;
    char reply[384];
    int used=snprintf(reply,sizeof(reply),"\033_Gi=%u",id);
    if (number) {
        used+=snprintf(reply+used,sizeof(reply)-(size_t)used,
            ",I=%u;EINVAL:Must not specify both image id and image number\033\\",number);
        nemo_protocol_send(term,reply,used);
        return;
    }
    if (malformed || quiet) return;
    for (char key='A';key<='z';key++) {
        if (nemo_kitty_has(c,key) && !strchr("aetofsvSONiIpxywhXYcrCUzPQHVdmq",key)) return;
    }
    /* Invalid enum bytes are rejected by the upstream parser before query
     * dispatch. Valid but unimplemented media/selectors simply are not echoed. */
    unsigned medium=nemo_kitty_get(c,'t'), compression=nemo_kitty_get(c,'o');
    unsigned deletion=nemo_kitty_get(c,'d');
    if (medium>127 || !strchr("dfts",(int)medium) ||
        (compression && compression!='z') || deletion>127 ||
        !strchr("aAiIcCnNpPqQrRxXyYzZfF",(int)deletion)) return;
    unsigned action=nemo_kitty_get(c,'e');
    if (!((action>='a' && action<='z') || (action>='A' && action<='Z'))) return;
    const char *keys=NULL;
    switch (action) {
      case 't': case 'q': keys="tofsvS"; break;
      case 'T': keys="tofsvSpxywhXYcrCz"; break;
      case 'p': keys="pxywhXYcrCz"; break;
      case 'd': keys="dpxyz"; break;
    }
    if (keys) {
        used+=snprintf(reply+used,sizeof(reply)-(size_t)used,",e=%c",(char)action);
        for (;*keys;keys++) {
            char key=*keys;
            uint32_t value=nemo_kitty_get(c,key);
            if (!nemo_kitty_has(c,key) || !value) continue;
            if ((key=='t' && value!='d') ||
                (key=='f' && value!=24 && value!=32 && value!=100) ||
                ((key=='s' || key=='v' || key=='c' || key=='r') && value>NEMO_KITTY_AXIS_MAX) ||
                (key=='S' && value>NEMO_KITTY_DATA_MAX) || (key=='C' && value!=1) ||
                (key=='d' && (value>127 || !strchr("aAiInNcCpPqQrRxXyYzZ",(int)value)))) continue;
            size_t available=sizeof(reply)-(size_t)used;
            int n= key=='t' || key=='o' || key=='d' ?
                snprintf(reply+used,available,",%c=%c",key,(char)value) :
                key=='z' ? snprintf(reply+used,available,",z=%d",nemo_kitty_signed(c,key)) :
                snprintf(reply+used,available,",%c=%u",key,value);
            if (n<0 || (size_t)n>=available) return;
            used+=n;
        }
    }
    /* At most 17 numeric/flag fields; no allocation or graphics-owner access. */
    if ((size_t)used+5>=sizeof(reply)) return;
    memcpy(reply+used,";OK\033\\",5);
    nemo_protocol_send(term,reply,used+5);
}

static const char *nemo_kitty_put(Terminal *term, NemoKittyScreen *s,
                                 NemoKittyImage *image, const NemoKittyCommand *c)
{
    /* Bounding cell extents also bounds cursor-induced scrolling work. */
    if (nemo_kitty_get(c,'c')>NEMO_KITTY_AXIS_MAX || nemo_kitty_get(c,'r')>NEMO_KITTY_AXIS_MAX)
        return "E2BIG:placement extent";
    NemoKittyLayout g;
    if (image) {
        const NemoRaster *r=nemo_kitty_image_raster(image);
        if (nemo_kitty_layout(c,r->width,r->height,term->curs.x,term->curs.y,
            term->cell_width,term->cell_height,&g)==NEMO_KITTY_LAYOUT_OK &&
            (g.effective_columns>NEMO_KITTY_AXIS_MAX || g.effective_rows>NEMO_KITTY_AXIS_MAX))
            return "E2BIG:placement extent";
    }
    NemoKittyPlacementStatus status=nemo_kitty_placements_put(s->placements,image,c,
        term->curs.x,term->curs.y,term->cell_width,term->cell_height,&g);
    switch (status) {
      case NEMO_KITTY_PLACE_NOT_FOUND: return "ENOENT:image not found";
      case NEMO_KITTY_PLACE_UNSUPPORTED: return "ENOTSUP:placement mode";
      case NEMO_KITTY_PLACE_LIMIT: return "E2BIG:placement limit";
      case NEMO_KITTY_PLACE_NOMEM: return "ENOMEM:placement allocation";
      case NEMO_KITTY_PLACE_INVALID: return "EINVAL:placement geometry";
      case NEMO_KITTY_PLACE_OK: break;
    }
    if (g.advance_columns || g.advance_rows) {
        uint64_t x=(uint64_t)term->curs.x+g.advance_columns;
        uint64_t y=(uint64_t)term->curs.y+g.advance_rows;
        if (x>=(unsigned)term->cols) { x=0; y++; }
        /* Geometry admission bounds this loop, including inferred dimensions. */
        while (y>(unsigned)term->marg_b) {
            int n=(int)min(y-term->marg_b,(uint64_t)(term->marg_b-term->marg_t+1));
            nemo_scroll_page(term,term->marg_t,term->marg_b,n,true);
            y-=n;
        }
        term->curs.x=(int)x;
        term->curs.y=(int)min(y,(uint64_t)(term->rows-1));
        term->wrapnext=false;
        term->grapheme_pending=false;
    }
    return "OK";
}

static void nemo_kitty_finish_apc(Terminal *term)
{
    if (!term->kitty_apc || !term->kitty) return;
    NemoKittyPacket packet;
    NemoKittyResult result=nemo_kitty_finish(term->kitty->input,&packet);
    if (result==NEMO_KITTY_MORE) return;
    const NemoKittyCommand *c=&packet.command;
    uint32_t id=nemo_kitty_get(c,'i'),number=nemo_kitty_get(c,'I');
    const char *status="EINVAL:graphics command";
    bool feature=nemo_kitty_get(c,'a')=='q' && nemo_kitty_has(c,'e');
    if (feature) {
        nemo_kitty_feature_reply(term,c,result==NEMO_KITTY_ERROR);
        if (result==NEMO_KITTY_ERROR) nemo_kitty_cancel(term->kitty->input);
        return;
    }
    NemoKittyScreen *s=&term->kitty->screen[term->alt_which];
    if (result==NEMO_KITTY_ERROR) {
        if (nemo_kitty_status(term->kitty->input)==NEMO_KITTY_LIMIT) status="E2BIG:graphics payload";
        else if (nemo_kitty_status(term->kitty->input)==NEMO_KITTY_OUT_OF_MEMORY) status="ENOMEM:graphics payload";
    } else if (!nemo_kitty_screen_ready(s)) status="ENOMEM:image owner";
    else {
        unsigned action=nemo_kitty_get(c,'a');
        if (action=='t' || action=='T' || action=='q') {
            NemoKittyImageResult r=nemo_kitty_cache_load(s->cache,&packet);
            if (r.status==NEMO_KITTY_IMAGE_OK) {
                id=r.id; number=r.number;
                status=action=='T' ? nemo_kitty_put(term,s,r.image,c) : "OK";
                if (r.image && !id && (action=='t' || strcmp(status,"OK")))
                    nemo_kitty_cache_remove(s->cache,r.image);
            } else if (r.status==NEMO_KITTY_IMAGE_UNSUPPORTED) status="ENOTSUP:image format or transport";
            else if (r.status==NEMO_KITTY_IMAGE_LIMIT) status="E2BIG:image budget";
            else if (r.status==NEMO_KITTY_IMAGE_NOMEM) status="ENOMEM:image allocation";
            else status="EINVAL:image data";
        } else if (action=='p') {
            NemoKittyImage *image=nemo_kitty_cache_find(s->cache,id,number);
            if (image) id=nemo_kitty_image_id(image);
            status=nemo_kitty_put(term,s,image,c);
        } else if (action=='d') {
            unsigned deleted=0;
            nemo_kitty_placements_delete(s->placements,c,term->curs.x,term->curs.y,
                term->cols,term->rows,term->cell_width,term->cell_height,&deleted);
        } else status="ENOTSUP:graphics action";
        term_invalidate(term);
    }
    nemo_kitty_reply(term,c,id,number,status);
    nemo_kitty_cancel(term->kitty->input);
}

/* Consume raw APC bytes before charset/UTF-8 decoding. BEL is payload, never
 * a terminator. An interrupted ESC is returned to the ordinary escape parser. */
static bool nemo_kitty_apc_byte(Terminal *term, unsigned char c)
{
    if (c==0x18 || c==0x1a) {
        nemo_kitty_cancel_input(term); term->termstate=TOPLEVEL; return true;
    }
    if (c==0x9c || (term->termstate==NEMO_APC_MAYBE_ST && c=='\\')) {
        nemo_kitty_finish_apc(term);
        term->kitty_apc=false; term->termstate=TOPLEVEL; return true;
    }
    if (term->termstate==NEMO_APC_MAYBE_ST) {
        nemo_kitty_cancel_input(term); term->termstate=SEEN_ESC;
        term->esc_query=0; return false;
    }
    if (term->termstate==NEMO_APC_MAYBE_ST_UTF8) nemo_kitty_cancel_input(term);
    if (c==0x1b) { term->termstate=NEMO_APC_MAYBE_ST; return true; }
    if (c==0xc2) { term->termstate=NEMO_APC_MAYBE_ST_UTF8; return true; }
    if (term->termstate==NEMO_APC_START) {
        term->kitty_apc=c=='G' && nemo_kitty_start(term);
        term->termstate=term->kitty_apc ? NEMO_APC_DATA : NEMO_APC_DROP;
    } else if (term->termstate==NEMO_APC_DATA && term->kitty_apc)
        nemo_kitty_feed(term->kitty->input,&c,1);
    return true;
}
