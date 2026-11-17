/* SPDX-License-Identifier: MIT
 * Real terminal DCS framing, live indexed image views and ownership.
 */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main
#include "../../../tests/regis_font_fixture.h"
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

static RegisFontInputs font_inputs;
static TermWinVtable regis_vtable;
static unsigned char grid_font[257][13][6];
static bool grid_font_loaded;

static bool mock_regis_glyph(TermWin *win,const char *font,unsigned ch,
    unsigned maxw,unsigned maxh,unsigned char *pixels,size_t capacity,
    unsigned *width,unsigned *height)
{
    (void)win;
    return font_input_glyph(&font_inputs,font,ch,maxw,maxh,pixels,capacity,width,height);
}

static Mock *regis_mock(void)
{
    Mock *mk=mock_new();
    mk->ucsdata->line_codepage=CP_UTF8;
    mk->tw.vt=&regis_vtable;
    mk->term=term_init(mk->conf,mk->ucsdata,&mk->tw);
    mk->ldisc=ldisc_create(mk->conf,mk->term,&mk->backend,&mk->seat);
    reset(mk);
    term_size(mk->term,12,40,0);
    term_set_cell_size(mk->term,6,13);
    IEQUAL(term_regis_set_size(mk->term,160,120,160,120),true);
    /* Match the reference's VT340 resources: 16 registers; the upstream
     * shared bank is calloc-initialized, while private banks use VT340 RGB.
     * Product-default 256-register Sixel behaviour is tested separately. */
    mk->term->sixel_register_count=16;
    for (unsigned i=0;i<NEMO_SIXEL_PALETTE_SIZE;i++)
        mk->term->sixel_palette[i]=UINT32_C(0xff000000);
    mk->term->sixel_palette_valid=true;
    return mk;
}

static void check_regis_accounting(Mock *mk)
{
    Terminal *t=mk->term;
    size_t bytes=t->image_bytes+term_regis_memory(t)+term_kitty_memory(t)+
        nemo_iterm_memory(t->iterm_pending)+nemo_sixel_stats(t->sixel_pending).allocated_bytes;
    IEQUAL(bytes<=NEMO_SIXEL_DEFAULT_BUDGET,true);
    if (term_regis_decoder(t))
        IEQUAL(nemo_regis_bytes(term_regis_decoder(t))<=term_regis_memory(t),true);
}

static void feed_regis(Mock *mk,const char *wire)
{
    term_data_fragmented(mk->term,wire);
    check_regis_accounting(mk);
}

static void expect_pixel(Mock *mk,unsigned y,unsigned x,uint32_t expected)
{
    const NemoRegis *decoder=term_regis_decoder(mk->term);
    uint32_t pixel=0;
    IEQUAL(nemo_regis_read_row(decoder,nemo_regis_display_page(decoder),y,x,&pixel,1),1);
    IEQUAL(pixel,expected);
}

