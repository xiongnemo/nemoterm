/* SPDX-License-Identifier: MIT
 * Experimental Direct3D 11 copy-only compositor. No shaders or Direct2D.
 * GDI rasterizes text into a bounded DIB. A retained GPU texture receives
 * copies from one bounded staging texture, and is copied into the swapchain.
 * Readback uses fixed tiles. All resources belong to the UI thread.
 */
#define COBJMACROS
#include "putty.h"
#include <d3d11.h>
#include <dxgi.h>
#include "nemo_d3d11.h"

#define STRIP_BYTES (4U*1024U*1024U)
#define FRAME_BYTES (128U*1024U*1024U)
#define TILE_W 512
#define TILE_H 64
#define BATCH_COUNT 512
typedef struct NemoCopyRect { RECT dest; int x,y; } NemoCopyRect;
static const GUID texture_iid={0x6f15aaf2,0xd208,0x4e89,{0x9a,0xb4,0x48,0x95,0x35,0xd3,0x4f,0x9c}};
static const GUID dxgi_device_iid={0x54ec77fa,0x1377,0x44e6,{0x8c,0x32,0x88,0xfd,0x5f,0x44,0xc8,0x4c}};
static const GUID factory_iid={0x7b7166ec,0x21c7,0x44ae,{0xb2,0x1a,0xc9,0xae,0x32,0x1a,0xe3,0x69}};
typedef HRESULT (WINAPI *CreateDeviceFn)(IDXGIAdapter *,D3D_DRIVER_TYPE,HMODULE,
    UINT,const D3D_FEATURE_LEVEL *,UINT,UINT,ID3D11Device **,
    D3D_FEATURE_LEVEL *,ID3D11DeviceContext **);
