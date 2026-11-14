/* SPDX-License-Identifier: MIT
 * Controlled event-order checks for the shutdown observer. The window stores
 * an opaque heap marker; its WndProc never reads or dereferences that marker. */
#include <windows.h>
#include <objbase.h>
#include <stdint.h>
#include <stdio.h>
#include <wchar.h>

static LRESULT CALLBACK window_proc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp)
{
    if (msg == WM_APP + 71) return 0;
    return DefWindowProcW(hwnd, msg, wp, lp);
}

int wmain(int argc, wchar_t **argv)
{
    if (argc != 3 || FAILED(CoInitializeEx(NULL, COINIT_APARTMENTTHREADED))) return 2;
    WNDCLASSW wc = {0};
    wc.lpfnWndProc = window_proc;
    wc.hInstance = GetModuleHandleW(NULL);
    wc.lpszClassName = L"NemotermShutdownObserverFixture";
    if (!RegisterClassW(&wc)) return 3;
    HWND hwnd = CreateWindowExW(0, wc.lpszClassName, L"Owned observer fixture",
                                WS_OVERLAPPEDWINDOW, 0, 0, 80, 80,
                                NULL, NULL, wc.hInstance, NULL);
    HANDLE heap = GetProcessHeap();
    void *marker = HeapAlloc(heap, 0, 64);
    if (!hwnd || !marker) return 4;
    SetWindowLongPtrW(hwnd, GWLP_USERDATA, (LONG_PTR)marker);
    FILE *ready = _wfopen(argv[2], L"wb");
    if (!ready) return 5;
    fprintf(ready, "{\"hwnd\":%llu}", (unsigned long long)(uintptr_t)hwnd);
    fclose(ready);
    if (getchar() != 'G') return 6;
    if (!wcscmp(argv[1], L"free-before-window")) {
        if (!HeapFree(heap, 0, marker)) return 7;
        /* An order signal only: no pointer to released storage is read. */
        SendMessageW(hwnd, WM_APP + 71, 0, 0);
        DestroyWindow(hwnd);
        CoUninitialize();
    } else if (!wcscmp(argv[1], L"free-after-com")) {
        DestroyWindow(hwnd);
        CoUninitialize();
        if (!HeapFree(heap, 0, marker)) return 8;
    } else if (!wcscmp(argv[1], L"ordered")) {
        DestroyWindow(hwnd);
        if (!HeapFree(heap, 0, marker)) return 9;
        CoUninitialize();
    } else return 10;
    return 0;
}
