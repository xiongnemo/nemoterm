/* SPDX-License-Identifier: MIT */
#define COBJMACROS
#include "putty.h"
#include <initguid.h>
#include <wincodec.h>
#include "nemo_wic.h"
#include "terminal/nemo_iterm.h"
#include "terminal/nemo_sixel.h"

static bool metadata_uint(IWICMetadataQueryReader *reader, const wchar_t *path,
                          unsigned fallback, unsigned *out)
{
    PROPVARIANT value = {0};
    HRESULT hr = IWICMetadataQueryReader_GetMetadataByName(reader, path, &value);
    bool ok = true;
    *out = fallback;
    if (SUCCEEDED(hr)) {
        switch (value.vt) {
          case VT_UI1: *out = value.bVal; break;
          case VT_UI2: *out = value.uiVal; break;
          case VT_UI4: *out = value.ulVal; break;
          case VT_BOOL: *out = value.boolVal != VARIANT_FALSE; break;
          default: ok = false; break;
        }
    }
    PropVariantClear(&value);
    return ok;
}

static unsigned gif_plays(IWICMetadataQueryReader *reader)
{
    for (unsigned i = 0; i < 256; i++) {
        wchar_t path[64];
        PROPVARIANT value = {0};
        swprintf(path, lenof(path), L"/[%u]appext/Application", i);
        HRESULT hr = IWICMetadataQueryReader_GetMetadataByName(reader, path, &value);
        bool match = SUCCEEDED(hr) && value.vt == (VT_UI1 | VT_VECTOR) &&
            value.caub.cElems == 11 &&
            (!memcmp(value.caub.pElems, "NETSCAPE2.0", 11) ||
             !memcmp(value.caub.pElems, "ANIMEXTS1.0", 11));
        PropVariantClear(&value);
        if (FAILED(hr)) break;
        if (!match) continue;
        swprintf(path, lenof(path), L"/[%u]appext/Data", i);
        hr = IWICMetadataQueryReader_GetMetadataByName(reader, path, &value);
        unsigned plays = 1;
        if (SUCCEEDED(hr) && value.vt == (VT_UI1 | VT_VECTOR) &&
            value.caub.cElems >= 4 && value.caub.pElems[0] == 3 &&
            value.caub.pElems[1] == 1) {
            unsigned repeats = value.caub.pElems[2] | (unsigned)value.caub.pElems[3] << 8;
            plays = repeats ? repeats+1 : 0;
        }
        PropVariantClear(&value);
        return plays;
    }
    return 1; /* No loop extension: one pass through the GIF data stream. */
}

