/* SPDX-License-Identifier: MIT
 * The Microsoft SDK's C declarations leave Direct2D COM types opaque.
 * Keep SDK method calls in one C++ unit, with a C ABI for the compositor.
 * No STL, allocation, exception handling or copied COM vtable is needed. */
#ifndef NEMO_D2D_API_H
#define NEMO_D2D_API_H
#include <d2d1.h>
#ifdef __cplusplus
extern "C" {
#endif
void nemo_d2d_release(void *object);
HRESULT nemo_d2d_query(void *object, const GUID *iid, void **out);
HRESULT nemo_d2d_create_hwnd(ID2D1Factory *, const D2D1_RENDER_TARGET_PROPERTIES *,
    const D2D1_HWND_RENDER_TARGET_PROPERTIES *, ID2D1HwndRenderTarget **);
UINT32 nemo_d2d_max_size(ID2D1RenderTarget *);
HRESULT nemo_d2d_resize(ID2D1HwndRenderTarget *, const D2D1_SIZE_U *);
HRESULT nemo_d2d_compatible(ID2D1RenderTarget *, const D2D1_SIZE_F *,
    const D2D1_SIZE_U *, const D2D1_PIXEL_FORMAT *, D2D1_COMPATIBLE_RENDER_TARGET_OPTIONS,
    ID2D1BitmapRenderTarget **);
HRESULT nemo_d2d_get_bitmap(ID2D1BitmapRenderTarget *, ID2D1Bitmap **);
HRESULT nemo_d2d_solid_brush(ID2D1RenderTarget *, const D2D1_COLOR_F *,
    const D2D1_BRUSH_PROPERTIES *, ID2D1SolidColorBrush **);
void nemo_d2d_antialias(ID2D1RenderTarget *, D2D1_ANTIALIAS_MODE);
void nemo_d2d_begin(ID2D1RenderTarget *);
HRESULT nemo_d2d_end(ID2D1RenderTarget *, D2D1_TAG *, D2D1_TAG *);
void nemo_d2d_clear(ID2D1RenderTarget *, const D2D1_COLOR_F *);
void nemo_d2d_draw_bitmap(ID2D1RenderTarget *, ID2D1Bitmap *, const D2D1_RECT_F *,
    FLOAT, D2D1_BITMAP_INTERPOLATION_MODE, const D2D1_RECT_F *);
HRESULT nemo_d2d_get_dc(ID2D1GdiInteropRenderTarget *, D2D1_DC_INITIALIZE_MODE, HDC *);
HRESULT nemo_d2d_release_dc(ID2D1GdiInteropRenderTarget *, const RECT *);
HRESULT nemo_d2d_create_bitmap(ID2D1RenderTarget *, D2D1_SIZE_U, const void *, UINT32,
    const D2D1_BITMAP_PROPERTIES *, ID2D1Bitmap **);
HRESULT nemo_d2d_copy_memory(ID2D1Bitmap *, const D2D1_RECT_U *, const void *, UINT32);
void nemo_d2d_fill(ID2D1RenderTarget *, const D2D1_RECT_F *, ID2D1Brush *);
void nemo_d2d_set_color(ID2D1SolidColorBrush *, const D2D1_COLOR_F *);
#ifdef __cplusplus
}
#endif
#endif
