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
static IUIAutomationElement *find(IUIAutomation *uia,IUIAutomationElement *parent,const wchar_t *name) {
    VARIANT value;VariantInit(&value);value.vt=VT_BSTR;value.bstrVal=SysAllocString(name);
    Com<IUIAutomationCondition> condition;
    HRESULT result=uia->CreatePropertyCondition(UIA_NamePropertyId,value,&condition.p);
    VariantClear(&value);check(result);
    for(int i=0;i<100;i++) {
        IUIAutomationElement *found=nullptr;
        check(parent->FindFirst(TreeScope_Descendants,condition.p,&found));
        if(found)return found;
        Sleep(20);
    }
    std::wstring text=name;
    throw std::runtime_error("Missing UIA control: "+std::string(text.begin(),text.end()));
}
struct Page {const wchar_t *id;std::vector<const wchar_t *> path,labels;};
static const Page pages[]={
    {L"profile",{L"Profile"},{L"New profile name",L"Add",L"Edit",L"Delete"}},
    {L"shell",{L"Profile",L"Shell"},{L"Choose shell on startup",L"Command (select Custom above):",L"Starting directory (blank inherits launcher):"}},
    {L"bell",{L"Terminal",L"Bell"},{L"Play a custom sound file",L"Browse...",L"Raise window on bell without taking keyboard focus",L"Ring when the application resets the terminal"}},
    {L"bell-overload",{L"Terminal",L"Bell",L"Overload"},{L"Bell is temporarily disabled when over-used",L"Seconds of silence required"}},
    {L"bindings",{L"Window",L"Bindings"},{L"Reset bindings",L"Rectangle modifier"}},
    {L"font",{L"Window",L"Bindings",L"Font"},{L"Increase key",L"Decrease key",L"Reset key"}},
    {L"tabs",{L"Window",L"Tabs"},{L"Top",L"Bottom",L"Left",L"Right",L"Preview terminal on hover"}}
};
int wmain(int argc,wchar_t **argv) {
    wchar_t actions[32]={},environment[32]={};
    GetEnvironmentVariableW(L"GITHUB_ACTIONS",actions,32);GetEnvironmentVariableW(L"RUNNER_ENVIRONMENT",environment,32);
    if(argc!=5 || wcscmp(actions,L"true") || wcscmp(environment,L"github-hosted"))return 2;
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
            if(!first)std::putchar(',');
            first=false;
            std::printf("{\"label\":");quoted(label);std::printf(",\"rect\":");rect(r);
            std::printf(",\"offscreen\":%s,\"contained\":%s,\"footer_clear\":%s}",
                offscreen?"true":"false",contained?"true":"false",clear?"true":"false");
            valid=valid && contained && clear;
        }
        std::putchar(']');controls_open=false;
        if(!valid)throw std::runtime_error("Control clipping or footer overlap");
        completed=true;
    } catch(const std::exception &error) {
        if(controls_open)std::putchar(']');
        std::printf(",\"error\":");std::string message=error.what();quoted(std::wstring(message.begin(),message.end()));
    }
    std::printf(",\"completed\":%s}\n",completed?"true":"false");
    CoUninitialize();return completed?0:1;
}
