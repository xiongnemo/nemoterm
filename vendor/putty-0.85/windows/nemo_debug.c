/* SPDX-License-Identifier: MIT
 * Opt-in, current-user and current-logon-session local automation transport.
 * Pipe I/O never runs on the UI thread. At most one bounded request is queued.
 */
#include "nemo_debug.h"
#include <sddl.h>

bool nemo_debug_enabled;
static struct {
    HWND hwnd;
    HANDLE pipe, thread, stop, ready, io;
    CRITICAL_SECTION lock;
    bool initialized, pending;
    DWORD session;
    NemoDebugDispatch dispatch;
    NemoDebugRequest request;
} debug_server;

static bool finish_io(OVERLAPPED *ov, BOOL immediate, DWORD *done, DWORD timeout)
{
    if (immediate) return true;
    if (GetLastError()!=ERROR_IO_PENDING) return false;
    HANDLE events[2]={debug_server.stop,ov->hEvent};
    if (WaitForMultipleObjects(2,events,FALSE,timeout)==WAIT_OBJECT_0+1)
        return GetOverlappedResult(debug_server.pipe,ov,done,FALSE)!=0;
    CancelIoEx(debug_server.pipe,ov);
    GetOverlappedResult(debug_server.pipe,ov,done,TRUE); /* drain before stack reuse */
    return false;
}
static bool transfer(void *data, DWORD length, bool write)
{
    ULONGLONG deadline=GetTickCount64()+5000;
    while (length) {
        ULONGLONG now=GetTickCount64();
        if (now>=deadline || WaitForSingleObject(debug_server.stop,0)==WAIT_OBJECT_0)
            return false;
        OVERLAPPED ov={0};ov.hEvent=debug_server.io;ResetEvent(ov.hEvent);
        DWORD done=0;
        BOOL ok=write?WriteFile(debug_server.pipe,data,length,&done,&ov):
                      ReadFile(debug_server.pipe,data,length,&done,&ov);
        if (!finish_io(&ov,ok,&done,(DWORD)(deadline-now)) || !done) return false;
        data=(char *)data+done;length-=done;
    }
    return true;
}
static void clear_request(void)
{
    strbuf_free(debug_server.request.input);
    strbuf_free(debug_server.request.output);
    memset(&debug_server.request,0,sizeof(debug_server.request));
    debug_server.pending=false;
}
static DWORD WINAPI serve(void *unused)
{
    (void)unused;
    while (WaitForSingleObject(debug_server.stop,0)!=WAIT_OBJECT_0) {
        OVERLAPPED ov={0};ov.hEvent=debug_server.io;ResetEvent(ov.hEvent);
        DWORD done=0;
        BOOL connected=ConnectNamedPipe(debug_server.pipe,&ov);
        if (!connected && GetLastError()==ERROR_PIPE_CONNECTED) connected=TRUE;
        if (!finish_io(&ov,connected,&done,INFINITE)) break;
        ULONG session;
        unsigned char header[24];
        if (!GetNamedPipeClientSessionId(debug_server.pipe,&session) ||
            session!=debug_server.session || !transfer(header,sizeof(header),false))
            goto disconnect;
        unsigned length=GET_32BIT_LSB_FIRST(header+16);
        if (memcmp(header,"NDBG",4) || GET_16BIT_LSB_FIRST(header+4)!=1 ||
            GET_32BIT_LSB_FIRST(header+20) || length>NEMO_DEBUG_MAX_INPUT)
            goto disconnect;
        NemoDebugRequest *r=&debug_server.request;
        r->op=GET_16BIT_LSB_FIRST(header+6);
        r->session=GET_64BIT_LSB_FIRST(header+8);
        r->input=strbuf_new();r->output=strbuf_new();r->kind=1;
        if (length && !transfer(strbuf_append(r->input,length),length,false))
            goto clear;
        ResetEvent(debug_server.ready);
        EnterCriticalSection(&debug_server.lock);
        debug_server.pending=true;
        LeaveCriticalSection(&debug_server.lock);
        if (!PostMessageW(debug_server.hwnd,NEMO_DEBUG_MESSAGE,0,0)) goto clear;
        HANDLE events[2]={debug_server.stop,debug_server.ready};
        if (WaitForMultipleObjects(2,events,FALSE,5000)!=WAIT_OBJECT_0+1) goto clear;
        if (r->output->len>NEMO_DEBUG_MAX_OUTPUT) goto clear;
        memcpy(header,"NDBG",4);PUT_16BIT_LSB_FIRST(header+4,1);
        PUT_16BIT_LSB_FIRST(header+6,r->status);
        PUT_32BIT_LSB_FIRST(header+8,r->output->len);
        PUT_32BIT_LSB_FIRST(header+12,r->kind);
        if (transfer(header,16,true) && transfer(r->output->s,(DWORD)r->output->len,true)) {
            /* DisconnectNamedPipe discards unread buffered data. The client
             * acknowledges receipt; never FlushFileBuffers on a slow peer. */
            unsigned char ack;
            transfer(&ack,1,false);
        }
      clear:
        EnterCriticalSection(&debug_server.lock);
        clear_request();
        LeaveCriticalSection(&debug_server.lock);
      disconnect:
        DisconnectNamedPipe(debug_server.pipe);
    }
    return 0;
}
void nemo_debug_dispatch(void)
{
    if (!debug_server.initialized) return;
    EnterCriticalSection(&debug_server.lock);
    if (debug_server.pending) {
        debug_server.pending=false;
        debug_server.dispatch(&debug_server.request);
        SetEvent(debug_server.ready);
    }
    LeaveCriticalSection(&debug_server.lock);
}
void nemo_debug_stop(void)
{
    if (!debug_server.initialized) return;
    SetEvent(debug_server.stop);
    if (debug_server.thread) {
        WaitForSingleObject(debug_server.thread,INFINITE);
        CloseHandle(debug_server.thread);
    }
    if (debug_server.pipe!=INVALID_HANDLE_VALUE) CloseHandle(debug_server.pipe);
    if (debug_server.io) CloseHandle(debug_server.io);
    if (debug_server.ready) CloseHandle(debug_server.ready);
    if (debug_server.stop) CloseHandle(debug_server.stop);
    DeleteCriticalSection(&debug_server.lock);
    memset(&debug_server,0,sizeof(debug_server));
}
bool nemo_debug_start(HWND hwnd, NemoDebugDispatch dispatch)
{
    HANDLE token=NULL;TOKEN_USER *user=NULL;DWORD bytes=0;
    LPWSTR sid=NULL;PSECURITY_DESCRIPTOR sd=NULL;wchar_t *sddl=NULL;
    bool ok=false;
    FILETIME created,exited,kernel,user_time;
    if (!OpenProcessToken(GetCurrentProcess(),TOKEN_QUERY,&token)) goto end;
    GetTokenInformation(token,TokenUser,NULL,0,&bytes);
    if (!bytes) goto end;
    user=(TOKEN_USER *)snewn(bytes,char);
    if (!GetTokenInformation(token,TokenUser,user,bytes,&bytes) ||
        !ConvertSidToStringSidW(user->User.Sid,&sid)) goto end;
    sddl=dupwcscat(L"D:P(A;;GA;;;",sid,L")");
    if (!ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl,SDDL_REVISION_1,&sd,NULL) ||
        !GetProcessTimes(GetCurrentProcess(),&created,&exited,&kernel,&user_time) ||
        !ProcessIdToSessionId(GetCurrentProcessId(),&debug_server.session)) goto end;
    wchar_t name[128];
    _snwprintf(name,lenof(name),L"\\\\.\\pipe\\Nemoterm.Debug.v1.%lu.%08lx%08lx",
               GetCurrentProcessId(),created.dwHighDateTime,created.dwLowDateTime);
    SECURITY_ATTRIBUTES sa={sizeof(sa),sd,FALSE};
    debug_server.pipe=CreateNamedPipeW(name,PIPE_ACCESS_DUPLEX|FILE_FLAG_OVERLAPPED|
        FILE_FLAG_FIRST_PIPE_INSTANCE,PIPE_TYPE_BYTE|PIPE_READMODE_BYTE|PIPE_WAIT|
        PIPE_REJECT_REMOTE_CLIENTS,1,65536,65536,5000,&sa);
    if (debug_server.pipe==INVALID_HANDLE_VALUE) goto end;
    InitializeCriticalSection(&debug_server.lock);debug_server.initialized=true;
    debug_server.hwnd=hwnd;debug_server.dispatch=dispatch;
    debug_server.stop=CreateEventW(NULL,TRUE,FALSE,NULL);
    debug_server.ready=CreateEventW(NULL,TRUE,FALSE,NULL);
    debug_server.io=CreateEventW(NULL,TRUE,FALSE,NULL);
    if (!debug_server.stop || !debug_server.ready || !debug_server.io) goto end;
    debug_server.thread=CreateThread(NULL,128*1024,serve,NULL,0,NULL);
    ok=debug_server.thread!=NULL;
  end:
    { DWORD error=GetLastError();
      if (!ok) nemo_debug_stop();
      if (token) CloseHandle(token);
      sfree(user);sfree(sddl);if (sid) LocalFree(sid);if (sd) LocalFree(sd);
      SetLastError(error); }
    return ok;
}
