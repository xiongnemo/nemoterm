/* SPDX-License-Identifier: MIT
 * Native adapters. Included after the upstream parser's private state types.
 */
#ifdef _MSC_VER
#pragma warning(push)
/* jmp_buf deliberately gives this heap-owned structure 16-byte alignment. */
#pragma warning(disable:4324)
#endif
struct NemoRegis {
    NemoRegisConfig config;
    RegisGraphicsContext context;
    RegisParseState state;
    Graphic *pages[16];
    ColorRegister shared[MAX_COLOR_REGISTERS];
    size_t bytes;
    uint64_t work;
    unsigned depth, screen, next_id;
    bool active;
    NemoRegisResult result;
    jmp_buf escape;
    char tempstr[1024], reply_buffer[4096], *input;
    size_t reply_length;
};
#ifdef _MSC_VER
#pragma warning(pop)
#endif

typedef union RegisAllocation {
    long double alignment; /* covers every allocation type used by this module */
    struct { NemoRegis *owner; size_t size; } record;
} RegisAllocation;

static void regis_abort(NemoRegis *owner, NemoRegisResult result)
{
    owner->result = result;
    assert(owner->active);
    longjmp(owner->escape,1);
}

static void regis_tick(NemoRegis *owner)
{
    if (!owner->work) regis_abort(owner,NEMO_REGIS_LIMIT);
    --owner->work;
}

static void *regis_allocate(NemoRegis *owner, size_t size)
{
    if (size > owner->config.memory_limit ||
        size+sizeof(RegisAllocation) > owner->config.memory_limit-owner->bytes)
        regis_abort(owner,NEMO_REGIS_LIMIT);
    size += sizeof(RegisAllocation);
    if (owner->config.resize_memory &&
        !owner->config.resize_memory(owner->config.user,owner->bytes,owner->bytes+size))
        regis_abort(owner,NEMO_REGIS_LIMIT);
    RegisAllocation *block = calloc(1,size);
    if (!block) {
        if (owner->config.resize_memory)
            owner->config.resize_memory(owner->config.user,owner->bytes+size,owner->bytes);
        regis_abort(owner,NEMO_REGIS_NOMEM);
    }
    block->record.owner = owner;
    block->record.size = size;
    owner->bytes += size;
    return block+1;
}

static void regis_deallocate(void *data)
{
    if (!data) return;
    RegisAllocation *block = (RegisAllocation *)data-1;
    NemoRegis *owner = block->record.owner;
    size_t size = block->record.size;
    assert(size <= owner->bytes);
    if (owner->config.resize_memory)
        owner->config.resize_memory(owner->config.user,owner->bytes,owner->bytes-size);
    owner->bytes -= size;
    free(block);
}

static void regis_free_tiles(Graphic *g)
{
    if (!g || !g->tiles) return;
    for (unsigned y=0;y<g->tile_rows;y++) {
        if (!g->tiles[y]) continue;
        for (unsigned x=0;x<g->tile_columns;x++)
            regis_deallocate(g->tiles[y][x]);
        regis_deallocate(g->tiles[y]);
        g->tiles[y]=NULL;
    }
}

static void regis_free_graphic(Graphic *g)
{
    if (!g) return;
    regis_free_tiles(g);
    regis_deallocate(g->tiles);
    regis_deallocate(g);
}

