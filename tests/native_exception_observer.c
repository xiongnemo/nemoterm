/* Test-only external debugger. Accepts inherited handles to one live member of
 * the caller's private job, never a searched/historical process ID. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <dbghelp.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <wchar.h>

static void error_record(const char *operation)
{
    printf("{\"event\":\"observer_error\",\"operation\":\"%s\",\"error\":%lu}\n",
           operation, GetLastError());
}

static void quoted(const wchar_t *text)
{
    putchar('"');
    for (; *text; text++) {
        unsigned value = (unsigned)*text;
        if (value == '"' || value == '\\') printf("\\%c", (char)value);
        else if (value >= 32 && value < 127) putchar((int)value);
        else printf("\\u%04x", value);
    }
    putchar('"');
}

static void module_record(HANDLE file, void *base)
{
    wchar_t path[32768] = L"";
    DWORD length = file ? GetFinalPathNameByHandleW(file, path, 32768, 0) : 0;
    if (length >= 32768) path[0] = 0;
    printf("{\"event\":\"module\",\"base\":\"%p\",\"path\":", base);
    quoted(path);
    printf("}\n");
    if (file) CloseHandle(file); /* Debug-event image handles are caller-owned. */
}

static BOOL dump_exception(HANDLE process, const DEBUG_EVENT *event,
                           const wchar_t *directory, unsigned ordinal)
{
    HANDLE thread = OpenThread(THREAD_GET_CONTEXT | THREAD_QUERY_INFORMATION,
                               FALSE, event->dwThreadId);
    CONTEXT context;
    EXCEPTION_RECORD record = event->u.Exception.ExceptionRecord;
    EXCEPTION_POINTERS pointers = {&record, &context};
    MINIDUMP_EXCEPTION_INFORMATION information = {event->dwThreadId, &pointers, FALSE};
    wchar_t path[32768];
    HANDLE file;
    BOOL result;
    if (!thread) { error_record("OpenThread"); return FALSE; }
    ZeroMemory(&context, sizeof(context));
    context.ContextFlags = CONTEXT_ALL;
    result = GetThreadContext(thread, &context);
    if (!result) error_record("GetThreadContext");
    CloseHandle(thread);
    if (!result) return FALSE;
#if defined(_M_X64) || defined(__x86_64__)
    printf("{\"event\":\"context\",\"tid\":%lu,\"rip\":\"%llx\",\"rsp\":\"%llx\"}\n",
           event->dwThreadId, (unsigned long long)context.Rip,
           (unsigned long long)context.Rsp);
#else
#error This diagnostic is verified only for Windows x64.
#endif
    if (swprintf(path, 32768, L"%ls/crash-%lu-%u.dmp", directory,
                 event->dwProcessId, ordinal) < 0) return FALSE;
    file = CreateFileW(path, GENERIC_WRITE, 0, NULL, CREATE_NEW,
                       FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) { error_record("CreateFileW"); return FALSE; }
    result = MiniDumpWriteDump(process, event->dwProcessId, file,
        (MINIDUMP_TYPE)(MiniDumpWithThreadInfo | MiniDumpWithUnloadedModules),
        &information, NULL, NULL);
    if (!result) error_record("MiniDumpWriteDump");
    CloseHandle(file);
    printf("{\"event\":\"dump\",\"success\":%s,\"path\":", result ? "true" : "false");
    quoted(path);
    printf("}\n");
    return result;
}

