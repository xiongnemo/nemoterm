/* SPDX-License-Identifier: MIT
 * Native Direct2D composition of the existing GDI text rasterizer and Sixel.
 * One bounded CPU strip, a bounded GPU run cache, and a retained GPU frame.
 * Hardware creation is explicit: unavailable devices fall back to frontend
 * GDI, not to an unreported Direct2D software rasterizer. */
#include "putty.h"
#include "nemo_d2d.h"
#include "nemo_d2d_api.h"

#define CACHE_COUNT 256
#define CACHE_BYTES (4U*1024U*1024U)
#define FRAME_BYTES (128U*1024U*1024U)
static const GUID factory_iid =
    {0x06152247,0x6f50,0x465a,{0x92,0x45,0x11,0x8b,0xfd,0x3b,0x60,0x07}};
static const GUID interop_iid =
    {0xe0db51c3,0x6f77,0x4bae,{0xb3,0xd5,0xe4,0x75,0x09,0xb3,0x58,0x38}};
typedef HRESULT (WINAPI *CreateFactoryFn)(D2D1_FACTORY_TYPE, REFIID,
    const D2D1_FACTORY_OPTIONS *, void **);
typedef struct D2DRun {
    ID2D1Bitmap *bitmap;
    unsigned bytes;
    uint64_t hash, used;
    strbuf *key;
    int width, height;
} D2DRun;
struct NemoD2D {
    HWND parent, surface;
    HMODULE module;
    ID2D1Factory *factory;
    ID2D1HwndRenderTarget *target;
    ID2D1BitmapRenderTarget *frame;
    ID2D1Bitmap *image, *upload;
    ID2D1SolidColorBrush *brush;
    ID2D1GdiInteropRenderTarget *interop;
    HDC scratch;
    HBITMAP bitmap;
    HGDIOBJ oldbitmap;
    uint32_t *pixels;
    int width, height, strip_width, strip_height, upload_width, upload_height;
    unsigned limit, cache_bytes;
    uint64_t tick;
    bool drawing, failed;
    D2DRun cache[CACHE_COUNT];
};
#define RT(g) ((ID2D1RenderTarget *)(g)->frame)
static bool check(NemoD2D *g, HRESULT hr)
{
    if (FAILED(hr)) g->failed=true;
    return !g->failed;
}
static D2D1_COLOR_F color(COLORREF c)
{
    D2D1_COLOR_F out={GetRValue(c)/255.f,GetGValue(c)/255.f,GetBValue(c)/255.f,1};
    return out;
}
static LRESULT CALLBACK surface_proc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp)
{
    if (msg==WM_NCHITTEST) return HTTRANSPARENT;
    if (msg==WM_MOUSEACTIVATE) return MA_NOACTIVATE;
    if (msg==WM_ERASEBKGND) return 1;
    if (msg==WM_PAINT) {
        ValidateRect(hwnd,NULL);InvalidateRect(GetParent(hwnd),NULL,false);return 0;
    }
    return DefWindowProcW(hwnd,msg,wp,lp);
}
static void evict(NemoD2D *g, D2DRun *r)
{
    if (r->bitmap) nemo_d2d_release(r->bitmap);
    if (r->key) strbuf_free(r->key);
    g->cache_bytes-=r->bytes;memset(r,0,sizeof(*r));
}
void nemo_d2d_clear_cache(NemoD2D *g)
{
    if (g) for (unsigned i=0;i<CACHE_COUNT;i++) evict(g,&g->cache[i]);
}
static bool end_frame(NemoD2D *g)
{
    if (g->drawing) {
        g->drawing=false;
        check(g,nemo_d2d_end(RT(g),NULL,NULL));
    }
    return !g->failed;
}
static void free_frame(NemoD2D *g)
{
    end_frame(g);nemo_d2d_clear_cache(g);
    if (g->interop) nemo_d2d_release(g->interop);
    if (g->brush) nemo_d2d_release(g->brush);
    if (g->upload) nemo_d2d_release(g->upload);
    if (g->image) nemo_d2d_release(g->image);
    if (g->frame) nemo_d2d_release(g->frame);
    g->interop=NULL;g->brush=NULL;g->upload=NULL;g->image=NULL;g->frame=NULL;
    g->upload_width=g->upload_height=0;
}
void nemo_d2d_free(NemoD2D *g)
{
    if (!g) return;
    free_frame(g);
    if (g->target) nemo_d2d_release(g->target);
    if (g->factory) nemo_d2d_release(g->factory);
    if (g->bitmap) {SelectObject(g->scratch,g->oldbitmap);DeleteObject(g->bitmap);}
    if (g->scratch) DeleteDC(g->scratch);
    if (g->surface) DestroyWindow(g->surface);
    if (g->module) FreeLibrary(g->module);
    sfree(g);
}
NemoD2D *nemo_d2d_create(HWND parent)
{
    NemoD2D *g=snew(NemoD2D);memset(g,0,sizeof(*g));g->parent=parent;
    g->module=load_system32_dll("d2d1.dll");
    if (!g->module) goto fail;
    CreateFactoryFn create;
    *(FARPROC *)&create=GetProcAddress(g->module,"D2D1CreateFactory");
    if (!create || !check(g,create(D2D1_FACTORY_TYPE_SINGLE_THREADED,
                         &factory_iid,NULL,(void **)&g->factory))) goto fail;
    WNDCLASSW wc={0};wc.lpfnWndProc=surface_proc;
    wc.hInstance=GetModuleHandle(NULL);wc.lpszClassName=L"NemotermDirect2D";
    if (!RegisterClassW(&wc) && GetLastError()!=ERROR_CLASS_ALREADY_EXISTS) goto fail;
    g->surface=CreateWindowExW(0,wc.lpszClassName,L"",WS_CHILD|WS_CLIPSIBLINGS,
                             0,0,1,1,parent,NULL,wc.hInstance,NULL);
    g->scratch=CreateCompatibleDC(NULL);
    if (!g->surface || !g->scratch) goto fail;
    D2D1_RENDER_TARGET_PROPERTIES props={0};
    props.type=D2D1_RENDER_TARGET_TYPE_HARDWARE;
    props.pixelFormat.format=DXGI_FORMAT_B8G8R8A8_UNORM;
    props.pixelFormat.alphaMode=D2D1_ALPHA_MODE_IGNORE;
    props.dpiX=props.dpiY=96;
    D2D1_HWND_RENDER_TARGET_PROPERTIES win={0};
    win.hwnd=g->surface;win.pixelSize.width=win.pixelSize.height=1;
    if (!check(g,nemo_d2d_create_hwnd(g->factory,&props,&win,&g->target))) goto fail;
    g->limit=nemo_d2d_max_size((ID2D1RenderTarget *)g->target);
    return g;
  fail:
    nemo_d2d_free(g);return NULL;
}
const char *nemo_d2d_device(NemoD2D *g) { return "Direct2D hardware render target"; }
HDC nemo_d2d_dc(NemoD2D *g) { return g->scratch; }
int nemo_d2d_frame(NemoD2D *g, COLORREF background)
{
    RECT r;
    if (g->failed || !GetClientRect(g->parent,&r) || r.right<=0 || r.bottom<=0) return 0;
    if ((unsigned)r.right>g->limit || (unsigned)r.bottom>g->limit ||
        (uint64_t)r.right*r.bottom*4>FRAME_BYTES) {g->failed=true;return 0;}
    bool changed=r.right!=g->width || r.bottom!=g->height;
    if (changed) {
        free_frame(g);
        D2D1_SIZE_U size={(UINT32)r.right,(UINT32)r.bottom};
        if (!check(g,nemo_d2d_resize(g->target,&size))) return 0;
        if (!check(g,nemo_d2d_compatible(
                (ID2D1RenderTarget *)g->target,NULL,&size,NULL,
                D2D1_COMPATIBLE_RENDER_TARGET_OPTIONS_GDI_COMPATIBLE,&g->frame))) return 0;
        if (!check(g,nemo_d2d_get_bitmap(g->frame,&g->image)) ||
            !check(g,nemo_d2d_query(g->frame,&interop_iid,(void **)&g->interop))) return 0;
        D2D1_COLOR_F c=color(background);
        if (!check(g,nemo_d2d_solid_brush(RT(g),&c,NULL,&g->brush))) return 0;
        nemo_d2d_antialias(RT(g),D2D1_ANTIALIAS_MODE_ALIASED);
        g->width=r.right;g->height=r.bottom;
        SetWindowPos(g->surface,NULL,0,0,g->width,g->height,SWP_NOACTIVATE|SWP_NOZORDER);
    }
    if (!g->drawing) {nemo_d2d_begin(RT(g));g->drawing=true;}
    if (changed) {D2D1_COLOR_F c=color(background);nemo_d2d_clear(RT(g),&c);}
    return changed?2:1;
}
bool nemo_d2d_present(NemoD2D *g)
{
    if (!end_frame(g) || !g->image) return false;
    ID2D1RenderTarget *target=(ID2D1RenderTarget *)g->target;
    D2D1_RECT_F rect={0,0,(float)g->width,(float)g->height};
    nemo_d2d_begin(target);
    nemo_d2d_draw_bitmap(target,g->image,&rect,1,
                                D2D1_BITMAP_INTERPOLATION_MODE_NEAREST_NEIGHBOR,NULL);
    if (!check(g,nemo_d2d_end(target,NULL,NULL))) return false;
    if (!IsWindowVisible(g->surface)) ShowWindow(g->surface,SW_SHOWNOACTIVATE);
    return true;
}
static bool strip(NemoD2D *g, int width, int height)
{
    if (g->failed || width<=0 || height<=0 || (unsigned)width>g->limit ||
        (unsigned)height>g->limit || (uint64_t)width*height*4>CACHE_BYTES) {
        g->failed=true;return false;
    }
    if (width<=g->strip_width && height<=g->strip_height) return true;
    width=max(width,g->strip_width);height=max(height,g->strip_height);
    if ((uint64_t)width*height*4>CACHE_BYTES) {g->failed=true;return false;}
    if (g->bitmap) {SelectObject(g->scratch,g->oldbitmap);DeleteObject(g->bitmap);g->bitmap=NULL;}
    BITMAPINFO bi={0};bi.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);
    bi.bmiHeader.biWidth=width;bi.bmiHeader.biHeight=-height;
    bi.bmiHeader.biPlanes=1;bi.bmiHeader.biBitCount=32;bi.bmiHeader.biCompression=BI_RGB;
    g->bitmap=CreateDIBSection(g->scratch,&bi,DIB_RGB_COLORS,(void **)&g->pixels,NULL,0);
    if (!g->bitmap) {g->failed=true;return false;}
    g->oldbitmap=SelectObject(g->scratch,g->bitmap);
    g->strip_width=width;g->strip_height=height;
    return true;
}
static uint64_t keyhash(ptrlen key)
{
    uint64_t hash=UINT64_C(14695981039346656037);const unsigned char *p=key.ptr;
    for (size_t i=0;i<key.len;i++) hash=(hash^p[i])*UINT64_C(1099511628211);
    return hash;
}
static void draw(NemoD2D *g, ID2D1Bitmap *image, RECT box)
{
    D2D1_RECT_F dst={(float)box.left,(float)box.top,(float)box.right,(float)box.bottom};
    D2D1_RECT_F src={0,0,(float)(box.right-box.left),(float)(box.bottom-box.top)};
    nemo_d2d_draw_bitmap(RT(g),image,&dst,1,D2D1_BITMAP_INTERPOLATION_MODE_NEAREST_NEIGHBOR,&src);
}
bool nemo_d2d_cached(NemoD2D *g, RECT box, ptrlen key)
{
    if (g->failed) return false;
    uint64_t hash=keyhash(key);
    for (unsigned i=0;i<CACHE_COUNT;i++) {
        D2DRun *r=&g->cache[i];
        if (r->key && r->hash==hash && r->width==box.right-box.left &&
            r->height==box.bottom-box.top && ptrlen_eq_ptrlen(ptrlen_from_strbuf(r->key),key)) {
            r->used=++g->tick;draw(g,r->bitmap,box);return true;
        }
    }
    return false;
}
static bool read_pixels(NemoD2D *g, HDC dest, int dx, int dy, int x, int y, int w, int h)
{
    if (g->failed || !g->interop) return false;
    bool opened=!g->drawing;
    if (opened) {nemo_d2d_begin(RT(g));g->drawing=true;}
    HDC source=NULL;
    if (check(g,nemo_d2d_get_dc(g->interop,D2D1_DC_INITIALIZE_MODE_COPY,&source))) {
        bool copied=BitBlt(dest,dx,dy,w,h,source,x,y,SRCCOPY);
        RECT unchanged={0};
        check(g,nemo_d2d_release_dc(g->interop,&unchanged));
        if (!copied) g->failed=true;
    }
    if (opened) end_frame(g);
    return !g->failed;
}
bool nemo_d2d_begin_run(NemoD2D *g, RECT box, bool overlay)
{
    int width=box.right-box.left,height=box.bottom-box.top;
    if (!strip(g,width,height)) return false;
    SelectClipRgn(g->scratch,NULL);SetViewportOrgEx(g->scratch,-box.left,-box.top,NULL);
    IntersectClipRect(g->scratch,box.left,box.top,box.right,box.bottom);
    if (overlay) return read_pixels(g,g->scratch,box.left,box.top,box.left,box.top,width,height);
    memset(g->pixels,0,(size_t)g->strip_width*height*4);return true;
}
static bool bitmap(NemoD2D *g, int w, int h, const void *data, unsigned pitch, ID2D1Bitmap **out)
{
    D2D1_BITMAP_PROPERTIES props={0};props.pixelFormat.format=DXGI_FORMAT_B8G8R8A8_UNORM;
    props.pixelFormat.alphaMode=D2D1_ALPHA_MODE_IGNORE;props.dpiX=props.dpiY=96;
    D2D1_SIZE_U size={(UINT32)w,(UINT32)h};
    return check(g,nemo_d2d_create_bitmap(RT(g),size,data,pitch,&props,out));
}
static void upload(NemoD2D *g, RECT box, const void *pixels, unsigned pitch)
{
    if (g->failed) return;
    int w=box.right-box.left,h=box.bottom-box.top;
    if (w<=0 || h<=0 || (unsigned)w>g->limit || (unsigned)h>g->limit ||
        (uint64_t)w*h*4>CACHE_BYTES) {g->failed=true;return;}
    if (w>g->upload_width || h>g->upload_height) {
        int nw=max(w,g->upload_width),nh=max(h,g->upload_height);
        if ((uint64_t)nw*nh*4>CACHE_BYTES) {g->failed=true;return;}
        if (g->upload) {nemo_d2d_release(g->upload);g->upload=NULL;}
        if (!bitmap(g,nw,nh,NULL,0,&g->upload)) return;
        g->upload_width=nw;g->upload_height=nh;
    }
    D2D1_RECT_U rect={0,0,(UINT32)w,(UINT32)h};
    if (check(g,nemo_d2d_copy_memory(g->upload,&rect,pixels,pitch))) draw(g,g->upload,box);
}
void nemo_d2d_end_run(NemoD2D *g, RECT box, ptrlen key)
{
    GdiFlush();
    if (g->failed) return;
    unsigned bytes=(unsigned)(box.right-box.left)*(box.bottom-box.top)*4;
    if (!key.len || key.len>16384 || bytes>CACHE_BYTES) {
        upload(g,box,g->pixels,g->strip_width*4);return;
    }
    D2DRun *r=NULL;
    for (unsigned i=0;i<CACHE_COUNT;i++)
        if (!r || g->cache[i].used<r->used) r=&g->cache[i];
    int width=box.right-box.left,height=box.bottom-box.top;
    /* Fill empty cache slots first. Once full, prefer an old resource with
     * exactly the required dimensions. Replacing its contents avoids a new
     * driver allocation for each distinct text/colour key. CopyFromMemory
     * flushes a batch that still references the bitmap before updating it. */
    if (r->bitmap) {
        D2DRun *same=NULL;
        for (unsigned i=0;i<CACHE_COUNT;i++)
            if (g->cache[i].bitmap && g->cache[i].width==width &&
                g->cache[i].height==height && (!same || g->cache[i].used<same->used))
                same=&g->cache[i];
        if (same) r=same;
    }
    if (r->bitmap && r->width==width && r->height==height) {
        if (!check(g,nemo_d2d_copy_memory(r->bitmap,NULL,g->pixels,g->strip_width*4))) return;
        strbuf_free(r->key);r->key=NULL;
    } else {
        evict(g,r);
        while (g->cache_bytes+bytes>CACHE_BYTES) {
            D2DRun *old=NULL;
            for (unsigned i=0;i<CACHE_COUNT;i++)
                if (g->cache[i].bitmap && (!old || g->cache[i].used<old->used)) old=&g->cache[i];
            if (!old) break;
            evict(g,old);
        }
        if (!bitmap(g,width,height,g->pixels,g->strip_width*4,&r->bitmap)) return;
        r->bytes=bytes;g->cache_bytes+=bytes;
    }
    r->used=++g->tick;r->hash=keyhash(key);
    r->width=width;r->height=height;
    r->key=strbuf_new();put_datapl(r->key,key);draw(g,r->bitmap,box);
}
void nemo_d2d_row(NemoD2D *g, int x, int y, int width, const uint32_t *pixels)
{
    RECT box={x,y,x+width,y+1};upload(g,box,pixels,width*4);
}
static void fill(NemoD2D *g, RECT r)
{
    if (r.right<=r.left || r.bottom<=r.top) return;
    D2D1_RECT_F box={(float)r.left,(float)r.top,(float)r.right,(float)r.bottom};
    nemo_d2d_fill(RT(g),&box,(ID2D1Brush *)g->brush);
}
void nemo_d2d_borders(NemoD2D *g, RECT text, COLORREF background)
{
    if (g->failed) return;
    D2D1_COLOR_F c=color(background);nemo_d2d_set_color(g->brush,&c);
    RECT r={0,0,g->width,text.top};fill(g,r);
    r.top=text.bottom;r.bottom=g->height;fill(g,r);
    r.top=text.top;r.bottom=text.bottom;r.right=text.left;fill(g,r);
    r.left=text.right;r.right=g->width;fill(g,r);
}
bool nemo_d2d_print(NemoD2D *g, HDC dc)
{
    return g->width>0 && g->height>0 && read_pixels(g,dc,0,0,0,0,g->width,g->height);
}
void nemo_d2d_fill_rect(NemoD2D *g, RECT rect, COLORREF colour)
{
    if (g->failed) return;
    D2D1_COLOR_F c=color(colour);nemo_d2d_set_color(g->brush,&c);
    fill(g,rect);
}
bool nemo_d2d_attach(NemoD2D *g, HWND parent)
{
    ShowWindow(g->surface,SW_HIDE);
    SetLastError(0);
    if (!SetParent(g->surface,parent) && GetLastError()) return false;
    g->parent=parent;nemo_d2d_clear_cache(g);return true;
}
void nemo_d2d_show(NemoD2D *g, bool visible)
{
    ShowWindow(g->surface,visible ? SW_SHOWNOACTIVATE : SW_HIDE);
}
bool nemo_d2d_print_band(NemoD2D *g, HDC dc, int top, int height)
{
    top=max(0,top);height=min(height,g->height-top);
    return g->width>0 && height>0 && read_pixels(g,dc,0,top,0,top,g->width,height);
}