static void check_shared_graphics(Mock *mk)
{
    Terminal *t=mk->term;
    test_context(mk,"ReGIS and Sixel retain one live colour bank");
    feed_regis(mk,"\033c\033[?1070l\033P1pS(E)S(M3(R20G80B20))W(I3)P[20,20]V[120,20]\033\\");
    expect_pixel(mk,20,20,0xff33cc33);
    feed_regis(mk,"\033P0;1q#3;2;100;0;0#3~\033\\");
    expect_pixel(mk,20,20,0xffff0000);
    NemoSixel *shared=NULL;
    for (NemoTermImage *image=t->images;image;image=image->next)
        if (image->source->bitmap) shared=image->source->bitmap;
    IEQUAL(shared!=NULL,true);
    uint32_t pixel=0;
    IEQUAL(nemo_sixel_read_row(shared,0,0,&pixel,1),1);
    IEQUAL(pixel,0xffff0000);
    feed_regis(mk,"\033P0pS(M3(R0G0B100))\033\\");
    expect_pixel(mk,20,20,0xff0000ff);
    IEQUAL(nemo_sixel_read_row(shared,0,0,&pixel,1),1);
    IEQUAL(pixel,0xff0000ff);

    test_context(mk,"mode changes keep existing graphic bindings and cancelled Sixel colours");
    feed_regis(mk,"\033[?1070h\033P0pS(M3(R100G0B0))\033\\");
    IEQUAL(nemo_sixel_read_row(shared,0,0,&pixel,1),1);
    IEQUAL(pixel,0xffff0000); /* matching ReGIS page remains shared */
    feed_regis(mk,"\033P0;1q#3;2;0;0;100#3\030");
    expect_pixel(mk,20,20,0xffff0000); /* cancelled private definition stays private */
    feed_regis(mk,"\033[?1070l\033P0;1q#3;2;0;0;100#3\030");
    expect_pixel(mk,20,20,0xff0000ff); /* completed shared definition survives CAN */
    IEQUAL(nemo_sixel_read_row(shared,0,0,&pixel,1),1);
    IEQUAL(pixel,0xff0000ff);

    test_context(mk,"shared registers belong to one terminal and RIS releases image owners");
    Mock *other=regis_mock();
    feed_regis(other,"\033[?1070l\033P1pS(M3(R20G80B20))W(I3)P[20,20]V[120,20]\033\\");
    expect_pixel(other,20,20,0xff33cc33);
    expect_pixel(mk,20,20,0xff0000ff);
    IEQUAL(other->any_test_failed,false);
    mock_free(other);
    feed_regis(mk,"\033c");
    IEQUAL(t->image_bytes,0);
    IEQUAL(term_regis_memory(t),0);
    IEQUAL(t->sixel_palette_valid,false);
}