int wmain(int argc, wchar_t **argv)
{
    HANDLE process, job, ready, stop;
    DWORD pid;
    BOOL member = FALSE, attached = FALSE, initialized = FALSE;
    int status = 0;
    unsigned dumps = 0;
    ULONGLONG started = GetTickCount64();
    if (argc != 6) return 2;
    setvbuf(stdout, NULL, _IONBF, 0);
    process = (HANDLE)(uintptr_t)wcstoull(argv[1], NULL, 10);
    job = (HANDLE)(uintptr_t)wcstoull(argv[2], NULL, 10);
    ready = (HANDLE)(uintptr_t)wcstoull(argv[3], NULL, 10);
    stop = (HANDLE)(uintptr_t)wcstoull(argv[4], NULL, 10);
    pid = GetProcessId(process);
    if (!pid || !IsProcessInJob(process, job, &member) || !member ||
        WaitForSingleObject(process, 0) != WAIT_TIMEOUT) {
        error_record("validate-owned-live-process"); return 2;
    }
    if (!DebugActiveProcess(pid)) { error_record("DebugActiveProcess"); return 2; }
    attached = TRUE;
    if (!DebugSetProcessKillOnExit(FALSE)) {
        error_record("DebugSetProcessKillOnExit"); status = 2; goto done;
    }
    printf("{\"event\":\"attached\",\"pid\":%lu,\"kill_on_exit\":false}\n", pid);
    while (WaitForSingleObject(stop, 0) == WAIT_TIMEOUT) {
        DEBUG_EVENT event;
        DWORD continuation = DBG_CONTINUE;
        BOOL announce_ready = FALSE, exited = FALSE;
        if (GetTickCount64() - started > 600000) {
            printf("{\"event\":\"observer_deadline\"}\n"); status = 2; break;
        }
        if (!WaitForDebugEventEx(&event, 50)) {
            if (GetLastError() == ERROR_SEM_TIMEOUT) continue;
            error_record("WaitForDebugEventEx"); status = 2; break;
        }
        if (event.dwProcessId != pid) {
            printf("{\"event\":\"unexpected_process\",\"pid\":%lu}\n", event.dwProcessId);
            status = 2;
        }
        switch (event.dwDebugEventCode) {
          case CREATE_PROCESS_DEBUG_EVENT:
            module_record(event.u.CreateProcessInfo.hFile, event.u.CreateProcessInfo.lpBaseOfImage);
            break;
          case LOAD_DLL_DEBUG_EVENT:
            module_record(event.u.LoadDll.hFile, event.u.LoadDll.lpBaseOfDll);
            break;
          case UNLOAD_DLL_DEBUG_EVENT:
            printf("{\"event\":\"unload\",\"base\":\"%p\"}\n", event.u.UnloadDll.lpBaseOfDll);
            break;
          case EXCEPTION_DEBUG_EVENT: {
            const EXCEPTION_RECORD *exception = &event.u.Exception.ExceptionRecord;
            BOOL initial_break = !initialized && event.u.Exception.dwFirstChance &&
                                 exception->ExceptionCode == EXCEPTION_BREAKPOINT;
            printf("{\"event\":\"exception\",\"tid\":%lu,\"code\":%lu,\"address\":\"%p\","
                   "\"first_chance\":%s,\"initial_attach_break\":%s,\"parameters\":[",
                   event.dwThreadId, exception->ExceptionCode, exception->ExceptionAddress,
                   event.u.Exception.dwFirstChance ? "true" : "false", initial_break ? "true" : "false");
            for (DWORD i = 0; i < exception->NumberParameters && i < EXCEPTION_MAXIMUM_PARAMETERS; i++)
                printf("%s%llu", i ? "," : "", (unsigned long long)exception->ExceptionInformation[i]);
            printf("]}\n");
            continuation = initial_break ? DBG_CONTINUE : DBG_EXCEPTION_NOT_HANDLED;
            announce_ready = initial_break;
            if (!event.u.Exception.dwFirstChance && event.dwProcessId == pid) {
                if (dumps < 4) {
                    if (!dump_exception(process, &event, argv[5], ++dumps)) status = 2;
                } else { printf("{\"event\":\"dump_limit\"}\n"); status = 2; }
            }
            break;
          }
          case EXIT_PROCESS_DEBUG_EVENT:
            printf("{\"event\":\"process_exit\",\"code\":%lu}\n", event.u.ExitProcess.dwExitCode);
            exited = TRUE;
            break;
        }
        /* Windows releases debug-event process/thread handles when their exit
         * events are continued. Do not close those handles a second time. */
        if (!ContinueDebugEvent(event.dwProcessId, event.dwThreadId, continuation)) {
            error_record("ContinueDebugEvent"); status = 2; break;
        }
        if (announce_ready) {
            initialized = TRUE;
            printf("{\"event\":\"ready\"}\n");
            if (!SetEvent(ready)) { error_record("SetEvent"); status = 2; break; }
        }
        if (exited) { attached = FALSE; break; }
        if (status) break;
    }
done:
    if (attached) {
        BOOL result = DebugActiveProcessStop(pid);
        printf("{\"event\":\"detach\",\"success\":%s}\n", result ? "true" : "false");
        if (!result) { error_record("DebugActiveProcessStop"); status = 2; }
    }
    CloseHandle(process); CloseHandle(job); CloseHandle(ready); CloseHandle(stop);
    return status;
}
