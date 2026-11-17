/* SPDX-License-Identifier: MIT
 * Complete DCS transactions, per-terminal ownership and live image views.
 */
#define NEMO_REGIS_INPUT_LIMIT (256U*1024U)
#define NEMO_REGIS_FONT_RESERVE (65U*1024U)

struct NemoTermRegis {
    Terminal *term;
    NemoRegis *decoder;
    unsigned char *input;
    size_t length, capacity, decoder_bytes, font_reserve;
    unsigned mode;
    bool pending, syncing;
    NemoRegisResult last_result;
};

static bool nemo_regis_views_locked(Terminal *term)
{
    return term->regis && (term->regis->syncing || nemo_regis_active(term->regis->decoder));
}

static void nemo_regis_sync_views(Terminal *term)
{
    if (!term->regis) return;
    NemoRegis *decoder=term->regis->decoder;
    term->regis->syncing=true;
    NemoTermImage **link=&term->images;
    while (*link) {
        NemoTermImage *image=*link;
        if (image->source->regis==decoder && !nemo_image_live(term,image))
            nemo_image_remove(term,link);
        else link=&image->next;
    }
    for (unsigned id=0;(id=nemo_regis_next_graphic(decoder,id))!=0;) {
        bool found=false;
        NemoTermImage **tail=&term->images;
        for (;*tail;tail=&(*tail)->next)
            if ((*tail)->source->regis==decoder && (*tail)->source->regis_id==id) found=true;
        if (found) continue;
        size_t bytes=sizeof(NemoTermImage)+sizeof(NemoImageSource);
        if (!nemo_image_admit(term,nemo_image_pending(term),bytes)) {
            nemo_regis_drop_graphic(decoder,id);
            continue;
        }
        /* Admission may evict a preceding raster; locate the tail again. */
        tail=&term->images;
        while (*tail) tail=&(*tail)->next;
        NemoTermImage *image=snew(NemoTermImage);
        memset(image,0,sizeof(*image));
        image->source=snew(NemoImageSource);
        *image->source=(NemoImageSource){.references=1,.memory_bytes=sizeof(NemoImageSource),
            .regis=decoder,.regis_id=id};
        image->memory_bytes=sizeof(*image);
        nemo_image_live(term,image);
        *tail=image;
        term->image_bytes+=bytes;
    }
    term->regis->syncing=false;
}

static void nemo_regis_erase_cells(Terminal *term,pos start,pos end)
{
    if (!term->regis) return;
    NemoRegis *decoder=term->regis->decoder;
    for (int y=max(0,start.y);y<=min(term->rows-1,end.y);y++) {
        int left=y==start.y ? max(0,start.x) : 0;
        int right=y==end.y ? min(term->cols,end.x) : term->cols;
        if (right<=left) continue;
        unsigned width=(unsigned)min((uint64_t)UINT_MAX,(uint64_t)(right-left)*term->cell_width);
        if (!nemo_regis_erase(decoder,(int64_t)left*term->cell_width,
                (int64_t)y*term->cell_height,width,(unsigned)term->cell_height,
                (unsigned)term->cell_width,(unsigned)term->cell_height)) break;
    }
    nemo_regis_sync_views(term);
    /* Text cells can already be blank. Repaint their background so holes in
     * a live graphic remove pixels from the previously presented frame. */
    term_invalidate(term);
}

size_t term_regis_memory(const Terminal *term)
{
    const NemoTermRegis *state=term ? term->regis : NULL;
    return state ? sizeof(*state)+state->capacity+state->decoder_bytes+state->font_reserve : 0;
}

bool term_regis_pending(const Terminal *term)
{ return term && term->regis && term->regis->pending; }

const NemoRegis *term_regis_decoder(const Terminal *term)
{ return term && term->regis ? term->regis->decoder : NULL; }

NemoRegisResult term_regis_last_result(const Terminal *term)
{ return term && term->regis ? term->regis->last_result : NEMO_REGIS_INVALID; }

static void nemo_regis_cancel_input(Terminal *term)
{
    if (!term->regis) return;
    free(term->regis->input);
    term->regis->input=NULL;
    term->regis->length=term->regis->capacity=0;
    term->regis->pending=false;
}

static bool nemo_regis_reserve(void *ctx, size_t old_bytes, size_t new_bytes)
{
    NemoTermRegis *state=ctx;
    assert(state->decoder_bytes==old_bytes);
    if (new_bytes>old_bytes &&
        !nemo_image_admit(state->term,nemo_image_pending(state->term),new_bytes-old_bytes))
        return false;
    state->decoder_bytes=new_bytes;
    return true;
}

static void nemo_regis_send(void *ctx, const char *data, size_t length)
{
    NemoTermRegis *state=ctx;
    nemo_protocol_send(state->term,data,(int)length); /* decoder reply <=4096 */
}

