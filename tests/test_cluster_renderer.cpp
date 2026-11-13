/* SPDX-License-Identifier: MIT
 * Offscreen native DirectWrite/GDI cluster integration; no window/input. */
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include "nemo_cluster.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cwchar>
#include <cstdint>
#include <climits>

#define CHECK(x) do { if (!(x)) { std::fprintf(stderr,"%s:%d: %s (Win32 %lu)\n", \
    __FILE__,__LINE__,#x,GetLastError());std::exit(1); } } while (0)
static const uint32_t SENTINEL=0x004d2713;
static const int WIDTH=200,HEIGHT=200;

struct Surface {
    HDC dc;HBITMAP bitmap;HGDIOBJ old;uint32_t *pixels;
    Surface() {
        dc=CreateCompatibleDC(nullptr);CHECK(dc);
        BITMAPINFO bi{};bi.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);
        bi.bmiHeader.biWidth=WIDTH;bi.bmiHeader.biHeight=-HEIGHT;
        bi.bmiHeader.biPlanes=1;bi.bmiHeader.biBitCount=32;
        void *bits=nullptr;
        bitmap=CreateDIBSection(dc,&bi,DIB_RGB_COLORS,&bits,nullptr,0);CHECK(bitmap && bits);
        pixels=static_cast<uint32_t *>(bits);old=SelectObject(dc,bitmap);CHECK(old);
    }
    void clear() {GdiFlush();for (int i=0;i<WIDTH*HEIGHT;i++) pixels[i]=SENTINEL;}
    ~Surface() {SelectObject(dc,old);DeleteObject(bitmap);DeleteDC(dc);}
};
static void outside_unchanged(Surface &s,RECT box)
{
    GdiFlush();unsigned ink=0;
    for (int y=0;y<HEIGHT;y++) for (int x=0;x<WIDTH;x++) {
        uint32_t pixel=s.pixels[y*WIDTH+x]&0xffffff;
        if (x<box.left || x>=box.right || y<box.top || y>=box.bottom) CHECK(pixel==SENTINEL);
        else ink+=pixel!=0;
    }
    CHECK(ink>0);
}
static bool draw(NemoClusterRenderer **r,Surface &s,RECT box,const wchar_t *text,
                 bool emoji=false,int offset=0,float scale=1,bool bold=false,
                 bool transparent=false)
{
    return nemo_cluster_draw(r,s.dc,&box,text,static_cast<unsigned>(std::wcslen(text)),
        offset,RGB(245,220,190),RGB(0,0,0),emoji,scale,bold,transparent);
}
static int ink_width(Surface &s,RECT box)
{
    GdiFlush();int lo=box.right,hi=box.left;
    for (int y=box.top;y<box.bottom;y++) for (int x=box.left;x<box.right;x++)
        if (s.pixels[y*WIDTH+x]&0xffffff) {if(x<lo)lo=x;if(x>hi)hi=x;}
    return hi>=lo?hi-lo+1:0;
}

