/* SPDX-License-Identifier: MIT
 * Whole-cluster shaping into a bounded GDI tile shared by all compositors.
 * No STL containers, retained layouts, external font files or GPU dependency.
 */
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include "nemo_cluster.h"
#include <dwrite.h>
#include <new>
#include <cstring>
#include <cmath>
#include <cstdio>
#include <cstdarg>
#include <float.h>

static const unsigned MAX_UNITS = 66; /* base plus 32 extensions, UTF-16 */
static const unsigned MAX_PIXELS = 65536; /* 256 KiB raster scratch */
typedef HRESULT (WINAPI *CreateFactory)(DWRITE_FACTORY_TYPE, REFIID, IUnknown **);
typedef int (WINAPI *Normalize)(NORM_FORM, LPCWSTR, int, LPWSTR, int);

template<class T> static void release(T *&p) { if (p) p->Release(); p=nullptr; }

struct NemoClusterRenderer final : IDWriteTextRenderer {
    ULONG refs=1;
    bool attempted=false;
    HMODULE library=nullptr, normaliz=nullptr;
    Normalize normalize=nullptr;
    IDWriteFactory *factory=nullptr;
    IDWriteGdiInterop *interop=nullptr;
    IDWriteRenderingParams *params=nullptr;
    IDWriteBitmapRenderTarget *target=nullptr;
    IDWriteTextFormat *format=nullptr;
    LOGFONTW font{};
    FLOAT em=0;
    unsigned width=0,height=0;
    COLORREF colour=0;
    bool shadow_bold=false;
    FLOAT draw_scale=1;
    HANDLE trace=INVALID_HANDLE_VALUE;
    unsigned trace_count=0;
    bool trace_glyph=false;

    void trace_line(const char *pattern, ...) {
        if (trace==INVALID_HANDLE_VALUE) return;
        char line[2048];va_list args;va_start(args,pattern);
        int n=std::vsnprintf(line,sizeof(line)-2,pattern,args);va_end(args);
        if (n<0) return;
        if (n>static_cast<int>(sizeof(line)-2)) n=sizeof(line)-2;
        line[n++]='\n';DWORD written;
        WriteFile(trace,line,n,&written,nullptr);
    }

