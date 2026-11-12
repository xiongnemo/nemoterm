/* SPDX-License-Identifier: MIT */
#include "nemo_d2d_api.h"

void nemo_d2d_release(void *object)
{ static_cast<IUnknown *>(object)->Release(); }
HRESULT nemo_d2d_query(void *object, const GUID *iid, void **out)
{ return static_cast<IUnknown *>(object)->QueryInterface(*iid,out); }
HRESULT nemo_d2d_create_hwnd(ID2D1Factory *p, const D2D1_RENDER_TARGET_PROPERTIES *r,
    const D2D1_HWND_RENDER_TARGET_PROPERTIES *h, ID2D1HwndRenderTarget **out)
{ return p->CreateHwndRenderTarget(r,h,out); }
UINT32 nemo_d2d_max_size(ID2D1RenderTarget *p)
{ return p->GetMaximumBitmapSize(); }
HRESULT nemo_d2d_resize(ID2D1HwndRenderTarget *p, const D2D1_SIZE_U *size)
{ return p->Resize(size); }
HRESULT nemo_d2d_compatible(ID2D1RenderTarget *p, const D2D1_SIZE_F *size,
    const D2D1_SIZE_U *pixels, const D2D1_PIXEL_FORMAT *format,
    D2D1_COMPATIBLE_RENDER_TARGET_OPTIONS options, ID2D1BitmapRenderTarget **out)
{ return p->CreateCompatibleRenderTarget(size,pixels,format,options,out); }
HRESULT nemo_d2d_get_bitmap(ID2D1BitmapRenderTarget *p, ID2D1Bitmap **out)
{ return p->GetBitmap(out); }
HRESULT nemo_d2d_solid_brush(ID2D1RenderTarget *p, const D2D1_COLOR_F *color,
    const D2D1_BRUSH_PROPERTIES *properties, ID2D1SolidColorBrush **out)
{ return p->CreateSolidColorBrush(color,properties,out); }
void nemo_d2d_antialias(ID2D1RenderTarget *p, D2D1_ANTIALIAS_MODE mode)
{ p->SetAntialiasMode(mode); }
void nemo_d2d_begin(ID2D1RenderTarget *p)
{ p->BeginDraw(); }
HRESULT nemo_d2d_end(ID2D1RenderTarget *p, D2D1_TAG *first, D2D1_TAG *last)
{ return p->EndDraw(first,last); }
void nemo_d2d_clear(ID2D1RenderTarget *p, const D2D1_COLOR_F *color)
{ p->Clear(color); }
void nemo_d2d_draw_bitmap(ID2D1RenderTarget *p, ID2D1Bitmap *bitmap, const D2D1_RECT_F *dest,
    FLOAT opacity, D2D1_BITMAP_INTERPOLATION_MODE mode, const D2D1_RECT_F *source)
{ p->DrawBitmap(bitmap,dest,opacity,mode,source); }
HRESULT nemo_d2d_get_dc(ID2D1GdiInteropRenderTarget *p, D2D1_DC_INITIALIZE_MODE mode, HDC *dc)
{ return p->GetDC(mode,dc); }
HRESULT nemo_d2d_release_dc(ID2D1GdiInteropRenderTarget *p, const RECT *rect)
{ return p->ReleaseDC(rect); }
HRESULT nemo_d2d_create_bitmap(ID2D1RenderTarget *p, D2D1_SIZE_U size, const void *data,
    UINT32 pitch, const D2D1_BITMAP_PROPERTIES *properties, ID2D1Bitmap **out)
{ return p->CreateBitmap(size,data,pitch,properties,out); }
HRESULT nemo_d2d_copy_memory(ID2D1Bitmap *p, const D2D1_RECT_U *rect, const void *data, UINT32 pitch)
{ return p->CopyFromMemory(rect,data,pitch); }
void nemo_d2d_fill(ID2D1RenderTarget *p, const D2D1_RECT_F *rect, ID2D1Brush *brush)
{ p->FillRectangle(rect,brush); }
void nemo_d2d_set_color(ID2D1SolidColorBrush *p, const D2D1_COLOR_F *color)
{ p->SetColor(color); }