static int framing_tests(void)
{
    Mock *mk=regis_mock();
    Terminal *t=mk->term;
    test_context(mk,"lazy owner, complete DCS and original geometry");
    IEQUAL(term_regis_memory(t),0);
    feed_regis(mk,"\033P1pS(E)W(I3)P[20,20]V[120,20]R(P)\033\\");
    SEQUAL(mk->to_backend->s,"[120,20]\r");
    IEQUAL(term_regis_last_result(t),NEMO_REGIS_OK);
    expect_pixel(mk,20,20,0xff33cc33);
    size_t retained=term_regis_memory(t);
    IEQUAL(retained<100000,true); /* no 8192-square tile pointer grid per page */

    test_context(mk,"cancelled transactions preserve prior pages and position");
    strbuf_clear(mk->to_backend);
    feed_regis(mk,"\033P0pS(E)P[99,99]R(P)");
    IEQUAL(term_regis_pending(t),true);
    IEQUAL(mk->to_backend->len,0);
    IEQUAL(term_regis_set_size(t,320,240,320,240),false);
    feed_regis(mk,"\030");
    IEQUAL(term_regis_pending(t),false);
    IEQUAL(term_regis_memory(t),retained);
    expect_pixel(mk,20,20,0xff33cc33);
    feed_regis(mk,"\033P0pR(P)\234");
    SEQUAL(mk->to_backend->s,"[120,20]\r");
    strbuf_clear(mk->to_backend);
    feed_regis(mk,"\033P0pP[5,6]R(P)\302\234");
    SEQUAL(mk->to_backend->s,"[5,6]\r");
    strbuf_clear(mk->to_backend);
    feed_regis(mk,"\033P0pP[88,88]\033[H\033P0pR(P)\033\\");
    SEQUAL(mk->to_backend->s,"[5,6]\r");
    IEQUAL(t->termstate,TOPLEVEL);

    test_context(mk,"alternate banks and soft reset preserve graphics state");
    feed_regis(mk,"\033[?1049h\033P0pS(E)W(I2)P[20,80]V[120,80]\033\\");
    expect_pixel(mk,80,20,0xffcc2121);
    feed_regis(mk,"\033[?1049l");
    expect_pixel(mk,20,20,0xff33cc33);
    strbuf_clear(mk->to_backend);
    feed_regis(mk,"\033[!p\033P0pR(P)\033\\");
    SEQUAL(mk->to_backend->s,"[120,80]\r");

    test_context(mk,"resize cancels partial input without losing retained graphics");
    retained=term_regis_memory(t);
    feed_regis(mk,"\033P0pS(E)");
    term_size(t,13,40,0);
    IEQUAL(term_regis_pending(t),false);
    IEQUAL(term_regis_memory(t),retained);
    feed_regis(mk,"P[99,99]\033\\");
    expect_pixel(mk,20,20,0xff33cc33);

    test_context(mk,"bounded raw DCS, recovery and shared raster accounting");
    feed_regis(mk,"\033P0p");
    char chunk[1024]; memset(chunk,' ',sizeof(chunk));
    for (unsigned i=0;i<257;i++) {
        term_data(t,chunk,sizeof(chunk));
        check_regis_accounting(mk);
    }
    IEQUAL(term_regis_pending(t),false);
    IEQUAL(term_regis_memory(t),retained);
    feed_regis(mk,"\033\\\033P0pR(P)\033\\");
    IEQUAL(term_regis_last_result(t),NEMO_REGIS_OK);
    feed_regis(mk,"\033[?80h\033P0;1q\"1;1;32;32#1;2;100;0;0!32~\033\\");
    IEQUAL(t->images!=NULL,true);
    feed_regis(mk,"\033c");
    IEQUAL(term_regis_memory(t),0);
    IEQUAL(t->image_bytes,0);
    IEQUAL(term_regis_pending(t),false);
    feed_regis(mk,"\033P1pP[7,9]R(P)\033\\");
    IEQUAL(term_regis_last_result(t),NEMO_REGIS_OK);

    test_context(mk,"address size growth preserves pixels and bounded sparse directories");
    IEQUAL(term_regis_set_size(t,160,120,8192,8192),true);
    feed_regis(mk,"\033P1pS(E)W(I3)P[20,20]V[120,20]\033\\");
    IEQUAL(term_regis_memory(t)<100000,true);
    feed_regis(mk,"\033P0pS(A[0,0][319,239])W(I2)P[20,200]V[120,200]\033\\");
    IEQUAL(term_regis_last_result(t),NEMO_REGIS_OK);
    expect_pixel(mk,20,20,0xff33cc33);
    expect_pixel(mk,200,20,0xffcc2121);
    expect_pixel(mk,200,200,0); /* newly exposed area remains transparent */
    feed_regis(mk,"\033P0pS(A[0,0][299,99])S(E)S(A[0,0][319,239])\033\\");
    IEQUAL(term_regis_last_result(t),NEMO_REGIS_OK);
    expect_pixel(mk,20,20,0xff000000);
    expect_pixel(mk,200,20,0xffcc2121); /* clearing a smaller extent preserves hidden ink */
    expect_pixel(mk,200,200,0);
    feed_regis(mk,"\033c");
    IEQUAL(term_regis_memory(t),0);
    check_shared_graphics(mk);
    bool failed=mk->any_test_failed;
    mock_free(mk);
    puts(failed ? "ReGIS terminal framing FAILED" : "ReGIS terminal framing passed");
    return failed ? 1 : 0;
}

