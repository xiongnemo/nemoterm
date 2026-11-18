/* Hosted reference only: wire the controller's two pipes directly to Windows
 * ConPTY. No Nemoterm, clipboard, text conversion or terminal emulation here. */
#define _WIN32_WINNT 0x0A00
#include <windows.h>
#include <stdio.h>
int wmain(int argc, wchar_t **argv) {
    if (argc != 2) return 2;
    COORD size = {100,30}; HPCON pc = NULL; DWORD code = 3;
    STARTUPINFOEXW si = {0}; PROCESS_INFORMATION pi = {0}; SIZE_T bytes = 0;
    BOOL initialized = FALSE; si.StartupInfo.cb = sizeof(si);
    HRESULT hr = CreatePseudoConsole(size, GetStdHandle(STD_INPUT_HANDLE),
        GetStdHandle(STD_OUTPUT_HANDLE), 0, &pc);
    if (FAILED(hr)) { fprintf(stderr,"CreatePseudoConsole: %08lx\n",(unsigned long)hr); return 3; }
    InitializeProcThreadAttributeList(NULL,1,0,&bytes);
    si.lpAttributeList = HeapAlloc(GetProcessHeap(),0,bytes);
    if (!si.lpAttributeList) goto out;
    if (!(initialized = InitializeProcThreadAttributeList(si.lpAttributeList,1,0,&bytes))) goto out;
    if (!UpdateProcThreadAttribute(si.lpAttributeList,0,PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE,
                                   pc,sizeof(pc),NULL,NULL)) goto out;
    if (!CreateProcessW(NULL,argv[1],NULL,NULL,FALSE,EXTENDED_STARTUPINFO_PRESENT,
                        NULL,NULL,&si.StartupInfo,&pi)) goto out;
    CloseHandle(pi.hThread);
    if (WaitForSingleObject(pi.hProcess,INFINITE)==WAIT_OBJECT_0) GetExitCodeProcess(pi.hProcess,&code);
    CloseHandle(pi.hProcess);
out:
    if (!pi.hProcess) fprintf(stderr,"pseudo console process setup: %lu\n",GetLastError());
    if (initialized) DeleteProcThreadAttributeList(si.lpAttributeList);
    if (si.lpAttributeList) HeapFree(GetProcessHeap(),0,si.lpAttributeList);
    ClosePseudoConsole(pc);
    return (int)code;
}