    ~NemoClusterRenderer() {
        if (trace!=INVALID_HANDLE_VALUE) CloseHandle(trace);
        release(format);release(target);release(params);release(interop);release(factory);
        if (normaliz) FreeLibrary(normaliz);
        if (library) FreeLibrary(library);
    }
    bool init() {
        if (attempted) return factory && interop && params && normalize;
        attempted=true;
        /* Opt-in diagnostics for an owned test process. No trace file exists
         * in normal use, and only the first 64 selected clusters are logged. */
        wchar_t path[MAX_PATH];
        DWORD length=GetEnvironmentVariableW(L"NEMOTERM_CLUSTER_TRACE",path,MAX_PATH);
        if (length && length<MAX_PATH)
            trace=CreateFileW(path,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,
                nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
        library=LoadLibraryExW(L"dwrite.dll",nullptr,LOAD_LIBRARY_SEARCH_SYSTEM32);
        normaliz=LoadLibraryExW(L"normaliz.dll",nullptr,LOAD_LIBRARY_SEARCH_SYSTEM32);
        if (!library || !normaliz) return false;
        auto create=reinterpret_cast<CreateFactory>(GetProcAddress(library,"DWriteCreateFactory"));
        normalize=reinterpret_cast<Normalize>(GetProcAddress(normaliz,"NormalizeString"));
        return create && normalize && SUCCEEDED(create(DWRITE_FACTORY_TYPE_SHARED,
            __uuidof(IDWriteFactory),reinterpret_cast<IUnknown **>(&factory))) &&
            SUCCEEDED(factory->GetGdiInterop(&interop)) &&
            SUCCEEDED(factory->CreateRenderingParams(&params));
    }
    bool select_font(HDC dc) {
        LOGFONTW next{};TEXTMETRICW metrics{};
        if (!GetObjectW(GetCurrentObject(dc,OBJ_FONT),sizeof(next),&next) ||
            !GetTextMetricsW(dc,&metrics)) return false;
        FLOAT size=static_cast<FLOAT>(metrics.tmHeight-metrics.tmInternalLeading);
        if (size<=0 || size>2048) return false;
        if (format && size==em && !std::memcmp(&font,&next,sizeof(font))) return true;
        release(format);
        IDWriteFont *face=nullptr;
        IDWriteFontFamily *family=nullptr;
        IDWriteLocalizedStrings *names=nullptr;
        wchar_t name[256]{};
        HRESULT hr=interop->CreateFontFromLOGFONT(&next,&face);
        if (SUCCEEDED(hr)) hr=face->GetFontFamily(&family);
        if (SUCCEEDED(hr)) hr=family->GetFamilyNames(&names);
        if (SUCCEEDED(hr)) hr=names->GetString(0,name,256);
        if (SUCCEEDED(hr)) hr=factory->CreateTextFormat(name,nullptr,face->GetWeight(),
            face->GetStyle(),face->GetStretch(),size,L"en-us",&format);
        release(names);release(family);release(face);
        /* Legacy bitmap font names may not exist in DirectWrite. Keep that
         * font for ordinary GDI runs; use a system mono face for this cluster. */
        if (FAILED(hr)) hr=factory->CreateTextFormat(L"Consolas",nullptr,
            static_cast<DWRITE_FONT_WEIGHT>(next.lfWeight),
            next.lfItalic?DWRITE_FONT_STYLE_ITALIC:DWRITE_FONT_STYLE_NORMAL,
            DWRITE_FONT_STRETCH_NORMAL,size,L"en-us",&format);
        if (FAILED(hr) || FAILED(format->SetWordWrapping(DWRITE_WORD_WRAPPING_NO_WRAP))) {
            release(format);return false;
        }
        font=next;em=size;return true;
    }
    bool resize(HDC dc, unsigned w, unsigned h) {
        if (width==w && height==h && target) return true;
        /* Release before allocating, including shrink: never retain a larger
         * old tile, and never need two raster tiles during font changes. */
        release(target);width=height=0;
        if (FAILED(interop->CreateBitmapRenderTarget(dc,w,h,&target))) return false;
        if (FAILED(target->SetPixelsPerDip(1))) {release(target);return false;}
        width=w;height=h;return true;
    }
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID iid, void **out) override {
        if (!out) return E_POINTER;
        *out=nullptr;
        if (iid==__uuidof(IUnknown) || iid==__uuidof(IDWritePixelSnapping) ||
            iid==__uuidof(IDWriteTextRenderer)) {
            *out=static_cast<IDWriteTextRenderer *>(this);AddRef();return S_OK;
        }
        return E_NOINTERFACE;
    }
    ULONG STDMETHODCALLTYPE AddRef() override {return ++refs;}
    /* Owned by the terminal, like the stack renderer in Microsoft's sample. */
    ULONG STDMETHODCALLTYPE Release() override {return --refs;}
    HRESULT STDMETHODCALLTYPE IsPixelSnappingDisabled(void*,BOOL *p) override {*p=FALSE;return S_OK;}
    HRESULT STDMETHODCALLTYPE GetCurrentTransform(void*,DWRITE_MATRIX *p) override {return target->GetCurrentTransform(p);}
    HRESULT STDMETHODCALLTYPE GetPixelsPerDip(void*,FLOAT *p) override {*p=1;return S_OK;}
    HRESULT STDMETHODCALLTYPE DrawGlyphRun(void*,FLOAT x,FLOAT y,DWRITE_MEASURING_MODE mode,
        const DWRITE_GLYPH_RUN *run,const DWRITE_GLYPH_RUN_DESCRIPTION*,IUnknown*) override {
        if (trace_glyph) {
            trace_line("glyph x=%a y=%a mode=%u em=%a count=%u sideways=%u bidi=%u face=%u",
                static_cast<double>(x),static_cast<double>(y),static_cast<unsigned>(mode),
                static_cast<double>(run->fontEmSize),run->glyphCount,run->isSideways,
                run->bidiLevel,run->fontFace->GetIndex());
            for (unsigned i=0;i<run->glyphCount && i<16;i++)
                trace_line("glyph-item id=%u advance=%a offset=%a,%a",run->glyphIndices[i],
                    run->glyphAdvances?static_cast<double>(run->glyphAdvances[i]):0,
                    run->glyphOffsets?static_cast<double>(run->glyphOffsets[i].advanceOffset):0,
                    run->glyphOffsets?static_cast<double>(run->glyphOffsets[i].ascenderOffset):0);
            IDWriteFontFile *files[4]{};UINT32 count=0;
            HRESULT file_hr=run->fontFace->GetFiles(&count,nullptr);
            if (SUCCEEDED(file_hr) && count<=4 && SUCCEEDED(run->fontFace->GetFiles(&count,files))) {
                for (unsigned i=0;i<count;i++) {
                    const void *key=nullptr;UINT32 key_size=0;
                    IDWriteFontFileLoader *loader=nullptr;IDWriteLocalFontFileLoader *local=nullptr;
                    HRESULT hr=files[i]->GetReferenceKey(&key,&key_size);
                    if (SUCCEEDED(hr)) hr=files[i]->GetLoader(&loader);
                    if (SUCCEEDED(hr)) hr=loader->QueryInterface(__uuidof(IDWriteLocalFontFileLoader),reinterpret_cast<void **>(&local));
                    wchar_t path[512];UINT32 length=0;
                    if (SUCCEEDED(hr)) hr=local->GetFilePathLengthFromKey(key,key_size,&length);
                    if (SUCCEEDED(hr) && length<512 && SUCCEEDED(local->GetFilePathFromKey(key,key_size,path,512))) {
                        char utf8[1024]{};WideCharToMultiByte(CP_UTF8,0,path,-1,utf8,sizeof(utf8),nullptr,nullptr);
                        trace_line("font-file %s",utf8);
                    } else trace_line("font-file loader-hr=%lx key-bytes=%u",static_cast<unsigned long>(hr),key_size);
                    release(local);release(loader);release(files[i]);
                }
            }
        }
        HRESULT hr=target->DrawGlyphRun(x,y,mode,run,params,colour,nullptr);
        if (SUCCEEDED(hr) && shadow_bold)
            hr=target->DrawGlyphRun(x-1/draw_scale,y,mode,run,params,colour,nullptr);
        return hr;
    }
    HRESULT STDMETHODCALLTYPE DrawUnderline(void*,FLOAT,FLOAT,const DWRITE_UNDERLINE*,IUnknown*) override {return S_OK;}
    HRESULT STDMETHODCALLTYPE DrawStrikethrough(void*,FLOAT,FLOAT,const DWRITE_STRIKETHROUGH*,IUnknown*) override {return S_OK;}
    HRESULT STDMETHODCALLTYPE DrawInlineObject(void*,FLOAT,FLOAT,IDWriteInlineObject*,BOOL,BOOL,IUnknown*) override {return E_NOTIMPL;}
};