static bool nemo_regis_native_glyph(void *ctx, const char *font, unsigned ch,
    unsigned maxw, unsigned maxh, unsigned char *pixels, size_t capacity,
    unsigned *width, unsigned *height)
{
    NemoTermRegis *state=ctx;
    Terminal *term=state->term;
    if (!term->win->vt->regis_glyph) return false;
    if (!state->font_reserve) {
        if (!nemo_image_admit(term,nemo_image_pending(term),NEMO_REGIS_FONT_RESERVE))
            return false;
        state->font_reserve=NEMO_REGIS_FONT_RESERVE;
    }
    return term->win->vt->regis_glyph(term->win,font,ch,maxw,maxh,pixels,capacity,width,height);
}

static void nemo_regis_clear(Terminal *term)
{
    if (!term->regis) return;
    NemoTermImage **link=&term->images;
    while (*link) {
        if ((*link)->source->regis && (*link)->source->regis==term->regis->decoder) nemo_image_remove(term,link);
        else link=&(*link)->next;
    }
    nemo_regis_cancel_input(term);
    nemo_regis_free(term->regis->decoder);
    assert(!term->regis->decoder_bytes);
    if (term->regis->font_reserve && term->win->vt->regis_clear_font)
        term->win->vt->regis_clear_font(term->win);
    free(term->regis);
    term->regis=NULL;
}

bool term_regis_set_size(Terminal *term, unsigned width, unsigned height,
                         unsigned max_width, unsigned max_height)
{
    if (!term || width<2 || height<2 || max_width<width || max_height<height ||
        max_width>8192 || max_height>8192 ||
        term_regis_pending(term)) return false;
    if (term->regis_width==width && term->regis_height==height &&
        term->regis_max_width==max_width && term->regis_max_height==max_height) return true;
    nemo_regis_clear(term);
    term->regis_width=width; term->regis_height=height;
    term->regis_max_width=max_width; term->regis_max_height=max_height;
    term_invalidate(term);
    return true;
}

static bool nemo_regis_begin(Terminal *term)
{
    nemo_regis_cancel_input(term);
    if (!term->regis) {
        if (!nemo_image_admit(term,nemo_image_pending(term),sizeof(NemoTermRegis))) return false;
        term->regis=calloc(1,sizeof(*term->regis));
        if (!term->regis) return false;
        term->regis->term=term;
        NemoRegisConfig config={0};
        config.width=term->regis_width ? term->regis_width : 800;
        config.height=term->regis_height ? term->regis_height : 480;
        config.max_width=term->regis_max_width ? term->regis_max_width : 8192;
        config.max_height=term->regis_max_height ? term->regis_max_height : 8192;
        config.colours=16; config.terminal_id=340;
        config.memory_limit=NEMO_SIXEL_DEFAULT_BUDGET;
        config.private_colours=term->sixel_private_palette;
        config.user=term->regis; config.resize_memory=nemo_regis_reserve;
        config.reply=nemo_regis_send; config.glyph=nemo_regis_native_glyph;
        term->regis->decoder=nemo_regis_new(&config);
        if (!term->regis->decoder) { nemo_regis_clear(term); return false; }
    }
    nemo_regis_screen(term->regis->decoder,term->alt_which);
    nemo_regis_private_colours(term->regis->decoder,term->sixel_private_palette);
    term->regis->mode=term->sixel_header[0];
    term->regis->pending=true;
    return true;
}

static bool nemo_regis_input_byte(Terminal *term, unsigned char c)
{
    NemoTermRegis *state=term->regis;
    if (!state || !state->pending) return false;
    if (!c || c==127) return true; /* String-state NUL and DEL are ignored. */
    if (state->length==NEMO_REGIS_INPUT_LIMIT) { nemo_regis_cancel_input(term); return false; }
    if (state->length==state->capacity) {
        size_t capacity=state->capacity ? state->capacity*2 : 128;
        /* Account for both buffers during growth, not only the final size. */
        if (!nemo_image_admit(term,nemo_image_pending(term),capacity)) {
            nemo_regis_cancel_input(term); return false;
        }
        unsigned char *input=malloc(capacity);
        if (!input) { nemo_regis_cancel_input(term); return false; }
        if (state->length) memcpy(input,state->input,state->length);
        free(state->input); state->input=input; state->capacity=capacity;
    }
    state->input[state->length++]=c;
    return true;
}

static void nemo_regis_complete(Terminal *term)
{
    if (!term_regis_pending(term)) return;
    NemoTermRegis *state=term->regis;
    state->last_result=nemo_regis_parse(state->decoder,state->mode,state->input,state->length);
    nemo_regis_cancel_input(term);
    nemo_regis_sync_views(term);
    term_invalidate(term);
}
