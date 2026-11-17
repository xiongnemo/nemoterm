/* A console child whose initial thread can be resumed after its PTY closes. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <wchar.h>

static void report(const wchar_t *path, const char *text)
{
    wchar_t temporary[32768];
    swprintf_s(temporary, _countof(temporary), L"%s.tmp", path);
    FILE *file = _wfopen(temporary, L"wb");
    if (!file) ExitProcess(21);
    fputs(text, file);
    if (fclose(file)) ExitProcess(22);
    if (!MoveFileExW(temporary, path, MOVEFILE_REPLACE_EXISTING)) ExitProcess(23);
}

int wmain(int argc, wchar_t **argv)
{
    if (argc != 3) return 2;
    if (!wcscmp(argv[1], L"child")) {
        DWORD processes[64], count = GetConsoleProcessList(processes, _countof(processes));
        DWORD received = 0;
        wchar_t ch;
        char text[256];
        sprintf_s(text, sizeof(text), "{\"pid\":%lu,\"connected\":%lu,\"phase\":\"before-read\"}",
                  GetCurrentProcessId(), count);
        report(argv[2], text);
        BOOL ok = ReadConsoleW(GetStdHandle(STD_INPUT_HANDLE), &ch, 1, &received, NULL);
        DWORD error = ok ? 0 : GetLastError();
        sprintf_s(text, sizeof(text), "{\"pid\":%lu,\"connected\":%lu,\"phase\":\"read-returned\",\"error\":%lu}",
                  GetCurrentProcessId(), count, error);
        report(argv[2], text);
        return 0;
    }
    if (wcscmp(argv[1], L"parent")) return 2;
    wchar_t self[32768], command[32768], child_report[32768];
    if (!GetModuleFileNameW(NULL, self, _countof(self))) return 3;
    swprintf_s(child_report, _countof(child_report), L"%s-child", argv[2]);
    swprintf_s(command, _countof(command), L"\"%s\" child \"%s\"", self, child_report);
    STARTUPINFOW startup = {0}; startup.cb = sizeof(startup);
    PROCESS_INFORMATION process = {0};
    if (!CreateProcessW(NULL, command, NULL, NULL, FALSE, CREATE_SUSPENDED,
                        NULL, NULL, &startup, &process)) return 4;
    char text[256];
    sprintf_s(text, sizeof(text), "{\"parent\":%lu,\"child\":%lu,\"thread\":%lu}",
              GetCurrentProcessId(), process.dwProcessId, process.dwThreadId);
    report(argv[2], text);
    CloseHandle(process.hThread); CloseHandle(process.hProcess);
    Sleep(INFINITE);
    return 0;
}
