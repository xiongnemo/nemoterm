/* SPDX-License-Identifier: MIT
 * Complete DCS transactions and per-terminal ReGIS ownership. Native image
 * placement/lifecycle integration follows separately; no capability claim
 * is made by this input adapter alone.
 */
#define NEMO_REGIS_INPUT_LIMIT (256U*1024U)
#define NEMO_REGIS_FONT_RESERVE (65U*1024U)

struct NemoTermRegis {
    Terminal *term;
    NemoRegis *decoder;
    unsigned char *input;
    size_t length, capacity, decoder_bytes, font_reserve;
    unsigned mode;
    bool pending;
    NemoRegisResult last_result;
};

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
    nemo_regis_cancel_input(term);
    nemo_regis_free(term->regis->decoder);
    assert(!term->regis->decoder_bytes);
    if (term->regis->font_reserve && term->win->vt->regis_clear_font)
        term->win->vt->regis_clear_font(term->win);
    free(term->regis);
    term->regis=NULL;
}

bool term_regis_set_size(Terminal *term, unsigned width, unsigned height)
{
    if (!term || width<2 || height<2 || width>8192 || height>8192 ||
        term_regis_pending(term)) return false;
    if (term->regis_width==width && term->regis_height==height) return true;
    nemo_regis_clear(term);
    term->regis_width=width; term->regis_height=height;
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
        config.max_width=config.max_height=8192;
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
    term_invalidate(term);
}
