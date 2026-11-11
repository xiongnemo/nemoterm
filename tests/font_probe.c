#include <windows.h>
#include <stdio.h>
int main(void) {
    HDC dc = GetDC(NULL);
    HFONT font = CreateFontW(-16,0,0,0,FW_DONTCARE,0,0,0,DEFAULT_CHARSET,
        OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,CLEARTYPE_QUALITY,
        FIXED_PITCH|FF_DONTCARE,L"SarasaTermSC Nerd Font Light");
    HGDIOBJ old = SelectObject(dc,font);
    wchar_t face[128]; TEXTMETRICW tm; SIZE latin,cjk;
    GetTextFaceW(dc,128,face); GetTextMetricsW(dc,&tm);
    GetTextExtentPoint32W(dc,L"0123456789",10,&latin);
    GetTextExtentPoint32W(dc,L"\x4e2d",1,&cjk);
    wprintf(L"face=%ls height=%ld ave=%ld max=%ld pitch=%u digits=%ld CJK=%ld\n",
        face,tm.tmHeight,tm.tmAveCharWidth,tm.tmMaxCharWidth,tm.tmPitchAndFamily,latin.cx,cjk.cx);
    SelectObject(dc,old); DeleteObject(font); ReleaseDC(NULL,dc);
    return 0;
}
