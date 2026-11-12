/* SPDX-License-Identifier: MIT
 * Offscreen system DirectWrite probe. No product integration or GUI input.
 * Build with g++ -std=c++17 -O2 -static-libgcc -static-libstdc++ this-file.cpp
 * -ldwrite -lole32 -lgdi32 -luser32 -lpsapi -luuid -lnormaliz -o probe.exe
 * Run probe.exe output.bmp > output.jsonl. Measurements describe this probe.
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <dwrite.h>
#include <psapi.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cwchar>

static void check(HRESULT hr) {
    if (FAILED(hr)) { std::fprintf(stderr,"HRESULT %08lx\n",(unsigned long)hr); std::exit(1); }
}
static void memory(const char *phase) {
    static ULONG_PTR entries[65537];
    if (!QueryWorkingSet(GetCurrentProcess(),entries,sizeof(entries))) std::exit(2);
    SIZE_T private_pages=0;
    for (ULONG_PTR i=0;i<entries[0];i++) private_pages+=!(entries[i+1]&256);
    PROCESS_MEMORY_COUNTERS_EX pc{};pc.cb=sizeof(pc);
    if (!GetProcessMemoryInfo(GetCurrentProcess(),reinterpret_cast<PROCESS_MEMORY_COUNTERS*>(&pc),sizeof(pc))) std::exit(2);
    std::printf("{\"phase\":\"%s\",\"private_ws\":%llu,\"total_ws\":%llu,\"private_commit\":%llu}\n",
        phase,(unsigned long long)private_pages*4096,(unsigned long long)entries[0]*4096,
        (unsigned long long)pc.PrivateUsage);
}

class Renderer final : public IDWriteTextRenderer {
    ULONG refs=1;
public:
    IDWriteBitmapRenderTarget *target;
    IDWriteRenderingParams *params;
    IDWriteGdiInterop *interop;
    const char *name="";
    Renderer(IDWriteBitmapRenderTarget *t,IDWriteRenderingParams *p,IDWriteGdiInterop *i):target(t),params(p),interop(i) {}
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID id,void **out) override {
        if (!out) return E_POINTER;
        *out=nullptr;
        if (id==__uuidof(IUnknown)||id==__uuidof(IDWritePixelSnapping)||id==__uuidof(IDWriteTextRenderer)) {
            *out=static_cast<IDWriteTextRenderer*>(this);AddRef();return S_OK;
        }
        return E_NOINTERFACE;
    }
    ULONG STDMETHODCALLTYPE AddRef() override {return ++refs;}
    ULONG STDMETHODCALLTYPE Release() override {return --refs;}
    HRESULT STDMETHODCALLTYPE IsPixelSnappingDisabled(void*,BOOL *value) override {*value=FALSE;return S_OK;}
    HRESULT STDMETHODCALLTYPE GetCurrentTransform(void*,DWRITE_MATRIX *value) override {return target->GetCurrentTransform(value);}
    HRESULT STDMETHODCALLTYPE GetPixelsPerDip(void*,FLOAT *value) override {*value=target->GetPixelsPerDip();return S_OK;}
    HRESULT STDMETHODCALLTYPE DrawGlyphRun(void*,FLOAT x,FLOAT y,DWRITE_MEASURING_MODE mode,
        const DWRITE_GLYPH_RUN *run,const DWRITE_GLYPH_RUN_DESCRIPTION*,IUnknown*) override {
        LOGFONTW face{};check(interop->ConvertFontFaceToLOGFONT(run->fontFace,&face));
        std::printf("{\"case\":\"%s\",\"face\":\"",name);
        for (const wchar_t *p=face.lfFaceName;*p;p++) std::printf("\\u%04x",(unsigned)*p);
        std::printf("\",\"glyphs\":[");
        for (UINT32 i=0;i<run->glyphCount;i++)
            std::printf("%s{\"id\":%u,\"advance\":%.4f}",i?",":"",run->glyphIndices[i],run->glyphAdvances[i]);
        std::puts("]}");
        return target->DrawGlyphRun(x,y,mode,run,params,RGB(235,235,235),nullptr);
    }
    HRESULT STDMETHODCALLTYPE DrawUnderline(void*,FLOAT,FLOAT,const DWRITE_UNDERLINE*,IUnknown*) override {return E_NOTIMPL;}
    HRESULT STDMETHODCALLTYPE DrawStrikethrough(void*,FLOAT,FLOAT,const DWRITE_STRIKETHROUGH*,IUnknown*) override {return E_NOTIMPL;}
    HRESULT STDMETHODCALLTYPE DrawInlineObject(void*,FLOAT,FLOAT,IDWriteInlineObject*,BOOL,BOOL,IUnknown*) override {return E_NOTIMPL;}
};

int main(int argc,char **argv) {
    if (argc!=2) return 1;
    check(CoInitializeEx(nullptr,COINIT_MULTITHREADED));
    memory("baseline");
    IDWriteFactory *factory=nullptr;
    check(DWriteCreateFactory(DWRITE_FACTORY_TYPE_SHARED,__uuidof(IDWriteFactory),reinterpret_cast<IUnknown**>(&factory)));
    IDWriteGdiInterop *interop=nullptr;check(factory->GetGdiInterop(&interop));
    IDWriteBitmapRenderTarget *target=nullptr;check(interop->CreateBitmapRenderTarget(nullptr,600,460,&target));
    check(target->SetPixelsPerDip(1));
    IDWriteRenderingParams *params=nullptr;check(factory->CreateRenderingParams(&params));
    IDWriteTextFormat *format=nullptr;
    check(factory->CreateTextFormat(L"SarasaTermSC Nerd Font",nullptr,DWRITE_FONT_WEIGHT_LIGHT,
        DWRITE_FONT_STYLE_NORMAL,DWRITE_FONT_STRETCH_NORMAL,24,L"zh-CN",&format));
    check(format->SetWordWrapping(DWRITE_WORD_WRAPPING_NO_WRAP));
    HDC dc=target->GetMemoryDC();PatBlt(dc,0,0,600,460,BLACKNESS);
    HFONT labels=CreateFontW(-14,0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,
        OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,DEFAULT_QUALITY,FIXED_PITCH,L"Consolas");
    HGDIOBJ oldfont=SelectObject(dc,labels);SetTextColor(dc,RGB(170,170,170));SetBkColor(dc,RGB(0,0,0));
    memory("factory-and-target");
    const struct {const char *name;const wchar_t *text;} cases[]={
        {"ascii",L"AB"},{"combining",L"e\u0301"},{"cjk",L"\u4e2d"},
        {"emoji",L"\U0001f642"},{"skin-tone",L"\U0001f44d\U0001f3fd"},
        {"zwj-profession",L"\U0001f469\u200d\U0001f4bb"},
        {"zwj-family",L"\U0001f468\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466"},
        {"flag",L"\U0001f1e6\U0001f1fa"},{"keycap",L"1\ufe0f\u20e3"},
        {"emoji-heart",L"\u2764\ufe0f"},{"text-heart",L"\u2764\ufe0e"},
        {"hangul-jamo",L"\u1100\u1161\u11a8"},{"indic",L"\u0915\u094d\u0937"}};
    Renderer renderer(target,params,interop);
    for (unsigned i=0;i<sizeof(cases)/sizeof(*cases);i++) {
        auto &item=cases[i];renderer.name=item.name;
        TextOutA(dc,8,12+i*34,item.name,(int)std::strlen(item.name));
        IDWriteTextLayout *layout=nullptr;
        check(factory->CreateTextLayout(item.text,(UINT32)std::wcslen(item.text),format,350,34,&layout));
        DWRITE_TEXT_METRICS metrics;check(layout->GetMetrics(&metrics));
        std::printf("{\"case\":\"%s\",\"layout_width\":%.4f}\n",item.name,metrics.width);
        check(layout->Draw(nullptr,&renderer,190,4+i*34));
        layout->Release();
        // Comparison only: normalize the rendering string, preserving the
        // original test text, and select the emoji face for the entire emoji
        // sequence instead of allowing fallback to split it between fonts.
        wchar_t normalized[128];
        int length=NormalizeString(NormalizationC,item.text,(int)std::wcslen(item.text),
                                   normalized,128);
        if (length<=0) return 5;
        check(factory->CreateTextLayout(normalized,(UINT32)length,format,200,34,&layout));
        bool emoji=i>=3 && i<=9;
        if (emoji) {
            check(layout->SetFontFamilyName(L"Segoe UI Emoji",DWRITE_TEXT_RANGE{0,(UINT32)length}));
            check(layout->SetFontWeight(DWRITE_FONT_WEIGHT_NORMAL,DWRITE_TEXT_RANGE{0,(UINT32)length}));
        }
        char cluster_name[64];std::snprintf(cluster_name,sizeof(cluster_name),"%s-cluster",item.name);
        renderer.name=cluster_name;
        check(layout->GetMetrics(&metrics));
        std::printf("{\"case\":\"%s\",\"layout_width\":%.4f,\"normalized_units\":%d,\"emoji_face\":%s}\n",
            cluster_name,metrics.width,length,emoji?"true":"false");
        check(layout->Draw(nullptr,&renderer,370,4+i*34));
        layout->Release();memory(item.name);
    }
    GdiFlush();
    // Copy into an explicitly top-down DIB: GetObject on DirectWrite's bitmap
    // does not preserve its internal scanline orientation in dsBmih.biHeight.
    BITMAPINFO bi{};bi.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);
    bi.bmiHeader.biWidth=600;bi.bmiHeader.biHeight=-460;
    bi.bmiHeader.biPlanes=1;bi.bmiHeader.biBitCount=32;bi.bmiHeader.biCompression=BI_RGB;
    void *pixels=nullptr;HDC copy=CreateCompatibleDC(dc);
    HBITMAP bitmap=CreateDIBSection(copy,&bi,DIB_RGB_COLORS,&pixels,nullptr,0);
    if (!copy||!bitmap||!pixels) return 3;
    HGDIOBJ oldbitmap=SelectObject(copy,bitmap);
    if (!BitBlt(copy,0,0,600,460,dc,0,0,SRCCOPY)) return 3;
    GdiFlush();
    BITMAPFILEHEADER file{};file.bfType=0x4d42;file.bfOffBits=sizeof(file)+sizeof(BITMAPINFOHEADER);
    BITMAPINFOHEADER info=bi.bmiHeader;info.biSizeImage=600*460*4;
    file.bfSize=file.bfOffBits+info.biSizeImage;
    FILE *out=std::fopen(argv[1],"wb");if (!out) return 4;
    std::fwrite(&file,sizeof(file),1,out);std::fwrite(&info,sizeof(info),1,out);
    std::fwrite(pixels,info.biSizeImage,1,out);std::fclose(out);
    SelectObject(copy,oldbitmap);DeleteObject(bitmap);DeleteDC(copy);
    SelectObject(dc,oldfont);DeleteObject(labels);
    format->Release();params->Release();target->Release();interop->Release();factory->Release();
    CoUninitialize();memory("released");
    return 0;
}
