/* SPDX-License-Identifier: MIT */
#include "putty.h"
#include "terminal.h"
#include "win-gui-seat.h"
#include "nemo_link_ui.h"
#include "nemo_clipboard.h"
#include <shellapi.h>

#define LINK_BUTTONS (MK_LBUTTON | MK_MBUTTON | MK_RBUTTON | MK_XBUTTON1 | MK_XBUTTON2)

typedef struct NemoLinkUI {
    HWND tip;
    uint32_t hover, pressed_link;
    NemoLinkPolicy policy;
    POINT press;
    bool pending, eat_release;
} NemoLinkUI;

static NemoLinkUI *link_ui(WinGuiSeat *wgs)
{
    if (!wgs->link_ui) {
        wgs->link_ui = snew(NemoLinkUI);
        memset(wgs->link_ui, 0, sizeof(*wgs->link_ui));
    }
    return wgs->link_ui;
}

static POINT point_from_lparam(LPARAM lp)
{
    return (POINT){(short)LOWORD(lp), (short)HIWORD(lp)};
}

static uint32_t hit(WinGuiSeat *wgs, POINT p)
{
    if (!wgs->term || wgs->font_width <= 0 || wgs->font_height <= 0 ||
        p.x < wgs->offset_width || p.y < wgs->offset_height) return 0;
    return term_hyperlink_at(wgs->term,
        (p.x-wgs->offset_width)/wgs->font_width,
        (p.y-wgs->offset_height)/wgs->font_height);
}

static NemoLinkPolicy policy(WinGuiSeat *wgs, const char *uri)
{
    char hostname[256] = "", fqdn[256] = "";
    DWORD n = sizeof(hostname);
    if (!GetComputerNameA(hostname, &n)) hostname[0] = 0;
    n = sizeof(fqdn);
    if (!GetComputerNameExA(ComputerNameDnsFullyQualified, fqdn, &n)) fqdn[0] = 0;
    return nemo_hyperlink_policy(uri, hostname, fqdn,
        conf_get_bool(wgs->conf, CONF_nemo_custom_url_schemes));
}

static wchar_t *wide_uri(const char *uri)
{
    size_t n = strlen(uri);
    wchar_t *wide = snewn(n+1, wchar_t);
    for (size_t i = 0; i <= n; i++) wide[i] = (unsigned char)uri[i];
    return wide;
}

static void open_link(WinGuiSeat *wgs, const char *uri)
{
    if (!uri || conf_get_bool(wgs->conf, CONF_no_remote_hyperlinks) ||
        policy(wgs, uri) != NEMO_LINK_OPEN_OK) return;
    wchar_t *wide = wide_uri(uri);
    INT_PTR result = (INT_PTR)ShellExecuteW(wgs->term_hwnd, L"open", wide,
                                           NULL, NULL, SW_SHOWNORMAL);
    sfree(wide);
    if (result <= 32) {
        wchar_t message[128];
        swprintf(message, lenof(message), L"Could not open this link (Windows code %ld).",
                 (long)result);
        MessageBoxW(wgs->term_hwnd, message, L"Nemoterm", MB_OK | MB_ICONERROR);
    }
}

static void copy_link(WinGuiSeat *wgs, const char *uri)
{
    if (!uri || conf_get_bool(wgs->conf, CONF_no_remote_hyperlinks)) return;
    size_t n = strlen(uri);
    HGLOBAL memory = GlobalAlloc(GMEM_MOVEABLE, (n+1)*sizeof(wchar_t));
    if (!memory) return;
    wchar_t *text = GlobalLock(memory);
    if (!text) { GlobalFree(memory); return; }
    for (size_t i = 0; i <= n; i++) text[i] = (unsigned char)uri[i];
    GlobalUnlock(memory);
    if (nemo_open_clipboard(wgs->term_hwnd)) {
        wgs->ignore_clip = true;
        if (EmptyClipboard() && SetClipboardData(CF_UNICODETEXT, memory)) memory = NULL;
        CloseClipboard();
        wgs->ignore_clip = false;
    }
    if (memory) GlobalFree(memory);
}