struct NemoD3D11 {
    HWND parent,surface;
    HMODULE module;
    ID3D11Device *device;
    ID3D11DeviceContext *context;
    IDXGISwapChain *swap;
    ID3D11Texture2D *frame,*back,*upload,*readback;
    HDC scratch;
    HBITMAP bitmap;
    HGDIOBJ oldbitmap;
    uint32_t *pixels;
    int width,height,strip_width,strip_height,upload_width,upload_height;
    int batch_x,batch_y,batch_row,batch_bottom,run_x,run_y;
    unsigned batch_count;
    NemoCopyRect batch[BATCH_COUNT];
    UINT limit;
    bool failed;
};
#define RESOURCE(p) ((ID3D11Resource *)(p))
#define RELEASE(p) do { if (p) { IUnknown_Release((IUnknown *)(p)); (p)=NULL; } } while (0)
static bool check(NemoD3D11 *g,HRESULT hr)
{
    if (FAILED(hr)) g->failed=true;
    return !g->failed;
}
static LRESULT CALLBACK surface_proc(HWND hwnd,UINT msg,WPARAM wp,LPARAM lp)
{
    if (msg==WM_NCHITTEST) return HTTRANSPARENT;
    if (msg==WM_MOUSEACTIVATE) return MA_NOACTIVATE;
    if (msg==WM_ERASEBKGND) return 1;
    if (msg==WM_PAINT) {
        ValidateRect(hwnd,NULL);InvalidateRect(GetParent(hwnd),NULL,false);return 0;
    }
    return DefWindowProcW(hwnd,msg,wp,lp);
}
static bool texture(NemoD3D11 *g,int width,int height,UINT access,ID3D11Texture2D **out)
{
    D3D11_TEXTURE2D_DESC d={0};d.Width=width;d.Height=height;
    d.MipLevels=d.ArraySize=d.SampleDesc.Count=1;
    d.Format=DXGI_FORMAT_B8G8R8A8_UNORM;
    d.Usage=access?D3D11_USAGE_STAGING:D3D11_USAGE_DEFAULT;
    d.CPUAccessFlags=access;
    return check(g,ID3D11Device_CreateTexture2D(g->device,&d,NULL,out));
}
void nemo_d3d11_free(NemoD3D11 *g)
{
    if (!g) return;
    if (g->context) ID3D11DeviceContext_ClearState(g->context);
    RELEASE(g->frame);RELEASE(g->back);RELEASE(g->upload);RELEASE(g->readback);
    RELEASE(g->swap);
    if (g->context) ID3D11DeviceContext_Flush(g->context);
    RELEASE(g->context);RELEASE(g->device);
    if (g->bitmap) {SelectObject(g->scratch,g->oldbitmap);DeleteObject(g->bitmap);}
    if (g->scratch) DeleteDC(g->scratch);
    if (g->surface) DestroyWindow(g->surface);
    if (g->module) FreeLibrary(g->module);
    sfree(g);
}
NemoD3D11 *nemo_d3d11_create(HWND parent)
{
    NemoD3D11 *g=snew(NemoD3D11);memset(g,0,sizeof(*g));g->parent=parent;
    IDXGIDevice *dxgi=NULL;IDXGIAdapter *adapter=NULL;IDXGIFactory *factory=NULL;
    CreateDeviceFn create=NULL;
    D3D_FEATURE_LEVEL level;
    const D3D_FEATURE_LEVEL levels[]={D3D_FEATURE_LEVEL_11_0,D3D_FEATURE_LEVEL_10_1,D3D_FEATURE_LEVEL_10_0};
    g->module=load_system32_dll("d3d11.dll");
    if (!g->module) goto fail;
    *(FARPROC *)&create=GetProcAddress(g->module,"D3D11CreateDevice");
    if (!create || !check(g,create(NULL,D3D_DRIVER_TYPE_HARDWARE,NULL,
            D3D11_CREATE_DEVICE_SINGLETHREADED|D3D11_CREATE_DEVICE_BGRA_SUPPORT,
            levels,lenof(levels),D3D11_SDK_VERSION,&g->device,&level,&g->context))) goto fail;
    g->limit=level>=D3D_FEATURE_LEVEL_11_0?16384:8192;
    if (!check(g,ID3D11Device_QueryInterface(g->device,&dxgi_device_iid,(void **)&dxgi)) ||
        !check(g,IDXGIDevice_GetAdapter(dxgi,&adapter)) ||
        !check(g,IDXGIAdapter_GetParent(adapter,&factory_iid,(void **)&factory))) goto fail;
    WNDCLASSW wc={0};wc.lpfnWndProc=surface_proc;
    wc.hInstance=GetModuleHandle(NULL);wc.lpszClassName=L"NemotermDirect3D11";
    if (!RegisterClassW(&wc) && GetLastError()!=ERROR_CLASS_ALREADY_EXISTS) goto fail;
    g->surface=CreateWindowExW(0,wc.lpszClassName,L"",WS_CHILD|WS_CLIPSIBLINGS,
                              0,0,1,1,parent,NULL,wc.hInstance,NULL);
    g->scratch=CreateCompatibleDC(NULL);
    if (!g->surface || !g->scratch) goto fail;
    DXGI_SWAP_CHAIN_DESC d={0};d.BufferDesc.Width=d.BufferDesc.Height=1;
    d.BufferDesc.Format=DXGI_FORMAT_B8G8R8A8_UNORM;d.SampleDesc.Count=1;
    d.BufferUsage=DXGI_USAGE_RENDER_TARGET_OUTPUT;d.BufferCount=1;
    d.OutputWindow=g->surface;d.Windowed=TRUE;d.SwapEffect=DXGI_SWAP_EFFECT_SEQUENTIAL;
    if (!check(g,IDXGIFactory_CreateSwapChain(factory,(IUnknown *)g->device,&d,&g->swap))) goto fail;
    if (!check(g,IDXGIFactory_MakeWindowAssociation(factory,g->surface,
              DXGI_MWA_NO_ALT_ENTER|DXGI_MWA_NO_WINDOW_CHANGES))) goto fail;
    RELEASE(factory);RELEASE(adapter);RELEASE(dxgi);
    return g;
  fail:
    RELEASE(factory);RELEASE(adapter);RELEASE(dxgi);nemo_d3d11_free(g);return NULL;
}
const char *nemo_d3d11_device(NemoD3D11 *g) { return "Direct3D 11 hardware copy compositor"; }
HDC nemo_d3d11_dc(NemoD3D11 *g) { return g->scratch; }
void nemo_d3d11_clear_cache(NemoD3D11 *g) { }
bool nemo_d3d11_cached(NemoD3D11 *g,RECT box,ptrlen key) { return false; }
static void reset_batch(NemoD3D11 *g)
{
    g->batch_x=g->batch_y=g->batch_row=g->batch_bottom=0;g->batch_count=0;
}
static bool flush_batch(NemoD3D11 *g)
{
    if (g->failed) return false;
    if (!g->batch_count) return true;
    GdiFlush();
    if (g->upload_width!=g->strip_width || g->upload_height!=g->strip_height) {
        RELEASE(g->upload);
        if (!texture(g,g->strip_width,g->strip_height,D3D11_CPU_ACCESS_WRITE,&g->upload)) return false;
        g->upload_width=g->strip_width;g->upload_height=g->strip_height;
    }
    D3D11_MAPPED_SUBRESOURCE mapped={0};
    if (!check(g,ID3D11DeviceContext_Map(g->context,RESOURCE(g->upload),0,D3D11_MAP_WRITE,0,&mapped))) return false;
    for (int row=0;row<g->batch_bottom;row++)
        memcpy((char *)mapped.pData+(size_t)row*mapped.RowPitch,g->pixels+(size_t)row*g->strip_width,g->strip_width*4);
    ID3D11DeviceContext_Unmap(g->context,RESOURCE(g->upload),0);
    for (unsigned i=0;i<g->batch_count;i++) {
        NemoCopyRect *r=&g->batch[i];
        D3D11_BOX box={(UINT)r->x,(UINT)r->y,0,
            (UINT)(r->x+r->dest.right-r->dest.left),(UINT)(r->y+r->dest.bottom-r->dest.top),1};
        ID3D11DeviceContext_CopySubresourceRegion(g->context,RESOURCE(g->frame),0,
            r->dest.left,r->dest.top,0,RESOURCE(g->upload),0,&box);
    }
    reset_batch(g);return true;
}
static bool strip(NemoD3D11 *g,int width,int height)
{
    if (g->failed || width<=0 || height<=0 || (unsigned)width>g->limit ||
        (unsigned)height>g->limit || (uint64_t)width*height*4>STRIP_BYTES) {
        g->failed=true;return false;
    }
    if (width<=g->strip_width && height<=g->strip_height) return true;
    if (!flush_batch(g)) return false;
    width=max(width,g->strip_width);height=max(height,g->strip_height);
    if ((uint64_t)width*height*4>STRIP_BYTES) {g->failed=true;return false;}
    if (g->bitmap) {SelectObject(g->scratch,g->oldbitmap);DeleteObject(g->bitmap);g->bitmap=NULL;}
    BITMAPINFO bi={0};bi.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);
    bi.bmiHeader.biWidth=width;bi.bmiHeader.biHeight=-height;
    bi.bmiHeader.biPlanes=1;bi.bmiHeader.biBitCount=32;bi.bmiHeader.biCompression=BI_RGB;
    g->bitmap=CreateDIBSection(g->scratch,&bi,DIB_RGB_COLORS,(void **)&g->pixels,NULL,0);
    if (!g->bitmap) {g->failed=true;return false;}
    g->oldbitmap=SelectObject(g->scratch,g->bitmap);
    g->strip_width=width;g->strip_height=height;return true;
}
static bool reserve_run(NemoD3D11 *g,int width,int height,int *x,int *y)
{
    if (!strip(g,max(g->width,width),max(TILE_H,height))) return false;
    if (g->batch_count>=BATCH_COUNT && !flush_batch(g)) return false;
    if (g->batch_x+width>g->strip_width) {
        g->batch_x=0;g->batch_y+=g->batch_row;g->batch_row=0;
    }
    if (g->batch_y+height>g->strip_height && !flush_batch(g)) return false;
    *x=g->batch_x;*y=g->batch_y;g->batch_x+=width;
    g->batch_row=max(g->batch_row,height);g->batch_bottom=max(g->batch_bottom,*y+height);
    return true;
}
static void queue_copy(NemoD3D11 *g,RECT box,int x,int y)
{
    RECT clipped={max(0,box.left),max(0,box.top),min(g->width,box.right),min(g->height,box.bottom)};
    if (clipped.right<=clipped.left || clipped.bottom<=clipped.top) return;
    assert(g->batch_count<BATCH_COUNT);
    g->batch[g->batch_count++]=(NemoCopyRect){clipped,x+clipped.left-box.left,y+clipped.top-box.top};
}
static void upload(NemoD3D11 *g,RECT box,const uint32_t *pixels,unsigned pitch)
{
    if (g->failed) return;
    int x=max(box.left,0),y=max(box.top,0),right=min(box.right,g->width),bottom=min(box.bottom,g->height);
    int width=right-x,height=bottom-y;
    if (width<=0 || height<=0) return;
    int sx,sy;
    if (!reserve_run(g,width,height,&sx,&sy)) return;
    GdiFlush();
    const unsigned char *source=(const unsigned char *)pixels+(size_t)(y-box.top)*pitch+(x-box.left)*4;
    for (int row=0;row<height;row++)
        memcpy(g->pixels+(size_t)(sy+row)*g->strip_width+sx,source+(size_t)row*pitch,width*4);
    RECT clipped={x,y,right,bottom};queue_copy(g,clipped,sx,sy);
}
void nemo_d3d11_fill_rect(NemoD3D11 *g,RECT rect,COLORREF colour)
{
    rect.left=max(0,rect.left);rect.top=max(0,rect.top);
    rect.right=min(g->width,rect.right);rect.bottom=min(g->height,rect.bottom);
    int width=rect.right-rect.left,height=rect.bottom-rect.top;
    if (width<=0 || height<=0) return;
    uint32_t pixel=0xff000000U|(GetRValue(colour)<<16)|(GetGValue(colour)<<8)|GetBValue(colour);
    for (int top=rect.top;top<rect.bottom;top+=TILE_H) {
        RECT band={rect.left,top,rect.right,min(top+TILE_H,rect.bottom)};
        int sx,sy,h=band.bottom-band.top;
        if (!reserve_run(g,width,h,&sx,&sy)) return;
        GdiFlush();
        for (int y=0;y<h;y++) for (int x=0;x<width;x++)
            g->pixels[(size_t)(sy+y)*g->strip_width+sx+x]=pixel;
        queue_copy(g,band,sx,sy);
    }
}
int nemo_d3d11_frame(NemoD3D11 *g,COLORREF background)
{
    RECT r;
    if (g->failed || !GetClientRect(g->parent,&r) || r.right<=0 || r.bottom<=0) return 0;
    if ((unsigned)r.right>g->limit || (unsigned)r.bottom>g->limit || (uint64_t)r.right*r.bottom*4>FRAME_BYTES) {g->failed=true;return 0;}
    bool changed=r.right!=g->width || r.bottom!=g->height;
    if (changed) {
        reset_batch(g);
        RELEASE(g->back);RELEASE(g->frame);
        if (!check(g,IDXGISwapChain_ResizeBuffers(g->swap,1,r.right,r.bottom,DXGI_FORMAT_UNKNOWN,0)) ||
            !check(g,IDXGISwapChain_GetBuffer(g->swap,0,&texture_iid,(void **)&g->back))) return 0;
        g->frame=g->back;ID3D11Texture2D_AddRef(g->frame);
        g->width=r.right;g->height=r.bottom;
        SetWindowPos(g->surface,NULL,0,0,g->width,g->height,SWP_NOACTIVATE|SWP_NOZORDER);
        nemo_d3d11_fill_rect(g,r,background);
    }
    return g->failed?0:changed?2:1;
}
bool nemo_d3d11_present(NemoD3D11 *g)
{
    if (g->failed || !g->frame || !flush_batch(g)) return false;
    if (!check(g,IDXGISwapChain_Present(g->swap,0,0))) return false;
    if (!IsWindowVisible(g->surface)) ShowWindow(g->surface,SW_SHOWNOACTIVATE);
    return true;
}
static bool read_pixels(NemoD3D11 *g,int x,int y,int width,int height,uint32_t *dest,unsigned pitch)
{
    if (g->failed || !g->frame || !flush_batch(g)) return false;
    if (!g->readback && !texture(g,TILE_W,TILE_H,D3D11_CPU_ACCESS_READ,&g->readback)) return false;
    for (int top=0;top<height;top+=TILE_H) for (int left=0;left<width;left+=TILE_W) {
        int w=min(TILE_W,width-left),h=min(TILE_H,height-top);
        D3D11_BOX box={(UINT)(x+left),(UINT)(y+top),0,(UINT)(x+left+w),(UINT)(y+top+h),1};
        ID3D11DeviceContext_CopySubresourceRegion(g->context,RESOURCE(g->readback),0,0,0,0,RESOURCE(g->frame),0,&box);
        D3D11_MAPPED_SUBRESOURCE mapped={0};
        if (!check(g,ID3D11DeviceContext_Map(g->context,RESOURCE(g->readback),0,D3D11_MAP_READ,0,&mapped))) return false;
        for (int row=0;row<h;row++) memcpy((char *)dest+(size_t)(top+row)*pitch+left*4,(char *)mapped.pData+(size_t)row*mapped.RowPitch,w*4);
        ID3D11DeviceContext_Unmap(g->context,RESOURCE(g->readback),0);
    }
    return true;
}
bool nemo_d3d11_begin_run(NemoD3D11 *g,RECT box,bool overlay)
{
    int width=box.right-box.left,height=box.bottom-box.top;
    if (overlay && !flush_batch(g)) return false;
    if (!reserve_run(g,width,height,&g->run_x,&g->run_y)) return false;
    GdiFlush();
    for (int y=0;y<height;y++) memset(g->pixels+(size_t)(g->run_y+y)*g->strip_width+g->run_x,0,width*4);
    SelectClipRgn(g->scratch,NULL);SetViewportOrgEx(g->scratch,g->run_x-box.left,g->run_y-box.top,NULL);
    IntersectClipRect(g->scratch,box.left,box.top,box.right,box.bottom);
    if (overlay) {
        int x=max(0,box.left),y=max(0,box.top),w=min(g->width,box.right)-x,h=min(g->height,box.bottom)-y;
        if (w>0 && h>0) return read_pixels(g,x,y,w,h,g->pixels+(size_t)(g->run_y+y-box.top)*g->strip_width+g->run_x+x-box.left,g->strip_width*4);
    }
    return true;
}
void nemo_d3d11_end_run(NemoD3D11 *g,RECT box,ptrlen key)
{
    if (!g->failed) queue_copy(g,box,g->run_x,g->run_y);
}
void nemo_d3d11_row(NemoD3D11 *g,int x,int y,int width,const uint32_t *pixels)
{
    RECT box={x,y,x+width,y+1};upload(g,box,pixels,width*4);
}
void nemo_d3d11_borders(NemoD3D11 *g,RECT text,COLORREF background)
{
    RECT r={0,0,g->width,text.top};nemo_d3d11_fill_rect(g,r,background);
    r.top=text.bottom;r.bottom=g->height;nemo_d3d11_fill_rect(g,r,background);
    r.top=text.top;r.bottom=text.bottom;r.right=text.left;nemo_d3d11_fill_rect(g,r,background);
    r.left=text.right;r.right=g->width;nemo_d3d11_fill_rect(g,r,background);
}
bool nemo_d3d11_print_band(NemoD3D11 *g,HDC dc,int top,int height)
{
    top=max(0,top);height=min(height,g->height-top);
    if (g->width<=0 || height<=0 || !flush_batch(g) || !strip(g,g->width,min(height,TILE_H))) return false;
    int saved=SaveDC(g->scratch);if (!saved) return false;
    SelectClipRgn(g->scratch,NULL);SetViewportOrgEx(g->scratch,0,0,NULL);
    bool ok=true;
    for (int y=top;y<top+height && ok;y+=TILE_H) {
        int h=min(TILE_H,top+height-y);GdiFlush();
        ok=read_pixels(g,0,y,g->width,h,g->pixels,g->strip_width*4) &&
            BitBlt(dc,0,y,g->width,h,g->scratch,0,0,SRCCOPY);
    }
    RestoreDC(g->scratch,saved);return ok;
}
bool nemo_d3d11_print(NemoD3D11 *g,HDC dc) { return nemo_d3d11_print_band(g,dc,0,g->height); }
bool nemo_d3d11_attach(NemoD3D11 *g,HWND parent)
{
    ShowWindow(g->surface,SW_HIDE);SetLastError(0);
    if (!SetParent(g->surface,parent) && GetLastError()) return false;
    g->parent=parent;return true;
}
void nemo_d3d11_show(NemoD3D11 *g,bool visible) { ShowWindow(g->surface,visible?SW_SHOWNOACTIVATE:SW_HIDE); }