static Graphic *get_new_or_matching_graphic(NemoRegis *owner, int row, int col,
                                            int width, int height, unsigned page)
{
    (void)row; (void)col;
    if (page>=8 || width<2 || height<2 || width>(int)owner->config.max_width ||
        height>(int)owner->config.max_height) regis_abort(owner,NEMO_REGIS_LIMIT);
    unsigned slot=owner->screen*8+page;
    Graphic *g=owner->pages[slot];
    if (g && g->actual_width==width && g->actual_height==height) return g;
    /* A page replacement has one owner; contexts are mapped again before use. */
    if (g) {
        if (owner->context.destination_graphic==g) owner->context.destination_graphic=NULL;
        if (owner->context.display_graphic==g) owner->context.display_graphic=NULL;
        regis_free_graphic(g);
        owner->pages[slot]=NULL;
    }
    g=regis_allocate(owner,sizeof(*g));
    owner->pages[slot]=g; /* ownership established before another allocation */
    g->xw=owner;
    g->page=page; g->screen=owner->screen; g->id=++owner->next_id;
    g->actual_width=width; g->actual_height=height;
    g->max_width=(int)owner->config.max_width; g->max_height=(int)owner->config.max_height;
    /* S(A) can change actual dimensions without remapping the graphic. Keep
     * the full supported coordinate range addressable, but allocate directory
     * rows lazily so a small page does not pay for an 8192-square pointer grid. */
    g->tile_columns=(owner->config.max_width+31)/32;
    g->tile_rows=(owner->config.max_height+31)/32;
    g->tiles=regis_allocate(owner,(size_t)g->tile_rows*sizeof(*g->tiles));
    g->background=COLOR_HOLE;
    g->valid_registers=owner->config.colours;
    g->color_registers=owner->config.private_colours ? g->private_registers : owner->shared;
    if (owner->config.private_colours) {
        static const short palette[16][3]={
            {0,0,0},{20,20,80},{80,13,13},{20,80,20},
            {80,20,80},{20,80,80},{80,80,20},{53,53,53},
            {26,26,26},{33,33,60},{60,26,26},{33,60,33},
            {60,33,60},{33,60,60},{60,60,33},{80,80,80}};
        for (unsigned i=0;i<16;i++) {
            g->private_registers[i].r=palette[i][0];
            g->private_registers[i].g=palette[i][1];
            g->private_registers[i].b=palette[i][2];
        }
    }
    return g;
}

static RegisterNum regis_background(const Graphic *g, unsigned x, unsigned y)
{
    return x<g->background_width && y<g->background_height ? g->background : COLOR_HOLE;
}

static RegisterNum read_pixel(const Graphic *g, int x, int y)
{
    if (!g || x<0 || y<0 || x>=g->actual_width || y>=g->actual_height ||
        x>=g->max_width || y>=g->max_height) return COLOR_HOLE;
    RegisterNum **row=g->tiles[(unsigned)y/32];
    RegisterNum *tile=row ? row[(unsigned)x/32] : NULL;
    return tile ? tile[((unsigned)y&31)*32+((unsigned)x&31)] :
        regis_background(g,(unsigned)x,(unsigned)y);
}

static void draw_solid_pixel(Graphic *g, int x, int y, unsigned colour)
{
    if (!g) return;
    regis_tick(g->xw);
    if (x<0 || y<0 || x>=g->actual_width || y>=g->actual_height ||
        x>=g->max_width || y>=g->max_height) return;
    if (colour>MAX_COLOR_REGISTERS && colour!=COLOR_HOLE) regis_abort(g->xw,NEMO_REGIS_INVALID);
    unsigned tx=(unsigned)x/32, ty=(unsigned)y/32;
    if (!g->tiles[ty]) {
        if (colour==regis_background(g,(unsigned)x,(unsigned)y)) return;
        g->tiles[ty]=regis_allocate(g->xw,(size_t)g->tile_columns*sizeof(**g->tiles));
    }
    RegisterNum **tile=&g->tiles[ty][tx];
    if (!*tile) {
        if (colour==regis_background(g,(unsigned)x,(unsigned)y)) return;
        *tile=regis_allocate(g->xw,TILE_PIXELS*sizeof(**tile));
        for (unsigned i=0;i<TILE_PIXELS;i++)
            (*tile)[i]=regis_background(g,tx*32+i%32,ty*32+i/32);
    }
    (*tile)[((unsigned)y&31)*32+((unsigned)x&31)]=(RegisterNum)colour;
    g->content_width=Max(g->content_width,(unsigned)x+1);
    g->content_height=Max(g->content_height,(unsigned)y+1);
    g->dirty=true;
}