static bool decode_gif(IWICImagingFactory *factory, IWICBitmapDecoder *decoder,
                       unsigned frames, NemoRaster *out, NemoRasterAdmission admit, void *ctx)
{
    IWICMetadataQueryReader *global = NULL, *metadata = NULL;
    IWICBitmapFrameDecode *frame = NULL;
    IWICFormatConverter *converter = NULL;
    IWICPalette *palette = NULL;
    unsigned width = 0, height = 0, background_index = 0;
    uint32_t background = 0, row[NEMO_SIXEL_MAX_DIMENSION];
    bool ok = false;
    NemoRasterComposer compose = {0};
#define GIF_TRY(call) do { if (FAILED(call)) goto done; } while (0)
    if (!frames || frames > NEMO_RASTER_MAX_FRAMES) return false;
    GIF_TRY(IWICBitmapDecoder_GetMetadataQueryReader(decoder, &global));
    if (!metadata_uint(global, L"/logscrdesc/Width", 0, &width) ||
        !metadata_uint(global, L"/logscrdesc/Height", 0, &height) ||
        !width || !height || width > NEMO_SIXEL_MAX_DIMENSION ||
        height > NEMO_SIXEL_MAX_DIMENSION) goto done;
    size_t bytes = nemo_raster_storage(width, height, frames);
    if (!bytes || bytes > NEMO_SIXEL_DEFAULT_BUDGET ||
        !admit(ctx, width, height, bytes) ||
        !nemo_raster_allocate(out, width, height, frames, bytes)) goto done;
    out->plays = gif_plays(global);
    if (metadata_uint(global, L"/logscrdesc/BackgroundColorIndex", 0, &background_index) &&
        SUCCEEDED(IWICImagingFactory_CreatePalette(factory, &palette)) &&
        SUCCEEDED(IWICBitmapDecoder_CopyPalette(decoder, palette))) {
        WICColor colours[256]; UINT count = 0;
        if (SUCCEEDED(IWICPalette_GetColors(palette, lenof(colours), colours, &count)) &&
            background_index < count) background = colours[background_index];
    }
    for (unsigned i = 0; i < frames; i++) {
        UINT fw = 0, fh = 0;
        unsigned left, top, disposal, delay, transparent;
        GIF_TRY(IWICBitmapDecoder_GetFrame(decoder, i, &frame));
        GIF_TRY(IWICBitmapFrameDecode_GetSize(frame, &fw, &fh));
        GIF_TRY(IWICBitmapFrameDecode_GetMetadataQueryReader(frame, &metadata));
        if (!metadata_uint(metadata, L"/imgdesc/Left", 0, &left) ||
            !metadata_uint(metadata, L"/imgdesc/Top", 0, &top) ||
            !metadata_uint(metadata, L"/grctlext/Disposal", 0, &disposal) ||
            !metadata_uint(metadata, L"/grctlext/Delay", 0, &delay) ||
            !metadata_uint(metadata, L"/grctlext/TransparencyFlag", 0, &transparent) ||
            !fw || !fh || left > width || top > height ||
            fw > width-left || fh > height-top || delay > 65535 || disposal > 3) goto done;
        if (!i) compose.background = transparent ? 0 : background;
        if (!nemo_raster_prepare(out, i, &compose)) goto done;
        GIF_TRY(IWICImagingFactory_CreateFormatConverter(factory, &converter));
        GIF_TRY(IWICFormatConverter_Initialize(converter, (IWICBitmapSource *)frame,
            &GUID_WICPixelFormat32bppBGRA, WICBitmapDitherTypeNone, NULL, 0,
            WICBitmapPaletteTypeCustom));
        for (unsigned y = 0; y < fh; y++) {
            WICRect rect = {0, (INT)y, (INT)fw, 1};
            GIF_TRY(IWICFormatConverter_CopyPixels(converter, &rect, fw*4, fw*4, (BYTE *)row));
            for (unsigned x = 0; x < fw; x++) {
                if (row[x] >> 24) out->frames[i].pixels[(size_t)(top+y)*width+left+x] = row[x];
            }
        }
        out->frames[i].delay_ms = delay*10;
        /* Transparent GIF disposal exposes the terminal underneath. Restore
         * previous must retain the preceding base and its clear colour. */
        if (disposal == 2) compose.background = transparent ? 0 : background;
        if (!nemo_raster_dispose(out, &compose, i, disposal, left, top, fw, fh)) goto done;
        IWICFormatConverter_Release(converter); converter = NULL;
        IWICMetadataQueryReader_Release(metadata); metadata = NULL;
        IWICBitmapFrameDecode_Release(frame); frame = NULL;
    }
    ok = true;
done:
    if (!ok) nemo_raster_free(out);
    if (converter) IWICFormatConverter_Release(converter);
    if (metadata) IWICMetadataQueryReader_Release(metadata);
    if (frame) IWICBitmapFrameDecode_Release(frame);
    if (palette) IWICPalette_Release(palette);
    if (global) IWICMetadataQueryReader_Release(global);
    return ok;
#undef GIF_TRY
}

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
    if (IsEqualGUID(&format, &GUID_ContainerFormatGif)) {
        ok = decode_gif(factory, decoder, frames, out, admit, ctx);
        goto done;
    }
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
