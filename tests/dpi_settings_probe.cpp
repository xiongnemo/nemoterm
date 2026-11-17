// Test-only native UIA client. The hosted image's legacy managed UIA client
// can expose only HWND panes; use Windows' native standard-control proxies.
#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#include <windows.h>
#include <UIAutomation.h>
#include <cstdio>
#include <cstdlib>
#include <cwchar>
#include <stdexcept>
#include <string>
#include <vector>
#include "../vendor/putty-0.85/utils/nemo_ui_catalog.h"

static bool chinese=false;
static std::wstring display(const wchar_t *text) {
    if(!chinese)return text;
    int length=WideCharToMultiByte(CP_UTF8,0,text,-1,nullptr,0,nullptr,nullptr);
    std::string en((size_t)length,'\0');
    WideCharToMultiByte(CP_UTF8,0,text,-1,&en[0],length,nullptr,nullptr);
    for(const auto &entry:nemo_ui_catalog)if(en.c_str()==std::string(entry.en)) {
        int count=MultiByteToWideChar(CP_UTF8,0,entry.zh,-1,nullptr,0);
        std::wstring value((size_t)count,L'\0');
        MultiByteToWideChar(CP_UTF8,0,entry.zh,-1,&value[0],count);
        value.resize(value.size()-1);return value;
    }
    return text;
}

