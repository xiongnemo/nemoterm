/* SPDX-License-Identifier: MIT */
#define COBJMACROS
#include "putty.h"
#include <initguid.h>
#include <wincodec.h>
#include "nemo_wic.h"
#include "terminal/nemo_iterm.h"
#include "terminal/nemo_sixel.h"

bool nemo_wic_decode(TermWin *win, const void *data, size_t length,
                     NemoRaster *out, NemoRasterAdmission admit, void *ctx)
{
    IWICImagingFactory *factory = NULL;
    IWICStream *stream = NULL;
    IWICBitmapDecoder *decoder = NULL;
    IWICBitmapFrameDecode *frame = NULL;
    IWICFormatConverter *converter = NULL;
    UINT width = 0, height = 0, frames = 0;
    GUID format;
    uint32_t *pixels = NULL;
    bool ok = false;
    (void)win;
    memset(out, 0, sizeof(*out));
    if (!data || !length || length > NEMO_ITERM_FILE_MAX || !admit) return false;
#define TRY(call) do { if (FAILED(call)) goto done; } while (0)
    TRY(CoCreateInstance(&CLSID_WICImagingFactory, NULL, CLSCTX_INPROC_SERVER,
                         &IID_IWICImagingFactory, (void **)&factory));
    TRY(IWICImagingFactory_CreateStream(factory, &stream));
    /* Synchronous borrowed stream: all WIC interfaces are released before
     * returning, while the transport's input buffer is still owned. */
    TRY(IWICStream_InitializeFromMemory(stream, (BYTE *)data, (DWORD)length));
    TRY(IWICImagingFactory_CreateDecoderFromStream(factory, (IStream *)stream,
        &GUID_VendorMicrosoft, WICDecodeMetadataCacheOnDemand, &decoder));
    TRY(IWICBitmapDecoder_GetContainerFormat(decoder, &format));
    if (!IsEqualGUID(&format, &GUID_ContainerFormatPng) &&
        !IsEqualGUID(&format, &GUID_ContainerFormatJpeg) &&
        !IsEqualGUID(&format, &GUID_ContainerFormatBmp) &&
        !IsEqualGUID(&format, &GUID_ContainerFormatGif)) goto done;
    TRY(IWICBitmapDecoder_GetFrameCount(decoder, &frames));
    /* Animation needs a bounded frame scheduler, not a silent first-frame
     * approximation. This decoder currently accepts single-frame images. */
    if (frames != 1) goto done;
    TRY(IWICBitmapDecoder_GetFrame(decoder, 0, &frame));
    TRY(IWICBitmapFrameDecode_GetSize(frame, &width, &height));
    if (!width || !height || width > NEMO_SIXEL_MAX_DIMENSION ||
        height > NEMO_SIXEL_MAX_DIMENSION ||
        (uint64_t)width * height * 4 > NEMO_SIXEL_DEFAULT_BUDGET) goto done;
    size_t bytes = (size_t)width * height * 4;
    if (!admit(ctx, width, height, bytes)) goto done;
    pixels = malloc(bytes);
    if (!pixels) goto done;
    TRY(IWICImagingFactory_CreateFormatConverter(factory, &converter));
    TRY(IWICFormatConverter_Initialize(converter, (IWICBitmapSource *)frame,
        &GUID_WICPixelFormat32bppBGRA, WICBitmapDitherTypeNone, NULL, 0,
        WICBitmapPaletteTypeCustom));
    TRY(IWICFormatConverter_CopyPixels(converter, NULL, width * 4,
                                      (UINT)bytes, (BYTE *)pixels));
    out->pixels = pixels; out->width = width; out->height = height;
    out->bytes = bytes;
    for (size_t i = 0; i < bytes / 4; i++) {
        unsigned alpha = pixels[i] >> 24;
        if (alpha && alpha != 255) { out->partial_alpha = true; break; }
    }
    pixels = NULL;
    ok = true;
done:
    free(pixels);
    if (converter) IWICFormatConverter_Release(converter);
    if (frame) IWICBitmapFrameDecode_Release(frame);
    if (decoder) IWICBitmapDecoder_Release(decoder);
    if (stream) IWICStream_Release(stream);
    if (factory) IWICImagingFactory_Release(factory);
    return ok;
#undef TRY
}