int main()
{
    Surface a,b;NemoClusterRenderer *renderer=nullptr;
    RECT box={30,40,78,80};
    a.clear();
    wchar_t long_text[68];for (auto &c:long_text) c=L'a';
    CHECK(!nemo_cluster_draw(&renderer,a.dc,&box,long_text,68,0,0,0,false,1,false,false));
    CHECK(!draw(&renderer,a,box,L"\xd800"));
    CHECK(!draw(&renderer,a,box,L"a\n"));
    CHECK(!draw(&renderer,a,box,L"\x2028"));
    RECT huge={LONG_MIN,0,LONG_MAX,10};CHECK(!draw(&renderer,a,huge,L"a"));
    RECT too_big={0,0,1024,1024};CHECK(!draw(&renderer,a,too_big,L"a"));
    CHECK(renderer==nullptr);
    const wchar_t *fonts[]={L"SarasaTermSC Nerd Font Light",L"Consolas",L"Courier"};
    const wchar_t *samples[]={L"e\x301",L"\x1100\x1161\x11a8",L"\x915\x94d\x937",
        L"\U0001f44d\U0001f3fd",L"\U0001f469\x200d\U0001f4bb",
        L"\U0001f468\x200d\U0001f469\x200d\U0001f467\x200d\U0001f466",
        L"\U0001f1e6\U0001f1fa",L"1\xfe0f\x20e3",L"\x2764\xfe0f"};
    for (auto font_name:fonts) {
        HFONT font=CreateFontW(-28,0,0,0,FW_LIGHT,FALSE,FALSE,FALSE,DEFAULT_CHARSET,
            OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,DEFAULT_QUALITY,FIXED_PITCH,font_name);
        CHECK(font);auto old=SelectObject(a.dc,font);auto old_b=SelectObject(b.dc,font);
        for (unsigned i=0;i<sizeof(samples)/sizeof(*samples);i++) {
            a.clear();CHECK(draw(&renderer,a,box,samples[i],i>=3));
            outside_unchanged(a,box);CHECK(nemo_cluster_raster_bytes(renderer)==48*40*4);
        }
        /* A missing glyph must not be mistaken for success merely because
         * every compositor paints the same empty cell or replacement box. */
        const wchar_t *rtl[]={L"\x5d0",L"\x5d1",L"\x5d2",L"\xfe8d",L"\xfe91",L"\xfe96"};
        unsigned long long hashes[6]{};
        for (unsigned i=0;i<6;i++) {
            a.clear();CHECK(draw(&renderer,a,box,rtl[i]));GdiFlush();
            outside_unchanged(a,box);
            unsigned long long hash=14695981039346656037ULL;
            for (int y=box.top;y<box.bottom;y++) for (int x=box.left;x<box.right;x++)
                hash=(hash^(a.pixels[y*WIDTH+x]&0xffffff))*1099511628211ULL;
            for (unsigned j=0;j<i;j++) CHECK(hashes[j]!=hash);
            hashes[i]=hash;
        }
        /* Transparent fallback must preserve a pre-existing background and
         * all earlier ink, including the second pass used for shadow bold. */
        a.clear();CHECK(draw(&renderer,a,box,rtl[0],false,0,1,false,true));GdiFlush();
        outside_unchanged(a,box);
        unsigned changed=0,unchanged=0;
        for (int y=box.top;y<box.bottom;y++) for (int x=box.left;x<box.right;x++) {
            unsigned pixel=a.pixels[y*WIDTH+x]&0xffffff;
            changed+=pixel!=SENTINEL;unchanged+=pixel==SENTINEL;
            for (unsigned shift=0;shift<24;shift+=8)
                CHECK(((pixel>>shift)&255)>=((SENTINEL>>shift)&255));
        }
        CHECK(changed && unchanged);
        CHECK(BitBlt(b.dc,0,0,WIDTH,HEIGHT,a.dc,0,0,SRCCOPY));GdiFlush();
        RECT shifted=box;shifted.left--;shifted.right--;
        CHECK(draw(&renderer,a,shifted,rtl[0],false,0,1,false,true));GdiFlush();
        for (int i=0;i<WIDTH*HEIGHT;i++) for (unsigned shift=0;shift<24;shift+=8)
            CHECK(((a.pixels[i]>>shift)&255)>=((b.pixels[i]>>shift)&255));
        /* Reuse a single-letter layout on a different destination/geometry.
         * It must match a fresh renderer, also after the selected font changes.
         * More than 32 distinct letters exercise bounded-cache replacement. */
        for (unsigned i=0;i<80;i++) {
            wchar_t text[]={static_cast<wchar_t>(0x5d0+i),0};
            a.clear();CHECK(draw(&renderer,a,box,text,false,0,1,false,true));
        }
        a.clear();CHECK(draw(&renderer,a,box,rtl[0],false,0,1,false,true));
        NemoClusterRenderer *fresh=nullptr;
        RECT narrow={12,15,43,54};a.clear();b.clear();
        CHECK(draw(&renderer,a,narrow,rtl[0],false,2,.75f,true,true));
        CHECK(draw(&fresh,b,narrow,rtl[0],false,2,.75f,true,true));GdiFlush();
        CHECK(std::memcmp(a.pixels,b.pixels,WIDTH*HEIGHT*4)==0);
        nemo_cluster_free(&fresh);
        /* A normalized rendering copy must make decomposed text identical
         * to its canonical equivalent, without modifying the input. */
        for (unsigned i=0;i<2;i++) {
            const wchar_t *original=i?samples[1]:samples[0];
            wchar_t saved[16]{};std::wcscpy(saved,original);
            a.clear();b.clear();CHECK(draw(&renderer,a,box,saved));
            CHECK(draw(&renderer,b,box,i?L"\xac01":L"\xe9"));GdiFlush();
            CHECK(std::wcscmp(saved,original)==0);
            CHECK(std::memcmp(a.pixels,b.pixels,WIDTH*HEIGHT*4)==0);
        }
        RECT wide={10,10,106,60};
        a.clear();b.clear();CHECK(draw(&renderer,a,wide,samples[0]));
        CHECK(draw(&renderer,b,wide,samples[0],false,0,2));
        CHECK(ink_width(b,wide)>ink_width(a,wide)*1.5);
        b.clear();CHECK(draw(&renderer,b,wide,samples[0],false,0,1,true));GdiFlush();
        CHECK(std::memcmp(a.pixels,b.pixels,WIDTH*HEIGHT*4)!=0);
        /* Destination clip and viewport transforms are used by both GPU
         * run caching and bounded synchronized-output snapshot bands. */
        a.clear();int saved=SaveDC(a.dc);CHECK(saved);
        CHECK(SetViewportOrgEx(a.dc,7,9,nullptr));
        CHECK(IntersectClipRect(a.dc,34,42,76,78)!=ERROR);
        CHECK(draw(&renderer,a,box,samples[4],true));RestoreDC(a.dc,saved);
        outside_unchanged(a,RECT{41,51,83,87});
        /* Reusing one scratch tile across deferred destination copies must
         * match a controller that explicitly finishes every individual copy. */
        a.clear();b.clear();
        for (int pass=0;pass<2;pass++) for (int i=0;i<16;i++) {
            RECT cell={(i%4)*48,(i/4)*40,(i%4+1)*48,(i/4+1)*40};
            const wchar_t *text=i%2?L"A\x308":samples[0];
            CHECK(draw(&renderer,pass?b:a,cell,text));
            if (pass) GdiFlush();
        }
        GdiFlush();CHECK(std::memcmp(a.pixels,b.pixels,WIDTH*HEIGHT*4)==0);
        SelectObject(a.dc,old);SelectObject(b.dc,old_b);CHECK(DeleteObject(font));
    }

    /* GDI's FW_DONTCARE (0) is valid for a legacy bitmap face, whereas
     * DirectWrite's fallback format requires an actual nonzero weight. */
    HFONT raster=CreateFontW(-16,0,0,0,FW_DONTCARE,FALSE,FALSE,FALSE,DEFAULT_CHARSET,
        OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,DEFAULT_QUALITY,FIXED_PITCH,L"Courier");
    CHECK(raster);auto raster_old=SelectObject(a.dc,raster);
    a.clear();CHECK(draw(&renderer,a,box,L"\x5d0"));outside_unchanged(a,box);
    a.clear();CHECK(draw(&renderer,a,box,L"e\x301"));outside_unchanged(a,box);
    SelectObject(a.dc,raster_old);CHECK(DeleteObject(raster));

    HFONT tall=CreateFontW(-48,0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,
        OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,DEFAULT_QUALITY,FIXED_PITCH,L"Consolas");
    CHECK(tall);auto old_a=SelectObject(a.dc,tall);auto old_b=SelectObject(b.dc,tall);
    TEXTMETRICW metrics{};CHECK(GetTextMetricsW(a.dc,&metrics));
    int height=metrics.tmHeight, half=height/2;
    RECT full={10,10,106,10+height},top={10,10,106,10+half},bottom={10,10+half,106,10+height};
    a.clear();b.clear();CHECK(draw(&renderer,a,full,samples[4],true));
    CHECK(draw(&renderer,b,top,samples[4],true));
    CHECK(draw(&renderer,b,bottom,samples[4],true,-half));GdiFlush();
    CHECK(std::memcmp(a.pixels,b.pixels,WIDTH*HEIGHT*4)==0);
    DWORD handles=GetGuiResources(GetCurrentProcess(),GR_GDIOBJECTS);
    for (unsigned i=0;i<100;i++) {
        RECT size={0,0,static_cast<LONG>(30+i%7),static_cast<LONG>(40+i%5)};
        CHECK(draw(&renderer,a,size,samples[i%9],i%9>=3));
        CHECK(nemo_cluster_raster_bytes(renderer)<=65536*4);
    }
    CHECK(GetGuiResources(GetCurrentProcess(),GR_GDIOBJECTS)<=handles);
    /* Independent tabs share the isolated font cache. Destroying its first
     * user must leave the remaining renderer and its layouts usable. */
    NemoClusterRenderer *sibling=nullptr;
    a.clear();b.clear();CHECK(draw(&renderer,a,full,samples[4],true));
    CHECK(draw(&sibling,b,full,samples[4],true));GdiFlush();
    CHECK(std::memcmp(a.pixels,b.pixels,WIDTH*HEIGHT*4)==0);
    nemo_cluster_free(&renderer);CHECK(!renderer);nemo_cluster_free(&renderer);
    b.clear();CHECK(draw(&sibling,b,full,samples[4],true));GdiFlush();
    CHECK(std::memcmp(a.pixels,b.pixels,WIDTH*HEIGHT*4)==0);
    nemo_cluster_free(&sibling);
    /* A new owner after the last close recreates the cache cleanly. */
    b.clear();CHECK(draw(&renderer,b,full,samples[4],true));GdiFlush();
    CHECK(std::memcmp(a.pixels,b.pixels,WIDTH*HEIGHT*4)==0);
    nemo_cluster_free(&renderer);
    SelectObject(a.dc,old_a);SelectObject(b.dc,old_b);CHECK(DeleteObject(tall));
    std::puts("Cluster renderer: system fallback, NFC, bounded cells, clipping, double-height and handle lifetime passed");
    return 0;
}
