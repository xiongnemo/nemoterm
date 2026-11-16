// Test-only display controller. Never linked into Nemoterm.
// The -3/-4 DPI packets are undocumented: layouts independently declared from
// https://github.com/lihas/windows-DPI-scaling-sample/tree/master/DPIHelper
// Unsupported drivers/packets are reported, never replaced with synthetic DPI.
#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#include <windows.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cwchar>
#include <vector>

struct ScaleGet { DISPLAYCONFIG_DEVICE_INFO_HEADER header; INT32 minimum, current, maximum; };
struct ScaleSet { DISPLAYCONFIG_DEVICE_INFO_HEADER header; INT32 relative; };
static_assert(sizeof(ScaleGet)==32 && sizeof(ScaleSet)==24, "DPI packet layout");
static const int percentages[]={100,125,150,175,200,225,250,300,350,400,450,500};
struct Monitor { MONITORINFOEXW info; UINT dpi; };
static std::vector<Monitor> monitors;

static void quoted(const wchar_t *s) {
    std::putchar('"');
    for (;*s;s++) {
        if (*s=='"' || *s=='\\') std::printf("\\%c",(char)*s);
        else if (*s>=32 && *s<127) std::putchar((char)*s);
        else std::printf("\\u%04x",(unsigned)*s);
    }
    std::putchar('"');
}
static void rect(const RECT &r) {std::printf("[%ld,%ld,%ld,%ld]",r.left,r.top,r.right,r.bottom);}
static BOOL CALLBACK collect(HMONITOR handle,HDC,LPRECT,LPARAM) {
    Monitor m={};m.info.cbSize=sizeof(m.info);
    if (!GetMonitorInfoW(handle,&m.info)) return TRUE;
    HWND probe=CreateWindowExW(0,L"STATIC",L"DPI environment probe",WS_POPUP,
        m.info.rcMonitor.left+8,m.info.rcMonitor.top+8,16,16,nullptr,nullptr,GetModuleHandleW(nullptr),nullptr);
    m.dpi=probe?GetDpiForWindow(probe):0;
    if (probe) DestroyWindow(probe);
    monitors.push_back(m);return TRUE;
}
static bool hosted() {
    wchar_t actions[32]={},environment[32]={};
    GetEnvironmentVariableW(L"GITHUB_ACTIONS",actions,32);
    GetEnvironmentVariableW(L"RUNNER_ENVIRONMENT",environment,32);
    return !wcscmp(actions,L"true") && !wcscmp(environment,L"github-hosted");
}
int wmain(int argc,wchar_t **argv) {
    bool set=argc==3 && !wcscmp(argv[1],L"--set-percent");
    bool resize=argc==4 && !wcscmp(argv[1],L"--set-size");
    if ((argc!=1 && !set && !resize) || ((set || resize) && !hosted())) {
        std::fputs("Display changes require a disposable GitHub-hosted runner.\n",stderr);return 2;
    }
    int wanted=set?_wtoi(argv[2]):0;
    bool aware=SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)!=0;
    EnumDisplayMonitors(nullptr,nullptr,collect,0);
    LONG resize_result=DISP_CHANGE_BADMODE;
    if (resize) {
        for (const auto &m:monitors) if (m.info.dwFlags&MONITORINFOF_PRIMARY) {
            DEVMODEW mode={};mode.dmSize=sizeof(mode);
            for (DWORD i=0;EnumDisplaySettingsExW(m.info.szDevice,i,&mode,0);i++) {
                if (mode.dmBitsPerPel==32 && mode.dmPelsWidth==(DWORD)_wtoi(argv[2]) &&
                    mode.dmPelsHeight==(DWORD)_wtoi(argv[3])) {
                    resize_result=ChangeDisplaySettingsExW(m.info.szDevice,&mode,nullptr,CDS_TEST,nullptr);
                    if (resize_result==DISP_CHANGE_SUCCESSFUL)
                        resize_result=ChangeDisplaySettingsExW(m.info.szDevice,&mode,nullptr,0,nullptr);
                    break;
                }
            }
        }
        monitors.clear();EnumDisplayMonitors(nullptr,nullptr,collect,0);
    }
    std::vector<DISPLAYCONFIG_PATH_INFO> paths;
    std::vector<DISPLAYCONFIG_MODE_INFO> modes;
    LONG query=ERROR_GEN_FAILURE;
    for (int attempt=0;attempt<3;attempt++) {
        UINT32 np=0,nm=0;query=GetDisplayConfigBufferSizes(QDC_ONLY_ACTIVE_PATHS,&np,&nm);
        if (query) break;
        paths.resize(np);modes.resize(nm);
        query=QueryDisplayConfig(QDC_ONLY_ACTIVE_PATHS,&np,paths.data(),&nm,modes.data(),nullptr);
        if (query==ERROR_INSUFFICIENT_BUFFER) continue;
        if (!query) {paths.resize(np);modes.resize(nm);}break;
    }
    if (query) paths.clear();
    std::printf("{\"per_monitor_v2\":%s,\"remote_session\":%s,\"query_error\":%ld,\"monitors\":[",
        aware?"true":"false",GetSystemMetrics(SM_REMOTESESSION)?"true":"false",query);
    bool first=true;
    for (const auto &m:monitors) {
        if (!first) std::putchar(',');
        first=false;
        std::printf("{\"device\":");quoted(m.info.szDevice);
        std::printf(",\"primary\":%s,\"dpi\":%u,\"bounds\":",(m.info.dwFlags&MONITORINFOF_PRIMARY)?"true":"false",m.dpi);
        rect(m.info.rcMonitor);std::printf(",\"work\":");rect(m.info.rcWork);
        std::printf(",\"display_modes\":[");
        DEVMODEW mode={};mode.dmSize=sizeof(mode);bool first_mode=true;
        for (DWORD i=0;EnumDisplaySettingsExW(m.info.szDevice,i,&mode,0);i++) if (mode.dmBitsPerPel==32) {
            std::printf("%s[%lu,%lu,%lu]",first_mode?"":",",mode.dmPelsWidth,mode.dmPelsHeight,mode.dmDisplayFrequency);
            first_mode=false;
        }
        std::printf("]}");
    }
    std::printf("],\"sources\":[");first=true;bool attempted=false;
    for (const auto &path:paths) {
        DISPLAYCONFIG_SOURCE_DEVICE_NAME name={};name.header.type=DISPLAYCONFIG_DEVICE_INFO_GET_SOURCE_NAME;
        name.header.size=sizeof(name);name.header.adapterId=path.sourceInfo.adapterId;name.header.id=path.sourceInfo.id;
        LONG name_error=DisplayConfigGetDeviceInfo(&name.header);
        ScaleGet scale={};scale.header.type=(DISPLAYCONFIG_DEVICE_INFO_TYPE)-3;scale.header.size=sizeof(scale);
        scale.header.adapterId=path.sourceInfo.adapterId;scale.header.id=path.sourceInfo.id;
        LONG scale_error=DisplayConfigGetDeviceInfo(&scale.header);
        if (!first) std::putchar(',');
        first=false;
        std::printf("{\"device\":");quoted(name.viewGdiDeviceName);
        std::printf(",\"name_error\":%ld,\"scale_error\":%ld,\"minimum_relative\":%d,\"current_relative\":%d,\"maximum_relative\":%d,\"supported_percentages\":[",
            name_error,scale_error,scale.minimum,scale.current,scale.maximum);
        int current_index=scale.current-scale.minimum;
        bool valid=!scale_error && scale.minimum<=0 && scale.current>=scale.minimum && scale.current<=scale.maximum &&
            scale.maximum-scale.minimum<(int)(sizeof(percentages)/sizeof(*percentages));
        if (valid) for (int i=0;i<=scale.maximum-scale.minimum;i++) std::printf("%s%d",i?",":"",percentages[i]);
        std::printf("],\"current_percent\":%d",valid?percentages[current_index]:0);
        bool primary=false;
        for (const auto &m:monitors) if ((m.info.dwFlags&MONITORINFOF_PRIMARY) && !wcscmp(m.info.szDevice,name.viewGdiDeviceName)) primary=true;
        if (set && !attempted && primary && valid) {
            for (int i=0;i<=scale.maximum-scale.minimum;i++) if (percentages[i]==wanted) {
                ScaleSet request={};request.header=scale.header;request.header.type=(DISPLAYCONFIG_DEVICE_INFO_TYPE)-4;
                request.header.size=sizeof(request);request.relative=i+scale.minimum;
                LONG result=DisplayConfigSetDeviceInfo(&request.header);attempted=true;
                std::printf(",\"set_percent\":%d,\"set_error\":%ld",wanted,result);break;
            }
        }
        std::putchar('}');
    }
    std::printf("],\"set_requested\":%d,\"set_attempted\":%s",wanted,attempted?"true":"false");
    if (resize) std::printf(",\"resize_requested\":[%d,%d],\"resize_result\":%ld",_wtoi(argv[2]),_wtoi(argv[3]),resize_result);
    std::printf("}\n");
    return 0;
}
