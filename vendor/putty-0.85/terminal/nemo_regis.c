/* SPDX-License-Identifier: MIT
 * See nemo_regis_parser.inc and nemo_regis_colour.inc for upstream notices.
 */
#define _CRT_SECURE_NO_WARNINGS
#include "nemo_regis.h"
#include <assert.h>
#include <ctype.h>
#include <errno.h>
#include <limits.h>
#include <math.h>
#include <setjmp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define M_PI 3.14159265358979323846
#define M_SQRT2 1.41421356237309504880
#define MAX_I_DELAY 32767
#define TRACE(args) ((void)0)
#define CharOf(c) ((unsigned char)(c))
#define IsSpace(c) isspace(CharOf(c))
#define xBIT(n) (1U << (n))
#define Min(a,b) ((a)<(b)?(a):(b))
#define Max(a,b) ((a)>(b)?(a):(b))
#define EXCHANGE(a,b,tmp) ((tmp)=(a),(a)=(b),(b)=(tmp))
#define True true
#define False false
#define L_BLOK '['
#define R_BLOK ']'
#define MAX_COLOR_REGISTERS 1024U
#define COLOR_HOLE 0x404U
#define TILE_SIDE 32U
#define TILE_PIXELS (TILE_SIDE*TILE_SIDE)
#define REGIS_INPUT_LIMIT (256U*1024U)
#define REGIS_MEMORY_LIMIT (4U*1024U*1024U)
#define REGIS_WORK_LIMIT UINT64_C(16000000)
typedef unsigned char Char;
typedef bool Boolean;
typedef bool Bool;
typedef unsigned short RegisterNum;
typedef struct { short r, g, b; } ColorRegister;
typedef NemoRegis *XtermWidget;
typedef struct Graphic {
    NemoRegis *xw;
    RegisterNum **tiles, background;
    ColorRegister *color_registers;
    ColorRegister private_registers[MAX_COLOR_REGISTERS];
    unsigned tile_columns, tile_rows, valid_registers, id, page, screen;
    int actual_width, actual_height, max_width, max_height;
    bool dirty, hidden, valid;
} Graphic;

#include "nemo_regis_colour.inc"
#include "nemo_regis_parser.inc"

NemoRegis *nemo_regis_new(const NemoRegisConfig *config)
{
    if (!config || config->width < 2 || config->height < 2 ||
        config->max_width < config->width || config->max_height < config->height ||
        config->max_width > 8192 || config->max_height > 8192 ||
        config->colours < 2 || config->colours > MAX_COLOR_REGISTERS ||
        config->memory_limit < sizeof(NemoRegis) ||
        config->memory_limit > REGIS_MEMORY_LIMIT)
        return NULL;
    if (config->resize_memory &&
        !config->resize_memory(config->user,0,sizeof(NemoRegis))) return NULL;
    NemoRegis *owner = calloc(1,sizeof(*owner));
    if (!owner) {
        if (config->resize_memory) config->resize_memory(config->user,sizeof(NemoRegis),0);
        return NULL;
    }
    owner->config = *config;
    owner->bytes = sizeof(*owner);
    owner->context.current_widget = owner;
    return owner;
}

void nemo_regis_reset(NemoRegis *owner)
{
    if (!owner || owner->active) return;
    for (unsigned i=0;i<16;i++) {
        regis_free_graphic(owner->pages[i]);
        owner->pages[i] = NULL;
    }
    for (unsigned i=0;i<MAX_REGIS_ALPHABETS;i++)
        regis_deallocate(owner->context.alphabets[i].bytes);
    memset(&owner->context,0,sizeof(owner->context));
    memset(&owner->state,0,sizeof(owner->state));
    memset(owner->shared,0,sizeof(owner->shared));
    owner->context.current_widget = owner;
    owner->reply_length = 0;
    owner->screen = 0;
}

void nemo_regis_free(NemoRegis *owner)
{
    if (!owner || owner->active) return;
    nemo_regis_reset(owner);
    assert(owner->bytes == sizeof(*owner));
    if (owner->config.resize_memory)
        owner->config.resize_memory(owner->config.user,owner->bytes,0);
    free(owner);
}

