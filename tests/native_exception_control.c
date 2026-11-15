/* Owned positive/negative controls, not terminal code. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <wchar.h>

#define HANDLED_CODE ((DWORD)0xe1234567)
static LONG CALLBACK handled(EXCEPTION_POINTERS *exception)
{
    return exception->ExceptionRecord->ExceptionCode == HANDLED_CODE ?
        EXCEPTION_CONTINUE_EXECUTION : EXCEPTION_CONTINUE_SEARCH;
}

int wmain(int argc, wchar_t **argv)
{
    HANDLE go;
    void *handler;
    DWORD wait;
    SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX);
    if (argc != 3) return 2;
    go = OpenEventW(SYNCHRONIZE, FALSE, argv[1]);
    if (!go) return 3;
    handler = AddVectoredExceptionHandler(1, handled);
    if (!handler) { CloseHandle(go); return 4; }
    wait = WaitForSingleObject(go, 60000);
    CloseHandle(go);
    if (wait != WAIT_OBJECT_0) return 5;
    RaiseException(HANDLED_CODE, 0, 0, NULL);
    RemoveVectoredExceptionHandler(handler);
    if (wcscmp(argv[2], L"crash") == 0) {
        volatile LONG *unwritable = VirtualAlloc(NULL, 4096,
            MEM_RESERVE | MEM_COMMIT, PAGE_NOACCESS);
        if (!unwritable) return 6;
        *unwritable = 7; /* Deliberate data AV in this dedicated control only. */
        VirtualFree((void *)unwritable, 0, MEM_RELEASE);
        return 7;
    }
    return 23;
}