bool nemo_cluster_draw(NemoClusterRenderer **slot, HDC dc, const RECT *box,
                      const wchar_t *text, unsigned units, int y_offset,
                      COLORREF fg, COLORREF bg, bool emoji,
                      float horizontal_scale, bool shadow_bold)
{
    if (!slot || !dc || !box || !text || !units || units>MAX_UNITS) return false;
    if (!std::isfinite(horizontal_scale) || horizontal_scale<=0 || horizontal_scale>2) return false;
    const long long w=static_cast<long long>(box->right)-box->left;
    const long long h=static_cast<long long>(box->bottom)-box->top;
    if (w<=0 || h<=0 || w>1024 || h>1024 || w*h>MAX_PIXELS) return false;
    /* Reject invalid UTF-16 and controls, rather than letting layout create
     * paragraphs, extra lines or a glyph outside this cell's contract. */
    for (unsigned i=0;i<units;i++) {
        unsigned c=text[i];
        if (c>=0xd800 && c<=0xdbff) {
            if (++i==units || text[i]<0xdc00 || text[i]>0xdfff) return false;
        } else if ((c>=0xdc00 && c<=0xdfff) || c<32 || (c>=127 && c<160) ||
                   c==0x2028 || c==0x2029) return false;
    }
    if (!*slot) {
        void *storage=HeapAlloc(GetProcessHeap(),0,sizeof(NemoClusterRenderer));
        if (storage) *slot=new(storage) NemoClusterRenderer;
    }
    if (!*slot) return false;
    auto &s=**slot;
    if (!s.init() || !s.select_font(dc) || !s.resize(dc,static_cast<unsigned>(w),static_cast<unsigned>(h))) return false;
    wchar_t normalized[MAX_UNITS*4];
    int length=s.normalize(NormalizationC,text,units,normalized,MAX_UNITS*4);
    if (length<=0 || length>static_cast<int>(MAX_UNITS*4)) return false;
    IDWriteTextLayout *layout=nullptr;
    HRESULT hr=s.factory->CreateTextLayout(normalized,length,s.format,4096,4096,&layout);
    if (SUCCEEDED(hr) && emoji) {
        const DWRITE_TEXT_RANGE all={0,static_cast<UINT32>(length)};
        hr=layout->SetFontFamilyName(L"Segoe UI Emoji",all);
        if (SUCCEEDED(hr)) hr=layout->SetFontWeight(DWRITE_FONT_WEIGHT_NORMAL,all);
    }
    DWRITE_TEXT_METRICS measured{};DWRITE_LINE_METRICS line{};UINT32 count=0;
    if (SUCCEEDED(hr)) hr=layout->GetMetrics(&measured);
    if (SUCCEEDED(hr)) hr=layout->GetLineMetrics(&line,1,&count);
    TEXTMETRICW native{};
    if (SUCCEEDED(hr) && (!GetTextMetricsW(dc,&native) || count!=1 ||
        !std::isfinite(measured.widthIncludingTrailingWhitespace))) hr=E_FAIL;
    if (SUCCEEDED(hr)) {
        FLOAT natural=measured.widthIncludingTrailingWhitespace;
        FLOAT scale=natural*horizontal_scale>w ? static_cast<FLOAT>(w)/natural : horizontal_scale;
        FLOAT advance=natural*scale;
        DWRITE_MATRIX transform={scale,0,0,1,(static_cast<FLOAT>(w)-advance)/2,0};
        hr=s.target->SetCurrentTransform(&transform);
        HDC tile=s.target->GetMemoryDC();
        RECT rect={0,0,static_cast<LONG>(w),static_cast<LONG>(h)};
        SetDCBrushColor(tile,bg);
        if (!FillRect(tile,&rect,static_cast<HBRUSH>(GetStockObject(DC_BRUSH)))) hr=E_FAIL;
        /* DirectWrite writes the DIB directly. Finish queued GDI background
         * drawing before crossing that boundary. */
        if (!GdiFlush()) hr=E_FAIL;
        s.colour=fg;s.shadow_bold=shadow_bold;s.draw_scale=scale;
        s.trace_glyph=s.trace!=INVALID_HANDLE_VALUE && s.trace_count<64 &&
            units==2 && (text[0]==L'A' || text[0]==L'e') && (text[1]==0x308 || text[1]==0x301);
        if (s.trace_glyph) {
            s.trace_count++;
            s.trace_line("normalized first=%04x length=%d",static_cast<unsigned>(normalized[0]),length);
            char face[256]{};WideCharToMultiByte(CP_UTF8,0,s.font.lfFaceName,-1,face,sizeof(face),nullptr,nullptr);
            s.trace_line("cluster id=%u text=%04x,%04x box=%ld,%ld,%ld,%ld font=%s height=%ld width=%ld weight=%ld italic=%u quality=%u charset=%u em=%a natural=%a scale=%a dx=%a baseline=%a ascent=%ld internal=%ld offset=%d fg=%lx bg=%lx fp=%x",
                s.trace_count,static_cast<unsigned>(text[0]),static_cast<unsigned>(text[1]),
                box->left,box->top,box->right,box->bottom,face,s.font.lfHeight,s.font.lfWidth,s.font.lfWeight,
                s.font.lfItalic,s.font.lfQuality,s.font.lfCharSet,static_cast<double>(s.em),
                static_cast<double>(natural),static_cast<double>(scale),static_cast<double>(transform.dx),
                static_cast<double>(line.baseline),native.tmAscent,native.tmInternalLeading,y_offset,fg,bg,
                static_cast<unsigned>(_controlfp(0,0)));
            s.trace_line("params gamma=%a contrast=%a cleartype=%a geometry=%u mode=%u",
                static_cast<double>(s.params->GetGamma()),static_cast<double>(s.params->GetEnhancedContrast()),
                static_cast<double>(s.params->GetClearTypeLevel()),static_cast<unsigned>(s.params->GetPixelGeometry()),
                static_cast<unsigned>(s.params->GetRenderingMode()));
        }
        if (SUCCEEDED(hr)) hr=layout->Draw(nullptr,&s,0,
            static_cast<FLOAT>(native.tmAscent+y_offset)-line.baseline);
        if (s.trace_glyph) {
            DIBSECTION dib{};
            if (GetObjectW(GetCurrentObject(tile,OBJ_BITMAP),sizeof(dib),&dib) && dib.dsBm.bmBits) {
                const auto *pixels=static_cast<const unsigned *>(dib.dsBm.bmBits);
                unsigned long long hash=14695981039346656037ULL;
                for (long long i=0;i<w*h;i++) hash=(hash^(pixels[i]&0xffffff))*1099511628211ULL;
                s.trace_line("tile hash=%llx hr=%lx",hash,static_cast<unsigned long>(hr));
            }
        }
        s.trace_glyph=false;
        /* The destination's viewport/clip belongs to the caller (including
         * snapshot bands and GPU cache tiles); BitBlt respects both. */
        if (SUCCEEDED(hr) && !BitBlt(dc,box->left,box->top,static_cast<int>(w),
            static_cast<int>(h),tile,0,0,SRCCOPY)) hr=E_FAIL;
        /* Complete the copy before another cluster reuses the source tile. */
        if (!GdiFlush()) hr=E_FAIL;
    }
    release(layout);
    return SUCCEEDED(hr);
}

void nemo_cluster_free(NemoClusterRenderer **p)
{
    if (p && *p) {
        (*p)->~NemoClusterRenderer();
        HeapFree(GetProcessHeap(),0,*p);
        *p=nullptr;
    }
}
size_t nemo_cluster_raster_bytes(const NemoClusterRenderer *p)
{return p?static_cast<size_t>(p->width)*p->height*4:0;}