void nemo_regis_screen(NemoRegis *owner, unsigned alternate)
{
    if (owner && !owner->active) owner->screen = alternate != 0;
}

void nemo_regis_private_colours(NemoRegis *owner, bool enabled)
{
    if (owner && !owner->active) owner->config.private_colours = enabled;
}

NemoRegisResult nemo_regis_parse(NemoRegis *owner, unsigned mode,
                                const void *data, size_t length)
{
    if (!owner || owner->active || (!data && length) ||
        (length && memchr(data,0,length))) return NEMO_REGIS_INVALID;
    if (length > REGIS_INPUT_LIMIT) return NEMO_REGIS_LIMIT;
    owner->result = NEMO_REGIS_OK;
    owner->active = true;
    owner->work = owner->config.work_limit ? owner->config.work_limit : REGIS_WORK_LIMIT;
    owner->depth = 0;
    owner->reply_length = 0;
    if (!setjmp(owner->escape)) {
        owner->input = regis_allocate(owner,length+1);
        if (length) memcpy(owner->input,data,length);
        owner->state.temp = regis_allocate(owner,length+1);
        owner->state.templen = (unsigned)length+1;
        init_fragment(&owner->state.input,owner,owner->input);
        if (!owner->context.width || !owner->context.height || mode==1 || mode==3) {
            init_regis_parse_state(&owner->state);
            init_regis_graphics_context(owner->config.terminal_id,
                (int)owner->config.width,(int)owner->config.height,
                owner->config.colours,"",&owner->context);
        }
        map_regis_graphics_pages(owner,&owner->context);
        while (!fragment_consumed(&owner->state.input)) {
            parse_regis_toplevel(&owner->state,&owner->context);
            if (owner->context.force_refresh) {
                owner->context.force_refresh = false;
                refresh_modified_displayed_graphics(owner);
            }
        }
        refresh_modified_displayed_graphics(owner);
    }
    regis_deallocate(owner->state.temp);
    regis_deallocate(owner->input);
    owner->state.temp = owner->input = NULL;
    memset(&owner->state.input,0,sizeof(owner->state.input));
    owner->active = false;
    /* A failed allocation may have created an incomplete page. Release all
     * decoder resources before accepting another request. */
    if (owner->result != NEMO_REGIS_OK) {
        unsigned screen = owner->screen;
        nemo_regis_reset(owner);
        owner->screen = screen;
    }
    return owner->result;
}

size_t nemo_regis_bytes(const NemoRegis *owner) { return owner ? owner->bytes : 0; }
unsigned nemo_regis_display_page(const NemoRegis *owner)
{ return owner ? owner->context.display_page : 0; }

bool nemo_regis_page_size(const NemoRegis *owner, unsigned page,
                          unsigned *width, unsigned *height)
{
    if (!owner || page >= 8 || !width || !height) return false;
    const Graphic *g = owner->pages[owner->screen*8+page];
    if (!g) return false;
    *width = (unsigned)g->actual_width;
    *height = (unsigned)g->actual_height;
    return true;
}

size_t nemo_regis_read_row(const NemoRegis *owner, unsigned page, unsigned y,
                          unsigned x, uint32_t *out, size_t count)
{
    if (!owner || page>=8 || !out) return 0;
    const Graphic *g = owner->pages[owner->screen*8+page];
    if (!g || y >= (unsigned)g->actual_height || x >= (unsigned)g->actual_width) return 0;
    if (count > (unsigned)g->actual_width-x) count = (unsigned)g->actual_width-x;
    for (size_t i=0;i<count;i++) {
        unsigned index = read_pixel(g,(int)(x+i),(int)y);
        if (index>=MAX_COLOR_REGISTERS) { out[i]=0; continue; }
        ColorRegister c = g->color_registers[index];
        out[i] = UINT32_C(0xff000000) | ((uint32_t)(c.r*255/100)<<16) |
                 ((uint32_t)(c.g*255/100)<<8) | (uint32_t)(c.b*255/100);
    }
    return count;
}