void nemo_link_leave(WinGuiSeat *wgs)
{
    wgs->link_mouse_inside = false;
    if (wgs->link_ui) {
        wgs->link_ui->hover = 0;
        if (wgs->link_ui->tip) ShowWindow(wgs->link_ui->tip, SW_HIDE);
    }
    if (wgs->term) term_hyperlink_hover(wgs->term, 0);
}

void nemo_link_cancel(WinGuiSeat *wgs)
{
    if (wgs->link_ui) wgs->link_ui->pending = false;
    /* Keep eat_release until the consumed press has a matching release. */
    nemo_link_leave(wgs);
}

void nemo_link_free(WinGuiSeat *wgs)
{
    if (!wgs->link_ui) return;
    if (wgs->link_ui->tip) DestroyWindow(wgs->link_ui->tip);
    sfree(wgs->link_ui);
    wgs->link_ui = NULL;
}

bool nemo_link_hand_cursor(WinGuiSeat *wgs)
{
    return wgs->link_ui && wgs->link_ui->hover &&
        wgs->link_ui->policy == NEMO_LINK_OPEN_OK;
}

static void show_tip(WinGuiSeat *wgs, const char *uri, POINT point, NemoLinkPolicy state)
{
    NemoLinkUI *ui = link_ui(wgs);
    if (!ui->tip) {
        ui->tip = CreateWindowExW(WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
            L"STATIC", L"", WS_POPUP | WS_BORDER | SS_LEFT | SS_NOPREFIX,
            0, 0, 0, 0, wgs->term_hwnd, NULL, GetModuleHandle(NULL), NULL);
        if (!ui->tip) return;
        SendMessage(ui->tip, WM_SETFONT, (WPARAM)GetStockObject(DEFAULT_GUI_FONT), FALSE);
    }
    ClientToScreen(wgs->term_hwnd, &point);
    MONITORINFO monitor = {sizeof(monitor)};
    GetMonitorInfo(MonitorFromPoint(point, MONITOR_DEFAULTTONEAREST), &monitor);
    int width = min(600, max(100, monitor.rcWork.right-monitor.rcWork.left-24));
    HDC dc = GetDC(ui->tip);
    HFONT oldfont = SelectObject(dc, GetStockObject(DEFAULT_GUI_FONT));
    int widths[95];
    TEXTMETRIC tm;
    GetTextMetrics(dc, &tm);
    if (!GetCharWidth32W(dc, 32, 126, widths))
        for (size_t i = 0; i < lenof(widths); i++) widths[i] = tm.tmAveCharWidth;
    /* Hard-wrap even long unbroken URLs. No ellipsis hides the real target. */
    wchar_t *label = snewn(2*strlen(uri)+160, wchar_t), *out = label;
    const wchar_t *hint = state == NEMO_LINK_OPEN_OK ?
        L"Ctrl+click to open; Ctrl+right-click for link actions.\n" :
        state == NEMO_LINK_REMOTE_FILE ?
        L"Remote file link; Ctrl+right-click to copy its address.\n" :
        state == NEMO_LINK_SCHEME_DISABLED ?
        L"Opening this URI scheme is disabled; Ctrl+right-click to copy.\n" :
        L"Cannot open this target locally; Ctrl+right-click to copy.\n";
    while (*hint) *out++ = *hint++;
    int used = 0;
    for (const unsigned char *p = (const unsigned char *)uri; *p; p++) {
        int advance = widths[*p-32];
        if (used && used + advance > width-8) { *out++ = L'\n'; used = 0; }
        *out++ = *p; used += advance;
    }
    *out = 0;
    RECT rect = {0, 0, width-8, 0};
    DrawTextW(dc, label, -1, &rect, DT_CALCRECT | DT_WORDBREAK | DT_NOPREFIX);
    SelectObject(dc, oldfont); ReleaseDC(ui->tip, dc);
    SetWindowTextW(ui->tip, label); sfree(label);
    int height = rect.bottom + 6, x = point.x + 12, y = point.y + 24;
    x = max(monitor.rcWork.left, min(x, monitor.rcWork.right-width));
    if (y + height > monitor.rcWork.bottom) y = point.y-height-12;
    y = max(monitor.rcWork.top, y);
    SetWindowPos(ui->tip, HWND_TOPMOST, x, y, width, height,
                 SWP_NOACTIVATE | SWP_SHOWWINDOW);
}