template<class T> struct Com {
    T *p=nullptr;
    ~Com() {if(p)p->Release();}
    T *operator->() const {return p;}
};
static void check(HRESULT result) {
    if (FAILED(result)) throw std::runtime_error("UIA HRESULT "+std::to_string((unsigned long)result));
}
static void quoted(const std::wstring &s) {
    std::putchar('"');
    for (wchar_t ch:s) {
        if (ch=='"' || ch=='\\') std::printf("\\%c",(char)ch);
        else if(ch>=32 && ch<127) std::putchar((char)ch);
        else std::printf("\\u%04x",(unsigned)ch);
    }
    std::putchar('"');
}
static void rect(const RECT &r) {std::printf("[%ld,%ld,%ld,%ld]",r.left,r.top,r.right-r.left,r.bottom-r.top);}
static bool text_fits(IUIAutomationElement *element) {
    UIA_HWND native=0;check(element->get_CurrentNativeWindowHandle(&native));
    HWND hwnd=(HWND)native;
    wchar_t classname[64]={};GetClassNameW(hwnd,classname,64);
    if(wcscmp(classname,L"Static"))return true;
    LONG_PTR type=GetWindowLongPtrW(hwnd,GWL_STYLE)&SS_TYPEMASK;
    if(type!=SS_LEFT && type!=SS_LEFTNOWORDWRAP)return true;
    std::wstring text((size_t)GetWindowTextLengthW(hwnd)+1,L'\0');
    GetWindowTextW(hwnd,&text[0],(int)text.size());
    RECT area={};GetClientRect(hwnd,&area);RECT measured=area;
    HDC dc=GetDC(hwnd);
    HFONT font=(HFONT)SendMessageW(hwnd,WM_GETFONT,0,0);
    HGDIOBJ old=SelectObject(dc,font);
    UINT flags=DT_CALCRECT|DT_EDITCONTROL;
    flags|=type==SS_LEFT?DT_WORDBREAK:DT_SINGLELINE;
    DrawTextW(dc,text.c_str(),-1,&measured,flags);
    SelectObject(dc,old);ReleaseDC(hwnd,dc);
    return measured.bottom<=area.bottom+1 && measured.right<=area.right+1;
}
static IUIAutomationElement *find(IUIAutomation *uia,IUIAutomationElement *parent,const wchar_t *name) {
    Com<IUIAutomationCondition> condition;
    std::wstring wanted=display(name);
    std::vector<IUIAutomationCondition *> variants;
    const wchar_t *keys=L"ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
    for(size_t index=0;index<=wcslen(keys);index++) {
        std::wstring label=wanted;
        if(index)label+=std::wstring(L" (")+keys[index-1]+L")";
        VARIANT value;VariantInit(&value);value.vt=VT_BSTR;value.bstrVal=SysAllocString(label.c_str());
        IUIAutomationCondition *entry=nullptr;
        HRESULT result=uia->CreatePropertyCondition(UIA_NamePropertyId,value,&entry);
        VariantClear(&value);
        if(FAILED(result)) {for(auto *old:variants)old->Release();check(result);}
        variants.push_back(entry);
    }
    HRESULT result=uia->CreateOrConditionFromNativeArray(variants.data(),(int)variants.size(),&condition.p);
    for(auto *entry:variants)entry->Release();
    check(result);
    for(int i=0;i<100;i++) {
        IUIAutomationElement *found=nullptr;
        check(parent->FindFirst(TreeScope_Descendants,condition.p,&found));
        if(found)return found;
        Sleep(20);
    }
    std::string text;
    for(;*name;name++)text.push_back(*name<128?(char)*name:'?');
    throw std::runtime_error("Missing UIA control: "+text);
}
struct Page {const wchar_t *id;std::vector<const wchar_t *> path,labels;};
static const Page pages[]={
    {L"language",{L"Window",L"Interface language"},{L"Language",L"Applies to all profiles after restarting Nemoterm.",L"This changes the interface language, not the terminal encoding or shell output."}},
    {L"profile",{L"Profile"},{L"New profile name",L"Add",L"Edit",L"Delete"}},
    {L"shell",{L"Profile",L"Shell"},{L"Choose shell on startup",L"Command (select Custom above):",L"Starting directory (blank inherits launcher):"}},
    {L"bell",{L"Terminal",L"Bell"},{L"Play a custom sound file",L"Browse...",L"Raise window on bell without taking keyboard focus",L"Ring when the application resets the terminal"}},
    {L"bell-overload",{L"Terminal",L"Bell",L"Overload"},{L"Bell is temporarily disabled when over-used",L"Seconds of silence required"}},
    {L"bindings",{L"Window",L"Bindings"},{L"Reset bindings",L"Rectangle modifier"}},
    {L"font",{L"Window",L"Bindings",L"Font"},{L"Increase key",L"Decrease key",L"Reset key"}},
    {L"translation",{L"Window",L"Translation"},{L"Remote character set:",L"Treat CJK ambiguous characters as wide",L"Use grapheme cluster widths at startup",L"Caps Lock acts as Cyrillic switch"}},
    {L"line-drawing",{L"Window",L"Translation",L"Line drawing"},{L"Use Unicode line drawing code points",L"Poor man's line drawing (+, - and |)",L"Font has XWindows encoding",L"Use font in both ANSI and OEM modes",L"Use font in OEM mode only",L"Copy and paste line drawing characters as lqqqk",L"Enable VT100 line drawing even in UTF-8 mode"}},
    {L"tabs",{L"Window",L"Tabs"},{L"Top",L"Bottom",L"Left",L"Right",L"Preview terminal on hover"}}
};
int wmain(int argc,wchar_t **argv) {
    wchar_t actions[32]={},environment[32]={};
    GetEnvironmentVariableW(L"GITHUB_ACTIONS",actions,32);GetEnvironmentVariableW(L"RUNNER_ENVIRONMENT",environment,32);
    if((argc!=5 && argc!=6 && argc!=8) || wcscmp(actions,L"true") || wcscmp(environment,L"github-hosted"))return 2;
    chinese=argc>=6 && !wcscmp(argv[5],L"zh-CN");
    const Page *page=nullptr;
    for(const auto &p:pages)if(!wcscmp(argv[4],p.id))page=&p;
    if(!page)return 2;
    DWORD pid=(DWORD)_wcstoui64(argv[1],nullptr,10),owner=0;
    HWND hwnd=(HWND)(UINT_PTR)_wcstoui64(argv[2],nullptr,10);
    UINT dpi=(UINT)_wtoi(argv[3]);
    wchar_t classname[64]={};GetWindowThreadProcessId(hwnd,&owner);GetClassNameW(hwnd,classname,64);
    if(owner!=pid || wcscmp(classname,L"PuTTYConfigBox"))return 2;
    SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
    HRESULT initialized=CoInitializeEx(nullptr,COINIT_MULTITHREADED);
    if(FAILED(initialized))return 2;
    std::printf("{\"id\":");quoted(page->id);
    bool completed=false,controls_open=false;
    try {
        Com<IUIAutomation> uia;
        check(CoCreateInstance(CLSID_CUIAutomation,nullptr,CLSCTX_INPROC_SERVER,IID_PPV_ARGS(&uia.p)));
        Com<IUIAutomationElement> dialog;check(uia->ElementFromHandle(hwnd,&dialog.p));
        IUIAutomationElement *parent=dialog.p;parent->AddRef();
        Com<IUIAutomationElement> selected;selected.p=parent;
        for(size_t i=0;i<page->path.size();i++) {
            IUIAutomationElement *next=find(uia.p,selected.p,page->path[i]);
            selected.p->Release();selected.p=next;
            Com<IUIAutomationSelectionItemPattern> selection;
            check(selected->GetCurrentPatternAs(UIA_SelectionItemPatternId,IID_PPV_ARGS(&selection.p)));
            check(selection->Select());
            if(i+1<page->path.size()) {
                Com<IUIAutomationExpandCollapsePattern> expand;
                check(selected->GetCurrentPatternAs(UIA_ExpandCollapsePatternId,IID_PPV_ARGS(&expand.p)));
                check(expand->Expand());
            }
        }
        UINT actual=GetDpiForWindow(hwnd);
        std::printf(",\"actual_dpi\":%u,\"expected_dpi\":%u",actual,dpi);
        if(actual!=dpi)throw std::runtime_error("Actual dialog DPI differs");
        RECT bounds={};check(dialog->get_CurrentBoundingRectangle(&bounds));
        std::printf(",\"window\":");rect(bounds);
        Com<IUIAutomationElement> save;save.p=find(uia.p,dialog.p,L"Save and Apply");
        RECT footer={};check(save->get_CurrentBoundingRectangle(&footer));
        std::vector<const wchar_t *> labels=page->labels;
        labels.push_back(L"Save and Apply");labels.push_back(L"Cancel");
        std::printf(",\"controls\":[");controls_open=true;bool first=true,valid=true;
        for(const wchar_t *label:labels) {
            Com<IUIAutomationElement> node;node.p=find(uia.p,dialog.p,label);
            RECT r={};BOOL offscreen=FALSE;
            check(node->get_CurrentBoundingRectangle(&r));check(node->get_CurrentIsOffscreen(&offscreen));
            bool contained=!offscreen && r.right>r.left && r.bottom>r.top &&
                r.left>=bounds.left && r.top>=bounds.top && r.right<=bounds.right && r.bottom<=bounds.bottom;
            bool bottom=!wcscmp(label,L"Save and Apply") || !wcscmp(label,L"Cancel");
            bool clear=bottom || r.bottom<=footer.top-2;
            bool fits=text_fits(node.p);
            if(!first)std::putchar(',');
            first=false;
            std::printf("{\"label\":");quoted(label);std::printf(",\"rect\":");rect(r);
            std::printf(",\"offscreen\":%s,\"contained\":%s,\"footer_clear\":%s,\"text_fits\":%s}",
                offscreen?"true":"false",contained?"true":"false",clear?"true":"false",fits?"true":"false");
            valid=valid && contained && clear && fits;
        }
        std::putchar(']');controls_open=false;
        if(!valid)throw std::runtime_error("Control clipping or footer overlap");
        if(!wcscmp(page->id,L"language")) {
            HWND combo=FindWindowExW(hwnd,nullptr,L"ComboBox",nullptr);
            if(!combo)throw std::runtime_error("Missing language selector");
            int before=(int)SendMessageW(combo,CB_GETCURSEL,0,0);
            if(argc==8) {
                int choice=_wtoi(argv[6]);
                if(choice<0 || choice>2)throw std::runtime_error("Invalid language choice");
                SendMessageW(combo,CB_SETCURSEL,(WPARAM)choice,0);
                SendMessageW(hwnd,WM_COMMAND,MAKEWPARAM(GetDlgCtrlID(combo),CBN_SELCHANGE),(LPARAM)combo);
            }
            std::printf(",\"language_before\":%d,\"language_after\":%d",before,(int)SendMessageW(combo,CB_GETCURSEL,0,0));
            if(argc==8 && wcscmp(argv[7],L"stage")) {
                Com<IUIAutomationElement> button;button.p=find(uia.p,dialog.p,!wcscmp(argv[7],L"save")?L"Save and Apply":L"Cancel");
                Com<IUIAutomationInvokePattern> invoke;
                check(button->GetCurrentPatternAs(UIA_InvokePatternId,IID_PPV_ARGS(&invoke.p)));
                check(invoke->Invoke());
            }
        }
        completed=true;
    } catch(const std::exception &error) {
        if(controls_open)std::putchar(']');
        std::printf(",\"error\":");std::string message=error.what();quoted(std::wstring(message.begin(),message.end()));
    }
    std::printf(",\"completed\":%s}\n",completed?"true":"false");
    CoUninitialize();return completed?0:1;
}
