/* SPDX-License-Identifier: MIT */
#include "putty.h"
#include "terminal.h"
#include "nemo_kitty_paint.h"
#include <float.h>
#include <math.h>

/* One reusable row; no image-sized bitmap, texture or window backbuffer. */
#define KITTY_ROW_PIXELS 1024
struct NemoKittyPainter {
    HDC dc;
    HBITMAP bitmap;
    HGDIOBJ previous;
    uint32_t *pixels;
};

/* Affine sampling can put an exact raster edge a few ulps inside the image.
 * Keep half-open border coverage stable across cell sizes without rounding
 * interior samples. The tolerance is measured in source pixels. */
static double raster_border(double value, uint32_t extent)
{
    double tolerance=16*DBL_EPSILON*extent;
    if (fabs(value)<tolerance) return 0;
    if (fabs(value-extent)<tolerance) return extent;
    return value;
}

void nemo_kitty_paint_free(NemoKittyPainter **slot)
{
    if (!slot || !*slot) return;
    NemoKittyPainter *s=*slot;
    if (s->dc && s->previous && s->previous!=HGDI_ERROR)
        SelectObject(s->dc,s->previous);
    if (s->bitmap) DeleteObject(s->bitmap);
    if (s->dc) DeleteDC(s->dc);
    sfree(s); *slot=NULL;
}

static bool prepare(NemoKittyPainter **slot, HDC target)
{
    if (*slot) return true;
    NemoKittyPainter *s=snew(NemoKittyPainter);
    memset(s,0,sizeof(*s));
    *slot=s;
    BITMAPINFO bi={0};
    bi.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);
    bi.bmiHeader.biWidth=KITTY_ROW_PIXELS;
    bi.bmiHeader.biHeight=-1;
    bi.bmiHeader.biPlanes=1;
    bi.bmiHeader.biBitCount=32;
    bi.bmiHeader.biCompression=BI_RGB;
    s->dc=CreateCompatibleDC(target);
    s->bitmap=CreateDIBSection(target,&bi,DIB_RGB_COLORS,(void **)&s->pixels,NULL,0);
    if (s->dc && s->bitmap) s->previous=SelectObject(s->dc,s->bitmap);
    if (!s->dc || !s->bitmap || !s->previous || s->previous==HGDI_ERROR) {
        nemo_kitty_paint_free(slot); return false;
    }
    return true;
}

static bool visible(Terminal *term, const NemoKittyPlacement *p, RECT clip,
                     int ox, int oy, bool foreground, bool default_bg, NemoKittyView *v)
{
    if (!nemo_kitty_placement_view(p,term->cell_width,term->cell_height,v) ||
        (v->z>=0)!=foreground || (!foreground && !default_bg && v->z<INT32_MIN/2))
        return false;
    double dy=oy-(double)term->disptop*term->cell_height;
    v->left+=ox; v->right+=ox; v->top+=dy; v->bottom+=dy;
    return v->left<clip.right && v->right>clip.left &&
        v->top<clip.bottom && v->bottom>clip.top;
}

bool nemo_kitty_intersects(Terminal *term, RECT clip, int ox, int oy,
                           bool foreground, bool default_bg)
{
    if (!term || clip.right<=clip.left || clip.bottom<=clip.top) return false;
    for (const NemoKittyPlacement *p=nemo_kitty_placements_first(term_kitty_placements(term,term->alt_which));
         p;p=nemo_kitty_placement_next(p)) {
        NemoKittyView v;
        if (visible(term,p,clip,ox,oy,foreground,default_bg,&v)) return true;
    }
    return false;
}

bool nemo_kitty_paint(NemoKittyPainter **slot, Terminal *term, HDC dc, RECT clip,
                      int ox, int oy, bool foreground, bool default_bg, NemoGPU *gpu)
{
    if (!slot || !term || !dc) return false;
    RECT text={ox,oy,ox+term->cols*term->cell_width,oy+term->rows*term->cell_height};
    if (!IntersectRect(&clip,&clip,&text)) return true;
    if (!gpu) {
        RECT current;
        int kind=GetClipBox(dc,&current);
        if (kind==ERROR) return false;
        if (kind==NULLREGION || !IntersectRect(&clip,&clip,&current)) return true;
    }
    if (!nemo_kitty_intersects(term,clip,ox,oy,foreground,default_bg)) return true;
    if (!prepare(slot,dc)) return false;
    NemoKittyPainter *s=*slot;
    for (const NemoKittyPlacement *p=nemo_kitty_placements_first(term_kitty_placements(term,term->alt_which));
         p;p=nemo_kitty_placement_next(p)) {
        NemoKittyView v;
        if (!visible(term,p,clip,ox,oy,foreground,default_bg,&v)) continue;
        const NemoRaster *r=nemo_kitty_image_raster(v.image);
        if (!r || !r->pixels || !r->width || !r->height) continue;
        /* Clip in floating point before integer conversion: a legal placement
         * can be much larger than a Windows client rectangle. Pixel centers
         * give a stable nearest-neighbour mapping after fractional cropping. */
        int left=(int)ceil(max((double)clip.left,v.left)-0.5);
        int right=(int)ceil(min((double)clip.right,v.right)-0.5);
        int top=(int)ceil(max((double)clip.top,v.top)-0.5);
        int bottom=(int)ceil(min((double)clip.bottom,v.bottom)-0.5);
        double sx=(v.source_right-v.source_left)/(v.right-v.left);
        double sy=(v.source_bottom-v.source_top)/(v.bottom-v.top);
        for (int y=top;y<bottom;y++) {
            double fy=raster_border(v.source_top+(y+0.5-v.top)*sy,r->height);
            /* Partly filled placeholder cells can extend beyond the raster.
             * Their border is transparent; repeating the final source pixel
             * would paint over the letterbox area. */
            if (fy<0 || fy>=r->height) continue;
            unsigned iy=(unsigned)floor(fy);
            for (int x=left;x<right;) {
                int count=min(KITTY_ROW_PIXELS,right-x);
                bool any=false,opaque=true;
                GdiFlush();
                for (int i=0;i<count;i++) {
                    double fx=raster_border(v.source_left+(x+i+0.5-v.left)*sx,r->width);
                    uint32_t pixel=fx>=0 && fx<r->width ?
                        r->pixels[(size_t)iy*r->width+(unsigned)floor(fx)] : 0;
                    unsigned a=pixel>>24;
                    any|=a!=0; opaque&=a==255;
                    uint32_t out=pixel&0xff000000u;
                    for (unsigned shift=0;shift<24;shift+=8)
                        out|=((((pixel>>shift)&255)*a+127)/255)<<shift;
                    s->pixels[i]=out;
                }
                if (any) {
                    RECT box={x,y,x+count,y+1};
                    if (gpu && opaque) nemo_gpu_row(gpu,x,y,count,s->pixels);
                    else {
                        if (gpu && !nemo_gpu_begin_run(gpu,box,true)) return false;
                        HDC target=gpu ? nemo_gpu_dc(gpu) : dc;
                        BLENDFUNCTION blend={AC_SRC_OVER,0,255,AC_SRC_ALPHA};
                        bool ok=GdiAlphaBlend(target,x,y,count,1,s->dc,0,0,count,1,blend)!=0;
                        if (gpu) nemo_gpu_end_run(gpu,box,make_ptrlen(NULL,0));
                        if (!ok) return false;
                    }
                }
                x+=count;
            }
        }
    }
    GdiFlush();
    return true;
}