void nemo_link_refresh(WinGuiSeat *wgs)
{
    if (!wgs->term) return;
    POINT point = point_from_lparam(wgs->last_wm_mousemove_lParam);
    uint32_t id = wgs->link_mouse_inside &&
        !(wgs->last_wm_mousemove_wParam & (LINK_BUTTONS | MK_SHIFT)) ? hit(wgs, point) : 0;
    const char *uri = term_hyperlink_uri(wgs->term, id);
    NemoLinkPolicy state = uri ? policy(wgs, uri) : NEMO_LINK_INVALID_TARGET;
    if (!id && !wgs->link_ui) return;
    NemoLinkUI *ui = link_ui(wgs);
    if (ui->hover == id && ui->policy == state) return;
    ui->hover = id; ui->policy = state;
    term_hyperlink_hover(wgs->term, id);
    if (uri) {
        char *owned = dupstr(uri);
        show_tip(wgs, owned, point, state);
        sfree(owned);
    }
    else if (ui->tip) ShowWindow(ui->tip, SW_HIDE);
    SetCursor(LoadCursor(NULL, nemo_link_hand_cursor(wgs) ? IDC_HAND :
                         wgs->pointer_indicates_raw_mouse ? IDC_ARROW : IDC_IBEAM));
}

static void local_drag(WinGuiSeat *wgs, WPARAM keys)
{
    NemoLinkUI *ui = wgs->link_ui;
    ui->pending = ui->eat_release = false;
    int x = ui->press.x-wgs->offset_width, y = ui->press.y-wgs->offset_height;
    term_mouse_pixels(wgs->term, MBT_LEFT, MBT_SELECT, MA_CLICK,
                       x/wgs->font_width, y/wgs->font_height, x, y,
                       true, (keys & MK_CONTROL) != 0, false);
}

static bool moved(WinGuiSeat *wgs, POINT point)
{
    POINT press = wgs->link_ui->press;
    return abs(point.x-press.x) > GetSystemMetrics(SM_CXDRAG) ||
        abs(point.y-press.y) > GetSystemMetrics(SM_CYDRAG);
}

bool nemo_link_button(WinGuiSeat *wgs, UINT message, WPARAM keys, LPARAM lp)
{
    NemoLinkUI *ui = wgs->link_ui;
    POINT point = point_from_lparam(lp);
    if (message == WM_LBUTTONDOWN) {
        if (ui) ui->pending = ui->eat_release = false;
        uint32_t id = hit(wgs, point);
        const char *uri = term_hyperlink_uri(wgs->term, id);
        if ((keys & (MK_CONTROL | MK_SHIFT)) == MK_CONTROL &&
            !(keys & (LINK_BUTTONS & ~MK_LBUTTON)) && !wgs->term->mouse_buttons &&
            uri && policy(wgs, uri) == NEMO_LINK_OPEN_OK) {
            ui = link_ui(wgs);
            ui->press = point; ui->pressed_link = id;
            ui->pending = ui->eat_release = true;
            nemo_link_leave(wgs);
            if (GetCapture() != wgs->term_hwnd) SetCapture(wgs->term_hwnd);
            return true;
        }
    } else if (message == WM_LBUTTONUP && ui && ui->eat_release) {
        if (ui->pending && ((keys & MK_SHIFT) || moved(wgs, point))) {
            local_drag(wgs, keys); return false;
        }
        const char *uri = ui->pending &&
            (keys & (MK_CONTROL | MK_SHIFT)) == MK_CONTROL &&
            hit(wgs, point) == ui->pressed_link ?
            term_hyperlink_uri(wgs->term, ui->pressed_link) : NULL;
        /* ReleaseCapture and ShellExecute can dispatch nested messages. */
        char *owned = uri ? dupstr(uri) : NULL;
        ui->pending = ui->eat_release = false;
        if (!(keys & (LINK_BUTTONS & ~MK_LBUTTON)) && GetCapture() == wgs->term_hwnd)
            ReleaseCapture();
        if (owned) { open_link(wgs, owned); sfree(owned); }
        return true;
    } else if (message == WM_MBUTTONDOWN || message == WM_RBUTTONDOWN ||
               message == WM_XBUTTONDOWN) {
        nemo_link_cancel(wgs);
    }
    if (message == WM_LBUTTONDOWN) nemo_link_leave(wgs);
    return false;
}