int main(int argc,char **argv)
{
    const char *actions=getenv("GITHUB_ACTIONS"),*hosted=getenv("RUNNER_ENVIRONMENT");
    if (!actions || strcmp(actions,"true") || !hosted || strcmp(hosted,"github-hosted")) return 2;
    regis_vtable=mock_termwin_vt;
    if (argc==2 && !strcmp(argv[1],"--self-test")) return framing_tests();
    bool bytewise=false,views=false;
    for (int i=1;i<argc;i++) {
        if (!strcmp(argv[i],"--font-inputs") && i+1<argc) {
            if (!font_inputs_load(&font_inputs,argv[++i])) return 3;
            regis_vtable.regis_glyph=mock_regis_glyph;
        } else if (!strcmp(argv[i],"--bytewise")) bytewise=true;
        else if (!strcmp(argv[i],"--views")) views=true;
        else if (!strcmp(argv[i],"--grid-font") && i+1<argc) {
            FILE *font=fopen(argv[++i],"rb"); char magic[8];
            if (!font || fread(magic,1,8,font)!=8 || memcmp(magic,"NEMOFIX2",8) ||
                fread(grid_font,1,sizeof(grid_font),font)!=sizeof(grid_font) || fgetc(font)!=EOF) return 8;
            fclose(font); grid_font_loaded=true;
        }
        else return 4;
    }
#ifdef _WIN32
    _setmode(_fileno(stdin),_O_BINARY); _setmode(_fileno(stdout),_O_BINARY);
#endif
    Mock *mk=regis_mock();
    char header[128];
    while (fgets(header,sizeof(header),stdin)) {
        size_t length;
        if (sscanf(header,"I %zu",&length)!=1 || length>300000) return 5;
        char *wire=malloc(length ? length : 1);
        if (!wire || fread(wire,1,length,stdin)!=length) return 6;
        strbuf_clear(mk->to_backend);
        if (bytewise) for (size_t i=0;i<length;i++) term_data(mk->term,wire+i,1);
        else term_data(mk->term,wire,length);
        free(wire);
        check_regis_accounting(mk);
        const NemoRegis *decoder=term_regis_decoder(mk->term);
        unsigned page=nemo_regis_display_page(decoder),width=0,height=0;
        nemo_regis_page_size(decoder,page,&width,&height);
        printf("%u %zu %u %u %u %zu\n",(unsigned)(decoder ? term_regis_last_result(mk->term) : NEMO_REGIS_OK),
               term_regis_memory(mk->term),page,width,height,mk->to_backend->len);
        fwrite(mk->to_backend->s,1,mk->to_backend->len,stdout);
        for (unsigned y=0;y<120;y++) {
            uint32_t row[160]={0};
            if (!views) nemo_regis_read_row(decoder,page,y,0,row,160);
            else {
                termline *line=index234(mk->term->screen,y/13);
                for (unsigned x=0;x<160;x++) {
                    unsigned code=(unsigned)line->chars[x/6].chr;
                    if ((code&CSET_MASK)==CSET_ASCII) code&=255;
                    if (code==' ') continue;
                    if (code==0x2426) code=256;
                    if (!grid_font_loaded || code>256) {
                        fprintf(stderr,"Unsupported fixed-grid input U+%04x\n",code); return 9;
                    }
                    if (grid_font[code][y%13][x%6]) row[x]=0xffffffff;
                }
            }
            if (views) for (NemoTermImage *im=mk->term->images;im;im=im->next) {
                if (im->screen!=mk->term->alt_which || !term_image_visible(im)) continue;
                for (unsigned sy=0;sy<(unsigned)im->pixel_height;sy++) {
                    if (term_image_pixel_y(im,sy,mk->term->cell_height)!=(int64_t)y) continue;
                    uint32_t pixels[NEMO_SIXEL_MAX_DIMENSION];
                    size_t n=term_image_read_row(im,sy,0,pixels,im->pixel_width);
                    int64_t left=(int64_t)im->x*mk->term->cell_width+im->pixel_x;
                    for (size_t x=0;x<n;x++)
                        if (left+(int64_t)x>=0 && left+(int64_t)x<160 && (pixels[x]>>24))
                            row[left+x]=pixels[x];
                }
            }
            for (unsigned x=0;x<160;x++) {
                unsigned char rgb[3]={(unsigned char)(row[x]>>16),(unsigned char)(row[x]>>8),(unsigned char)row[x]};
                fwrite(rgb,1,3,stdout);
            }
        }
        fflush(stdout);
    }
    bool failed=mk->any_test_failed || font_inputs.misses;
    mock_free(mk);
    fprintf(stderr,"terminal font-inputs: calls=%u misses=%u\n",font_inputs.calls,font_inputs.misses);
    font_inputs_free(&font_inputs);
    return failed ? 7 : 0;
}
