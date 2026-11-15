/* Test-only, out-of-process snapshot of a retained private-job member.
 * No debugger attach, injected code, full-memory capture or PID search. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <dbghelp.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <wchar.h>

static HANDLE inherited_handle(const wchar_t *value)
{
    wchar_t *end;
    unsigned long long number = wcstoull(value, &end, 10);
    return *value && !*end && number ? (HANDLE)(uintptr_t)number : NULL;
}

int wmain(int argc, wchar_t **argv)
{
    HANDLE process, job, file;
    DWORD pid, error;
    BOOL member = FALSE, success;
    LARGE_INTEGER length;
    const MINIDUMP_TYPE flags = (MINIDUMP_TYPE)(MiniDumpWithThreadInfo |
                                               MiniDumpWithUnloadedModules);
    if (argc != 4) return 2;
    setvbuf(stdout, NULL, _IONBF, 0);
    process = inherited_handle(argv[1]);
    job = inherited_handle(argv[2]);
    pid = process ? GetProcessId(process) : 0;
    if (!pid || !job || !IsProcessInJob(process, job, &member) || !member ||
        WaitForSingleObject(process, 0) != WAIT_TIMEOUT) {
        printf("{\"event\":\"ownership_rejected\"}\n");
        return 2;
    }
    file = CreateFileW(argv[3], GENERIC_WRITE, 0, NULL, CREATE_NEW,
                       FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        printf("{\"event\":\"create_failed\",\"error\":%lu}\n", GetLastError());
        return 3;
    }
    success = MiniDumpWriteDump(process, pid, file, flags, NULL, NULL, NULL);
    error = success ? 0 : GetLastError();
    length.QuadPart = 0;
    if (!GetFileSizeEx(file, &length)) length.QuadPart = -1;
    CloseHandle(file);
    printf("{\"event\":\"dump\",\"success\":%s,\"pid\":%lu,"
           "\"bytes\":%lld,\"flags\":%u,\"error\":%lu}\n",
           success ? "true" : "false", pid, (long long)length.QuadPart,
           (unsigned)flags, error);
    CloseHandle(process);
    CloseHandle(job);
    return success ? 0 : 4;
}