bool nemo_link_motion(WinGuiSeat *wgs, WPARAM *keys, LPARAM lp)
{
    if (!wgs->link_mouse_inside) {
        TRACKMOUSEEVENT track = {sizeof(track), TME_LEAVE, wgs->term_hwnd, 0};
        TrackMouseEvent(&track);
        wgs->link_mouse_inside = true;
    }
    NemoLinkUI *ui = wgs->link_ui;
    if (ui && ui->pending &&
        ((*keys & MK_SHIFT) || !(*keys & MK_CONTROL) || moved(wgs, point_from_lparam(lp))))
        local_drag(wgs, *keys);
    nemo_link_refresh(wgs);
    ui = wgs->link_ui;
    if (ui && ui->eat_release && (*keys & MK_LBUTTON)) {
        *keys &= ~MK_LBUTTON;
        if (!(*keys & LINK_BUTTONS)) return true;
    }
    return false;
}

void nemo_link_key(WinGuiSeat *wgs, UINT message, WPARAM key)
{
    unsigned bit = key == VK_SHIFT || key == VK_LSHIFT || key == VK_RSHIFT ? MK_SHIFT :
        key == VK_CONTROL || key == VK_LCONTROL || key == VK_RCONTROL ? MK_CONTROL : 0;
    if (!bit) return;
    bool down = message == WM_KEYDOWN || message == WM_SYSKEYDOWN;
    if (down) wgs->last_wm_mousemove_wParam |= bit;
    else wgs->last_wm_mousemove_wParam &= ~bit;
    if (bit == MK_SHIFT && down && wgs->link_ui && wgs->link_ui->pending)
        local_drag(wgs, wgs->last_wm_mousemove_wParam);
    nemo_link_refresh(wgs);
}

UINT nemo_link_menu(WinGuiSeat *wgs, HMENU menu, POINT point)
{
    const char *uri = term_hyperlink_uri(wgs->term, hit(wgs, point));
    char *owned = uri ? dupstr(uri) : NULL;
    EnableMenuItem(menu, IDM_NEMO_OPEN_LINK, MF_BYCOMMAND |
        (owned && policy(wgs, owned) == NEMO_LINK_OPEN_OK ? MF_ENABLED : MF_GRAYED));
    EnableMenuItem(menu, IDM_NEMO_COPY_LINK, MF_BYCOMMAND | (owned ? MF_ENABLED : MF_GRAYED));
    nemo_link_cancel(wgs);
    ClientToScreen(wgs->term_hwnd, &point);
    UINT cmd = TrackPopupMenu(menu, TPM_LEFTALIGN | TPM_TOPALIGN | TPM_RIGHTBUTTON |
                             TPM_RETURNCMD | TPM_NONOTIFY, point.x, point.y,
                             0, wgs->term_hwnd, NULL);
    if (cmd == IDM_NEMO_OPEN_LINK) { open_link(wgs, owned); cmd = 0; }
    if (cmd == IDM_NEMO_COPY_LINK) { copy_link(wgs, owned); cmd = 0; }
    sfree(owned);
    return cmd;
}
