/* SPDX-License-Identifier: MIT */
#include "putty.h"
#include "terminal.h"
#include "win-gui-seat.h"
#include "nemo_clipboard.h"
#include "nemo_osc52_ui.h"

typedef struct NemoClipboardRead {
    volatile LONG refs, cancelled, ready;
    HWND hwnd;
    uint64_t id;
    WPARAM cookie;
    char *text;
    size_t length;
    bool found;
} NemoClipboardRead;

static volatile LONG64 next_cookie;

static void read_release(NemoClipboardRead *read)
{
    if (!InterlockedDecrement(&read->refs)) {
        free(read->text);
        free(read);
    }
}

bool nemo_osc52_system_write(TermWin *win, const char *text, size_t length)
{
    WinGuiSeat *wgs = container_of(win, WinGuiSeat, termwin);
    if (!conf_get_bool(wgs->conf, CONF_nemo_osc52_write) || length > NEMO_OSC52_TEXT_MAX ||
        !nemo_osc52_utf8(text, length)) return false;
    int wide_length = length ? MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS,
                                                  text, length, NULL, 0) : 0;
    if (length && !wide_length) return false;
    HGLOBAL memory = GlobalAlloc(GMEM_MOVEABLE, (wide_length+1)*sizeof(wchar_t));
    if (!memory) return false;
    wchar_t *wide = GlobalLock(memory);
    if (!wide) { GlobalFree(memory); return false; }
    bool converted = !length || MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS,
                                                   text, length, wide, wide_length) == wide_length;
    wide[wide_length] = 0; GlobalUnlock(memory);
    if (!converted || !nemo_open_clipboard(wgs->term_hwnd)) { GlobalFree(memory); return false; }
    /* A remote system copy must not replace or deselect the user's local
     * selection. Explicit OSC 52 primary writes are handled by the terminal. */
    bool ignored = wgs->ignore_clip;
    wgs->ignore_clip = true;
    bool success = EmptyClipboard() && SetClipboardData(CF_UNICODETEXT, memory);
    CloseClipboard();
    wgs->ignore_clip = ignored;
    if (!success) GlobalFree(memory);
    return success;
}

static DWORD WINAPI read_worker(void *context)
{
    NemoClipboardRead *read = context;
    if (!InterlockedCompareExchange(&read->cancelled, 0, 0) && nemo_open_clipboard(NULL)) {
        HGLOBAL memory = GetClipboardData(CF_UNICODETEXT);
        size_t count = memory ? GlobalSize(memory)/sizeof(wchar_t) : 0;
        /* Limit both the scan and the conversion; delayed rendering can block
         * in Windows, which is why this operation never runs on the UI thread. */
        if (count > NEMO_OSC52_TEXT_MAX+1) count = NEMO_OSC52_TEXT_MAX+1;
        const wchar_t *wide = count ? GlobalLock(memory) : NULL;
        if (wide) {
            size_t n = 0; while (n < count && wide[n]) n++;
            if (n < count) {
                int bytes = n ? WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, wide, n,
                                                     NULL, 0, NULL, NULL) : 0;
                if ((!n || bytes > 0) && bytes <= NEMO_OSC52_TEXT_MAX) {
                    read->text = malloc(bytes+1);
                    if (read->text) {
                        read->found = !n || WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS,
                            wide, n, read->text, bytes, NULL, NULL) == bytes;
                        read->length = bytes; read->text[bytes] = 0;
                    }
                }
            }
            GlobalUnlock(memory);
        }
        CloseClipboard();
    }
    InterlockedExchange(&read->ready, 1);
    if (!InterlockedCompareExchange(&read->cancelled, 0, 0))
        PostMessage(read->hwnd, WM_NEMO_OSC52_READY, read->cookie, 0);
    read_release(read);
    return 0;
}

bool nemo_osc52_system_read(TermWin *win, uint64_t id)
{
    WinGuiSeat *wgs = container_of(win, WinGuiSeat, termwin);
    if (wgs->osc52_read || !conf_get_bool(wgs->conf, CONF_nemo_osc52_read)) return false;
    NemoClipboardRead *read = calloc(1, sizeof(*read));
    if (!read) return false;
    read->refs = 2; read->hwnd = wgs->term_hwnd; read->id = id;
    read->cookie = (WPARAM)InterlockedIncrement64(&next_cookie);
    if (!SetTimer(wgs->term_hwnd, NEMO_OSC52_TIMER, 100, NULL)) { free(read); return false; }
    wgs->osc52_read = read;
    HANDLE worker = CreateThread(NULL, 0, read_worker, read, 0, NULL);
    if (!worker) {
        wgs->osc52_read = NULL;
        KillTimer(wgs->term_hwnd, NEMO_OSC52_TIMER);
        free(read); return false;
    }
    CloseHandle(worker);
    return true;
}

void nemo_osc52_poll(WinGuiSeat *wgs, WPARAM cookie)
{
    NemoClipboardRead *read = wgs->osc52_read;
    if (!read || (cookie && cookie != read->cookie) ||
        !InterlockedCompareExchange(&read->ready, 0, 0)) return;
    wgs->osc52_read = NULL;
    KillTimer(wgs->term_hwnd, NEMO_OSC52_TIMER);
    if (wgs->term)
        term_osc52_read_result(wgs->term, read->id, read->text, read->length, read->found);
    read_release(read);
}

void nemo_osc52_window_free(WinGuiSeat *wgs)
{
    NemoClipboardRead *read = wgs->osc52_read;
    if (!read) return;
    wgs->osc52_read = NULL;
    KillTimer(wgs->term_hwnd, NEMO_OSC52_TIMER);
    InterlockedExchange(&read->cancelled, 1);
    read_release(read);
}