static void draw_solid_rectangle(Graphic *g, int x1, int y1, int x2, int y2, unsigned colour)
{
    int tmp;
    if (!g) return;
    if (x1>x2) EXCHANGE(x1,x2,tmp);
    if (y1>y2) EXCHANGE(y1,y2,tmp);
    x1=Max(x1,0); y1=Max(y1,0);
    x2=Min(x2,g->actual_width-1); y2=Min(y2,g->actual_height-1);
    if (x1==0 && y1==0 && x2==g->actual_width-1 && y2==g->actual_height-1 &&
        (unsigned)g->actual_width>=g->content_width &&
        (unsigned)g->actual_height>=g->content_height) {
        regis_tick(g->xw);
        regis_free_tiles(g);
        g->background=(RegisterNum)colour;
        g->content_width=g->background_width=(unsigned)g->actual_width;
        g->content_height=g->background_height=(unsigned)g->actual_height;
        g->dirty=true;
        return;
    }
    for (int y=y1;y<=y2;y++)
        for (int x=x1;x<=x2;x++) draw_solid_pixel(g,x,y,colour);
}

static void copy_overlapping_area(Graphic *g, int sx, int sy, int dx, int dy,
                                  unsigned width, unsigned height, unsigned background)
{
    if (!width || !height) return;
    if (width>8192 || height>8192) regis_abort(g->xw,NEMO_REGIS_LIMIT);
    for (unsigned row=0;row<height;row++) {
        int y=dy<=sy ? (int)row : (int)(height-1-row);
        for (unsigned col=0;col<width;col++) {
            int x=dx<=sx ? (int)col : (int)(width-1-col);
            unsigned colour=read_pixel(g,sx+x,sy+y);
            if (sx+x<0 || sy+y<0 || sx+x>=g->actual_width || sy+y>=g->actual_height)
                colour=background;
            draw_solid_pixel(g,dx+x,dy+y,colour);
        }
    }
}

static void fetch_color_register(Graphic *g, unsigned index, ColorRegister *out)
{ *out=g->color_registers[index%g->valid_registers]; }

static void update_color_register(Graphic *g, unsigned index, int r, int green, int b)
{
    ColorRegister *colour=&g->color_registers[index%g->valid_registers];
    colour->r=(short)Min(100,Max(0,r));
    colour->g=(short)Min(100,Max(0,green));
    colour->b=(short)Min(100,Max(0,b));
    g->dirty=true;
}

static RegisterNum find_color_register(const ColorRegister *colours, int r, int g, int b)
{
    unsigned closest=0, distance=UINT_MAX;
    for (unsigned i=0;i<MAX_COLOR_REGISTERS;i++) {
        int dr=2*(colours[i].r-r), dg=3*(colours[i].g-g), db=colours[i].b-b;
        unsigned candidate=(unsigned)(dr*dr+dg*dg+db*db);
        if (candidate<distance) { closest=i; distance=candidate; }
    }
    return (RegisterNum)closest;
}

static void refresh_modified_displayed_graphics(NemoRegis *owner)
{ if (owner->config.refresh) owner->config.refresh(owner->config.user); }

static void regis_delay(NemoRegis *owner, unsigned milliseconds)
{ if (owner->config.delay) owner->config.delay(owner->config.user,milliseconds); }

static void unparseputc(NemoRegis *owner, int ch)
{
    regis_tick(owner);
    if (owner->reply_length==sizeof(owner->reply_buffer)) regis_abort(owner,NEMO_REGIS_LIMIT);
    owner->reply_buffer[owner->reply_length++]=(char)ch;
}
static void unparseputs(NemoRegis *owner, const char *text)
{ while (*text) unparseputc(owner,*text++); }
static void unparseputn(NemoRegis *owner, unsigned number)
{
    char text[32];
    snprintf(text,sizeof(text),"%u",number);
    unparseputs(owner,text);
}
static void unparse_end(NemoRegis *owner)
{
    if (owner->config.reply)
        owner->config.reply(owner->config.user,owner->reply_buffer,owner->reply_length);
    owner->reply_length=0;
}
