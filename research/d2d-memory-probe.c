#define WIN32_LEAN_AND_MEAN
#define INITGUID
#include <windows.h>
#include <d2d1.h>
#include <psapi.h>
#include <stdio.h>
#include <stdlib.h>
static void sample(const char *phase) {
    static ULONG_PTR pages[65537];PROCESS_MEMORY_COUNTERS_EX pm={0};SYSTEM_INFO si;GetSystemInfo(&si);
    if (!QueryWorkingSet(GetCurrentProcess(),pages,sizeof(pages)) || !GetProcessMemoryInfo(GetCurrentProcess(),(void *)&pm,sizeof(pm))) exit(20);
    size_t priv=0;for(size_t i=1;i<=pages[0];i++) if (!(pages[i]&256)) priv+=si.dwPageSize;
    printf("{\"phase\":\"%s\",\"private_ws\":%zu,\"total_ws\":%zu,\"private_commit\":%zu}\n",phase,priv,(size_t)pm.WorkingSetSize,(size_t)pm.PrivateUsage);
}
#define CHECK(call) do {HRESULT hr=(call);if(FAILED(hr)){printf("{\"failure\":\"%s\",\"hresult\":\"%08lx\"}\n",#call,(unsigned long)hr);return 5;}}while(0)
int main(void) {
    HINSTANCE inst=GetModuleHandleW(NULL);WNDCLASSW wc={0};wc.lpfnWndProc=DefWindowProcW;wc.hInstance=inst;wc.lpszClassName=L"NemotermOwnedDirect2DProbe";
    if(!RegisterClassW(&wc))return 1;HWND window=CreateWindowW(wc.lpszClassName,L"",WS_OVERLAPPEDWINDOW,0,0,1280,960,NULL,NULL,inst,NULL);if(!window)return 2;
    sample("hidden-window-before-device");ID2D1Factory *factory=NULL;ID2D1HwndRenderTarget *hwndtarget=NULL;ID2D1BitmapRenderTarget *retained=NULL;ID2D1Bitmap *atlas=NULL;
    CHECK(D2D1CreateFactory(D2D1_FACTORY_TYPE_SINGLE_THREADED,&IID_ID2D1Factory,NULL,(void **)&factory));
    D2D1_RENDER_TARGET_PROPERTIES props={0};props.type=D2D1_RENDER_TARGET_TYPE_HARDWARE;props.pixelFormat.format=DXGI_FORMAT_B8G8R8A8_UNORM;props.pixelFormat.alphaMode=D2D1_ALPHA_MODE_IGNORE;props.dpiX=props.dpiY=96;
    D2D1_HWND_RENDER_TARGET_PROPERTIES win={0};win.hwnd=window;win.pixelSize.width=1280;win.pixelSize.height=960;
    CHECK(ID2D1Factory_CreateHwndRenderTarget(factory,&props,&win,&hwndtarget));
    D2D1_SIZE_U size={1280,960};CHECK(ID2D1RenderTarget_CreateCompatibleRenderTarget((ID2D1RenderTarget *)hwndtarget,NULL,&size,NULL,D2D1_COMPATIBLE_RENDER_TARGET_OPTIONS_GDI_COMPATIBLE,&retained));
    sample("hardware-device-and-retained-frame");unsigned char *pixels=malloc(1024*1024*4);for(size_t i=0;i<1024*1024*4;i++)pixels[i]=(unsigned char)i;
    D2D1_BITMAP_PROPERTIES bp={0};bp.pixelFormat=props.pixelFormat;bp.dpiX=bp.dpiY=96;D2D1_SIZE_U as={1024,1024};
    CHECK(ID2D1RenderTarget_CreateBitmap((ID2D1RenderTarget *)retained,as,pixels,4096,&bp,&atlas));free(pixels);
    D2D1_RECT_F rect={0,0,1280,960};D2D1_COLOR_F black={0,0,0,1};
    for(int frame=0;frame<120;frame++){
        ID2D1RenderTarget_BeginDraw((ID2D1RenderTarget *)retained);ID2D1RenderTarget_Clear((ID2D1RenderTarget *)retained,&black);
        ID2D1RenderTarget_DrawBitmap((ID2D1RenderTarget *)retained,atlas,&rect,1,D2D1_BITMAP_INTERPOLATION_MODE_NEAREST_NEIGHBOR,NULL);
        CHECK(ID2D1RenderTarget_EndDraw((ID2D1RenderTarget *)retained,NULL,NULL));
    }
    sample("atlas-and-120-frames");
    ID2D1GdiInteropRenderTarget *interop=NULL;HDC readback=NULL;
    CHECK(ID2D1BitmapRenderTarget_QueryInterface(retained,&IID_ID2D1GdiInteropRenderTarget,(void **)&interop));
    ID2D1RenderTarget_BeginDraw((ID2D1RenderTarget *)retained);
    CHECK(ID2D1GdiInteropRenderTarget_GetDC(interop,D2D1_DC_INITIALIZE_MODE_COPY,&readback));
    COLORREF pixel=GetPixel(readback,0,0);
    printf("{\"pixel\":[%u,%u,%u],\"expected\":[2,1,0]}\n",GetRValue(pixel),GetGValue(pixel),GetBValue(pixel));
    RECT unchanged={0};CHECK(ID2D1GdiInteropRenderTarget_ReleaseDC(interop,&unchanged));
    CHECK(ID2D1RenderTarget_EndDraw((ID2D1RenderTarget *)retained,NULL,NULL));
    ID2D1GdiInteropRenderTarget_Release(interop);
    if(pixel!=RGB(2,1,0))return 6;
    sample("after-pixel-readback");
    ID2D1Bitmap_Release(atlas);ID2D1BitmapRenderTarget_Release(retained);ID2D1HwndRenderTarget_Release(hwndtarget);ID2D1Factory_Release(factory);
    DestroyWindow(window);UnregisterClassW(wc.lpszClassName,inst);sample("after-device-destruction");return 0;
}
