/* SPDX-License-Identifier: MIT
 * Hosted-only GDI glyph checks. The independent TextOutW path draws into an
 * offscreen DIB and compares pixels; no window or desktop input is used.
 */
#define _CRT_SECURE_NO_WARNINGS
#include "nemo_regis_font.h"
#include "nemo_regis.h"
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int failures;
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"%s:%d: %s\n",__FILE__,__LINE__,#x); failures++; } } while (0)

static unsigned compare_textout(const NemoRegisFontInfo *info, unsigned ch,
                                 const unsigned char *pixels)
{
    HDC dc = CreateCompatibleDC(NULL);
    if (!dc) return UINT_MAX;
    BITMAPINFO bitmap = {0};
    bitmap.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    bitmap.bmiHeader.biWidth = (LONG)info->width;
    bitmap.bmiHeader.biHeight = -(LONG)info->height;
    bitmap.bmiHeader.biPlanes = 1; bitmap.bmiHeader.biBitCount = 32;
    bitmap.bmiHeader.biCompression = BI_RGB;
    uint32_t *bits = NULL;
    HBITMAP dib = CreateDIBSection(dc, &bitmap, DIB_RGB_COLORS, (void **)&bits, NULL, 0);
    HFONT font = CreateFontW(-info->pixel_height, 0, 0, 0, info->weight, FALSE,
        FALSE, FALSE, DEFAULT_CHARSET, OUT_TT_ONLY_PRECIS, CLIP_DEFAULT_PRECIS,
        NONANTIALIASED_QUALITY, FIXED_PITCH | FF_MODERN, info->family);
    unsigned mismatches = UINT_MAX;
    if (dib && font && bits) {
        HGDIOBJ previous_bitmap = SelectObject(dc, dib), previous_font = SelectObject(dc, font);
        memset(bits, 0, (size_t)info->width*info->height*sizeof(*bits));
        SetBkMode(dc, TRANSPARENT); SetTextColor(dc, RGB(255,255,255));
        SetTextAlign(dc, TA_LEFT | TA_BASELINE | TA_NOUPDATECP);
        WCHAR text = (WCHAR)ch;
        if (TextOutW(dc, -info->left, -info->top, &text, 1) && GdiFlush()) {
            mismatches = 0;
            for (size_t i=0; i<(size_t)info->width*info->height; i++)
                if ((bits[i]&0xffffffU ? 1 : 0) != pixels[i]) mismatches++;
            if (mismatches) {
                char name[128];
                snprintf(name,sizeof(name),"build/regis-component/difference-%u-%u.pgm",ch,info->pixel_height);
                FILE *file=fopen(name,"wb");
                if (file) {
                    fprintf(file,"P5\n%u %u\n255\n",info->width*2,info->height);
                    for (unsigned y=0;y<info->height;y++) {
                        for (unsigned x=0;x<info->width;x++) fputc(pixels[y*info->width+x] ? 255 : 0,file);
                        for (unsigned x=0;x<info->width;x++) fputc(bits[y*info->width+x]&0xffffffU ? 255 : 0,file);
                    }
                    fclose(file);
                }
                printf("font metrics: ch=%u height=%d left=%d top=%d box=%ux%u\n",ch,
                       info->pixel_height,info->left,info->top,info->width,info->height);
                WORD glyph=0xffff;
                if (GetGlyphIndicesW(dc,&text,1,&glyph,GGI_MARK_NONEXISTING_GLYPHS)!=GDI_ERROR && glyph!=0xffff) {
                    memset(bits,0,(size_t)info->width*info->height*sizeof(*bits));
                    if (ExtTextOutW(dc,-info->left,-info->top,ETO_GLYPH_INDEX,NULL,(const WCHAR *)&glyph,1,NULL) && GdiFlush()) {
                        unsigned raw_differences=0;
                        for (size_t i=0;i<(size_t)info->width*info->height;i++)
                            raw_differences+=(bits[i]&0xffffffU ? 1 : 0)!=pixels[i];
                        printf("explicit glyph diagnostic: ch=%u index=%u differences=%u\n",ch,(unsigned)glyph,raw_differences);
                    }
                }
            }
        }
        SelectObject(dc, previous_font); SelectObject(dc, previous_bitmap);
    }
    if (font) DeleteObject(font);
    if (dib) DeleteObject(dib);
    DeleteDC(dc);
    return mismatches;
}

static void save_glyph(unsigned ch, const unsigned char *pixels, unsigned w, unsigned h)
{
    char name[80]; snprintf(name,sizeof(name),"build/regis-component/glyph-%u.pgm",ch);
    FILE *file=fopen(name,"wb"); CHECK(file!=NULL);
    if (!file) return;
    fprintf(file,"P5\n%u %u\n255\n",w,h);
    for (size_t i=0;i<(size_t)w*h;i++) fputc(pixels[i] ? 255 : 0,file);
    fclose(file);
}

static bool native_glyph(void *ctx, const char *font, unsigned ch, unsigned maxw,
                          unsigned maxh, unsigned char *pixels, size_t capacity,
                          unsigned *width, unsigned *height)
{
    return nemo_regis_font_glyph(ctx,font,ch,maxw,maxh,pixels,capacity,width,height);
}

static void decoder_frame(NemoRegisFontWin *provider)
{
    NemoRegisConfig config={0};
    config.width=config.max_width=160; config.height=config.max_height=120;
    config.colours=16; config.terminal_id=340; config.private_colours=true;
    config.memory_limit=4*1024*1024; config.user=provider; config.glyph=native_glyph;
    NemoRegis *decoder=nemo_regis_new(&config); CHECK(decoder!=NULL);
    if (!decoder) return;
    const char input[]="S(E)W(I3)P[20,60]T\"ABC gjW\"";
    CHECK(nemo_regis_parse(decoder,1,input,sizeof(input)-1)==NEMO_REGIS_OK);
    FILE *file=fopen("build/regis-component/native-text.ppm","wb"); CHECK(file!=NULL);
    if (file) {
        fputs("P6\n160 120\n255\n",file);
        unsigned foreground=0;
        for (unsigned y=0;y<120;y++) {
            uint32_t row[160]={0};
            CHECK(nemo_regis_read_row(decoder,0,y,0,row,160)==160);
            if (y>=60 && y<80)
                for (unsigned x=47;x<56;x++) CHECK(row[x]==0xff000000);
            for (unsigned x=0;x<160;x++) {
                unsigned char rgb[3]={(unsigned char)(row[x]>>16),(unsigned char)(row[x]>>8),(unsigned char)row[x]};
                if (row[x]==0xff33cc33) foreground++;
                fwrite(rgb,1,3,file);
            }
        }
        fclose(file);
        CHECK(foreground>20 && foreground<1000);
        printf("native ReGIS frame: foreground=%u\n",foreground);
    }
    nemo_regis_free(decoder);
}

int main(void)
{
    const char *actions=getenv("GITHUB_ACTIONS"),*hosted=getenv("RUNNER_ENVIRONMENT");
    const wchar_t *family=_wgetenv(L"NEMOTERM_TEST_FONT");
    if (!actions || strcmp(actions,"true") || !hosted || strcmp(hosted,"github-hosted") || !family)
        return 2;
    unsigned char pixels[8192+16]; unsigned w=0,h=0;
    /* Warm system font initialization before measuring owned GDI handles. */
    NemoRegisFontWin *warm=nemo_regis_font_new(family,300); CHECK(warm!=NULL);
    CHECK(nemo_regis_font_glyph(warm,"",'A',8,20,pixels,8192,&w,&h));
    nemo_regis_font_free(warm);
    DWORD before=GetGuiResources(GetCurrentProcess(),GR_GDIOBJECTS);
    NemoRegisFontWin *first=nemo_regis_font_new(family,300);
    NemoRegisFontWin *second=nemo_regis_font_new(L"Consolas",400);
    CHECK(first && second);
    if (!first || !second) return 3;
    const unsigned sizes[][2]={{8,20},{16,30},{32,60}};
    unsigned comparisons=0, mismatches=0;
    for (unsigned s=0;s<3;s++) {
        for (unsigned ch=32;ch<256;ch++) {
            if (ch>=127 && ch<160) continue;
            memset(pixels,0xa5,sizeof(pixels));
            bool ok=nemo_regis_font_glyph(first,"",ch,sizes[s][0],sizes[s][1],pixels,8192,&w,&h);
            CHECK(ok);
            if (!ok) { fprintf(stderr,"glyph unavailable: ch=%u max=%ux%u\n",ch,sizes[s][0],sizes[s][1]); continue; }
            CHECK(w && h && w<=sizes[s][0] && h<=sizes[s][1] && w*h<=8192);
            for (size_t i=(size_t)w*h;i<sizeof(pixels);i++) CHECK(pixels[i]==0xa5);
            NemoRegisFontInfo info;
            CHECK(nemo_regis_font_info(first,&info));
            CHECK(!wcscmp(info.family,family));
            unsigned different=compare_textout(&info,ch,pixels);
            if (different) fprintf(stderr,"glyph %u size %ux%u: differences=%u\n",ch,sizes[s][0],sizes[s][1],different);
            CHECK(different==0); mismatches+=different!=0; comparisons++;
            if (!s && (ch=='A' || ch=='B' || ch=='C' || ch=='g' || ch=='j')) save_glyph(ch,pixels,w,h);
        }
    }
    for (unsigned i=0;i<128;i++) {
        CHECK(nemo_regis_font_glyph(first,"",'A',8,20,pixels,8192,&w,&h));
        CHECK(nemo_regis_font_glyph(second,"",'g',16,30,pixels,8192,&w,&h));
    }
    unsigned char first_mask[8192];
    CHECK(nemo_regis_font_glyph(first,"",'A',8,20,first_mask,sizeof(first_mask),&w,&h));
    unsigned first_width=w,first_height=h;
    CHECK(nemo_regis_font_glyph(first,"Consolas",'A',8,20,pixels,8192,&w,&h));
    NemoRegisFontInfo named;
    CHECK(nemo_regis_font_info(first,&named) && !wcscmp(named.family,L"Consolas"));
    CHECK(nemo_regis_font_glyph(first,"",'A',8,20,pixels,8192,&w,&h));
    CHECK(w==first_width && h==first_height && !memcmp(first_mask,pixels,(size_t)w*h));
    CHECK(GetGuiResources(GetCurrentProcess(),GR_GDIOBJECTS)==before+6);
    CHECK(!nemo_regis_font_glyph(first,"\xff",'A',8,20,pixels,8192,&w,&h));
    CHECK(!w && !h);
    CHECK(!nemo_regis_font_glyph(first,"Nemoterm Missing Face 719",'A',8,20,pixels,8192,&w,&h));
    CHECK(!nemo_regis_font_glyph(first,"",256,8,20,pixels,8192,&w,&h));
    CHECK(!nemo_regis_font_glyph(first,"",'A',0,20,pixels,8192,&w,&h));
    CHECK(!nemo_regis_font_glyph(first,"",'A',8,20,pixels,0,&w,&h));
    /* Failed lookup and size changes must not poison the owner's next call. */
    CHECK(nemo_regis_font_glyph(first,"",'A',8,20,pixels,8192,&w,&h));
    decoder_frame(first);
    size_t bytes=nemo_regis_font_bytes(first);
    nemo_regis_font_free(first); nemo_regis_font_free(second);
    DWORD after=GetGuiResources(GetCurrentProcess(),GR_GDIOBJECTS);
    CHECK(after==before);
    printf("GDI font checks: comparisons=%u mismatches=%u owner_bytes=%zu handles=%lu->%lu failures=%d\n",
           comparisons,mismatches,bytes,(unsigned long)before,(unsigned long)after,failures);
    return failures ? 1 : 0;
}
