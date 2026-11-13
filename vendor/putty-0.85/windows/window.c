/*
 * window.c - the PuTTY(tel)/pterm main program, which runs a PuTTY
 * terminal emulator and backend in a window.
 */

#include <stdio.h>
#include <stdlib.h>
#include <ctype.h>
#include <time.h>
#include <limits.h>
#include <assert.h>
#include <wchar.h>

#define COMPILE_MULTIMON_STUBS

#include "putty.h"
#include "ssh.h"
#include "terminal.h"
#include "storage.h"
#include "putty-rc.h"
#include "security-api.h"
#include "win-gui-seat.h"
#include "nemo_snapshot.h"
#include "nemo_debug.h"
#include "nemo_drop.h"
#include "nemo_link_ui.h"
#include "nemo_shell.h"
#include "nemo_key_input.h"
#include "nemo_clipboard.h"
#include "nemo_osc52_ui.h"
#include "nemo_font_fallback.h"
#include "nemo_cluster.h"
#include "nemo_gpu.h"
#include "nemo_tabs_host.h"
#include "terminal/nemo_window_size.h"
#include "tree234.h"

#ifdef NO_MULTIMON
#include <multimon.h>
#endif

#include <imm.h>
#include <commctrl.h>
#include <richedit.h>
#include <mmsystem.h>

/* From MSDN: In the WM_SYSCOMMAND message, the four low-order bits of
 * wParam are used by Windows, and should be masked off, so we shouldn't
 * attempt to store information in them. Hence all these identifiers have
 * the low 4 bits clear. Also, identifiers should < 0xF000. */

#define IDM_SHOWLOG   0x0010
#define IDM_NEWSESS   0x0020
#define IDM_DUPSESS   0x0030
#define IDM_RESTART   0x0040
#define IDM_RECONF    0x0050
#define IDM_CLRSB     0x0060
#define IDM_RESET     0x0070
#define IDM_HELP      0x0140
#define IDM_ABOUT     0x0150
#define IDM_SAVEDSESS 0x0160
#define IDM_COPYALL   0x0170
#define IDM_FULLSCREEN  0x0180
#define IDM_COPY      0x0190
#define IDM_PASTE     0x01A0
#define IDM_COPYPASTE 0x01B0
#define IDM_COPYDIR   0x01E0
#define IDM_SPECIALSEP 0x0200

#define IDM_SPECIAL_MIN 0x0400
#define IDM_SPECIAL_MAX 0x0800
#define IDM_PREVPROMPT 0x0900
#define IDM_NEXTPROMPT 0x0910
#define IDM_SELECTCOMMAND 0x0920
#define IDM_SELECTOUTPUT 0x0930

#define IDM_SAVED_MIN 0x1000
#define IDM_SAVED_MAX 0x5000
#define MENU_SAVED_STEP 16
/* Maximum number of sessions on saved-session submenu */
#define MENU_SAVED_MAX ((IDM_SAVED_MAX-IDM_SAVED_MIN) / MENU_SAVED_STEP)

#define WM_IGNORE_CLIP (WM_APP + 2)
#define WM_FULLSCR_ON_MAX (WM_APP + 3)
#define WM_GOT_CLIPDATA (WM_APP + 4)

typedef struct NemoPasteRequest {
    HWND hwnd;
    UINT_PTR session_id;
    HGLOBAL data;
    bool unicode;
    bool application_paste;
    bool files;
} NemoPasteRequest;

/* Needed for Chinese support and apparently not always defined. */
#ifndef VK_PROCESSKEY
#define VK_PROCESSKEY 0xE5
#endif

/* Mouse wheel support. */
#ifndef WM_MOUSEWHEEL
#define WM_MOUSEWHEEL 0x020A           /* not defined in earlier SDKs */
#endif
#ifndef WM_MOUSEHWHEEL
#define WM_MOUSEHWHEEL 0x020E          /* not defined in earlier SDKs */
#endif
#ifndef WHEEL_DELTA
#define WHEEL_DELTA 120
#endif

/* DPI awareness support */
#ifndef WM_DPICHANGED
#define WM_DPICHANGED 0x02E0
#define WM_DPICHANGED_BEFOREPARENT 0x02E2
#define WM_DPICHANGED_AFTERPARENT 0x02E3
#define WM_GETDPISCALEDSIZE 0x02E4
#endif

/* VK_PACKET, used to send Unicode characters in WM_KEYDOWNs */
#ifndef VK_PACKET
#define VK_PACKET 0xE7
#endif

static Conf *nemo_duplicate_conf(WinGuiSeat *wgs)
{
    Conf *copy=conf_copy(wgs->conf);
    if (!conf_get_bool(copy,CONF_nemo_inherit_directory)) return copy;
    NemoCwd *cwd=&wgs->term->working_directory;
    char hostname[256]="",fqdn[256]="";DWORD n=sizeof(hostname);
    GetComputerNameA(hostname,&n);n=sizeof(fqdn);
    GetComputerNameExA(ComputerNameDnsFullyQualified,fqdn,&n);
    if (!cwd->path || !*cwd->path || !nemo_cwd_local(cwd,hostname,fqdn)) return copy;
    bool utf8;
    bool explicit_command=*conf_get_str_ambi(copy,CONF_remote_cmd,&utf8)!=0;
    const char *shell=conf_get_str(copy,CONF_nemo_shell);
    bool posix_shell=!explicit_command &&
        (!strcmp(shell,"git-bash") || !strcmp(shell,"wsl-bash"));
    char *directory=nemo_cwd_native(cwd,hostname,fqdn,false);
    if (!directory && posix_shell && cwd->path[0]=='/' && cwd->path[1]!='/')
        directory=dupstr(cwd->path);
    if (directory) { conf_set_utf8(copy,CONF_nemo_starting_directory,directory);sfree(directory); }
    return copy;
}
static void nemo_copy_directory(WinGuiSeat *wgs)
{
    char *uri=nemo_cwd_uri(&wgs->term->working_directory);
    if (!uri) return;
    size_t length=strlen(uri);HGLOBAL memory=GlobalAlloc(GMEM_MOVEABLE,(length+1)*sizeof(wchar_t));
    wchar_t *out=memory?GlobalLock(memory):NULL;
    if (out) {
        for (size_t i=0;i<=length;i++) out[i]=(unsigned char)uri[i];
        GlobalUnlock(memory);
        if (nemo_open_clipboard(wgs->term_hwnd)) {
            wgs->ignore_clip=true;
            if (EmptyClipboard() && SetClipboardData(CF_UNICODETEXT,memory)) memory=NULL;
            CloseClipboard();wgs->ignore_clip=false;
        }
    }
    if (memory) GlobalFree(memory);
    sfree(uri);
}

static Mouse_Button translate_button(WinGuiSeat *wgs, Mouse_Button button);
static void show_mouseptr(WinGuiSeat *wgs, bool show);
static LRESULT CALLBACK WndProc(HWND, UINT, WPARAM, LPARAM);
static int TranslateKey(WinGuiSeat *wgs, UINT message, WPARAM wParam,
                        LPARAM lParam, unsigned char *output);
static void init_palette(WinGuiSeat *wgs);
static void init_fonts(WinGuiSeat *wgs, int, int);
static void nemo_renderer_configure(WinGuiSeat *wgs);
static bool nemo_renderer_begin(WinGuiSeat *wgs);
static void nemo_renderer_finish(WinGuiSeat *wgs);
static void nemo_paint_images(WinGuiSeat *wgs);
static void init_dpi_info(WinGuiSeat *wgs);
static void another_font(WinGuiSeat *wgs, int);
static void deinit_fonts(WinGuiSeat *wgs);
static void set_input_locale(WinGuiSeat *wgs, HKL);
static void update_savedsess_menu(WinGuiSeat *wgs);
static void init_winfuncs(void);

static bool is_alt_pressed(void);
static bool is_full_screen(WinGuiSeat *wgs);
static void make_full_screen(WinGuiSeat *wgs);
static void clear_full_screen(WinGuiSeat *wgs);
static void flip_full_screen(WinGuiSeat *wgs);
static void process_clipdata(WinGuiSeat *wgs, HGLOBAL clipdata, bool unicode);
static void nemo_paste_drop(WinGuiSeat *wgs, HDROP drop)
{
    if (!wgs || wgs->closing || !wgs->term || !wgs->ldisc || !wgs->backend) return;
    size_t length=0;wchar_t *paths=nemo_drop_paths(drop,wgs->conf,&length);
    if (paths) {term_do_paste(wgs->term,paths,length);sfree(paths);}
    else MessageBeep(MB_ICONWARNING);
}
static void setup_clipboards(Terminal *, Conf *);
static void wgs_cleanup(void *vctx);
static void wgs_request_close(WinGuiSeat *wgs);
static void wgs_free_menus(WinGuiSeat *wgs);
static HWND app_event_hwnd;
static UINT_PTR next_session_id;

/* Window layout information */
static void reset_window(WinGuiSeat *wgs, int reinit);

static void flash_window(WinGuiSeat *wgs, int mode);
static void sys_cursor_update(WinGuiSeat *wgs);
static bool get_fullscreen_rect(WinGuiSeat *wgs, RECT *ss);
static bool get_workingarea_rect(WinGuiSeat *wgs, RECT *ss);

static void conf_cache_data(WinGuiSeat *wgs);

static struct sesslist sesslist;       /* for saved-session menu */

enum MONITOR_DPI_TYPE { MDT_EFFECTIVE_DPI, MDT_ANGULAR_DPI, MDT_RAW_DPI, MDT_DEFAULT };
DECL_WINDOWS_FUNCTION(static, BOOL, GetMonitorInfoA, (HMONITOR, LPMONITORINFO));
DECL_WINDOWS_FUNCTION(static, HMONITOR, MonitorFromPoint, (POINT, DWORD));
DECL_WINDOWS_FUNCTION(static, HMONITOR, MonitorFromWindow, (HWND, DWORD));
DECL_WINDOWS_FUNCTION(static, HRESULT, GetDpiForMonitor, (HMONITOR hmonitor, enum MONITOR_DPI_TYPE dpiType, UINT *dpiX, UINT *dpiY));
DECL_WINDOWS_FUNCTION(static, HRESULT, GetSystemMetricsForDpi, (int nIndex, UINT dpi));
DECL_WINDOWS_FUNCTION(static, HRESULT, AdjustWindowRectExForDpi, (LPRECT lpRect, DWORD dwStyle, BOOL bMenu, DWORD dwExStyle, UINT dpi));

static UINT wm_mousewheel = WM_MOUSEWHEEL;

struct WinGuiSeatListNode wgslisthead = {
    .next = &wgslisthead, .prev = &wgslisthead,
};

#define IS_HIGH_VARSEL(wch1, wch2) \
    ((wch1) == 0xDB40 && ((wch2) >= 0xDD00 && (wch2) <= 0xDDEF))
#define IS_LOW_VARSEL(wch) \
    (((wch) >= 0x180B && (wch) <= 0x180D) || /* MONGOLIAN FREE VARIATION SELECTOR */ \
     ((wch) >= 0xFE00 && (wch) <= 0xFE0F)) /* VARIATION SELECTOR 1-16 */

static bool wintw_setup_draw_ctx(TermWin *);
static bool wintw_set_synchronized_update(TermWin *, bool);
static void wintw_draw_text(TermWin *, int x, int y, wchar_t *text, int len,
                            unsigned long attrs, int lattrs, truecolour tc);
static void wintw_draw_cursor(TermWin *, int x, int y, wchar_t *text, int len,
                              unsigned long attrs, int lattrs, truecolour tc);
static void wintw_draw_trust_sigil(TermWin *, int x, int y);
static int wintw_char_width(TermWin *, int uc);
static void wintw_free_draw_ctx(TermWin *);
static void wintw_set_cursor_pos(TermWin *, int x, int y);
static void wintw_set_raw_mouse_mode(TermWin *, bool enable);
static void wintw_set_raw_mouse_mode_pointer(TermWin *, bool enable);
static void wintw_set_scrollbar(TermWin *, int total, int start, int page);
static void wintw_bell(TermWin *, int mode);
static void wintw_clip_write(
    TermWin *, int clipboard, wchar_t *text, int *attrs,
    truecolour *colours, int len, bool must_deselect);
static void wintw_clip_request_paste(TermWin *, int clipboard);
static void wintw_refresh(TermWin *);
static void wintw_request_resize(TermWin *, int w, int h);
static void wintw_request_window_resize(TermWin *, int w, int h, bool pixels);
static bool wintw_get_geometry(TermWin *, TermWindowGeometry *);
static void wintw_set_title(TermWin *, const char *title, int codepage);
static void wintw_set_icon_title(TermWin *, const char *icontitle,
                                 int codepage);
static void wintw_set_minimised(TermWin *, bool minimised);
static void wintw_set_maximised(TermWin *, bool maximised);
static void wintw_move(TermWin *, int x, int y);
static void wintw_set_zorder(TermWin *, bool top);
static void wintw_palette_set(TermWin *, unsigned, unsigned, const rgb *);
static void wintw_palette_get_overrides(TermWin *, Terminal *);
static void wintw_unthrottle(TermWin *win, size_t bufsize);

static const TermWinVtable windows_termwin_vt = {
    .grapheme_clusters = true,
    .get_geometry = wintw_get_geometry,
    .set_synchronized_update = wintw_set_synchronized_update,
    .setup_draw_ctx = wintw_setup_draw_ctx,
    .draw_text = wintw_draw_text,
    .draw_cursor = wintw_draw_cursor,
    .draw_trust_sigil = wintw_draw_trust_sigil,
    .char_width = wintw_char_width,
    .free_draw_ctx = wintw_free_draw_ctx,
    .set_cursor_pos = wintw_set_cursor_pos,
    .set_raw_mouse_mode = wintw_set_raw_mouse_mode,
    .set_raw_mouse_mode_pointer = wintw_set_raw_mouse_mode_pointer,
    .set_scrollbar = wintw_set_scrollbar,
    .bell = wintw_bell,
    .clip_write = wintw_clip_write,
    .clip_request_paste = wintw_clip_request_paste,
    .osc52_write = nemo_osc52_system_write,
    .osc52_read = nemo_osc52_system_read,
    .refresh = wintw_refresh,
    .request_resize = wintw_request_resize,
    .request_window_resize = wintw_request_window_resize,
    .set_title = wintw_set_title,
    .set_icon_title = wintw_set_icon_title,
    .set_minimised = wintw_set_minimised,
    .set_maximised = wintw_set_maximised,
    .move = wintw_move,
    .set_zorder = wintw_set_zorder,
    .palette_set = wintw_palette_set,
    .palette_get_overrides = wintw_palette_get_overrides,
    .unthrottle = wintw_unthrottle,
};


const bool share_can_be_downstream = true;
const bool share_can_be_upstream = true;

static bool is_utf8(WinGuiSeat *wgs)
{
    return wgs->ucsdata.line_codepage == CP_UTF8;
}

static bool win_seat_is_utf8(Seat *seat)
{
    WinGuiSeat *wgs = container_of(seat, WinGuiSeat, seat);
    return is_utf8(wgs);
}

static char *win_seat_get_ttymode(Seat *seat, const char *mode)
{
    WinGuiSeat *wgs = container_of(seat, WinGuiSeat, seat);
    return term_get_ttymode(wgs->term, mode);
}

static StripCtrlChars *win_seat_stripctrl_new(
    Seat *seat, BinarySink *bs_out, SeatInteractionContext sic)
{
    WinGuiSeat *wgs = container_of(seat, WinGuiSeat, seat);
    return stripctrl_new_term(bs_out, false, 0, wgs->term);
}

static size_t win_seat_output(
    Seat *seat, SeatOutputType type, const void *, size_t);
static bool win_seat_eof(Seat *seat);
static SeatPromptResult win_seat_get_userpass_input(Seat *seat, prompts_t *p);
static void win_seat_notify_remote_exit(Seat *seat);
static void win_seat_connection_fatal(Seat *seat, const char *msg);
static void win_seat_nonfatal(Seat *seat, const char *msg);
static void win_seat_update_specials_menu(Seat *seat);
static void win_seat_set_busy_status(Seat *seat, BusyStatus status);
static void win_seat_set_trust_status(Seat *seat, bool trusted);
static bool win_seat_can_set_trust_status(Seat *seat);
static bool win_seat_get_cursor_position(Seat *seat, int *x, int *y);
static bool win_seat_get_window_pixel_size(Seat *seat, int *x, int *y);

static const SeatVtable win_seat_vt = {
    .output = win_seat_output,
    .eof = win_seat_eof,
    .sent = nullseat_sent,
    .banner = nullseat_banner_to_stderr,
    .get_userpass_input = win_seat_get_userpass_input,
    .notify_session_started = nullseat_notify_session_started,
    .notify_remote_exit = win_seat_notify_remote_exit,
    .notify_remote_disconnect = nullseat_notify_remote_disconnect,
    .connection_fatal = win_seat_connection_fatal,
    .nonfatal = win_seat_nonfatal,
    .update_specials_menu = win_seat_update_specials_menu,
    .get_ttymode = win_seat_get_ttymode,
    .set_busy_status = win_seat_set_busy_status,
    .confirm_ssh_host_key = win_seat_confirm_ssh_host_key,
    .confirm_weak_crypto_primitive = win_seat_confirm_weak_crypto_primitive,
    .confirm_weak_cached_hostkey = win_seat_confirm_weak_cached_hostkey,
    .prompt_descriptions = win_seat_prompt_descriptions,
    .is_utf8 = win_seat_is_utf8,
    .echoedit_update = nullseat_echoedit_update,
    .get_display = nullseat_get_display,
    .get_windowid = nullseat_get_windowid,
    .get_window_pixel_size = win_seat_get_window_pixel_size,
    .stripctrl_new = win_seat_stripctrl_new,
    .set_trust_status = win_seat_set_trust_status,
    .can_set_trust_status = win_seat_can_set_trust_status,
    .has_mixed_input_stream = nullseat_has_mixed_input_stream_yes,
    .verbose = nullseat_verbose_yes,
    .interactive = nullseat_interactive_yes,
    .get_cursor_position = win_seat_get_cursor_position,
};

static bool start_backend(WinGuiSeat *wgs)
{
    const struct BackendVtable *vt;
    char *error, *realhost;
    int i;

    /* A restart must not receive a delayed paste intended for the old shell. */
    wgs->session_id = ++next_session_id;
    SetPropW(wgs->term_hwnd, L"NemotermSessionId", (HANDLE)wgs->session_id);
    nemo_cwd_clear(&wgs->term->working_directory);
    wgs->cmdline_get_passwd_state = cmdline_get_passwd_input_state_new;

    vt = backend_vt_from_conf(wgs->conf);

    seat_set_trust_status(&wgs->seat, true);
    error = backend_init(vt, &wgs->seat, &wgs->backend, wgs->logctx, wgs->conf,
                         conf_get_str(wgs->conf, CONF_host),
                         conf_get_int(wgs->conf, CONF_port),
                         &realhost,
                         conf_get_bool(wgs->conf, CONF_tcp_nodelay),
                         conf_get_bool(wgs->conf, CONF_tcp_keepalives));
    if (error) {
        char *str = dupprintf("%s Error", appname);
        char *msg;
        if (cmdline_tooltype & TOOLTYPE_NONNETWORK) {
            /* Special case for pterm. */
            msg = dupprintf("Unable to open terminal:\n%s", error);
        } else {
            msg = dupprintf("Unable to open connection to\n%s\n%s",
                            conf_dest(wgs->conf), error);
        }
        sfree(error);
        MessageBox(wgs->term_hwnd, msg, str, MB_ICONERROR | MB_OK);
        sfree(str);
        sfree(msg);
        wgs->session_closed = true;
        return false;
    }
    term_setup_window_titles(wgs->term, realhost);
    sfree(realhost);

    /*
     * Connect the terminal to the backend for resize purposes.
     */
    term_provide_backend(wgs->term, wgs->backend);

    /*
     * Set up a line discipline.
     */
    wgs->ldisc = ldisc_create(wgs->conf, wgs->term, wgs->backend, &wgs->seat);

    /*
     * Destroy the Restart Session menu item. (This will return
     * failure if it's already absent, as it will be the very first
     * time we call this function. We ignore that, because as long
     * as the menu item ends up not being there, we don't care
     * whether it was us who removed it or not!)
     */
    for (i = 0; i < lenof(wgs->popup_menus); i++) {
        DeleteMenu(wgs->popup_menus[i].menu, IDM_RESTART, MF_BYCOMMAND);
    }

    wgs->session_closed = false;
    return true;
}

static void close_session(void *vctx)
{
    WinGuiSeat *wgs = (WinGuiSeat *)vctx;
    char *newtitle;
    int i;

    wgs->session_closed = true;
    newtitle = dupprintf("%s (inactive)", appname);
    win_set_icon_title(&wgs->termwin, newtitle, DEFAULT_CODEPAGE);
    win_set_title(&wgs->termwin, newtitle, DEFAULT_CODEPAGE);
    sfree(newtitle);

    if (wgs->ldisc) {
        ldisc_free(wgs->ldisc);
        wgs->ldisc = NULL;
    }
    if (wgs->backend) {
        term_provide_backend(wgs->term, NULL);
        backend_free(wgs->backend);
        wgs->backend = NULL;
        seat_update_specials_menu(&wgs->seat);
    }

    /*
     * Show the Restart Session menu item. Do a precautionary
     * delete first to ensure we never end up with more than one.
     */
    for (i = 0; i < lenof(wgs->popup_menus); i++) {
        DeleteMenu(wgs->popup_menus[i].menu, IDM_RESTART, MF_BYCOMMAND);
        InsertMenu(wgs->popup_menus[i].menu, IDM_DUPSESS,
                   MF_BYCOMMAND | MF_ENABLED, IDM_RESTART, "&Restart Session");
    }
}

/*
 * Some machinery to deal with switching the window type between ANSI
 * and Unicode. We prefer Unicode, but some PuTTY builds still try to
 * run on machines so old that they don't support that mode. So we're
 * prepared to fall back to an ANSI window if we have to. For this
 * purpose, we swap out a few Windows API functions, and wrap
 * SetWindowText so that if we're not in Unicode mode we first convert
 * the wide string we're given.
 */
static bool unicode_window;
static BOOL (WINAPI *sw_PeekMessage)(LPMSG, HWND, UINT, UINT, UINT);
static LRESULT (WINAPI *sw_DispatchMessage)(const MSG *);
static LRESULT (WINAPI *sw_DefWindowProc)(HWND, UINT, WPARAM, LPARAM);
static void sw_SetWindowText(HWND hwnd, wchar_t *text)
{
    if (unicode_window) {
        SetWindowTextW(hwnd, text);
    } else {
        char *mb = dup_wc_to_mb(DEFAULT_CODEPAGE, text, "?");
        SetWindowTextA(hwnd, mb);
        sfree(mb);
    }
}

static HINSTANCE hprev;

/*
 * Also, registering window classes has to be done in a fiddly way.
 */
#define SETUP_WNDCLASS(wndclass, classname) do {                        \
        wndclass.style = 0;                                             \
        wndclass.lpfnWndProc = WndProc;                                 \
        wndclass.cbClsExtra = 0;                                        \
        wndclass.cbWndExtra = 0;                                        \
        wndclass.hInstance = hinst;                                     \
        wndclass.hIcon = LoadIcon(hinst, MAKEINTRESOURCE(IDI_MAINICON)); \
        wndclass.hCursor = LoadCursor(NULL, IDC_IBEAM);                 \
        wndclass.hbrBackground = NULL;                                  \
        wndclass.lpszMenuName = NULL;                                   \
        wndclass.lpszClassName = classname;                             \
    } while (0)
wchar_t *terminal_window_class_w(void)
{
    static wchar_t *classname = NULL;
    if (!classname)
        classname = dup_mb_to_wc(DEFAULT_CODEPAGE, appname);
    if (!hprev) {
        WNDCLASSW wndclassw;
        SETUP_WNDCLASS(wndclassw, classname);
        RegisterClassW(&wndclassw);
    }
    return classname;
}
char *terminal_window_class_a(void)
{
    static char *classname = NULL;
    if (!classname)
        classname = dupcat(appname, ".ansi");
    if (!hprev) {
        WNDCLASSA wndclassa;
        SETUP_WNDCLASS(wndclassa, classname);
        RegisterClassA(&wndclassa);
    }
    return classname;
}

HINSTANCE hinst;

/* Takes ownership of conf on both success and failure. Application state and
 * the message pump outlive every session created here. */
static WinGuiSeat *wgs_create(Conf *conf, int show)
{
    int guess_width, guess_height;
    WinGuiSeat *wgs = snew(WinGuiSeat);
    memset(wgs, 0, sizeof(*wgs));
    wgs_link(wgs);

    wgs->seat.vt = &win_seat_vt;
    wgs->logpolicy.vt = &win_gui_logpolicy_vt;
    wgs->termwin.vt = &windows_termwin_vt;

    wgs->caret_x = wgs->caret_y = -1;
    wgs->busy_status = BUSY_NOT;

    wgs->conf = conf;
    wgs->tabbed = conf_get_bool(conf,CONF_nemo_tabs);

    memset(&wgs->ucsdata, 0, sizeof(wgs->ucsdata));

    conf_cache_data(wgs);

    /*
     * Guess some defaults for the window size. This all gets
     * updated later, so we don't really care too much. However, we
     * do want the font width/height guesses to correspond to a
     * large font rather than a small one...
     */

    wgs->font_width = 10;
    wgs->font_height = 20;
    wgs->extra_width = 25;
    wgs->extra_height = 28;
    guess_width = wgs->extra_width + wgs->font_width * conf_get_int(
        wgs->conf, CONF_width);
    guess_height = wgs->extra_height + wgs->font_height * conf_get_int(
        wgs->conf, CONF_height);
    {
        RECT r;
        get_fullscreen_rect(wgs, &r);
        if (guess_width > r.right - r.left)
            guess_width = r.right - r.left;
        if (guess_height > r.bottom - r.top)
            guess_height = r.bottom - r.top;
    }

    {
        if (wgs->tabbed && !nemo_host_create(conf,guess_width,guess_height)) {
            MessageBoxA(NULL,"Unable to create tab host",appname,MB_OK|MB_ICONERROR);
            wgs_cleanup(wgs);return NULL;
        }
        int winmode = (wgs->tabbed ? WS_CHILD|WS_CLIPSIBLINGS : WS_OVERLAPPEDWINDOW) | WS_VSCROLL;
        int exwinmode = 0;
        const struct BackendVtable *vt =
            backend_vt_from_proto(be_default_protocol);
        bool resize_forbidden = false;
        if (vt && vt->flags & BACKEND_RESIZE_FORBIDDEN)
            resize_forbidden = true;
        wchar_t *uappname = dup_mb_to_wc(DEFAULT_CODEPAGE, appname);
        wgs->window_name = dup_mb_to_wc(DEFAULT_CODEPAGE, appname);
        wgs->icon_name = dup_mb_to_wc(DEFAULT_CODEPAGE, appname);
        if (!conf_get_bool(wgs->conf, CONF_scrollbar))
            winmode &= ~(WS_VSCROLL);
        if (conf_get_int(wgs->conf, CONF_resize_action) == RESIZE_DISABLED ||
            resize_forbidden)
            winmode &= ~(WS_THICKFRAME | WS_MAXIMIZEBOX);
        if (!wgs->tabbed && conf_get_bool(wgs->conf, CONF_alwaysontop))
            exwinmode |= WS_EX_TOPMOST;
        if (conf_get_bool(wgs->conf, CONF_sunken_edge))
            exwinmode |= WS_EX_CLIENTEDGE;

#ifdef TEST_ANSI_WINDOW
        /* For developer testing of ANSI window support, pretend
         * CreateWindowExW failed */
        wgs->term_hwnd = NULL;
        SetLastError(ERROR_CALL_NOT_IMPLEMENTED);
#else
        unicode_window = true;
        sw_PeekMessage = PeekMessageW;
        sw_DispatchMessage = DispatchMessageW;
        sw_DefWindowProc = DefWindowProcW;
        wgs->term_hwnd = CreateWindowExW(
            exwinmode, terminal_window_class_w(), uappname,
            winmode, wgs->tabbed ? 0 : CW_USEDEFAULT, wgs->tabbed ? 0 : CW_USEDEFAULT,
            guess_width, guess_height, wgs->tabbed ? tab_host.hwnd : NULL, NULL, hinst, NULL);
#endif

#if defined LEGACY_WINDOWS || defined TEST_ANSI_WINDOW
        if (!wgs->term_hwnd && GetLastError() == ERROR_CALL_NOT_IMPLEMENTED) {
            /* Fall back to an ANSI window, swapping in all the ANSI
             * window message handling functions */
            unicode_window = false;
            sw_PeekMessage = PeekMessageA;
            sw_DispatchMessage = DispatchMessageA;
            sw_DefWindowProc = DefWindowProcA;
            wgs->term_hwnd = CreateWindowExA(
                exwinmode, terminal_window_class_a(), appname,
                winmode, CW_USEDEFAULT, CW_USEDEFAULT,
                guess_width, guess_height, NULL, NULL, hinst, NULL);
        }
#endif

        if (!wgs->term_hwnd) {
            char *message = dupprintf("Unable to create terminal window: %s",
                                      win_strerror(GetLastError()));
            MessageBoxA(GetActiveWindow(), message, appname, MB_OK | MB_ICONERROR);
            sfree(message);
            sfree(uappname);
            wgs_cleanup(wgs);
            return NULL;
        }
        memset(&wgs->dpi_info, 0, sizeof(struct _dpi_info));
        init_dpi_info(wgs);
        sfree(uappname);
    }

    SetWindowLongPtr(wgs->term_hwnd, GWLP_USERDATA, (LONG_PTR)wgs);
    DragAcceptFiles(wgs->term_hwnd,TRUE);

    /*
     * Initialise the fonts, simultaneously correcting the guesses
     * for font_{width,height}.
     */
    init_fonts(wgs, 0, 0);

    /*
     * Prepare a logical palette.
     */
    init_palette(wgs);
    if (wgs->tabbed) { tab_host.dpi=wgs->dpi_info.cur_dpi.x; nemo_host_font(); nemo_host_layout(); }

    /*
     * Correct the guesses for extra_{width,height}.
     */
    {
        RECT cr, wr;
        GetWindowRect(wgs_window(wgs), &wr);
        GetClientRect(wgs->term_hwnd, &cr);
        wgs->offset_width = wgs->offset_height =
            conf_get_int(wgs->conf, CONF_window_border);
        wgs->extra_width =
            wr.right - wr.left - cr.right + cr.left + wgs->offset_width*2;
        wgs->extra_height =
            wr.bottom - wr.top - cr.bottom + cr.top +wgs->offset_height*2;
    }

    /*
     * Clamp the actual-font grid before allocating terminal screen buffers.
     * Oversized requests must not allocate an offscreen grid, then move its
     * blank rows into history when shrinking to the work area.
     */
    RECT startup_work;
    if (get_workingarea_rect(wgs, &startup_work)) {
        int cols = max(1, (startup_work.right-startup_work.left-wgs->extra_width) /
                           max(1, wgs->font_width));
        int rows = max(1, (startup_work.bottom-startup_work.top-wgs->extra_height) /
                           max(1, wgs->font_height));
        conf_set_int(wgs->conf, CONF_width,
                     max(1, min(cols, conf_get_int(wgs->conf, CONF_width))));
        conf_set_int(wgs->conf, CONF_height,
                     max(1, min(rows, conf_get_int(wgs->conf, CONF_height))));
    }

    if (wgs->tabbed && tab_host.active) {
        RECT cr;GetClientRect(wgs->term_hwnd,&cr);
        int border=conf_get_int(conf,CONF_window_border);
        conf_set_int(conf,CONF_width,max(1,(cr.right-2*border)/wgs->font_width));
        conf_set_int(conf,CONF_height,max(1,(cr.bottom-2*border)/wgs->font_height));
    }
    /* The window exists before terminal timers can be scheduled. */
    wgs->term = term_init(wgs->conf, &wgs->ucsdata, &wgs->termwin);
    term_set_cell_size(wgs->term, wgs->font_width, wgs->font_height);
    setup_clipboards(wgs->term, wgs->conf);
    wgs->logctx = log_init(&wgs->logpolicy, wgs->conf);
    term_provide_logctx(wgs->term, wgs->logctx);
    term_size(wgs->term, conf_get_int(wgs->conf, CONF_height),
              conf_get_int(wgs->conf, CONF_width),
              conf_get_int(wgs->conf, CONF_savelines));

    guess_width = wgs->extra_width + wgs->font_width * wgs->term->cols;
    guess_height = wgs->extra_height + wgs->font_height * wgs->term->rows;

    /*
     * Resize the window to that size, also repositioning it if it's extended
     * off the edge of a monitor.
     */
    {
        /* Find the previous coordinates of the window */
        RECT winr;
        GetWindowRect(wgs_window(wgs), &winr);

        int x = winr.left;
        int y = winr.top;

        /* Adjust them if necessary */
        RECT war;
        if (get_workingarea_rect(wgs, &war)) {
            /*
             * Try to ensure the window is entirely within the monitor's
             * working area, by adjusting its position if not.
             *
             * We first move it left, if it overlaps off the right side. Then
             * we move it right if it overlaps off the left side. This means
             * that if it's wider than the working area (so that some overlap
             * is unavoidable), we prefer to get its left edge in bounds than
             * its right edge. Similarly, we do the y checks in the same
             * order, privileging the top edge over the bottom.
             */
            if (x + guess_width > war.right)
                x = war.right - guess_width;
            if (x < war.left)
                x = war.left;
            if (y + guess_height > war.bottom)
                y = war.bottom - guess_height;
            if (y < war.top)
                y = war.top;
        }

        /* And set the window to the final size and position we've chosen */
        if (!wgs->tabbed || !tab_host.active)
        SetWindowPos(wgs_window(wgs), NULL, x, y, guess_width, guess_height,
                    SWP_NOREDRAW | SWP_NOZORDER);
    }

    nemo_renderer_configure(wgs);

    /*
     * Set up a caret bitmap, with no content.
     */
    {
        char *bits;
        int size = (wgs->font_width + 15) / 16 * 2 * wgs->font_height;
        bits = snewn(size, char);
        memset(bits, 0, size);
        wgs->caretbm = CreateBitmap(wgs->font_width, wgs->font_height,
                                    1, 1, bits);
        sfree(bits);
    }
    /* Startup SetWindowPos can deliver WM_SETFOCUS before caretbm exists.
     * Complete this seat's caret only if it actually owns keyboard focus;
     * creating an inactive session must not replace another seat's caret. */
    if (wgs->caretbm && GetFocus() == wgs->term_hwnd) {
        CreateCaret(wgs->term_hwnd, wgs->caretbm,
                    wgs->font_width, wgs->font_height);
        ShowCaret(wgs->term_hwnd);
    }

    /*
     * Initialise the scroll bar.
     */
    {
        SCROLLINFO si;

        si.cbSize = sizeof(si);
        si.fMask = SIF_ALL | SIF_DISABLENOSCROLL;
        si.nMin = 0;
        si.nMax = wgs->term->rows - 1;
        si.nPage = wgs->term->rows;
        si.nPos = 0;
        SetScrollInfo(wgs->term_hwnd, SB_VERT, &si, false);
    }

    /*
     * Prepare the mouse handler.
     */
    wgs->lastact = MA_NOTHING;
    wgs->lastbtn = MBT_NOTHING;
    wgs->dbltime = GetDoubleClickTime();

    /*
     * Set up the session-control options on the system menu.
     */
    {
        HMENU m;
        int j;
        char *str;

        wgs->popup_menus[SYSMENU].menu = wgs->tabbed ? NULL : GetSystemMenu(wgs->term_hwnd, false);
        wgs->popup_menus[CTXMENU].menu = CreatePopupMenu();

        for (j = 0; j < lenof(wgs->popup_menus); j++) {
            m = wgs->popup_menus[j].menu;
            AppendMenu(m, MF_ENABLED, IDM_COPY, "&Copy");
            AppendMenu(m, MF_ENABLED, IDM_COPYPASTE, "Copy a&nd Paste");
            AppendMenu(m, MF_ENABLED, IDM_PASTE, "&Paste");
        }
        AppendMenu(wgs->popup_menus[CTXMENU].menu, MF_ENABLED,
                   IDM_NEMO_OPEN_LINK, "&Open Link");
        AppendMenu(wgs->popup_menus[CTXMENU].menu, MF_ENABLED,
                   IDM_NEMO_COPY_LINK, "Copy Link &Address");
        for (j = 0; j < lenof(wgs->popup_menus); j++) {
            if (!wgs->popup_menus[j].menu) continue;
            AppendMenu(wgs->popup_menus[j].menu, MF_GRAYED,
                       IDM_COPYDIR, "Copy Working Directory URI");
            HMENU shell_menu = CreatePopupMenu();
            wgs->popup_menus[j].shell_menu = shell_menu;
            AppendMenu(shell_menu, MF_ENABLED, IDM_PREVPROMPT, "&Previous Prompt");
            AppendMenu(shell_menu, MF_ENABLED, IDM_NEXTPROMPT, "&Next Prompt");
            AppendMenu(shell_menu, MF_GRAYED, IDM_SELECTCOMMAND, "Select &Command");
            AppendMenu(shell_menu, MF_GRAYED, IDM_SELECTOUTPUT, "Select &Output");
            AppendMenu(wgs->popup_menus[j].menu, MF_POPUP | MF_ENABLED,
                       (UINT_PTR)shell_menu, "Shell &Integration");
        }

        wgs->savedsess_menu = CreateMenu();
        update_savedsess_menu(wgs);

        for (j = 0; j < lenof(wgs->popup_menus); j++) {
            m = wgs->popup_menus[j].menu;

            AppendMenu(m, MF_SEPARATOR, 0, 0);
            AppendMenu(m, MF_ENABLED, IDM_SHOWLOG, "&Event Log");
            AppendMenu(m, MF_SEPARATOR, 0, 0);
            AppendMenu(m, MF_ENABLED, IDM_NEWSESS, "Ne&w Session...");
            AppendMenu(m, MF_ENABLED, IDM_DUPSESS, "&Duplicate Session");
            AppendMenu(m, MF_POPUP | MF_ENABLED, (UINT_PTR)wgs->savedsess_menu,
                       "Sa&ved Sessions");
            AppendMenu(m, MF_ENABLED, IDM_RECONF, "Chan&ge Settings...");
            AppendMenu(m, MF_SEPARATOR, 0, 0);
            AppendMenu(m, MF_ENABLED, IDM_COPYALL, "C&opy All to Clipboard");
            AppendMenu(m, MF_ENABLED, IDM_CLRSB, "C&lear Scrollback");
            AppendMenu(m, MF_ENABLED, IDM_RESET, "Rese&t Terminal");
            AppendMenu(m, MF_SEPARATOR, 0, 0);
            AppendMenu(m, (conf_get_int(wgs->conf, CONF_resize_action)
                           == RESIZE_DISABLED) ? MF_GRAYED : MF_ENABLED,
                       IDM_FULLSCREEN, "&Full Screen");
            AppendMenu(m, MF_SEPARATOR, 0, 0);
            if (has_help())
                AppendMenu(m, MF_ENABLED, IDM_HELP, "&Help");
            str = dupprintf("&About %s", appname);
            AppendMenu(m, MF_ENABLED, IDM_ABOUT, str);
            sfree(str);
        }
    }

    if (restricted_acl()) {
        lp_eventlog(&wgs->logpolicy, "Running with restricted process ACL");
    }

    if (!start_backend(wgs)) {
        wgs_cleanup(wgs);
        return NULL;
    }

    /*
     * Set up the initial input locale.
     */
    set_input_locale(wgs, GetKeyboardLayout(0));

    /*
     * Finally show the window!
     */
    if (wgs->tabbed) {
        wgs->tab_ready=true;nemo_host_layout();nemo_host_select(wgs);
    }
    ShowWindow(wgs_window(wgs), show);
    SetForegroundWindow(wgs_window(wgs));
    if (wgs->tabbed) SetFocus(wgs->term_hwnd);

    term_set_focus(wgs->term, wgs_active(wgs) && GetForegroundWindow() == wgs_window(wgs));
    UpdateWindow(wgs->term_hwnd);

    gui_terminal_ready(wgs->term_hwnd, &wgs->seat, wgs->backend);

    return wgs;
}

#include "nemo_tabs_host.inc"
#include "nemo_debug_ui.inc"

/* Socket notifications belong to the application, not the first session's
 * window. Closing that session must not orphan another backend's events. */
static LRESULT CALLBACK app_event_proc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp)
{
    if (msg == NEMO_DEBUG_MESSAGE) {
        nemo_debug_dispatch();
        return 0;
    }
    if (msg == WM_NETEVENT || msg == WM_DONE_WITH_SOCKET) {
        winselgui_response(msg, wp, lp);
        return 0;
    }
    return DefWindowProcW(hwnd, msg, wp, lp);
}

int WINAPI WinMain(HINSTANCE inst, HINSTANCE prev, LPSTR cmdline, int show)
{
    MSG msg;
    HRESULT hr;

    dll_hijacking_protection();
    enable_dit();

    hinst = inst;
    hprev = prev;

    sk_init();

    init_common_controls();

    /* Set Explicit App User Model Id so that jump lists don't cause
       PuTTY to hang on to removable media. */

    set_explicit_app_user_model_id();

    /* Ensure a Maximize setting in Explorer doesn't maximise the
     * config box. */
    defuse_showwindow();

    init_winver();

    /*
     * If we're running a version of Windows that doesn't support
     * WM_MOUSEWHEEL, find out what message number we should be
     * using instead.
     */
    if (osMajorVersion < 4 ||
        (osMajorVersion == 4 && osPlatformId != VER_PLATFORM_WIN32_NT))
        wm_mousewheel = RegisterWindowMessage("MSWHEEL_ROLLMSG");

    init_help();

    init_winfuncs();

    setup_gui_timing();

    Conf *conf = conf_new();
    /*
     * Initialize COM.
     */
    hr = CoInitialize(NULL);
    if (hr != S_OK && hr != S_FALSE) {
        char *str = dupprintf("%s Fatal Error", appname);
        MessageBox(NULL, "Failed to initialize COM subsystem",
                   str, MB_OK | MB_ICONEXCLAMATION);
        sfree(str);
        conf_free(conf);
        return 1;
    }

    /*
     * Process the command line.
     * (If the command line doesn't provide enough info to start a
     * session, this will detour via the config box.)
     */
    gui_term_process_cmdline(conf, cmdline);

    WNDCLASSW event_class = {0};
    event_class.lpfnWndProc = app_event_proc;
    event_class.hInstance = hinst;
    event_class.lpszClassName = L"NemotermEvents";
    RegisterClassW(&event_class);
    app_event_hwnd = CreateWindowW(event_class.lpszClassName, L"", 0,
        0, 0, 0, 0, HWND_MESSAGE, NULL, hinst, NULL);
    if (!app_event_hwnd)
        modalfatalbox("Unable to create session event window: %s",
                      win_strerror(GetLastError()));
    winselgui_set_hwnd(app_event_hwnd);
    get_sesslist(&sesslist, true);
    if (!wgs_create(conf, show))
        cleanup_exit(1);
    if (nemo_debug_enabled && !nemo_debug_start(app_event_hwnd,nemo_debug_ui))
        modalfatalbox("Unable to start local automation: %s",win_strerror(GetLastError()));

    while (1) {
        int n;
        DWORD timeout;

        if (toplevel_callback_pending() ||
            PeekMessage(&msg, NULL, 0, 0, PM_NOREMOVE)) {
            /*
             * If we have anything we'd like to do immediately, set
             * the timeout for MsgWaitForMultipleObjects to zero so
             * that we'll only do a quick check of our handles and
             * then get on with whatever that was.
             *
             * One such option is a pending toplevel callback. The
             * other is a non-empty Windows message queue, which you'd
             * think we could leave to MsgWaitForMultipleObjects to
             * check for us along with all the handles, but in fact we
             * can't because once PeekMessage in one iteration of this
             * loop has removed a message from the queue, the whole
             * queue is considered uninteresting by the next
             * invocation of MWFMO. So we check ourselves whether the
             * message queue is non-empty, and if so, set this timeout
             * to zero to ensure MWFMO doesn't block.
             */
            timeout = 0;
        } else {
            timeout = INFINITE;
            /* The messages seem unreliable; especially if we're being tricky */
            HWND foreground = GetForegroundWindow();
            for (struct WinGuiSeatListNode *node = wgslisthead.next;
                 node != &wgslisthead; node = node->next) {
                WinGuiSeat *wgs = container_of(node, WinGuiSeat, wgslistnode);
                if (!wgs->closing && wgs->term)
                    term_set_focus(wgs->term, wgs_active(wgs) && foreground == wgs_window(wgs));
            }
        }

        HandleWaitList *hwl = get_handle_wait_list();

        n = MsgWaitForMultipleObjects(hwl->nhandles, hwl->handles, false,
                                      timeout, QS_ALLINPUT);

        if ((unsigned)(n - WAIT_OBJECT_0) < (unsigned)hwl->nhandles)
            handle_wait_activate(hwl, n - WAIT_OBJECT_0);
        handle_wait_list_free(hwl);

        while (sw_PeekMessage(&msg, NULL, 0, 0, PM_REMOVE)) {
            if (msg.message == WM_QUIT)
                goto finished;         /* two-level break */

            HWND logbox = event_log_window();
            if (!(IsWindow(logbox) && IsDialogMessage(logbox, &msg)))
                sw_DispatchMessage(&msg);

            /*
             * WM_NETEVENT messages seem to jump ahead of others in
             * the message queue. I'm not sure why; the docs for
             * PeekMessage mention that messages are prioritised in
             * some way, but I'm unclear on which priorities go where.
             *
             * Anyway, in practice I observe that WM_NETEVENT seems to
             * jump to the head of the queue, which means that if we
             * were to only process one message every time round this
             * loop, we'd get nothing but NETEVENTs if the server
             * flooded us with data, and stop responding to any other
             * kind of window message. So instead, we keep on round
             * this loop until we've consumed at least one message
             * that _isn't_ a NETEVENT, or run out of messages
             * completely (whichever comes first). And we don't go to
             * run_toplevel_callbacks (which is where the netevents
             * are actually processed, causing fresh NETEVENT messages
             * to appear) until we've done this.
             */
            if (msg.message != WM_NETEVENT)
                break;
        }

        run_toplevel_callbacks();
    }

  finished:
    cleanup_exit(msg.wParam);          /* this doesn't return... */
    return msg.wParam;                 /* ... but optimiser doesn't know */
}

/* Shared submenus must be detached from both parents before destroying them.
 * DestroyWindow owns the system menu; we own the context menu. */
static void wgs_free_menus(WinGuiSeat *wgs)
{
    for (size_t j = 0; j < lenof(wgs->popup_menus); j++) {
        HMENU menu = wgs->popup_menus[j].menu;
        for (int i = GetMenuItemCount(menu)-1; i >= 0; i--) {
            HMENU sub = GetSubMenu(menu, i);
            if (sub && (sub == wgs->savedsess_menu || sub == wgs->specials_menu))
                RemoveMenu(menu, i, MF_BYPOSITION);
        }
    }
    if (wgs->savedsess_menu) DestroyMenu(wgs->savedsess_menu);
    if (wgs->specials_menu) DestroyMenu(wgs->specials_menu);
    if (wgs->popup_menus[CTXMENU].menu)
        DestroyMenu(wgs->popup_menus[CTXMENU].menu);
    wgs->savedsess_menu = wgs->specials_menu = NULL;
    memset(wgs->popup_menus, 0, sizeof(wgs->popup_menus));
}

static void wgs_request_close(WinGuiSeat *wgs)
{
    if (wgs->closing) return;
    wgs->closing = true;
    /* Never free a seat on a backend or WndProc stack. */
    queue_toplevel_callback(wgs_cleanup, wgs);
}

static void wgs_cleanup(void *vctx)
{
    WinGuiSeat *wgs = vctx;
    wgs->closing = true;
    nemo_host_remove(wgs);
    delete_callbacks_for_context(wgs);
    expire_timer_context(wgs);
    nemo_osc52_window_free(wgs);
    nemo_link_free(wgs);
    if (wgs->term) term_end_synchronized_update(wgs->term);

    if (wgs->ldisc) {
        ldisc_free(wgs->ldisc);
        wgs->ldisc = NULL;
    }
    if (wgs->term) term_provide_backend(wgs->term, NULL);
    if (wgs->backend) {
        backend_free(wgs->backend);
        wgs->backend = NULL;
    }
    wgs->session_closed = true;
    wgs_free_menus(wgs);
    nemo_gpu_free(wgs->gpu);
    wgs->gpu = NULL;

    /* Destroy the HWND while callbacks can still use terminal/font/input
     * state. COM and other windows can dispatch messages after this returns. */
    if (wgs->term_hwnd &&
        GetWindowLongPtr(wgs->term_hwnd, GWLP_USERDATA) == (LONG_PTR)wgs)
        DestroyWindow(wgs->term_hwnd);
    wgs->term_hwnd = NULL;
    if (wgs->term) term_free(wgs->term);
    wgs->term = NULL;
    if (wgs->logctx) log_free(wgs->logctx);
    nemo_keyboard_free(wgs);
    nemo_cluster_free(&wgs->cluster_renderer);
    deinit_fonts(wgs);
    if (wgs->caretbm) DeleteObject(wgs->caretbm);
    sfree(wgs->logpal);
    if (wgs->pal) DeleteObject(wgs->pal);
    sfree(wgs->window_name);
    sfree(wgs->icon_name);
    conf_free(wgs->conf);
    /* Freeing dependent objects may cancel or schedule more callbacks. */
    delete_callbacks_for_context(wgs);
    expire_timer_context(wgs);
    wgs_unlink(wgs);
    sfree(wgs);
    if (wgslisthead.next == &wgslisthead) {
        if (tab_host.hwnd) DestroyWindow(tab_host.hwnd);
        if (tab_host.font) DeleteObject(tab_host.font);
        memset(&tab_host,0,sizeof(tab_host));
        PostQuitMessage(0);
    }
}

char *handle_restrict_acl_cmdline_prefix(char *p)
{
    /*
     * Process the &R prefix on a command line, which is equivalent to
     * -restrict-acl but lexically easier to prepend when another
     * instance of ourself automatically constructs a command line.
     *
     * If successful, restricts the process ACL and advances the input
     * pointer past the prefix. Returns the updated pointer (whether
     * it moved or not).
     */
    while (*p && isspace((unsigned char)*p))
        p++;
    if (*p == '&' && p[1] == 'R' &&
        (!p[2] || p[2] == '@' || p[2] == '&')) {
        /* &R restrict-acl prefix */
        restrict_process_acl();
        p += 2;
    }
    return p;
}

bool handle_special_sessionname_cmdline(char *p, Conf *conf)
{
    /*
     * Process the special form of command line with an initial @
     * followed by the name of a saved session with _no quoting or
     * escaping_. This is a very convenient means of automated
     * saved-session launching, via IDM_SAVEDSESS or Windows 7 jump
     * lists.
     *
     * If successful, the whole command line has been interpreted in
     * this way, so there's nothing left to parse into other arguments.
     */
    if (*p != '@')
        return false;

    ptrlen sessionname = ptrlen_from_asciz(p + 1);
    while (sessionname.len > 0 &&
           isspace(((unsigned char *)sessionname.ptr)[sessionname.len-1]))
        sessionname.len--;

    char *dup = mkstr(sessionname);
    bool loaded = do_defaults(dup, conf);
    sfree(dup);

    return loaded;
}

bool handle_special_filemapping_cmdline(char *p, Conf *conf)
{
    /*
     * Process the special form of command line with an initial &
     * followed by the hex value of a HANDLE for a file mapping object
     * and the size of the data contained in it, which we must
     * interpret as a serialised Conf.
     *
     * If successful, the whole command line has been interpreted in
     * this way, so there's nothing left to parse into other arguments.
     */

    if (*p != '&')
        return false;

    HANDLE filemap;
    unsigned cpsize;
    if (sscanf(p + 1, "%p:%u", &filemap, &cpsize) != 2)
        return false;

    void *cp = MapViewOfFile(filemap, FILE_MAP_READ, 0, 0, cpsize);
    if (!cp)
        return false;

    BinarySource src[1];
    BinarySource_BARE_INIT(src, cp, cpsize);
    if (!conf_deserialise(conf, src))
        modalfatalbox("Serialised configuration data was invalid");
    UnmapViewOfFile(cp);
    CloseHandle(filemap);
    return true;
}

static void setup_clipboards(Terminal *term, Conf *conf)
{
    assert(term->mouse_select_clipboards[0] == CLIP_LOCAL);

    term->n_mouse_select_clipboards = 1;

    if (conf_get_bool(conf, CONF_mouseautocopy)) {
        term->mouse_select_clipboards[
            term->n_mouse_select_clipboards++] = CLIP_SYSTEM;
    }

    switch (conf_get_int(conf, CONF_mousepaste)) {
      case CLIPUI_IMPLICIT:
        term->mouse_paste_clipboard = CLIP_LOCAL;
        break;
      case CLIPUI_EXPLICIT:
        term->mouse_paste_clipboard = CLIP_SYSTEM;
        break;
      default:
        term->mouse_paste_clipboard = CLIP_NULL;
        break;
    }
}

/*
 * Clean up and exit.
 */
void cleanup_exit(int code)
{
    nemo_debug_stop();
    /*
     * Clean up.
     */
    while (wgslisthead.next != &wgslisthead) {
        WinGuiSeat *wgs = container_of(
            wgslisthead.next, WinGuiSeat, wgslistnode);
        wgs_cleanup(wgs);
    }
    sk_cleanup();
    winselgui_clear_hwnd();
    if (app_event_hwnd) DestroyWindow(app_event_hwnd);
    app_event_hwnd = NULL;
    get_sesslist(&sesslist, false);

    random_save_seed();
    shutdown_help();

    /* Clean up COM. */
    CoUninitialize();

    exit(code);
}

/*
 * Refresh the saved-session submenu from `sesslist'.
 */
static void update_savedsess_menu(WinGuiSeat *wgs)
{
    int i;
    while (DeleteMenu(wgs->savedsess_menu, 0, MF_BYPOSITION)) ;
    /* skip sesslist.sessions[0] == Default Settings */
    for (i = 1;
         i < ((sesslist.nsessions <= MENU_SAVED_MAX+1) ? sesslist.nsessions
                                                       : MENU_SAVED_MAX+1);
         i++)
        AppendMenu(wgs->savedsess_menu, MF_ENABLED,
                   IDM_SAVED_MIN + (i-1)*MENU_SAVED_STEP,
                   sesslist.sessions[i]);
    if (sesslist.nsessions <= 1)
        AppendMenu(wgs->savedsess_menu, MF_GRAYED, IDM_SAVED_MIN,
                   "(No sessions)");
}

/*
 * Update the Special Commands submenu.
 */
static void win_seat_update_specials_menu(Seat *seat)
{
    WinGuiSeat *wgs = container_of(seat, WinGuiSeat, seat);
    HMENU new_menu;
    int i, j;

    if (wgs->backend)
        wgs->specials = backend_get_specials(wgs->backend);
    else
        wgs->specials = NULL;

    if (wgs->specials) {
        /* We can't use Windows to provide a stack for submenus, so
         * here's a lame "stack" that will do for now. */
        HMENU saved_menu = NULL;
        int nesting = 1;
        new_menu = CreatePopupMenu();
        for (i = 0; nesting > 0; i++) {
            assert(IDM_SPECIAL_MIN + 0x10 * i < IDM_SPECIAL_MAX);
            switch (wgs->specials[i].code) {
              case SS_SEP:
                AppendMenu(new_menu, MF_SEPARATOR, 0, 0);
                break;
              case SS_SUBMENU:
                assert(nesting < 2);
                nesting++;
                saved_menu = new_menu; /* XXX lame stacking */
                new_menu = CreatePopupMenu();
                AppendMenu(saved_menu, MF_POPUP | MF_ENABLED,
                           (UINT_PTR) new_menu, wgs->specials[i].name);
                break;
              case SS_EXITMENU:
                nesting--;
                if (nesting) {
                    new_menu = saved_menu; /* XXX lame stacking */
                    saved_menu = NULL;
                }
                break;
              default:
                AppendMenu(new_menu, MF_ENABLED, IDM_SPECIAL_MIN + 0x10 * i,
                           wgs->specials[i].name);
                break;
            }
        }
        /* Squirrel the highest special. */
        wgs->n_specials = i - 1;
    } else {
        new_menu = NULL;
        wgs->n_specials = 0;
    }

    for (j = 0; j < lenof(wgs->popup_menus); j++) {
        if (wgs->specials_menu) {
            /* XXX does this free up all submenus? */
            RemoveMenu(wgs->popup_menus[j].menu, (UINT_PTR)wgs->specials_menu,
                       MF_BYCOMMAND);
            DeleteMenu(wgs->popup_menus[j].menu, IDM_SPECIALSEP, MF_BYCOMMAND);
        }
        if (new_menu) {
            InsertMenu(wgs->popup_menus[j].menu, IDM_SHOWLOG,
                       MF_BYCOMMAND | MF_POPUP | MF_ENABLED,
                       (UINT_PTR) new_menu, "S&pecial Command");
            InsertMenu(wgs->popup_menus[j].menu, IDM_SHOWLOG,
                       MF_BYCOMMAND | MF_SEPARATOR, IDM_SPECIALSEP, 0);
        }
    }
    if (wgs->specials_menu) DestroyMenu(wgs->specials_menu);
    wgs->specials_menu = new_menu;
}

static void update_mouse_pointer(WinGuiSeat *wgs)
{
    LPTSTR curstype = NULL;
    bool force_visible = false;
    static bool forced_visible = false;
    switch (wgs->busy_status) {
      case BUSY_NOT:
        if (nemo_link_hand_cursor(wgs))
            curstype = IDC_HAND;
        else if (wgs->pointer_indicates_raw_mouse)
            curstype = IDC_ARROW;
        else
            curstype = IDC_IBEAM;
        break;
      case BUSY_WAITING:
        curstype = IDC_APPSTARTING; /* this may be an abuse */
        force_visible = true;
        break;
      case BUSY_CPU:
        curstype = IDC_WAIT;
        force_visible = true;
        break;
      default:
        unreachable("Bad busy_status");
    }
    {
        HCURSOR cursor = LoadCursor(NULL, curstype);
        SetClassLongPtr(wgs->term_hwnd, GCLP_HCURSOR, (LONG_PTR)cursor);
        SetCursor(cursor); /* force redraw of cursor at current posn */
    }
    if (force_visible != forced_visible) {
        /* We want some cursor shapes to be visible always.
         * Along with show_mouseptr(), this manages the ShowCursor()
         * counter such that if we switch back to a non-force_visible
         * cursor, the previous visibility state is restored. */
        ShowCursor(force_visible);
        forced_visible = force_visible;
    }
}

static void win_seat_set_busy_status(Seat *seat, BusyStatus status)
{
    WinGuiSeat *wgs = container_of(seat, WinGuiSeat, seat);
    wgs->busy_status = status;
    update_mouse_pointer(wgs);
}

static void wintw_set_raw_mouse_mode(TermWin *tw, bool activate)
{
    WinGuiSeat *wgs = container_of(tw, WinGuiSeat, termwin);
    wgs->send_raw_mouse = activate;
}

static void wintw_set_raw_mouse_mode_pointer(TermWin *tw, bool activate)
{
    WinGuiSeat *wgs = container_of(tw, WinGuiSeat, termwin);
    wgs->pointer_indicates_raw_mouse = activate;
    update_mouse_pointer(wgs);
}

/*
 * Print a message box and close the connection.
 */
static void win_seat_connection_fatal(Seat *seat, const char *msg)
{
    WinGuiSeat *wgs = container_of(seat, WinGuiSeat, seat);
    char *title = dupprintf("%s Fatal Error", appname);
    show_mouseptr(wgs, true);
    MessageBox(wgs->term_hwnd, msg, title, MB_ICONERROR | MB_OK);
    sfree(title);

    if (conf_get_int(wgs->conf, CONF_close_on_exit) == FORCE_ON)
        wgs_request_close(wgs);
    else {
        queue_toplevel_callback(close_session, wgs);
    }
}

/*
 * Print a message box and don't close the connection.
 */
static void win_seat_nonfatal(Seat *seat, const char *msg)
{
    WinGuiSeat *wgs = container_of(seat, WinGuiSeat, seat);
    char *title = dupprintf("%s Error", appname);
    show_mouseptr(wgs, true);
    MessageBox(wgs->term_hwnd, msg, title, MB_ICONERROR | MB_OK);
    sfree(title);
}

static HWND find_window_for_msgbox(void)
{
    if (wgslisthead.next != &wgslisthead) {
        WinGuiSeat *wgs = container_of(
            wgslisthead.next, WinGuiSeat, wgslistnode);
        return wgs->term_hwnd;
    }
    return NULL;
}

/*
 * Report an error at the command-line parsing stage.
 */
void cmdline_error(const char *fmt, ...)
{
    va_list ap;
    char *message, *title;

    va_start(ap, fmt);
    message = dupvprintf(fmt, ap);
    va_end(ap);
    title = dupprintf("%s Command Line Error", appname);
    MessageBox(find_window_for_msgbox(), message, title, MB_ICONERROR | MB_OK);
    sfree(message);
    sfree(title);
    exit(1);
}

static inline rgb rgb_from_colorref(COLORREF cr)
{
    rgb toret;
    toret.r = GetRValue(cr);
    toret.g = GetGValue(cr);
    toret.b = GetBValue(cr);
    return toret;
}

static void wintw_palette_get_overrides(TermWin *tw, Terminal *term)
{
    WinGuiSeat *wgs = container_of(tw, WinGuiSeat, termwin);
    if (conf_get_bool(wgs->conf, CONF_system_colour)) {
        rgb rgb;

        rgb = rgb_from_colorref(GetSysColor(COLOR_WINDOWTEXT));
        term_palette_override(term, OSC4_COLOUR_fg, rgb);
        term_palette_override(term, OSC4_COLOUR_fg_bold, rgb);

        rgb = rgb_from_colorref(GetSysColor(COLOR_WINDOW));
        term_palette_override(term, OSC4_COLOUR_bg, rgb);
        term_palette_override(term, OSC4_COLOUR_bg_bold, rgb);

        rgb = rgb_from_colorref(GetSysColor(COLOR_HIGHLIGHTTEXT));
        term_palette_override(term, OSC4_COLOUR_cursor_fg, rgb);

        rgb = rgb_from_colorref(GetSysColor(COLOR_HIGHLIGHT));
        term_palette_override(term, OSC4_COLOUR_cursor_bg, rgb);
    }
}

/*
 * This is a wrapper to ExtTextOut() to force Windows to display
 * the precise glyphs we give it. Otherwise it would do its own
 * bidi and Arabic shaping, and we would end up uncertain which
 * characters it had put where.
 */
static void exact_textout(HDC hdc, int x, int y, CONST RECT *lprc,
                          unsigned short *lpString, UINT cbCount,
                          CONST INT *lpDx, bool opaque)
{
#if HAVE_GCP_RESULTSW
    GCP_RESULTSW gcpr;
#else
    /*
     * If building against old enough headers that the GCP_RESULTSW
     * type isn't available, we can make do with GCP_RESULTS proper:
     * the differences aren't important to us (the only variable-width
     * string parameter is one we don't use anyway).
     */
    GCP_RESULTS gcpr;
#endif
    char *buffer = snewn(cbCount*2+2, char);
    char *classbuffer = snewn(cbCount, char);
    memset(&gcpr, 0, sizeof(gcpr));
    memset(buffer, 0, cbCount*2+2);
    memset(classbuffer, GCPCLASS_NEUTRAL, cbCount);

    gcpr.lStructSize = sizeof(gcpr);
    gcpr.lpGlyphs = (void *)buffer;
    gcpr.lpClass = (void *)classbuffer;
    gcpr.nGlyphs = cbCount;
    GetCharacterPlacementW(hdc, lpString, cbCount, 0, &gcpr,
                           FLI_MASK | GCP_CLASSIN | GCP_DIACRITIC);

    ExtTextOut(hdc, x, y,
               ETO_GLYPH_INDEX | ETO_CLIPPED | (opaque ? ETO_OPAQUE : 0),
               lprc, buffer, cbCount, lpDx);
    sfree(classbuffer);
    sfree(buffer);
}

/*
 * The exact_textout() wrapper, unfortunately, destroys the useful
 * Windows `font linking' behaviour: automatic handling of Unicode
 * code points not supported in this font by falling back to a font
 * which does contain them. Therefore, we adopt a multi-layered
 * approach: for any potentially-bidi text, we use exact_textout(),
 * and for everything else we use a simple ExtTextOut as we did
 * before exact_textout() was introduced.
 */
static uint32_t nemo_text_cluster(const unsigned short *text, int available, int *units)
{
    uint32_t cp = text[0];
    *units = 1;
    if (available > 1 && IS_SURROGATE_PAIR(text[0], text[1])) {
        cp = 0x10000+((text[0]-0xd800)<<10)+(text[1]-0xdc00);
        *units = 2;
    }
    if (*units < available && IS_LOW_VARSEL(text[*units])) (*units)++;
    else if (*units+1 < available && IS_HIGH_VARSEL(text[*units], text[*units+1])) *units += 2;
    return cp;
}

static bool nemo_missing_rtl_glyph(HDC dc, uint32_t cp)
{
    /* GetGlyphIndicesW addresses UTF-16 units, not supplementary scalars.
     * Those already use the ordinary linked GDI path below. */
    if (cp > 0xffff) return false;
    wchar_t text = cp;
    WORD glyph;
    return GetGlyphIndicesW(dc, &text, 1, &glyph,
                           GGI_MARK_NONEXISTING_GLYPHS) != GDI_ERROR &&
        (glyph == 0 || glyph == 0xffff);
}

static void general_textout(
    WinGuiSeat *wgs, HDC hdc, int x, int y, CONST RECT *lprc,
    unsigned short *lpString, UINT cbCount, CONST INT *lpDx, bool opaque,
    float horizontal_scale)
{
    int i, j, xp, xn;
    int bkmode = 0;
    bool got_bkmode = false;
    /* An opaque run erases its entire rectangle once. Its fallback cells
     * can fill their own background without reading pixels back from the
     * window surface. Combining and shadow passes must preserve earlier ink. */
    bool preserve_pixels = !opaque;

    xp = xn = x;

    for (i = 0; i < (int)cbCount ;) {
        bool rtl = is_rtl(lpString[i]);
        int units;
        uint32_t cp = nemo_text_cluster(lpString+i, cbCount-i, &units);
        bool linked_rtl = rtl && nemo_missing_rtl_glyph(hdc, cp);
        int advance = 0;
        for (int k = 0; k < units; k++) advance += lpDx[i+k];
        WORD glyph_index;
        HFONT fallback = nemo_font_fallback(&wgs->font_fallback, hdc, cp, advance, &glyph_index);
        xn += advance;
        j = i+units;
        if (!fallback && !linked_rtl) {
            while (j < (int)cbCount) {
                cp = nemo_text_cluster(lpString+j, cbCount-j, &units);
                advance = 0;
                for (int k = 0; k < units; k++) advance += lpDx[j+k];
                if (rtl != is_rtl(lpString[j]) ||
                    (rtl && nemo_missing_rtl_glyph(hdc, cp)) ||
                    nemo_font_fallback(&wgs->font_fallback, hdc, cp, advance, NULL)) break;
                xn += advance;
                j += units;
            }
        }

        /*
         * Now [i,j) indicates a maximal substring of lpString
         * which should be displayed using the same textout
         * function.
         */
        if (fallback) {
            /* Erase the complete run once, then clip an icon to its own cell.
             * Font linking cannot choose a meaningful private-use icon font. */
            if (opaque)
                ExtTextOutW(hdc, xp, y, ETO_OPAQUE | ETO_CLIPPED, lprc, L"", 0, NULL);
            RECT clip = *lprc;
            int centre = wgs->font_varpitch ? (xn-xp)/2 : 0;
            clip.left = max(clip.left, xp-centre);
            clip.right = min(clip.right, xn-centre);
            HFONT previous = SelectObject(hdc, fallback);
            int previous_mode = SetBkMode(hdc, TRANSPARENT);
            /* Use the verified cmap index directly. GDI's UTF-16 font linking
             * can otherwise substitute the private supplementary-plane font. */
            ExtTextOutW(hdc, xp, y, ETO_CLIPPED | ETO_GLYPH_INDEX, &clip,
                        &glyph_index, 1, wgs->font_varpitch ? NULL : &advance);
            SetBkMode(hdc, previous_mode);
            SelectObject(hdc, previous);
        } else if (linked_rtl) {
            /* The terminal already chose visual cell order and Arabic forms.
             * Map only this missing cell through DirectWrite's system font
             * fallback; shaping a whole visual run would reorder it again.
             * Preserve existing pixels for legacy marks and shadow bold. */
            if (opaque)
                ExtTextOutW(hdc, xp, y, ETO_OPAQUE | ETO_CLIPPED,
                            lprc, L"", 0, NULL);
            RECT box = *lprc;
            int centre = wgs->font_varpitch ? (xn-xp)/2 : 0;
            box.left = max(box.left, xp-centre);
            box.right = min(box.right, xn-centre);
            if (!nemo_cluster_draw(&wgs->cluster_renderer, hdc, &box,
                    lpString+i, j-i, y-box.top, GetTextColor(hdc),
                    GetBkColor(hdc), false, horizontal_scale, false,
                    preserve_pixels))
                exact_textout(hdc, xp, y, lprc, lpString+i, j-i,
                              wgs->font_varpitch ? NULL : lpDx+i, false);
        } else if (rtl) {
            exact_textout(hdc, xp, y, lprc, lpString+i, j-i,
                          wgs->font_varpitch ? NULL : lpDx+i, opaque);
        } else {
            ExtTextOutW(hdc, xp, y, ETO_CLIPPED | (opaque ? ETO_OPAQUE : 0),
                        lprc, lpString+i, j-i,
                        wgs->font_varpitch ? NULL : lpDx+i);
        }

        i = j;
        xp = xn;

        bkmode = GetBkMode(hdc);
        got_bkmode = true;
        SetBkMode(hdc, TRANSPARENT);
        opaque = false;
    }

    if (got_bkmode)
        SetBkMode(hdc, bkmode);
}

static int get_font_width(WinGuiSeat *wgs, HDC hdc, const TEXTMETRIC *tm)
{
    int ret;
    /* Note that the TMPF_FIXED_PITCH bit is defined upside down :-( */
    if (!(tm->tmPitchAndFamily & TMPF_FIXED_PITCH)) {
        /* Patched CJK/Nerd fonts can report the full-width average here
         * even though ASCII advances are half-width. Measure actual glyphs;
         * fixed-pitch metadata is not a reliable terminal cell width. */
        SIZE digits;
        if (GetTextExtentPoint32W(hdc, L"0123456789", 10, &digits) && digits.cx > 0)
            ret = (digits.cx + 5) / 10;
        else
            ret = tm->tmAveCharWidth;
    } else {
#define FIRST '0'
#define LAST '9'
        ABCFLOAT widths[LAST-FIRST + 1];
        int j;

        wgs->font_varpitch = true;
        wgs->font_dualwidth = true;
        if (GetCharABCWidthsFloat(hdc, FIRST, LAST, widths)) {
            ret = 0;
            for (j = 0; j < lenof(widths); j++) {
                int width = (int)(0.5 + widths[j].abcfA +
                                  widths[j].abcfB + widths[j].abcfC);
                if (ret < width)
                    ret = width;
            }
        } else {
            ret = tm->tmMaxCharWidth;
        }
#undef FIRST
#undef LAST
    }
    return ret;
}

static void init_dpi_info(WinGuiSeat *wgs)
{
    if (wgs->dpi_info.cur_dpi.x == 0 || wgs->dpi_info.cur_dpi.y == 0) {
        if (p_GetDpiForMonitor && p_MonitorFromWindow) {
            UINT dpiX, dpiY;
            HMONITOR currentMonitor = p_MonitorFromWindow(
                wgs->term_hwnd, MONITOR_DEFAULTTOPRIMARY);
            if (p_GetDpiForMonitor(currentMonitor, MDT_EFFECTIVE_DPI,
                                   &dpiX, &dpiY) == S_OK) {
                wgs->dpi_info.cur_dpi.x = (int)dpiX;
                wgs->dpi_info.cur_dpi.y = (int)dpiY;
            }
        }

        /* Fall back to system DPI */
        if (wgs->dpi_info.cur_dpi.x == 0 || wgs->dpi_info.cur_dpi.y == 0) {
            HDC hdc = GetDC(wgs->term_hwnd);
            wgs->dpi_info.cur_dpi.x = GetDeviceCaps(hdc, LOGPIXELSX);
            wgs->dpi_info.cur_dpi.y = GetDeviceCaps(hdc, LOGPIXELSY);
            ReleaseDC(wgs->term_hwnd, hdc);
        }
    }
}

/*
 * Initialise all the fonts we will need initially. There may be as many as
 * three or as few as one.  The other (potentially) twenty-one fonts are done
 * if/when they are needed.
 *
 * We also:
 *
 * - check the font width and height, correcting our guesses if
 *   necessary.
 *
 * - verify that the bold font is the same width as the ordinary
 *   one, and engage shadow bolding if not.
 *
 * - verify that the underlined font is the same width as the
 *   ordinary one (manual underlining by means of line drawing can
 *   be done in a pinch).
 *
 * - find a trust sigil icon that will look OK with the chosen font.
 */
static void init_fonts(WinGuiSeat *wgs, int pick_width, int pick_height)
{
    nemo_link_cancel(wgs);
    TEXTMETRIC tm;
    OUTLINETEXTMETRIC otm;
    CPINFO cpinfo;
    FontSpec *font;
    int fontsize[3];
    int i;
    int quality;
    HDC hdc;
    int fw_dontcare, fw_bold;

    for (i = 0; i < FONT_MAXNO; i++)
        wgs->fonts[i] = NULL;

    wgs->bold_font_mode =
        conf_get_int(wgs->conf, CONF_bold_style) & BOLD_STYLE_FONT ?
        BOLD_FONT : BOLD_NONE;
    wgs->bold_colours =
        conf_get_int(wgs->conf, CONF_bold_style) & BOLD_STYLE_COLOUR ?
        true : false;
    wgs->und_mode = UND_FONT;

    font = conf_get_fontspec(wgs->conf, CONF_font);
    if (font->isbold) {
        fw_dontcare = FW_BOLD;
        fw_bold = FW_HEAVY;
    } else {
        fw_dontcare = FW_DONTCARE;
        fw_bold = FW_BOLD;
    }

    hdc = GetDC(wgs->term_hwnd);

    if (pick_height)
        wgs->font_height = pick_height;
    else {
        wgs->font_height = font->height;
        if (wgs->font_height > 0) {
            wgs->font_height = -MulDiv(
                wgs->font_height, wgs->dpi_info.cur_dpi.y, 72);
        }
    }
    wgs->font_width = pick_width;
    wgs->font_gdi_width = 0;

    quality = conf_get_int(wgs->conf, CONF_font_quality);
#define f(i,c,w,u)                                                      \
    wgs->fonts[i] = CreateFont(                                         \
        wgs->font_height, wgs->font_gdi_width, 0, 0, w, false, u, false, c, \
        OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, FONT_QUALITY(quality), \
        FIXED_PITCH | FF_DONTCARE, font->name)

    f(FONT_NORMAL, font->charset, fw_dontcare, false);

    SelectObject(hdc, wgs->fonts[FONT_NORMAL]);
    GetTextMetrics(hdc, &tm);
    if (pick_width > 0) {
        /* A font-resizing window requests a cell advance. First measure
         * the font at its natural width at this height, then translate
         * the requested cell advance to CreateFont's average width. */
        int natural_width = get_font_width(wgs, hdc, &tm);
        if (natural_width > 0 && natural_width != pick_width) {
            HFONT natural_font = wgs->fonts[FONT_NORMAL];
            wgs->font_gdi_width = max(1, MulDiv(
                tm.tmAveCharWidth, pick_width, natural_width));
            f(FONT_NORMAL, font->charset, fw_dontcare, false);
            if (wgs->fonts[FONT_NORMAL]) {
                SelectObject(hdc, wgs->fonts[FONT_NORMAL]);
                DeleteObject(natural_font);
                GetTextMetrics(hdc, &tm);
            } else {
                wgs->fonts[FONT_NORMAL] = natural_font;
            }
        }
    }
    /* CreateFont's width is an average, not the terminal cell advance.
     * Sarasa's average is almost twice its ASCII advance. Reusing the
     * grid width for bold/italic would horizontally squeeze their glyphs. */
    wgs->font_gdi_width = tm.tmAveCharWidth;
    if (GetOutlineTextMetrics(hdc, sizeof(otm), &otm))
        wgs->font_strikethrough_y = tm.tmAscent - otm.otmsStrikeoutPosition;
    else
        wgs->font_strikethrough_y = tm.tmAscent - (tm.tmAscent * 3 / 8);

    GetObject(wgs->fonts[FONT_NORMAL], sizeof(LOGFONT), &wgs->lfont);

    /* Note that the TMPF_FIXED_PITCH bit is defined upside down :-( */
    if (!(tm.tmPitchAndFamily & TMPF_FIXED_PITCH)) {
        wgs->font_varpitch = false;
        wgs->font_dualwidth = (tm.tmAveCharWidth != tm.tmMaxCharWidth);
    } else {
        wgs->font_varpitch = true;
        wgs->font_dualwidth = true;
    }
    if (pick_width == 0 || pick_height == 0) {
        wgs->font_height = tm.tmHeight;
        wgs->font_width = get_font_width(wgs, hdc, &tm);
    }
    if (wgs->term)
        term_set_cell_size(wgs->term, wgs->font_width, wgs->font_height);

    {
        CHARSETINFO info;
        DWORD cset = tm.tmCharSet;
        memset(&info, 0xFF, sizeof(info));

        /* !!! Yes the next line is right */
        if (cset == OEM_CHARSET)
            wgs->ucsdata.font_codepage = GetOEMCP();
        else if (TranslateCharsetInfo ((DWORD *)(ULONG_PTR)cset,
                                       &info, TCI_SRCCHARSET))
            wgs->ucsdata.font_codepage = info.ciACP;
        else
            wgs->ucsdata.font_codepage = -1;

        GetCPInfo(wgs->ucsdata.font_codepage, &cpinfo);
        wgs->ucsdata.dbcs_screenfont = (cpinfo.MaxCharSize > 1);
    }

    f(FONT_UNDERLINE, font->charset, fw_dontcare, true);

    /*
     * Some fonts, e.g. 9-pt Courier, draw their underlines
     * outside their character cell. We successfully prevent
     * screen corruption by clipping the text output, but then
     * we lose the underline completely. Here we try to work
     * out whether this is such a font, and if it is, we set a
     * flag that causes underlines to be drawn by hand.
     *
     * Having tried other more sophisticated approaches (such
     * as examining the TEXTMETRIC structure or requesting the
     * height of a string), I think we'll do this the brute
     * force way: we create a small bitmap, draw an underlined
     * space on it, and test to see whether any pixels are
     * foreground-coloured. (Since we expect the underline to
     * go all the way across the character cell, we only search
     * down a single column of the bitmap, half way across.)
     */
    {
        HDC und_dc;
        HBITMAP und_bm, und_oldbm;
        int i;
        bool gotit;
        COLORREF c;

        und_dc = CreateCompatibleDC(hdc);
        und_bm = CreateCompatibleBitmap(
            hdc, wgs->font_width, wgs->font_height);
        und_oldbm = SelectObject(und_dc, und_bm);
        SelectObject(und_dc, wgs->fonts[FONT_UNDERLINE]);
        SetTextAlign(und_dc, TA_TOP | TA_LEFT | TA_NOUPDATECP);
        SetTextColor(und_dc, RGB(255, 255, 255));
        SetBkColor(und_dc, RGB(0, 0, 0));
        SetBkMode(und_dc, OPAQUE);
        ExtTextOut(und_dc, 0, 0, ETO_OPAQUE, NULL, " ", 1, NULL);
        gotit = false;
        for (i = 0; i < wgs->font_height; i++) {
            c = GetPixel(und_dc, wgs->font_width / 2, i);
            if (c != RGB(0, 0, 0))
                gotit = true;
        }
        SelectObject(und_dc, und_oldbm);
        DeleteObject(und_bm);
        DeleteDC(und_dc);
        if (!gotit) {
            wgs->und_mode = UND_LINE;
            DeleteObject(wgs->fonts[FONT_UNDERLINE]);
            wgs->fonts[FONT_UNDERLINE] = 0;
        }
    }

    if (wgs->bold_font_mode == BOLD_FONT) {
        f(FONT_BOLD, font->charset, fw_bold, false);
    }
#undef f

    wgs->descent = tm.tmAscent + 1;
    if (wgs->descent >= wgs->font_height)
        wgs->descent = wgs->font_height - 1;

    for (i = 0; i < 3; i++) {
        if (wgs->fonts[i]) {
            if (SelectObject(hdc, wgs->fonts[i]) && GetTextMetrics(hdc, &tm))
                fontsize[i] = (get_font_width(wgs, hdc, &tm) +
                               256 * tm.tmHeight);
            else
                fontsize[i] = -i;
        } else
            fontsize[i] = -i;
    }

    ReleaseDC(wgs->term_hwnd, hdc);

    if (wgs->trust_icon != NULL) {
        DestroyIcon(wgs->trust_icon);
    }
    wgs->trust_icon = LoadImage(hinst, MAKEINTRESOURCE(IDI_MAINICON),
                           IMAGE_ICON, wgs->font_width*2, wgs->font_height,
                           LR_DEFAULTCOLOR);

    if (fontsize[FONT_UNDERLINE] != fontsize[FONT_NORMAL]) {
        wgs->und_mode = UND_LINE;
        DeleteObject(wgs->fonts[FONT_UNDERLINE]);
        wgs->fonts[FONT_UNDERLINE] = 0;
    }

    if (wgs->bold_font_mode == BOLD_FONT &&
        fontsize[FONT_BOLD] != fontsize[FONT_NORMAL]) {
        wgs->bold_font_mode = BOLD_SHADOW;
        DeleteObject(wgs->fonts[FONT_BOLD]);
        wgs->fonts[FONT_BOLD] = 0;
    }
    wgs->fontflag[0] = true;
    wgs->fontflag[1] = true;
    wgs->fontflag[2] = true;

    init_ucs(wgs->conf, &wgs->ucsdata);

    /* An active composition survives a font or DPI change. Update its font
     * here as well as at WM_IME_STARTCOMPOSITION. */
    HIMC hIMC = ImmGetContext(wgs->term_hwnd);
    if (hIMC) {
        ImmSetCompositionFont(hIMC, &wgs->lfont);
        ImmReleaseContext(wgs->term_hwnd, hIMC);
    }
}

static void another_font(WinGuiSeat *wgs, int fontno)
{
    int basefont;
    int fw_dontcare, fw_bold, quality;
    int c, w, x;
    bool u;
    char *s;
    FontSpec *font;

    if (fontno < 0 || fontno >= FONT_MAXNO || wgs->fontflag[fontno])
        return;

    basefont = (fontno & ~(FONT_BOLDUND));
    if (basefont != fontno && !wgs->fontflag[basefont])
        another_font(wgs, basefont);

    font = conf_get_fontspec(wgs->conf, CONF_font);

    if (font->isbold) {
        fw_dontcare = FW_BOLD;
        fw_bold = FW_HEAVY;
    } else {
        fw_dontcare = FW_DONTCARE;
        fw_bold = FW_BOLD;
    }

    c = font->charset;
    w = fw_dontcare;
    u = false;
    s = font->name;
    x = wgs->font_gdi_width;

    if (fontno & FONT_WIDE)
        x *= 2;
    if (fontno & FONT_NARROW)
        x = (x+1)/2;
    if (fontno & FONT_OEM)
        c = OEM_CHARSET;
    if (fontno & FONT_BOLD)
        w = fw_bold;
    if (fontno & FONT_UNDERLINE)
        u = true;

    quality = conf_get_int(wgs->conf, CONF_font_quality);

    wgs->fonts[fontno] =
        CreateFont(wgs->font_height * (1 + !!(fontno & FONT_HIGH)), x, 0, 0, w,
                   !!(fontno & FONT_ITALIC), u, false, c, OUT_DEFAULT_PRECIS,
                   CLIP_DEFAULT_PRECIS, FONT_QUALITY(quality),
                   DEFAULT_PITCH | FF_DONTCARE, s);

    wgs->fontflag[fontno] = true;
}

static void deinit_fonts(WinGuiSeat *wgs)
{
    nemo_gpu_clear_cache(wgs->gpu);
    nemo_font_fallback_free(&wgs->font_fallback);
    int i;
    for (i = 0; i < FONT_MAXNO; i++) {
        if (wgs->fonts[i])
            DeleteObject(wgs->fonts[i]);
        wgs->fonts[i] = 0;
        wgs->fontflag[i] = false;
    }

    if (wgs->trust_icon != NULL) {
        DestroyIcon(wgs->trust_icon);
    }
    wgs->trust_icon = NULL;
}

static bool wintw_get_geometry(TermWin *tw, TermWindowGeometry *g)
{
    WinGuiSeat *wgs = container_of(tw, WinGuiSeat, termwin);
    RECT outer, screen;
    POINT text = {wgs->offset_width, wgs->offset_height};
    if (!GetWindowRect(wgs_window(wgs), &outer) ||
        !ClientToScreen(wgs->term_hwnd, &text) ||
        !get_fullscreen_rect(wgs, &screen)) return false;
    *g = (TermWindowGeometry) {
        .outer_x = outer.left, .outer_y = outer.top,
        .outer_width = outer.right - outer.left,
        .outer_height = outer.bottom - outer.top,
        .text_x = text.x, .text_y = text.y,
        .text_width = wgs->term->cols * wgs->font_width,
        .text_height = wgs->term->rows * wgs->font_height,
        .screen_width = screen.right - screen.left,
        .screen_height = screen.bottom - screen.top,
        .cell_width = wgs->font_width, .cell_height = wgs->font_height,
        .minimised = IsIconic(wgs_window(wgs)),
    };
    return true;
}

static void wintw_request_resize(TermWin *tw, int w, int h)
{
    WinGuiSeat *wgs = container_of(tw, WinGuiSeat, termwin);
    const struct BackendVtable *vt;
    int width, height;
    int resize_action = conf_get_int(wgs->conf, CONF_resize_action);
    bool deny_resize = !wgs_active(wgs);

    /* Suppress server-originated resizing attempts if local resizing
     * is disabled entirely, or if it's supposed to change
     * rows/columns but the window is maximised. */
    if (resize_action == RESIZE_DISABLED
        || (resize_action == RESIZE_TERM && IsZoomed(wgs_window(wgs)))) {
        deny_resize = true;
    }

    vt = backend_vt_from_proto(be_default_protocol);
    if (vt && vt->flags & BACKEND_RESIZE_FORBIDDEN)
        deny_resize = true;
    if (h == wgs->term->rows && w == wgs->term->cols) deny_resize = true;

    /* We still need to acknowledge a suppressed resize attempt. */
    if (deny_resize) {
        term_resize_request_completed(wgs->term);
        return;
    }

    /* Sanity checks ... */
    {
        RECT ss;
        if (get_fullscreen_rect(wgs, &ss)) {
            /* Make sure the values aren't too big */
            width = (ss.right - ss.left - wgs->extra_width) / 4;
            height = (ss.bottom - ss.top - wgs->extra_height) / 6;

            if (w > width || h > height) {
                term_resize_request_completed(wgs->term);
                return;
            }
            if (w < 15)
                w = 15;
            if (h < 1)
                h = 1;
        }
    }

    if (resize_action != RESIZE_FONT && !IsZoomed(wgs_window(wgs))) {
        width = wgs->extra_width + wgs->font_width * w;
        height = wgs->extra_height + wgs->font_height * h;

        SetWindowPos(wgs_window(wgs), NULL, 0, 0, width, height,
                     SWP_NOACTIVATE | SWP_NOCOPYBITS |
                     SWP_NOMOVE | SWP_NOZORDER);
    } else {
        /*
         * If we're resizing by changing the font, we must tell the
         * terminal the new size immediately, so that reset_window
         * will know what to do.
         */
        term_size(wgs->term, h, w, conf_get_int(wgs->conf, CONF_savelines));
        reset_window(wgs, 0);
    }

    term_resize_request_completed(wgs->term);
    InvalidateRect(wgs->term_hwnd, NULL, true);
}

static void wintw_request_window_resize(TermWin *tw, int w, int h, bool pixels)
{
    WinGuiSeat *wgs = container_of(tw, WinGuiSeat, termwin);
    if (!wgs_active(wgs)) {term_resize_request_completed(wgs->term);return;}
    int action = conf_get_int(wgs->conf, CONF_resize_action);
    const struct BackendVtable *backend = backend_vt_from_proto(be_default_protocol);
    if (wgs->term->no_remote_resize || action == RESIZE_DISABLED ||
        (backend && backend->flags & BACKEND_RESIZE_FORBIDDEN) ||
        ((IsZoomed(wgs_window(wgs)) || is_full_screen(wgs)) &&
         (pixels || action != RESIZE_FONT))) goto completed;

    RECT outer, client, monitor;
    WINDOWPLACEMENT placement = {sizeof(placement)};
    bool iconic = IsIconic(wgs_window(wgs));
    if (!get_fullscreen_rect(wgs, &monitor) ||
        !GetWindowRect(wgs_window(wgs), &outer) ||
        !GetClientRect(wgs->term_hwnd, &client)) goto completed;
    int frame_w = outer.right-outer.left-client.right;
    int frame_h = outer.bottom-outer.top-client.bottom;
    if (iconic) {
        /* Iconic rectangles describe the minimized icon, not its restore
         * surface. Compute the frame for the current style/DPI instead. */
        if (!GetWindowPlacement(wgs_window(wgs), &placement)) goto completed;
        DWORD style = GetWindowLongPtr(wgs->term_hwnd, GWL_STYLE) &
            ~(WS_MINIMIZE | WS_MAXIMIZE);
        DWORD exstyle = GetWindowLongPtr(wgs->term_hwnd, GWL_EXSTYLE);
        RECT frame = {0};
        UINT dpi = wgs->dpi_info.cur_dpi.x;
        if (p_AdjustWindowRectExForDpi) {
            if (!p_AdjustWindowRectExForDpi(&frame, style, false, exstyle, dpi))
                goto completed;
        } else if (!AdjustWindowRectEx(&frame, style, false, exstyle)) goto completed;
        frame_w = frame.right-frame.left;
        frame_h = frame.bottom-frame.top;
        if (style & WS_VSCROLL)
            frame_w += p_GetSystemMetricsForDpi ?
                p_GetSystemMetricsForDpi(SM_CXVSCROLL, dpi) : GetSystemMetrics(SM_CXVSCROLL);
        if (style & WS_HSCROLL)
            frame_h += p_GetSystemMetricsForDpi ?
                p_GetSystemMetricsForDpi(SM_CYHSCROLL, dpi) : GetSystemMetrics(SM_CYHSCROLL);
        client.right = placement.rcNormalPosition.right-placement.rcNormalPosition.left-frame_w;
        client.bottom = placement.rcNormalPosition.bottom-placement.rcNormalPosition.top-frame_h;
    }
    int border = conf_get_int(wgs->conf, CONF_window_border);
    if (frame_w < 0 || frame_h < 0 || border < 0 || border > 32767) goto completed;
    NemoWindowSize metrics = {
        .width = client.right, .height = client.bottom,
        .cols = wgs->term->cols, .rows = wgs->term->rows,
        .cell_width = wgs->font_width, .cell_height = wgs->font_height,
        .padding_width = 2*border, .padding_height = 2*border,
        .limit_width = monitor.right-monitor.left-frame_w,
        .limit_height = monitor.bottom-monitor.top-frame_h,
    };
    int width, height;
    if (!nemo_window_size(&metrics, w, h, pixels, &width, &height)) goto completed;
    int cols = (width-2*border)/wgs->font_width;
    int rows = (height-2*border)/wgs->font_height;
    if (!pixels && action == RESIZE_FONT) {
        /* Character requests change the grid; the configured font-resize
         * policy fits that grid into the existing window. */
        term_size(wgs->term, rows, cols, conf_get_int(wgs->conf, CONF_savelines));
        reset_window(wgs, 0);
    } else if (iconic) {
        placement.rcNormalPosition.right = placement.rcNormalPosition.left+width+frame_w;
        placement.rcNormalPosition.bottom = placement.rcNormalPosition.top+height+frame_h;
        if (SetWindowPlacement(wgs_window(wgs), &placement)) {
            /* Keep draining output at the requested size without showing or
             * activating the minimized window. WM_SIZE finishes on restore. */
            if (action != RESIZE_FONT)
                term_size(wgs->term, rows, cols, conf_get_int(wgs->conf, CONF_savelines));
        }
    } else if (width != client.right || height != client.bottom) {
        wgs->remote_window_resize = true;
        SetWindowPos(wgs_window(wgs), NULL, 0, 0, width+frame_w, height+frame_h,
                     SWP_NOACTIVATE | SWP_NOCOPYBITS | SWP_NOMOVE | SWP_NOZORDER);
        wgs->remote_window_resize = false;
    }
    InvalidateRect(wgs->term_hwnd, NULL, true);
  completed:
    term_resize_request_completed(wgs->term);
}

static void recompute_window_offset(WinGuiSeat *wgs)
{
    RECT cr;
    GetClientRect(wgs->term_hwnd, &cr);

    int win_width  = cr.right - cr.left;
    int win_height = cr.bottom - cr.top;

    int new_offset_width = (win_width-wgs->font_width*wgs->term->cols)/2;
    int new_offset_height = (win_height-wgs->font_height*wgs->term->rows)/2;

    if (wgs->offset_width != new_offset_width ||
        wgs->offset_height != new_offset_height) {
        wgs->offset_width = new_offset_width;
        wgs->offset_height = new_offset_height;
    }
    /* Even an unchanged border width encloses different pixels after a
     * resize. Windows can preserve old image/text pixels in the new margin. */
    InvalidateRect(wgs->term_hwnd, NULL, true);
}

static void reset_window(WinGuiSeat *wgs, int reinit)
{
    if (wgs->tabbed) {nemo_host_resize(wgs,reinit);return;}
    /*
     * This function decides how to resize or redraw when the
     * user changes something.
     *
     * This function doesn't like to change the terminal size but if the
     * font size is locked that may be it's only soluion.
     */
    int win_width, win_height, resize_action, window_border;
    RECT cr, wr;

    /* Current window sizes ... */
    GetWindowRect(wgs_window(wgs), &wr);
    GetClientRect(wgs->term_hwnd, &cr);

    win_width  = cr.right - cr.left;
    win_height = cr.bottom - cr.top;

    resize_action = conf_get_int(wgs->conf, CONF_resize_action);
    window_border = conf_get_int(wgs->conf, CONF_window_border);

    if (resize_action == RESIZE_DISABLED)
        reinit = 2;

    /* Are we being forced to reload the fonts ? */
    if (reinit>1) {
        deinit_fonts(wgs);
        init_fonts(wgs, 0, 0);
    }

    /* Oh, looks like we're minimised */
    if (win_width == 0 || win_height == 0)
        return;

    /* Is the window out of position ? */
    if (!reinit) {
        recompute_window_offset(wgs);
    }

    if (IsZoomed(wgs_window(wgs))) {
        /* We're fullscreen, this means we must not change the size of
         * the window so it's the font size or the terminal itself.
         */

        wgs->extra_width = wr.right - wr.left - cr.right + cr.left;
        wgs->extra_height = wr.bottom - wr.top - cr.bottom + cr.top;

        if (resize_action != RESIZE_TERM) {
            if (wgs->font_width != win_width/wgs->term->cols ||
                wgs->font_height != win_height/wgs->term->rows) {
                int fw = (win_width - 2*window_border) / wgs->term->cols;
                int fh = (win_height - 2*window_border) / wgs->term->rows;
                /* In case that subtraction made the font size go
                 * negative in an edge case, bound it below by 1 */
                if (fw < 1) fw = 1;
                if (fh < 1) fh = 1;
                deinit_fonts(wgs);
                init_fonts(wgs, fw, fh);
                wgs->offset_width =
                    (win_width - wgs->font_width*wgs->term->cols) / 2;
                wgs->offset_height =
                    (win_height - wgs->font_height*wgs->term->rows) / 2;
                InvalidateRect(wgs->term_hwnd, NULL, true);
            }
        } else {
            if (wgs->font_width * wgs->term->cols != win_width ||
                wgs->font_height * wgs->term->rows != win_height) {
                /* Our only choice at this point is to change the
                 * size of the terminal; Oh well.
                 */
                term_size(wgs->term,
                          (win_height - 2*window_border) / wgs->font_height,
                          (win_width - 2*window_border) / wgs->font_width,
                          conf_get_int(wgs->conf, CONF_savelines));
                wgs->offset_width =
                    (win_width - window_border - wgs->font_width*wgs->term->cols) / 2;
                wgs->offset_height =
                    (win_height - window_border - wgs->font_height*wgs->term->rows) / 2;
                InvalidateRect(wgs->term_hwnd, NULL, true);
            }
        }
        return;
    }

    /* Resize window after DPI change */
    if (reinit == 3 && p_GetSystemMetricsForDpi && p_AdjustWindowRectExForDpi) {
        RECT rect;
        rect.left = rect.top = 0;
        rect.right = (wgs->font_width * wgs->term->cols);
        if (conf_get_bool(wgs->conf, CONF_scrollbar))
            rect.right += p_GetSystemMetricsForDpi(SM_CXVSCROLL,
                                                   wgs->dpi_info.cur_dpi.x);
        rect.bottom = (wgs->font_height * wgs->term->rows);
        p_AdjustWindowRectExForDpi(
            &rect, GetWindowLongPtr(wgs->term_hwnd, GWL_STYLE),
            FALSE, GetWindowLongPtr(wgs->term_hwnd, GWL_EXSTYLE),
            wgs->dpi_info.cur_dpi.x);
        rect.right += (window_border * 2);
        rect.bottom += (window_border * 2);
        OffsetRect(&wgs->dpi_info.new_wnd_rect,
                   ((wgs->dpi_info.new_wnd_rect.right -
                     wgs->dpi_info.new_wnd_rect.left) -
                    (rect.right - rect.left)) / 2,
                   ((wgs->dpi_info.new_wnd_rect.bottom -
                     wgs->dpi_info.new_wnd_rect.top) -
                    (rect.bottom - rect.top)) / 2);
        SetWindowPos(wgs_window(wgs), NULL,
                     wgs->dpi_info.new_wnd_rect.left,
                     wgs->dpi_info.new_wnd_rect.top,
                     rect.right - rect.left, rect.bottom - rect.top,
                     SWP_NOZORDER);

        InvalidateRect(wgs->term_hwnd, NULL, true);
        return;
    }

    /* Hmm, a force re-init means we should ignore the current window
     * so we resize to the default font size.
     */
    if (reinit>0) {
        wgs->offset_width = wgs->offset_height = window_border;
        wgs->extra_width =
            wr.right - wr.left - cr.right + cr.left + wgs->offset_width*2;
        wgs->extra_height =
            wr.bottom - wr.top - cr.bottom + cr.top + wgs->offset_height*2;

        if (win_width != (wgs->font_width*wgs->term->cols +
                          wgs->offset_width*2) ||
            win_height != (wgs->font_height*wgs->term->rows +
                           wgs->offset_height*2)) {

            /* If this is too large windows will resize it to the maximum
             * allowed window size, we will then be back in here and resize
             * the font or terminal to fit.
             */
            SetWindowPos(wgs_window(wgs), NULL, 0, 0,
                         wgs->font_width*wgs->term->cols + wgs->extra_width,
                         wgs->font_height*wgs->term->rows + wgs->extra_height,
                         SWP_NOMOVE | SWP_NOZORDER);
        }

        InvalidateRect(wgs->term_hwnd, NULL, true);
        return;
    }

    /* Okay the user doesn't want us to change the font so we try the
     * window. But that may be too big for the screen which forces us
     * to change the terminal.
     */
    if ((resize_action == RESIZE_TERM && reinit<=0) ||
        (resize_action == RESIZE_EITHER && reinit<0) ||
        reinit>0) {
        wgs->offset_width = wgs->offset_height = window_border;
        wgs->extra_width =
            wr.right - wr.left - cr.right + cr.left + wgs->offset_width*2;
        wgs->extra_height =
            wr.bottom - wr.top - cr.bottom + cr.top + wgs->offset_height*2;

        if (win_width != (wgs->font_width*wgs->term->cols +
                          wgs->offset_width*2) ||
            win_height != (wgs->font_height*wgs->term->rows +
                           wgs->offset_height*2)) {

            RECT ss;
            int width, height;

            get_fullscreen_rect(wgs, &ss);

            width = (ss.right - ss.left - wgs->extra_width) / wgs->font_width;
            height = (ss.bottom - ss.top - wgs->extra_height)/wgs->font_height;

            /* Grrr too big */
            if ( wgs->term->rows > height || wgs->term->cols > width ) {
                if (resize_action == RESIZE_EITHER) {
                    /* Make the font the biggest we can */
                    if (wgs->term->cols > width)
                        wgs->font_width =
                            (ss.right - ss.left - wgs->extra_width) /
                            wgs->term->cols;
                    if (wgs->term->rows > height)
                        wgs->font_height =
                            (ss.bottom - ss.top - wgs->extra_height) /
                            wgs->term->rows;

                    deinit_fonts(wgs);
                    init_fonts(wgs, wgs->font_width, wgs->font_height);

                    width = (ss.right - ss.left - wgs->extra_width) /
                        wgs->font_width;
                    height = (ss.bottom - ss.top - wgs->extra_height) /
                        wgs->font_height;
                } else {
                    if ( height > wgs->term->rows ) height = wgs->term->rows;
                    if ( width > wgs->term->cols )  width = wgs->term->cols;
                    term_size(wgs->term, height, width,
                              conf_get_int(wgs->conf, CONF_savelines));
                }
            }

            SetWindowPos(wgs_window(wgs), NULL, 0, 0,
                         wgs->font_width*wgs->term->cols + wgs->extra_width,
                         wgs->font_height*wgs->term->rows + wgs->extra_height,
                         SWP_NOMOVE | SWP_NOZORDER);

            InvalidateRect(wgs->term_hwnd, NULL, true);
        }
        return;
    }

    /* We're allowed to or must change the font but do we want to ?  */

    if (wgs->font_width != (win_width-window_border*2)/wgs->term->cols ||
        wgs->font_height != (win_height-window_border*2)/wgs->term->rows) {

        deinit_fonts(wgs);
        init_fonts(wgs, (win_width-window_border*2)/wgs->term->cols,
                   (win_height-window_border*2)/wgs->term->rows);
        wgs->offset_width = (win_width-wgs->font_width*wgs->term->cols)/2;
        wgs->offset_height = (win_height-wgs->font_height*wgs->term->rows)/2;

        wgs->extra_width =
            wr.right - wr.left - cr.right + cr.left + wgs->offset_width*2;
        wgs->extra_height =
            wr.bottom - wr.top - cr.bottom + cr.top + wgs->offset_height*2;

        InvalidateRect(wgs->term_hwnd, NULL, true);
    }
}

static void set_input_locale(WinGuiSeat *wgs, HKL kl)
{
    char lbuf[20];

    GetLocaleInfo(LOWORD(kl), LOCALE_IDEFAULTANSICODEPAGE,
                  lbuf, sizeof(lbuf));

    wgs->kbd_codepage = atoi(lbuf);
}

static void click(WinGuiSeat *wgs, Mouse_Button b, int x, int y,
                  int px, int py, bool shift, bool ctrl, bool alt)
{
    int thistime = GetMessageTime();

    if (wgs->send_raw_mouse && !shift &&
        !(b == MBT_LEFT && wgs->term->xterm_mouse == MOUSE_TRACK_HIGHLIGHT)) {
        wgs->lastbtn = MBT_NOTHING;
        term_mouse_pixels(wgs->term, b, translate_button(wgs, b), MA_CLICK,
                          x, y, px, py, shift, ctrl, alt);
        return;
    }

    /* Separate drags elsewhere in the grid are not double/triple clicks.
     * Use the system's click rectangle as well as its time threshold. */
    if (wgs->lastbtn == b &&
        (DWORD)thistime - (DWORD)wgs->lasttime < (DWORD)wgs->dbltime &&
        abs(px - wgs->lastclick_x) <= GetSystemMetrics(SM_CXDOUBLECLK) / 2 &&
        abs(py - wgs->lastclick_y) <= GetSystemMetrics(SM_CYDOUBLECLK) / 2) {
        wgs->lastact = (wgs->lastact == MA_CLICK ? MA_2CLK :
                   wgs->lastact == MA_2CLK ? MA_3CLK :
                   wgs->lastact == MA_3CLK ? MA_CLICK : MA_NOTHING);
    } else {
        wgs->lastbtn = b;
        wgs->lastact = MA_CLICK;
    }
    if (wgs->lastact != MA_NOTHING)
        term_mouse_pixels(wgs->term, b, translate_button(wgs, b), wgs->lastact,
                          x, y, px, py, shift, ctrl, alt);
    wgs->lasttime = thistime;
    wgs->lastclick_x = px;
    wgs->lastclick_y = py;
}

/*
 * Translate a raw mouse button designation (LEFT, MIDDLE, RIGHT)
 * into a cooked one (SELECT, EXTEND, PASTE).
 */
static Mouse_Button translate_button(WinGuiSeat *wgs, Mouse_Button button)
{
    if (button == MBT_LEFT)
        return MBT_SELECT;
    if (button == MBT_MIDDLE)
        return conf_get_int(wgs->conf, CONF_mouse_is_xterm) == MOUSE_XTERM ?
            MBT_PASTE : MBT_EXTEND;
    if (button == MBT_RIGHT)
        return conf_get_int(wgs->conf, CONF_mouse_is_xterm) == MOUSE_XTERM ?
            MBT_EXTEND : MBT_PASTE;
    return MBT_NOTHING;                /* no local binding for other buttons */
}

static void show_mouseptr(WinGuiSeat *wgs, bool show)
{
    /* NB that the counter in ShowCursor() is also frobbed by
     * update_mouse_pointer() */
    static bool cursor_visible = true;
    if (wgs) {
        if (!conf_get_bool(wgs->conf, CONF_hide_mouseptr))
            show = true; /* hiding mouse pointer disabled in Conf */
    } else {
        /*
         * You can pass wgs==NULL if you want to _show_ the pointer
         * rather than hiding it, because that's never disallowed.
         */
        assert(show);
    }
    if (cursor_visible && !show)
        ShowCursor(false);
    else if (!cursor_visible && show)
        ShowCursor(true);
    cursor_visible = show;
}

static bool is_alt_pressed(void)
{
    BYTE keystate[256];
    int r = GetKeyboardState(keystate);
    if (!r)
        return false;
    if (keystate[VK_MENU] & 0x80)
        return true;
    if (keystate[VK_RMENU] & 0x80)
        return true;
    return false;
}

static void exit_callback(void *vctx)
{
    WinGuiSeat *wgs = (WinGuiSeat *)vctx;
    int exitcode, close_on_exit;

    if (!wgs->closing && !wgs->session_closed && wgs->backend &&
        (exitcode = backend_exitcode(wgs->backend)) >= 0) {
        close_on_exit = conf_get_int(wgs->conf, CONF_close_on_exit);
        /* Abnormal exits will already have set session_closed and taken
         * appropriate action. */
        if (close_on_exit == FORCE_ON ||
            (close_on_exit == AUTO && exitcode != INT_MAX)) {
            wgs_request_close(wgs);
        } else {
            queue_toplevel_callback(close_session, wgs);
            wgs->session_closed = true;
            /* exitcode == INT_MAX indicates that the connection was closed
             * by a fatal error, so an error box will be coming our way and
             * we should not generate this informational one. */
            if (exitcode != INT_MAX) {
                show_mouseptr(wgs, true);
                MessageBox(wgs->term_hwnd, "Connection closed by remote host",
                           appname, MB_OK | MB_ICONINFORMATION);
            }
        }
    }
}

static void win_seat_notify_remote_exit(Seat *seat)
{
    WinGuiSeat *wgs = container_of(seat, WinGuiSeat, seat);
    term_end_synchronized_update(wgs->term);
    if (!wgs->closing) queue_toplevel_callback(exit_callback, wgs);
}

static void conf_cache_data(WinGuiSeat *wgs)
{
    /* Cache some items from conf to speed lookups in very hot code */
    wgs->vtmode = conf_get_int(wgs->conf, CONF_vtmode);
}

static const int clips_system[] = { CLIP_SYSTEM };

static HDC make_hdc(WinGuiSeat *wgs)
{
    HDC hdc;

    if (!wgs->term_hwnd)
        return NULL;

    hdc = GetDC(wgs->term_hwnd);
    if (!hdc)
        return NULL;

    SelectPalette(hdc, wgs->pal, false);
    return hdc;
}

static void free_hdc(WinGuiSeat *wgs, HDC hdc)
{
    assert(wgs->term_hwnd);
    SelectPalette(hdc, GetStockObject(DEFAULT_PALETTE), false);
    ReleaseDC(wgs->term_hwnd, hdc);
}

static void wm_size_resize_term(WinGuiSeat *wgs, LPARAM lParam)
{
    int width = LOWORD(lParam);
    int height = HIWORD(lParam);
    int border_size = conf_get_int(wgs->conf, CONF_window_border);

    int w = (width - border_size*2) / wgs->font_width;
    int h = (height - border_size*2) / wgs->font_height;

    if (w < 1) w = 1;
    if (h < 1) h = 1;

    if (wgs->resizing) {
        /*
         * If we're in the middle of an interactive resize, we don't
         * call term_size. This means that, firstly, the user can drag
         * the size back and forth indecisively without wiping out any
         * actual terminal contents, and secondly, the Terminal
         * doesn't call back->size in turn for each increment of the
         * resizing drag, so we don't spam the server with huge
         * numbers of resize events.
         */
        wgs->need_backend_resize = true;
    } else {
        term_size(wgs->term, h, w,
                  conf_get_int(wgs->conf, CONF_savelines));
    }
    conf_set_int(wgs->conf, CONF_height, h);
    conf_set_int(wgs->conf, CONF_width, w);
}

static LRESULT CALLBACK WndProc(HWND hwnd, UINT message,
                                WPARAM wParam, LPARAM lParam)
{
    HDC hdc;
    int resize_action;
    WinGuiSeat *wgs = (WinGuiSeat *)GetWindowLongPtr(hwnd, GWLP_USERDATA);
    if (!wgs) return sw_DefWindowProc(hwnd, message, wParam, lParam);
    if (!wgs->term && message!=WM_NCDESTROY && message!=WM_DESTROY)
        return sw_DefWindowProc(hwnd,message,wParam,lParam);
    if (wgs->tabbed && message==WM_SYSCOMMAND && wParam>=0xF000 &&
        (wParam&~0xf)!=SC_VSCROLL && (wParam&~0xf)!=SC_HSCROLL)
        return SendMessage(wgs_window(wgs),message,wParam,lParam);

    switch (message) {
      case WM_CREATE:
        break;
      case WM_CLOSE: {
        char *title, *msg, *additional = NULL;
        show_mouseptr(wgs, true);
        title = dupprintf("%s Exit Confirmation", appname);
        if (wgs->backend && wgs->backend->vt->close_warn_text) {
            additional = wgs->backend->vt->close_warn_text(wgs->backend);
        }
        msg = dupprintf("Are you sure you want to close this session?%s%s",
                        additional ? "\n" : "",
                        additional ? additional : "");
        if (wgs->session_closed ||
            !conf_get_bool(wgs->conf, CONF_warn_on_close) ||
            MessageBox(hwnd, msg, title,
                       MB_ICONWARNING | MB_OKCANCEL | MB_DEFBUTTON1)
            == IDOK)
            wgs_request_close(wgs);
        sfree(title);
        sfree(msg);
        sfree(additional);
        return 0;
      }
      case WM_DESTROY:
        if (wgs->tabbed && !wgs->closing) {
            wgs_request_close(wgs);nemo_host_remove(wgs);
        }
        nemo_osc52_window_free(wgs);
        nemo_link_free(wgs);
        if (wgs->term) term_end_synchronized_update(wgs->term);
        show_mouseptr(wgs, true);
        wgs_free_menus(wgs);
        wgs_request_close(wgs);
        return 0;
      case WM_NCDESTROY:
        RemovePropW(hwnd, L"NemotermSessionId");
        SetWindowLongPtr(hwnd, GWLP_USERDATA, 0);
        break;
      case WM_INITMENUPOPUP:
        for (size_t mi=0;mi<lenof(wgs->popup_menus);mi++) {
            EnableMenuItem(wgs->popup_menus[mi].menu,IDM_COPYDIR,MF_BYCOMMAND |
                (wgs->term->working_directory.path && *wgs->term->working_directory.path ? MF_ENABLED : MF_GRAYED));
            HMENU shell = wgs->popup_menus[mi].shell_menu;
            for (int output = 0; output < 2; output++) {
                NemoShellPoint start, end;
                bool available = term_shell_mark_range(wgs->term, output, &start, &end) != 0;
                bool clipped = available && (start.truncated || end.truncated);
                UINT id = output ? IDM_SELECTOUTPUT : IDM_SELECTCOMMAND;
                const char *label = output ? (clipped ? "Select &Output (Truncated)" : "Select &Output") :
                    (clipped ? "Select &Command (Truncated)" : "Select &Command");
                ModifyMenu(shell, id, MF_BYCOMMAND | MF_STRING |
                    (available ? MF_ENABLED : MF_GRAYED), id, label);
            }
        }
        if ((HMENU)wParam == wgs->savedsess_menu) {
            /* About to pop up Saved Sessions sub-menu.
             * Refresh the session list. */
            get_sesslist(&sesslist, false); /* free */
            get_sesslist(&sesslist, true);
            update_savedsess_menu(wgs);
            return 0;
        }
        break;
      case WM_COMMAND:
      case WM_SYSCOMMAND:
        switch (wParam & ~0xF) {       /* low 4 bits reserved to Windows */
          case SC_VSCROLL:
          case SC_HSCROLL:
            if (message == WM_SYSCOMMAND) {
                /* As per the long comment in WM_VSCROLL handler: give
                 * this message the default handling, which starts a
                 * subsidiary message loop, but set a flag so that
                 * when we're re-entered from that loop, scroll events
                 * within an interactive scrollbar-drag can be handled
                 * differently. */
                wgs->in_scrollbar_loop = true;
                LRESULT result = sw_DefWindowProc(
                    hwnd, message, wParam, lParam);
                wgs->in_scrollbar_loop = false;
                return result;
            }
            break;
          case IDM_SHOWLOG:
            showeventlog(hwnd);
            break;
          case IDM_DUPSESS:
            wgs_create(nemo_duplicate_conf(wgs), SW_SHOWNORMAL);
            break;
          case IDM_NEWSESS:
          case IDM_SAVEDSESS: {
            if (wgs->tabbed) {
                if (wParam==IDM_NEWSESS) nemo_host_new_tab(wgs);
                else {
                    unsigned int sessno=((lParam-IDM_SAVED_MIN)/MENU_SAVED_STEP)+1;
                    if (sessno<(unsigned)sesslist.nsessions) {
                        Conf *conf=conf_new();do_defaults(sesslist.sessions[sessno],conf);
                        conf_set_bool(conf,CONF_nemo_tabs,true);wgs_create(conf,SW_SHOWNORMAL);
                    }
                }
                break;
            }
            wchar_t b[32768];
            char *cl;
            const char *argprefix;
            bool inherit_handles;
            STARTUPINFOW si = {0};
            PROCESS_INFORMATION pi = {0};

            if (restricted_acl())
                argprefix = "&R";
            else
                argprefix = "";

            if (wParam == IDM_SAVEDSESS) {
                unsigned int sessno = ((lParam - IDM_SAVED_MIN)
                                       / MENU_SAVED_STEP) + 1;
                if (sessno < (unsigned)sesslist.nsessions) {
                    const char *session = sesslist.sessions[sessno];
                    cl = dupprintf("putty %s@%s", argprefix, session);
                    inherit_handles = false;
                } else
                    break;
            } else /* IDM_NEWSESS */ {
                cl = dupprintf("putty%s%s",
                               *argprefix ? " " : "",
                               argprefix);
                inherit_handles = false;
            }

            DWORD path_length=GetModuleFileNameW(NULL, b, lenof(b));
            si.cb = sizeof(si);
            si.lpReserved = NULL;
            si.lpDesktop = NULL;
            si.lpTitle = NULL;
            si.dwFlags = 0;
            si.cbReserved2 = 0;
            si.lpReserved2 = NULL;
            wchar_t *command=dup_mb_to_wc(CP_ACP,cl);
            DWORD error=ERROR_SUCCESS;
            if (!path_length) error=GetLastError();
            else if (path_length>=lenof(b)) error=ERROR_INSUFFICIENT_BUFFER;
            else if (!CreateProcessW(b, command, NULL, NULL, inherit_handles,
                                    NORMAL_PRIORITY_CLASS, NULL, NULL, &si, &pi)) error=GetLastError();
            if (error==ERROR_SUCCESS) {
                CloseHandle(pi.hProcess);
                CloseHandle(pi.hThread);
            } else {
                char *message=dupprintf("Could not create session: %s",win_strerror(error));
                MessageBoxA(hwnd,message,"Nemoterm",MB_OK|MB_ICONERROR);sfree(message);
            }
            sfree(command);

            sfree(cl);
            break;
          }
          case IDM_RESTART:
            if (!wgs->backend) {
                lp_eventlog(&wgs->logpolicy, "----- Session restarted -----");
                term_pwron(wgs->term, false);
                start_backend(wgs);
            }

            break;
          case IDM_RECONF: {
            Conf *prev_conf;
            int init_lvl = 1;
            bool reconfig_result;

            if (wgs->reconfiguring)
                break;
            else
                wgs->reconfiguring = true;

            term_pre_reconfig(wgs->term, wgs->conf);
            prev_conf = conf_copy(wgs->conf);

            reconfig_result = do_reconfig(
                hwnd, wgs->conf,
                wgs->backend ? backend_cfg_info(wgs->backend) : 0);
            wgs->reconfiguring = false;
            if (!reconfig_result) {
                conf_free(prev_conf);
                break;
            }

            conf_cache_data(wgs);

            resize_action = conf_get_int(wgs->conf, CONF_resize_action);
            {
                /* Disable full-screen if resizing forbidden */
                int i;
                for (i = 0; i < lenof(wgs->popup_menus); i++)
                    EnableMenuItem(wgs->popup_menus[i].menu, IDM_FULLSCREEN,
                                   MF_BYCOMMAND |
                                   (resize_action == RESIZE_DISABLED
                                    ? MF_GRAYED : MF_ENABLED));
                /* Gracefully unzoom if necessary */
                if (IsZoomed(hwnd) && (resize_action == RESIZE_DISABLED))
                    ShowWindow(hwnd, SW_RESTORE);
            }

            /* Pass new config data to the logging module */
            log_reconfig(wgs->logctx, wgs->conf);

            sfree(wgs->logpal);
            /*
             * Flush the line discipline's edit buffer in the
             * case where local editing has just been disabled.
             */
            if (wgs->ldisc) {
                ldisc_configure(wgs->ldisc, wgs->conf);
                ldisc_echoedit_update(wgs->ldisc);
            }

            if (conf_get_bool(wgs->conf, CONF_system_colour) !=
                conf_get_bool(prev_conf, CONF_system_colour))
                term_notify_palette_changed(wgs->term);

            /* Pass new config data to the terminal */
            term_reconfig(wgs->term, wgs->conf);
            setup_clipboards(wgs->term, wgs->conf);

            /* Reinitialise the colour palette, in case the terminal
             * just read new settings out of Conf */
            if (wgs->pal)
                DeleteObject(wgs->pal);
            wgs->logpal = NULL;
            wgs->pal = NULL;
            init_palette(wgs);

            /* Pass new config data to the back end */
            if (wgs->backend)
                backend_reconfig(wgs->backend, wgs->conf);

            /* Screen size changed ? */
            if (conf_get_int(wgs->conf, CONF_height) !=
                conf_get_int(prev_conf, CONF_height) ||
                conf_get_int(wgs->conf, CONF_width) !=
                conf_get_int(prev_conf, CONF_width) ||
                conf_get_int(wgs->conf, CONF_savelines) !=
                conf_get_int(prev_conf, CONF_savelines) ||
                resize_action == RESIZE_FONT ||
                (resize_action == RESIZE_EITHER && IsZoomed(hwnd)) ||
                resize_action == RESIZE_DISABLED)
                term_size(wgs->term, conf_get_int(wgs->conf, CONF_height),
                          conf_get_int(wgs->conf, CONF_width),
                          conf_get_int(wgs->conf, CONF_savelines));

            /* Enable or disable the scroll bar, etc */
            {
                LONG nflg, flag = GetWindowLongPtr(hwnd, GWL_STYLE);
                LONG nexflag, exflag =
                    GetWindowLongPtr(hwnd, GWL_EXSTYLE);

                nexflag = exflag;
                if (conf_get_bool(wgs->conf, CONF_alwaysontop) !=
                    conf_get_bool(prev_conf, CONF_alwaysontop)) {
                    if (conf_get_bool(wgs->conf, CONF_alwaysontop)) {
                        nexflag |= WS_EX_TOPMOST;
                        SetWindowPos(wgs_window(wgs), HWND_TOPMOST, 0, 0, 0, 0,
                                     SWP_NOMOVE | SWP_NOSIZE);
                    } else {
                        nexflag &= ~(WS_EX_TOPMOST);
                        SetWindowPos(wgs_window(wgs), HWND_NOTOPMOST, 0, 0, 0, 0,
                                     SWP_NOMOVE | SWP_NOSIZE);
                    }
                }
                if (conf_get_bool(wgs->conf, CONF_sunken_edge))
                    nexflag |= WS_EX_CLIENTEDGE;
                else
                    nexflag &= ~(WS_EX_CLIENTEDGE);

                nflg = flag;
                if (conf_get_bool(wgs->conf, is_full_screen(wgs) ?
                                  CONF_scrollbar_in_fullscreen :
                                  CONF_scrollbar))
                    nflg |= WS_VSCROLL;
                else
                    nflg &= ~WS_VSCROLL;

                if (resize_action == RESIZE_DISABLED ||
                    is_full_screen(wgs))
                    nflg &= ~WS_THICKFRAME;
                else
                    nflg |= WS_THICKFRAME;

                if (resize_action == RESIZE_DISABLED)
                    nflg &= ~WS_MAXIMIZEBOX;
                else
                    nflg |= WS_MAXIMIZEBOX;

                if (wgs->tabbed) {
                    nflg &= ~(WS_THICKFRAME|WS_MAXIMIZEBOX);
                    nexflag &= ~WS_EX_TOPMOST;
                }
                if (nflg != flag || nexflag != exflag) {
                    if (nflg != flag)
                        SetWindowLongPtr(hwnd, GWL_STYLE, nflg);
                    if (nexflag != exflag)
                        SetWindowLongPtr(hwnd, GWL_EXSTYLE, nexflag);

                    SetWindowPos(hwnd, NULL, 0, 0, 0, 0,
                                 SWP_NOACTIVATE | SWP_NOCOPYBITS |
                                 SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER |
                                 SWP_FRAMECHANGED);

                    init_lvl = 2;
                }
            }

            /* Oops */
            if (resize_action == RESIZE_DISABLED && IsZoomed(hwnd)) {
                force_normal(hwnd);
                init_lvl = 2;
            }

            {
                FontSpec *font = conf_get_fontspec(wgs->conf, CONF_font);
                FontSpec *prev_font = conf_get_fontspec(prev_conf,
                                                        CONF_font);

                if (!strcmp(font->name, prev_font->name) ||
                    !strcmp(conf_get_str(wgs->conf, CONF_line_codepage),
                            conf_get_str(prev_conf, CONF_line_codepage)) ||
                    font->isbold != prev_font->isbold ||
                    font->height != prev_font->height ||
                    font->charset != prev_font->charset ||
                    conf_get_int(wgs->conf, CONF_font_quality) !=
                    conf_get_int(prev_conf, CONF_font_quality) ||
                    conf_get_int(wgs->conf, CONF_vtmode) !=
                    conf_get_int(prev_conf, CONF_vtmode) ||
                    conf_get_int(wgs->conf, CONF_bold_style) !=
                    conf_get_int(prev_conf, CONF_bold_style) ||
                    resize_action == RESIZE_DISABLED ||
                    resize_action == RESIZE_EITHER ||
                    resize_action != conf_get_int(prev_conf,
                                                  CONF_resize_action))
                    init_lvl = 2;
            }

            InvalidateRect(hwnd, NULL, true);
            reset_window(wgs, init_lvl);

            if (conf_get_int(wgs->conf, CONF_nemo_renderer) !=
                conf_get_int(prev_conf, CONF_nemo_renderer)) {
                term_end_synchronized_update(wgs->term);
                wgs->gpu_failed = false;
                nemo_renderer_configure(wgs);
            }

            nemo_host_configure(wgs);
            conf_free(prev_conf);
            break;
          }
          case IDM_COPYDIR:
            nemo_copy_directory(wgs);
            break;
          case IDM_PREVPROMPT:
          case IDM_NEXTPROMPT:
            term_shell_mark_navigate(wgs->term, (wParam & ~0xF) == IDM_PREVPROMPT ? -1 : 1);
            break;
          case IDM_SELECTCOMMAND:
          case IDM_SELECTOUTPUT:
            term_shell_mark_select(wgs->term, (wParam & ~0xF) == IDM_SELECTOUTPUT);
            break;
          case IDM_COPYALL:
            term_copyall(wgs->term, clips_system, lenof(clips_system));
            break;
          case IDM_COPY:
            term_request_copy(wgs->term, clips_system, lenof(clips_system));
            break;
          case IDM_COPYPASTE:
            term_request_copy(wgs->term, clips_system, lenof(clips_system));
            /* Paste the same selection even if the system clipboard is busy
             * or another application replaces it between copy and paste. */
            term_request_paste(wgs->term, CLIP_LOCAL);
            break;
          case IDM_PASTE:
            term_request_paste(wgs->term, CLIP_SYSTEM);
            break;
          case IDM_CLRSB:
            term_clrsb(wgs->term);
            break;
          case IDM_RESET:
            term_pwron(wgs->term, true);
            if (wgs->ldisc)
                ldisc_echoedit_update(wgs->ldisc);
            break;
          case IDM_ABOUT:
            showabout(hwnd);
            break;
          case IDM_HELP:
            launch_help(hwnd, NULL);
            break;
          case SC_MOUSEMENU:
            /*
             * We get this if the System menu has been activated
             * using the mouse.
             */
            show_mouseptr(wgs, true);
            break;
          case SC_KEYMENU:
            /*
             * We get this if the System menu has been activated
             * using the keyboard. This might happen from within
             * TranslateKey, in which case it really wants to be
             * followed by a `space' character to actually _bring
             * the menu up_ rather than just sitting there in
             * `ready to appear' state.
             */
            show_mouseptr(wgs, true);    /* make sure pointer is visible */
            if (lParam == 0)
                PostMessage(hwnd, WM_CHAR, ' ', 0);
            break;
          case IDM_FULLSCREEN:
            flip_full_screen(wgs);
            break;
          default:
            if (wParam >= IDM_SAVED_MIN && wParam < IDM_SAVED_MAX) {
                SendMessage(hwnd, WM_SYSCOMMAND, IDM_SAVEDSESS, wParam);
            }
            if (wParam >= IDM_SPECIAL_MIN && wParam <= IDM_SPECIAL_MAX) {
                int i = (wParam - IDM_SPECIAL_MIN) / 0x10;
                /*
                 * Ensure we haven't been sent a bogus SYSCOMMAND
                 * which would cause us to reference invalid memory
                 * and crash. Perhaps I'm just too paranoid here.
                 */
                if (i >= wgs->n_specials)
                    break;
                if (wgs->backend)
                    backend_special(wgs->backend, wgs->specials[i].code,
                                    wgs->specials[i].arg);
            }
        }
        break;

#define X_POS(l) ((int)(short)LOWORD(l))
#define Y_POS(l) ((int)(short)HIWORD(l))

#define TO_CHR_X(x) ((((x)<0 ? (x)-wgs->font_width+1 :                  \
                       (x))-wgs->offset_width) / wgs->font_width)
#define TO_CHR_Y(y) ((((y)<0 ? (y)-wgs->font_height+1 :                 \
                       (y))-wgs->offset_height) / wgs->font_height)
      case WM_LBUTTONDOWN:
      case WM_MBUTTONDOWN:
      case WM_RBUTTONDOWN:
      case WM_LBUTTONUP:
      case WM_MBUTTONUP:
      case WM_RBUTTONUP:
      case WM_XBUTTONDOWN:
      case WM_XBUTTONUP:
        if (nemo_link_button(wgs, message, wParam, lParam)) return 0;
        if (message == WM_RBUTTONUP && wgs->nemo_consumed_right_click) {
            wgs->nemo_consumed_right_click = false;
            return 0;
        }
        if (message == WM_RBUTTONDOWN && !(wParam & MK_CONTROL) &&
            wgs->term->selstate == SELECTED) {
            wgs->nemo_consumed_right_click = true;
            term_request_copy(wgs->term, clips_system, lenof(clips_system));
            if (conf_get_bool(wgs->conf, CONF_nemo_right_click_paste))
                term_request_paste(wgs->term, CLIP_LOCAL);
            return 0;
        }
        if (message == WM_RBUTTONDOWN &&
            ((wParam & MK_CONTROL) ||
             (wParam & MK_SHIFT) || !wgs->term->xterm_mouse ||
             (conf_get_int(wgs->conf, CONF_mouse_is_xterm) == MOUSE_WINDOWS))) {
            POINT cursorpos = {X_POS(lParam), Y_POS(lParam)};

            /* Just in case this happened in mid-select */
            term_cancel_selection_drag(wgs->term);
            wgs->nemo_consumed_right_click = true;

            show_mouseptr(wgs, true);    /* make sure pointer is visible */
            UINT command = nemo_link_menu(wgs, wgs->popup_menus[CTXMENU].menu, cursorpos);
            if (command) SendMessage(hwnd, WM_COMMAND, command, 0);
            break;
        }
        {
            int button;
            bool press;

            switch (message) {
              case WM_LBUTTONDOWN:
                button = MBT_LEFT;
                wParam |= MK_LBUTTON;
                press = true;
                break;
              case WM_MBUTTONDOWN:
                button = MBT_MIDDLE;
                wParam |= MK_MBUTTON;
                press = true;
                break;
              case WM_RBUTTONDOWN:
                button = MBT_RIGHT;
                wParam |= MK_RBUTTON;
                press = true;
                break;
              case WM_LBUTTONUP:
                button = MBT_LEFT;
                wParam &= ~MK_LBUTTON;
                press = false;
                break;
              case WM_MBUTTONUP:
                button = MBT_MIDDLE;
                wParam &= ~MK_MBUTTON;
                press = false;
                break;
              case WM_RBUTTONUP:
                button = MBT_RIGHT;
                wParam &= ~MK_RBUTTON;
                press = false;
                break;
              case WM_XBUTTONDOWN:
              case WM_XBUTTONUP: {
                unsigned xbutton = HIWORD(wParam);
                if (xbutton != XBUTTON1 && xbutton != XBUTTON2)
                    return TRUE;
                button = xbutton == XBUTTON1 ? MBT_X1 : MBT_X2;
                unsigned mask = xbutton == XBUTTON1 ? MK_XBUTTON1 : MK_XBUTTON2;
                press = message == WM_XBUTTONDOWN;
                wParam = LOWORD(wParam);
                if (press) wParam |= mask;
                else wParam &= ~mask;
                break;
              }
              default: /* shouldn't happen */
                button = 0;
                press = false;
            }
            show_mouseptr(wgs, true);
            /*
             * Special case: in full-screen mode, if the left
             * button is clicked in the very top left corner of the
             * window, we put up the System menu instead of doing
             * selection.
             */
            {
                bool mouse_on_hotspot = false;
                POINT pt;

                GetCursorPos(&pt);
#ifndef NO_MULTIMON
                if (p_GetMonitorInfoA && p_MonitorFromPoint) {
                    HMONITOR mon;
                    MONITORINFO mi;

                    mon = p_MonitorFromPoint(pt, MONITOR_DEFAULTTONULL);

                    if (mon != NULL) {
                        mi.cbSize = sizeof(MONITORINFO);
                        p_GetMonitorInfoA(mon, &mi);

                        if (mi.rcMonitor.left == pt.x &&
                            mi.rcMonitor.top == pt.y) {
                            mouse_on_hotspot = true;
                        }
                    }
                } else
#endif
                if (pt.x == 0 && pt.y == 0) {
                    mouse_on_hotspot = true;
                }
                if (is_full_screen(wgs) && press &&
                    button == MBT_LEFT && mouse_on_hotspot) {
                    SendMessage(hwnd, WM_SYSCOMMAND, SC_MOUSEMENU,
                                MAKELPARAM(pt.x, pt.y));
                    return 0;
                }
            }

            if (press) {
                click(wgs, button,
                      TO_CHR_X(X_POS(lParam)), TO_CHR_Y(Y_POS(lParam)),
                      X_POS(lParam)-wgs->offset_width,
                      Y_POS(lParam)-wgs->offset_height,
                      wParam & MK_SHIFT, wParam & MK_CONTROL,
                      is_alt_pressed());
                /* Reacquiring our own capture sends WM_CAPTURECHANGED too,
                 * which must not cancel another button still held down. */
                if (GetCapture() != hwnd &&
                    ((button != MBT_X1 && button != MBT_X2) ||
                     (wgs->send_raw_mouse && !(wParam & MK_SHIFT))))
                    SetCapture(hwnd);
            } else {
                term_mouse_pixels(wgs->term, button, translate_button(wgs, button),
                           MA_RELEASE, TO_CHR_X(X_POS(lParam)),
                           TO_CHR_Y(Y_POS(lParam)),
                           X_POS(lParam)-wgs->offset_width,
                           Y_POS(lParam)-wgs->offset_height, wParam & MK_SHIFT,
                           wParam & MK_CONTROL, is_alt_pressed());
                if (!(wParam & (MK_LBUTTON | MK_MBUTTON | MK_RBUTTON |
                                MK_XBUTTON1 | MK_XBUTTON2)))
                    ReleaseCapture();
            }
        }
        return message == WM_XBUTTONDOWN || message == WM_XBUTTONUP ? TRUE : 0;
      case WM_MOUSEMOVE:
        /*
         * Windows seems to like to occasionally send MOUSEMOVE
         * events even if the mouse hasn't moved. Don't unhide
         * the mouse pointer in this case.
         */
        if (wgs->last_mousemove != WM_MOUSEMOVE ||
            wParam != wgs->last_wm_mousemove_wParam ||
            lParam != wgs->last_wm_mousemove_lParam) {
            show_mouseptr(wgs, true);
            wgs->last_mousemove = WM_MOUSEMOVE;
            wgs->last_wm_mousemove_wParam = wParam;
            wgs->last_wm_mousemove_lParam = lParam;
        }
        /*
         * Add the mouse position and message time to the random
         * number noise.
         */
        noise_ultralight(NOISE_SOURCE_MOUSEPOS, lParam);

        if (nemo_link_motion(wgs, &wParam, lParam)) return 0;
        if (wParam & (MK_LBUTTON | MK_MBUTTON | MK_RBUTTON |
                      MK_XBUTTON1 | MK_XBUTTON2) &&
            GetCapture() == hwnd) {
            Mouse_Button b;
            if (wParam & MK_LBUTTON)
                b = MBT_LEFT;
            else if (wParam & MK_MBUTTON)
                b = MBT_MIDDLE;
            else if (wParam & MK_RBUTTON)
                b = MBT_RIGHT;
            else if (wParam & MK_XBUTTON1)
                b = MBT_X1;
            else
                b = MBT_X2;
            term_mouse_pixels(wgs->term, b, translate_button(wgs, b), MA_DRAG,
                       TO_CHR_X(X_POS(lParam)),
                       TO_CHR_Y(Y_POS(lParam)),
                       X_POS(lParam)-wgs->offset_width,
                       Y_POS(lParam)-wgs->offset_height, wParam & MK_SHIFT,
                       wParam & MK_CONTROL, is_alt_pressed());
        } else {
            term_mouse_pixels(wgs->term, MBT_NOTHING, MBT_NOTHING, MA_MOVE,
                       TO_CHR_X(X_POS(lParam)),
                       TO_CHR_Y(Y_POS(lParam)),
                       X_POS(lParam)-wgs->offset_width,
                       Y_POS(lParam)-wgs->offset_height, (wParam & MK_SHIFT) != 0,
                       (wParam & MK_CONTROL) != 0, is_alt_pressed());
        }
        return 0;
      case WM_CAPTURECHANGED:
        if ((HWND)lParam == hwnd) return 0;
        /* fall through: only an actual loss cancels reported buttons */
      case WM_CANCELMODE:
        nemo_link_cancel(wgs);
        term_mouse_cancel(wgs->term);
        term_cancel_selection_drag(wgs->term);
        if (message == WM_CANCELMODE && GetCapture() == hwnd)
            ReleaseCapture();
        if (message == WM_CANCELMODE)
            return DefWindowProc(hwnd, message, wParam, lParam);
        return 0;
      case WM_MOUSELEAVE:
        nemo_link_leave(wgs);
        return 0;
      case WM_SETCURSOR:
        if (LOWORD(lParam) == HTCLIENT && nemo_link_hand_cursor(wgs)) {
            SetCursor(LoadCursor(NULL, IDC_HAND));
            return TRUE;
        }
        break;
      case WM_NCMOUSEMOVE:
        nemo_link_leave(wgs);
        if (wgs->last_mousemove != WM_NCMOUSEMOVE ||
            wParam != wgs->last_wm_ncmousemove_wParam ||
            lParam != wgs->last_wm_ncmousemove_lParam) {
            show_mouseptr(wgs, true);
            wgs->last_mousemove = WM_NCMOUSEMOVE;
            wgs->last_wm_ncmousemove_wParam = wParam;
            wgs->last_wm_ncmousemove_lParam = lParam;
        }
        noise_ultralight(NOISE_SOURCE_MOUSEPOS, lParam);
        break;
      case WM_IGNORE_CLIP:
        wgs->ignore_clip = wParam; /* don't panic on DESTROYCLIPBOARD */
        break;
      case WM_DESTROYCLIPBOARD:
        if (!wgs->ignore_clip)
            term_lost_clipboard_ownership(wgs->term, CLIP_SYSTEM);
        wgs->ignore_clip = false;
        return 0;
      case WM_PRINTCLIENT:
        if (wgs->sync_snapshot && wgs->term->synchronized_update &&
            nemo_snapshot_paint(wgs->sync_snapshot,(HDC)wParam,NULL,NULL)) return 0;
        if (wgs->gpu && nemo_gpu_print(wgs->gpu, (HDC)wParam)) return 0;
        {
            /* Render the requested client image directly for standalone GDI
             * windows too. DefWindowProc/DWM may otherwise return a stale
             * redirection surface while the resized window is repainting. */
            RECT rect;GetClientRect(hwnd,&rect);
            nemo_render_snapshot_band((HDC)wParam,0,rect.bottom,wgs);
            term_invalidate(wgs->term);return 0;
        }
      case WM_PAINT: {
        PAINTSTRUCT p;

        HideCaret(hwnd);
        hdc = BeginPaint(hwnd, &p);
        if (IsIconic(wgs_window(wgs)) || !wgs_active(wgs)) {
            /* A minimized client can be zero-sized. Keep its renderer and
             * dirty terminal cells until restoration instead of treating
             * the unavailable surface as device failure. */
            EndPaint(hwnd, &p);
            ShowCaret(hwnd);
            return 0;
        }
        if (wgs->gpu) {
            if (!wgs->term->synchronized_update && nemo_renderer_begin(wgs)) {
                term_paint(wgs->term, 0, 0, wgs->term->cols-1,
                           wgs->term->rows-1, !wgs->term->window_update_pending);
                nemo_renderer_finish(wgs);
            } else if (wgs->gpu && !nemo_gpu_present(wgs->gpu)) {
                wgs->gpu_failed = true;
                nemo_renderer_configure(wgs);
            }
            EndPaint(hwnd, &p);
            ShowCaret(hwnd);
            nemo_link_refresh(wgs);
            return 0;
        }
        if (wgs->sync_snapshot && wgs->term->synchronized_update) {
            NemoSnapshotError error;
            if (nemo_snapshot_paint(wgs->sync_snapshot, hdc, &p.rcPaint, &error)) {
                EndPaint(hwnd, &p);
                ShowCaret(hwnd);
                return 0;
            }
            logeventf(wgs->logctx, "Synchronized repaint failed at %s (%lu)",
                      error.stage, (unsigned long)error.win32_error);
            term_end_synchronized_update(wgs->term);
        }
        if (wgs->pal) {
            SelectPalette(hdc, wgs->pal, true);
            RealizePalette(hdc);
        }

        /*
         * We have to be careful about term_paint(). It will
         * set a bunch of character cells to INVALID and then
         * call do_paint(), which will redraw those cells and
         * _then mark them as done_. This may not be accurate:
         * when painting in WM_PAINT context we are restricted
         * to the rectangle which has just been exposed - so if
         * that only covers _part_ of a character cell and the
         * rest of it was already visible, that remainder will
         * not be redrawn at all. Accordingly, we must not
         * paint any character cell in a WM_PAINT context which
         * already has a pending update due to terminal output.
         * The simplest solution to this - and many, many
         * thanks to Hung-Te Lin for working all this out - is
         * not to do any actual painting at _all_ if there's a
         * pending terminal update: just mark the relevant
         * character cells as INVALID and wait for the
         * scheduled full update to sort it out.
         *
         * I have a suspicion this isn't the _right_ solution.
         * An alternative approach would be to have terminal.c
         * separately track what _should_ be on the terminal
         * screen and what _is_ on the terminal screen, and
         * have two completely different types of redraw (one
         * for full updates, which syncs the former with the
         * terminal itself, and one for WM_PAINT which syncs
         * the latter with the former); yet another possibility
         * would be to have the Windows front end do what the
         * GTK one already does, and maintain a bitmap of the
         * current terminal appearance so that WM_PAINT becomes
         * completely trivial. However, this should do for now.
         */
        assert(!wgs->wintw_hdc);
        wgs->wintw_hdc = hdc;
        term_paint(wgs->term,
                   (p.rcPaint.left-wgs->offset_width)/wgs->font_width,
                   (p.rcPaint.top-wgs->offset_height)/wgs->font_height,
                   (p.rcPaint.right-wgs->offset_width-1)/wgs->font_width,
                   (p.rcPaint.bottom-wgs->offset_height-1)/wgs->font_height,
                   !wgs->term->window_update_pending);
        if (!wgs->term->window_update_pending)
            nemo_paint_images(wgs);
        wgs->wintw_hdc = NULL;

        if (p.fErase ||
            p.rcPaint.left  < wgs->offset_width  ||
            p.rcPaint.top   < wgs->offset_height ||
            p.rcPaint.right >= (wgs->offset_width +
                                wgs->font_width*wgs->term->cols) ||
            p.rcPaint.bottom>= (wgs->offset_height +
                                wgs->font_height*wgs->term->rows)) {
            HBRUSH fillcolour, oldbrush;
            HPEN   edge, oldpen;
            fillcolour = CreateSolidBrush (
                wgs->colours[ATTR_DEFBG>>ATTR_BGSHIFT]);
            oldbrush = SelectObject(hdc, fillcolour);
            edge = CreatePen(PS_SOLID, 0,
                             wgs->colours[ATTR_DEFBG>>ATTR_BGSHIFT]);
            oldpen = SelectObject(hdc, edge);

            /*
             * Jordan Russell reports that this apparently
             * ineffectual IntersectClipRect() call masks a
             * Windows NT/2K bug causing strange display
             * problems when the PuTTY window is taller than
             * the primary monitor. It seems harmless enough...
             */
            IntersectClipRect(hdc,
                              p.rcPaint.left, p.rcPaint.top,
                              p.rcPaint.right, p.rcPaint.bottom);

            ExcludeClipRect(
                hdc, wgs->offset_width, wgs->offset_height,
                wgs->offset_width+wgs->font_width*wgs->term->cols,
                wgs->offset_height+wgs->font_height*wgs->term->rows);

            Rectangle(hdc, p.rcPaint.left, p.rcPaint.top,
                      p.rcPaint.right, p.rcPaint.bottom);

            /* SelectClipRgn(hdc, NULL); */

            SelectObject(hdc, oldbrush);
            DeleteObject(fillcolour);
            SelectObject(hdc, oldpen);
            DeleteObject(edge);
        }
        SelectObject(hdc, GetStockObject(SYSTEM_FONT));
        SelectObject(hdc, GetStockObject(WHITE_PEN));
        EndPaint(hwnd, &p);
        ShowCaret(hwnd);
        nemo_link_refresh(wgs);
        return 0;
      }
      case WM_NETEVENT:
      case WM_DONE_WITH_SOCKET:
        winselgui_response(message, wParam, lParam);
        return 0;
      case WM_SETFOCUS:
        if (wgs->tabbed) {
            HIMC imc=ImmGetContext(hwnd);
            if (imc) {ImmSetCompositionFont(imc,&wgs->lfont);ImmReleaseContext(hwnd,imc);}
        }
        term_set_focus(wgs->term, true);
        if (wgs->caretbm) {
            CreateCaret(hwnd, wgs->caretbm, wgs->font_width, wgs->font_height);
            ShowCaret(hwnd);
        }
        flash_window(wgs, 0);               /* stop */
        wgs->compose_state = 0;
        term_update(wgs->term);
        break;
      case WM_KILLFOCUS:
        nemo_link_cancel(wgs);
        nemo_keyboard_focus_lost(wgs);
        wgs->pending_surrogate = 0;
        show_mouseptr(wgs, true);
        term_set_focus(wgs->term, false);
        term_cancel_selection_drag(wgs->term);
        if (GetCapture() == hwnd) ReleaseCapture();
        DestroyCaret();
        wgs->caret_x = wgs->caret_y = -1; /* ensure caret replaced next time */
        term_update(wgs->term);
        break;
      case WM_ENTERSIZEMOVE:
        nemo_link_cancel(wgs);
        term_end_synchronized_update(wgs->term);
        EnableSizeTip(true);
        wgs->resizing = true;
        wgs->need_backend_resize = false;
        break;
      case WM_EXITSIZEMOVE:
        EnableSizeTip(false);
        wgs->resizing = false;
        if (wgs->need_backend_resize) {
            term_size(wgs->term, conf_get_int(wgs->conf, CONF_height),
                      conf_get_int(wgs->conf, CONF_width),
                      conf_get_int(wgs->conf, CONF_savelines));
            InvalidateRect(hwnd, NULL, true);
        }
        recompute_window_offset(wgs);
        break;
      case WM_SIZING:
        /*
         * This does two jobs:
         * 1) Keep the sizetip uptodate
         * 2) Make sure the window size is _stepped_ in units of the font size.
         */
        resize_action = conf_get_int(wgs->conf, CONF_resize_action);
        if (resize_action == RESIZE_TERM ||
            (resize_action == RESIZE_EITHER && !is_alt_pressed())) {
            int width, height, w, h, ew, eh;
            LPRECT r = (LPRECT) lParam;

            if (!wgs->need_backend_resize && resize_action == RESIZE_EITHER &&
                (conf_get_int(wgs->conf, CONF_height) != wgs->term->rows ||
                 conf_get_int(wgs->conf, CONF_width) != wgs->term->cols)) {
                /*
                 * Great! It seems that both the terminal size and the
                 * font size have been changed and the user is now dragging.
                 *
                 * It will now be difficult to get back to the configured
                 * font size!
                 *
                 * This would be easier but it seems to be too confusing.
                 */
                conf_set_int(wgs->conf, CONF_height, wgs->term->rows);
                conf_set_int(wgs->conf, CONF_width, wgs->term->cols);

                InvalidateRect(hwnd, NULL, true);
                wgs->need_backend_resize = true;
            }

            width = r->right - r->left - wgs->extra_width;
            height = r->bottom - r->top - wgs->extra_height;
            w = (width + wgs->font_width / 2) / wgs->font_width;
            if (w < 1)
                w = 1;
            h = (height + wgs->font_height / 2) / wgs->font_height;
            if (h < 1)
                h = 1;
            UpdateSizeTip(hwnd, w, h);
            ew = width - w * wgs->font_width;
            eh = height - h * wgs->font_height;
            if (ew != 0) {
                if (wParam == WMSZ_LEFT ||
                    wParam == WMSZ_BOTTOMLEFT || wParam == WMSZ_TOPLEFT)
                    r->left += ew;
                else
                    r->right -= ew;
            }
            if (eh != 0) {
                if (wParam == WMSZ_TOP ||
                    wParam == WMSZ_TOPRIGHT || wParam == WMSZ_TOPLEFT)
                    r->top += eh;
                else
                    r->bottom -= eh;
            }
            if (ew || eh)
                return 1;
            else
                return 0;
        } else {
            int width, height, w, h, rv = 0;
            int window_border = conf_get_int(wgs->conf, CONF_window_border);
            int ex_width = wgs->extra_width +
                (window_border - wgs->offset_width) * 2;
            int ex_height = wgs->extra_height +
                (window_border - wgs->offset_height) * 2;
            LPRECT r = (LPRECT) lParam;

            width = r->right - r->left - ex_width;
            height = r->bottom - r->top - ex_height;

            w = (width + wgs->term->cols/2)/wgs->term->cols;
            h = (height + wgs->term->rows/2)/wgs->term->rows;
            if ( r->right != r->left + w*wgs->term->cols + ex_width)
                rv = 1;

            if (wParam == WMSZ_LEFT ||
                wParam == WMSZ_BOTTOMLEFT || wParam == WMSZ_TOPLEFT)
                r->left = r->right - w*wgs->term->cols - ex_width;
            else
                r->right = r->left + w*wgs->term->cols + ex_width;

            if (r->bottom != r->top + h*wgs->term->rows + ex_height)
                rv = 1;

            if (wParam == WMSZ_TOP ||
                wParam == WMSZ_TOPRIGHT || wParam == WMSZ_TOPLEFT)
                r->top = r->bottom - h*wgs->term->rows - ex_height;
            else
                r->bottom = r->top + h*wgs->term->rows + ex_height;

            return rv;
        }
        /* break;  (never reached) */
      case WM_FULLSCR_ON_MAX:
        wgs->fullscr_on_max = true;
        break;
      case WM_MOVE:
        term_notify_window_pos(wgs->term, LOWORD(lParam), HIWORD(lParam));
        sys_cursor_update(wgs);
        break;
      case WM_SIZE:
        if (wgs->tabbed) {
            if (!tab_host.moving) nemo_host_resize(wgs,0);
            return 0;
        }
        nemo_link_cancel(wgs);
        term_end_synchronized_update(wgs->term);
        resize_action = conf_get_int(wgs->conf, CONF_resize_action);
        term_notify_minimised(wgs->term, wParam == SIZE_MINIMIZED);
        {
            /*
             * WM_SIZE's lParam tells us the size of the client area.
             * But historic PuTTY practice is that we want to tell the
             * terminal the size of the overall window.
             */
            RECT r;
            GetWindowRect(hwnd, &r);
            term_notify_window_size_pixels(
                wgs->term, r.right - r.left, r.bottom - r.top);
        }
        if (wParam == SIZE_MINIMIZED)
            sw_SetWindowText(hwnd,
                             conf_get_bool(wgs->conf, CONF_win_name_always) ?
                             wgs->window_name : wgs->icon_name);
        if (wParam == SIZE_RESTORED || wParam == SIZE_MAXIMIZED)
            sw_SetWindowText(hwnd, wgs->window_name);
        if (wParam == SIZE_RESTORED) {
            wgs->processed_resize = false;
            clear_full_screen(wgs);
            if (wgs->processed_resize) {
                /*
                 * Inhibit normal processing of this WM_SIZE; a
                 * secondary one was triggered just now by
                 * clear_full_screen which contained the correct
                 * client area size.
                 */
                return 0;
            }
        }
        if (wParam == SIZE_MAXIMIZED && wgs->fullscr_on_max) {
            wgs->fullscr_on_max = false;
            wgs->processed_resize = false;
            make_full_screen(wgs);
            if (wgs->processed_resize) {
                /*
                 * Inhibit normal processing of this WM_SIZE; a
                 * secondary one was triggered just now by
                 * make_full_screen which contained the correct client
                 * area size.
                 */
                return 0;
            }
        }

        wgs->processed_resize = true;

        if (resize_action == RESIZE_DISABLED) {
            /* A resize, well it better be a minimize. */
            reset_window(wgs, -1);
        } else {
            if (wParam == SIZE_MAXIMIZED) {
                wgs->was_zoomed = true;
                wgs->prev_rows = wgs->term->rows;
                wgs->prev_cols = wgs->term->cols;
                if (resize_action == RESIZE_TERM)
                    wm_size_resize_term(wgs, lParam);
                reset_window(wgs, 0);
            } else if (wParam == SIZE_RESTORED && wgs->was_zoomed) {
                wgs->was_zoomed = false;
                if (resize_action == RESIZE_TERM) {
                    wm_size_resize_term(wgs, lParam);
                    reset_window(wgs, 2);
                } else if (resize_action != RESIZE_FONT)
                    reset_window(wgs, 2);
                else
                    reset_window(wgs, 0);
            } else if (wParam == SIZE_MINIMIZED) {
                /* do nothing */
            } else if (resize_action == RESIZE_TERM ||
                       (resize_action == RESIZE_EITHER &&
                        (wgs->remote_window_resize || !is_alt_pressed()))) {
                wm_size_resize_term(wgs, lParam);

                /*
                 * Sometimes, we can get a spontaneous resize event
                 * outside a WM_SIZING interactive drag which wants to
                 * set us to a new specific SIZE_RESTORED size. An
                 * example is what happens if you press Windows+Right
                 * and then Windows+Up: the first operation fits the
                 * window to the right-hand half of the screen, and
                 * the second one changes that for the top right
                 * quadrant. In that situation, if we've responded
                 * here by resizing the terminal, we may still need to
                 * recompute the border around the window and do a
                 * full redraw to clear the new border.
                 */
                if (!wgs->resizing)
                    recompute_window_offset(wgs);
            } else {
                reset_window(wgs, 0);
            }
        }
        sys_cursor_update(wgs);
        return 0;
      case WM_DPICHANGED:
        term_end_synchronized_update(wgs->term);
        wgs->dpi_info.cur_dpi.x = LOWORD(wParam);
        wgs->dpi_info.cur_dpi.y = HIWORD(wParam);
        wgs->dpi_info.new_wnd_rect = *(RECT*)(lParam);
        reset_window(wgs, 3);
        return 0;
      case WM_VSCROLL:
        switch (LOWORD(wParam)) {
          case SB_BOTTOM:
            term_scroll(wgs->term, -1, 0);
            break;
          case SB_TOP:
            term_scroll(wgs->term, +1, 0);
            break;
          case SB_LINEDOWN:
            term_scroll(wgs->term, 0, +1);
            break;
          case SB_LINEUP:
            term_scroll(wgs->term, 0, -1);
            break;
          case SB_PAGEDOWN:
            term_scroll(wgs->term, 0, +wgs->term->rows / 2);
            break;
          case SB_PAGEUP:
            term_scroll(wgs->term, 0, -wgs->term->rows / 2);
            break;
          case SB_THUMBPOSITION:
          case SB_THUMBTRACK: {
            /*
             * Use GetScrollInfo instead of HIWORD(wParam) to get
             * 32-bit scroll position.
             */
            SCROLLINFO si;

            si.cbSize = sizeof(si);
            si.fMask = SIF_TRACKPOS;
            if (GetScrollInfo(hwnd, SB_VERT, &si) == 0)
                si.nTrackPos = HIWORD(wParam);
            term_scroll(wgs->term, 1, si.nTrackPos);
            break;
          }
        }

        if (wgs->in_scrollbar_loop) {
            /*
             * Allow window updates to happen during interactive
             * scroll.
             *
             * When the user takes hold of our window's scrollbar and
             * wobbles it interactively back and forth, or presses on
             * one of the arrow buttons at the ends, the first thing
             * that happens is that this window procedure receives
             * WM_SYSCOMMAND / SC_VSCROLL. [1] The default handler for
             * that window message starts a subsidiary message loop,
             * which continues to run until the user lets go of the
             * scrollbar again. All WM_VSCROLL / SB_THUMBTRACK
             * messages are generated by the handlers within that
             * subsidiary message loop.
             *
             * So, during that time, _our_ message loop is not
             * running, which means toplevel callbacks and timers and
             * so forth are not happening, which means that when we
             * redraw the window and set a timer to clear the cooldown
             * flag 20ms later, that timer never fires, and we aren't
             * able to keep redrawing the window.
             *
             * The 'obvious' answer would be to seize that SYSCOMMAND
             * ourselves and inhibit the default handler, so that our
             * message loop carries on running. But that would mean
             * we'd have to reimplement the whole of the scrollbar
             * handler!
             *
             * So instead we apply a bodge: set a static variable that
             * indicates that we're _in_ that sub-loop, and if so,
             * decide it's OK to manually call term_update() proper,
             * bypassing the timer and cooldown and rate-limiting
             * systems completely, whenever we see an SB_THUMBTRACK.
             * This shouldn't cause a rate overload, because we're
             * only doing it once per UI event!
             *
             * [1] Actually, there's an extra oddity where SC_HSCROLL
             * and SC_VSCROLL have their documented values the wrong
             * way round. Many people on the Internet have noticed
             * this, e.g. https://stackoverflow.com/q/55528397
             */
            term_update(wgs->term);
        }
        break;
      case WM_PALETTECHANGED:
        if ((HWND) wParam != hwnd && wgs->pal != NULL) {
            HDC hdc = make_hdc(wgs);
            if (hdc) {
                if (RealizePalette(hdc) > 0)
                    UpdateColors(hdc);
                free_hdc(wgs, hdc);
            }
        }
        break;
      case WM_QUERYNEWPALETTE:
        if (wgs->pal != NULL) {
            HDC hdc = make_hdc(wgs);
            if (hdc) {
                if (RealizePalette(hdc) > 0)
                    UpdateColors(hdc);
                free_hdc(wgs, hdc);
                return true;
            }
        }
        return false;
      case WM_KEYDOWN:
      case WM_SYSKEYDOWN:
      case WM_KEYUP:
      case WM_SYSKEYUP:
        nemo_link_key(wgs, message, wParam);
        /*
         * Add the scan code and keypress timing to the random
         * number noise.
         */
        noise_ultralight(NOISE_SOURCE_KEY, lParam);

        /*
         * We don't do TranslateMessage since it disassociates the
         * resulting CHAR message from the KEYDOWN that sparked it,
         * which we occasionally don't want. Instead, we process
         * KEYDOWN, and call the Win32 translator functions so that
         * we get the translations under _our_ control.
         */
        {
            unsigned char buf[20];
            int len;

            if (wParam == VK_PROCESSKEY || /* IME PROCESS key */
                wParam == VK_PACKET) {     /* 'this key is a Unicode char' */
                if (message == WM_KEYDOWN) {
                    MSG m;
                    m.hwnd = hwnd;
                    m.message = WM_KEYDOWN;
                    m.wParam = wParam;
                    m.lParam = lParam & 0xdfff;
                    TranslateMessage(&m);
                } else break; /* pass to Windows for default processing */
            } else {
                len = TranslateKey(wgs, message, wParam, lParam, buf);
                if (len == -1)
                    return sw_DefWindowProc(hwnd, message, wParam, lParam);

                if (len != 0) {
                    /*
                     * We need not bother about stdin backlogs
                     * here, because in GUI PuTTY we can't do
                     * anything about it anyway; there's no means
                     * of asking Windows to hold off on KEYDOWN
                     * messages. We _have_ to buffer everything
                     * we're sent.
                     */
                    term_keyinput(wgs->term, -1, buf, len);
                    show_mouseptr(wgs, false);
                }
            }
        }
        return 0;
      case WM_INPUTLANGCHANGE:
        /* wParam == Font number */
        /* lParam == Locale */
        set_input_locale(wgs, (HKL)lParam);
        sys_cursor_update(wgs);
        break;
      case WM_IME_STARTCOMPOSITION: {
        wgs->pending_surrogate = 0;
        HIMC hImc = ImmGetContext(hwnd);
        if (hImc) {
            ImmSetCompositionFont(hImc, &wgs->lfont);
            ImmReleaseContext(hwnd, hImc);
        }
        break;
      }
      case WM_IME_ENDCOMPOSITION:
        wgs->pending_surrogate = 0;
        break;
      case WM_IME_COMPOSITION: {
        HIMC hIMC;
        int n;
        char *buff;

        if (osPlatformId == VER_PLATFORM_WIN32_WINDOWS ||
            osPlatformId == VER_PLATFORM_WIN32s)
            break; /* no Unicode */

        if ((lParam & GCS_RESULTSTR) == 0) /* Composition unfinished. */
            break; /* fall back to DefWindowProc */

        hIMC = ImmGetContext(hwnd);
        if (!hIMC) break;
        n = ImmGetCompositionStringW(hIMC, GCS_RESULTSTR, NULL, 0);

        /* Both IMM calls return byte counts. A commit may disappear or
         * shrink between them; never send uninitialized or stale tail bytes.
         * Bound transient IME storage independently of terminal history. */
        if (n > 0 && n <= 65536 && !(n & 1)) {
            int i;
            buff = snewn(n, char);
            int actual = ImmGetCompositionStringW(hIMC, GCS_RESULTSTR, buff, n);
            if (actual < 0 || actual > n || (actual & 1)) actual = 0;
            n = actual;
            wgs->pending_surrogate = 0;
            /*
             * Jaeyoun Chung reports that Korean character
             * input doesn't work correctly if we do a single
             * term_keyinputw covering the whole of buff. So
             * instead we send the characters one by one.
             */
            /* don't divide SURROGATE PAIR */
            if (wgs->ldisc && !nemo_keyboard_text(wgs, (wchar_t *)buff, n/2)) {
                for (i = 0; i < n; i += 2) {
                    WCHAR hs = *(unsigned short *)(buff+i);
                    if (IS_HIGH_SURROGATE(hs) && i+2 < n) {
                        WCHAR ls = *(unsigned short *)(buff+i+2);
                        if (IS_LOW_SURROGATE(ls)) {
                            term_keyinputw(
                                wgs->term, (unsigned short *)(buff+i), 2);
                            i += 2;
                            continue;
                        }
                    }
                    term_keyinputw(
                        wgs->term, (unsigned short *)(buff+i), 1);
                }
            }
            free(buff);
        }
        ImmReleaseContext(hwnd, hIMC);
        return 1;
      }

      case WM_IME_CHAR:
        if (unicode_window) goto unicode_character;
        if (wParam & 0xFF00) {
            char buf[2];

            buf[1] = wParam;
            buf[0] = wParam >> 8;
            term_keyinput(wgs->term, wgs->kbd_codepage, buf, 2);
        } else {
            char c = (unsigned char) wParam;
            term_seen_key_event(wgs->term);
            term_keyinput(wgs->term, wgs->kbd_codepage, &c, 1);
        }
        return (0);
      case WM_CHAR:
      case WM_SYSCHAR:
        /*
         * Nevertheless, we are prepared to deal with WM_CHAR
         * messages, should they crop up. So if someone wants to
         * post the things to us as part of a macro manoeuvre,
         * we're ready to cope.
         */
      unicode_character:
        if (unicode_window) {
            wchar_t c = wParam;

            if (IS_HIGH_SURROGATE(c)) {
                wgs->pending_surrogate = c;
            } else if (IS_SURROGATE_PAIR(wgs->pending_surrogate, c)) {
                wchar_t pair[2];
                pair[0] = wgs->pending_surrogate;
                pair[1] = c;
                wgs->pending_surrogate = 0;
                if (!nemo_keyboard_text(wgs, pair, 2))
                    term_keyinputw(wgs->term, pair, 2);
            } else if (!IS_SURROGATE(c)) {
                wgs->pending_surrogate = 0;
                if (!nemo_keyboard_text(wgs, &c, 1))
                    term_keyinputw(wgs->term, &c, 1);
            } else {
                wgs->pending_surrogate = 0;
            }
        } else {
            char c = (unsigned char)wParam;
            term_seen_key_event(wgs->term);
            if (wgs->ldisc)
                term_keyinput(wgs->term, CP_ACP, &c, 1);
        }
        return 0;
      case WM_UNICHAR: {
        /* UTF-32 input (including the UNICODE_NOCHAR capability probe). */
        if (wParam == 0xffff) return TRUE;
        wgs->pending_surrogate = 0;
        if (wParam > 0x10ffff || (wParam >= 0xd800 && wParam <= 0xdfff))
            return 0;
        wchar_t text[2];
        int length = 1;
        if (wParam >= 0x10000) {
            unsigned scalar = (unsigned)wParam - 0x10000;
            text[0] = 0xd800 + (scalar >> 10);
            text[1] = 0xdc00 + (scalar & 0x3ff);
            length = 2;
        } else text[0] = (wchar_t)wParam;
        if (!nemo_keyboard_text(wgs, text, length))
            term_keyinputw(wgs->term, text, length);
        return 0;
      }
      case WM_SYSCOLORCHANGE:
        if (conf_get_bool(wgs->conf, CONF_system_colour)) {
            /* Refresh palette from system colours. */
            term_notify_palette_changed(wgs->term);
            init_palette(wgs);
            /* Force a repaint of the terminal window. */
            term_invalidate(wgs->term);
        }
        break;
      case WM_DROPFILES:
        nemo_paste_drop(wgs,(HDROP)wParam);DragFinish((HDROP)wParam);return 0;
      case WM_GOT_CLIPDATA:
        /* The worker owns this request until SendMessage returns. A delayed
         * clipboard owner may outlive its target window; never route the
         * result to a new session that reuses that HWND. */
        if (!wgs->closing && wgs->backend && wgs->ldisc &&
            wParam == wgs->session_id) {
            const NemoPasteRequest *request = (const NemoPasteRequest *)lParam;
            if (request->files) nemo_paste_drop(wgs,(HDROP)request->data);
            else if (request->application_paste) {
                /* Image transfer belongs to the foreground application's
                 * native clipboard reader. Never encode pixels as VT text. */
                wchar_t paste_key=0x16;
                term_keyinputw(wgs->term,&paste_key,1);
            } else process_clipdata(wgs, request->data, request->unicode);
        }
        return 0;
      case WM_NEMO_OSC52_READY:
        nemo_osc52_poll(wgs, wParam);
        return 0;
      case WM_TIMER:
        if (wParam == NEMO_OSC52_TIMER) {
            nemo_osc52_poll(wgs, 0);
            return 0;
        }
        break;
      default:
        if (message == wm_mousewheel || message == WM_MOUSEWHEEL
                                                || message == WM_MOUSEHWHEEL) {
            bool shift_pressed = false, control_pressed = false;
            int *accumulator = message == WM_MOUSEHWHEEL ?
                &wgs->horizontal_wheel_accumulator : &wgs->wheel_accumulator;

            if (message == WM_MOUSEWHEEL || message == WM_MOUSEHWHEEL) {
                *accumulator += (short)HIWORD(wParam);
                shift_pressed=LOWORD(wParam) & MK_SHIFT;
                control_pressed=LOWORD(wParam) & MK_CONTROL;
            } else {
                BYTE keys[256];
                *accumulator += (int)wParam;
                if (GetKeyboardState(keys)!=0) {
                    shift_pressed=keys[VK_SHIFT]&0x80;
                    control_pressed=keys[VK_CONTROL]&0x80;
                }
            }

            /* process events when the threshold is reached */
            while (abs(*accumulator) >= WHEEL_DELTA) {
                int b;

                /* reduce amount for next time */
                if (*accumulator > 0) {
                    b = message == WM_MOUSEHWHEEL ? MBT_WHEEL_RIGHT : MBT_WHEEL_UP;
                    *accumulator -= WHEEL_DELTA;
                } else if (*accumulator < 0) {
                    b =  message == WM_MOUSEHWHEEL ? MBT_WHEEL_LEFT : MBT_WHEEL_DOWN;
                    *accumulator += WHEEL_DELTA;
                } else
                    break;

                if (wgs->send_raw_mouse && !shift_pressed) {
                    /* Mouse wheel position is in screen coordinates for
                     * some reason */
                    POINT p;
                    p.x = X_POS(lParam); p.y = Y_POS(lParam);
                    if (ScreenToClient(hwnd, &p)) {
                        /* Wheels send presses only, including horizontal axes. */
                        term_mouse_pixels(wgs->term, b, translate_button(wgs, b),
                                   MA_CLICK,
                                   TO_CHR_X(p.x),
                                   TO_CHR_Y(p.y),
                                   p.x-wgs->offset_width, p.y-wgs->offset_height,
                                   shift_pressed,
                                   control_pressed, is_alt_pressed());
                    } /* else: not sure when this can fail */
                } else if (!term_mouse_wheel(wgs->term, b, shift_pressed,
                                            control_pressed, is_alt_pressed()) &&
                           message != WM_MOUSEHWHEEL) {
                    UINT lines = 3;
                    SystemParametersInfo(SPI_GETWHEELSCROLLLINES, 0, &lines, 0);
                    int amount = lines == WHEEL_PAGESCROLL ?
                        max(wgs->term->rows-1, 1) : min(lines, INT_MAX);
                    term_scroll(wgs->term, 0,
                                b == MBT_WHEEL_UP ? -amount : amount);
                }
            }
            return 0;
        }
    }

    /*
     * Any messages we don't process completely above are passed through to
     * DefWindowProc() for default processing.
     */
    return sw_DefWindowProc(hwnd, message, wParam, lParam);
}

/*
 * Move the system caret. (We maintain one, even though it's
 * invisible, for the benefit of blind people: apparently some
 * helper software tracks the system caret, so we should arrange to
 * have one.)
 */
static void wintw_set_cursor_pos(TermWin *tw, int x, int y)
{
    WinGuiSeat *wgs = container_of(tw, WinGuiSeat, termwin);
    int cx, cy;

    if (!wgs->term->has_focus) return;

    /*
     * Avoid gratuitously re-updating the cursor position and IMM
     * window if there's no actual change required.
     */
    cx = x * wgs->font_width + wgs->offset_width;
    cy = y * wgs->font_height + wgs->offset_height;
    if (cx == wgs->caret_x && cy == wgs->caret_y)
        return;
    wgs->caret_x = cx;
    wgs->caret_y = cy;

    sys_cursor_update(wgs);
}

static void sys_cursor_update(WinGuiSeat *wgs)
{
    COMPOSITIONFORM cf;
    HIMC hIMC;

    if (!wgs->term->has_focus) return;

    if (wgs->caret_x < 0 || wgs->caret_y < 0)
        return;

    SetCaretPos(wgs->caret_x, wgs->caret_y);

    /* IMM calls on Win98 and beyond only */
    if (osPlatformId == VER_PLATFORM_WIN32s) return; /* 3.11 */

    if (osPlatformId == VER_PLATFORM_WIN32_WINDOWS &&
        osMinorVersion == 0) return; /* 95 */

    /* we should have the IMM functions */
    hIMC = ImmGetContext(wgs->term_hwnd);
    cf.dwStyle = CFS_POINT;
    cf.ptCurrentPos.x = wgs->caret_x;
    cf.ptCurrentPos.y = wgs->caret_y;
    ImmSetCompositionWindow(hIMC, &cf);

    ImmReleaseContext(wgs->term_hwnd, hIMC);
}

static void draw_horizontal_line_on_text(
    WinGuiSeat *wgs, int y, int lattr, RECT line_box, COLORREF colour)
{
    if (lattr == LATTR_TOP || lattr == LATTR_BOT) {
        y *= 2;
        if (lattr == LATTR_BOT)
            y -= wgs->font_height;
    }

    if (!(0 <= y && y < wgs->font_height))
        return;

    HPEN oldpen = SelectObject(wgs->wintw_hdc, CreatePen(PS_SOLID, 0, colour));
    MoveToEx(wgs->wintw_hdc, line_box.left, line_box.top + y, NULL);
    LineTo(wgs->wintw_hdc, line_box.right, line_box.top + y);
    oldpen = SelectObject(wgs->wintw_hdc, oldpen);
    DeleteObject(oldpen);
}

/*
 * Draw a line of text in the window, at given character
 * coordinates, in given attributes.
 *
 * We are allowed to fiddle with the contents of `text'.
 */
static void nemo_draw_underline(WinGuiSeat *wgs, RECT box, int lattr,
                                unsigned style, COLORREF colour)
{
    if (lattr == LATTR_TOP || box.right <= box.left) return;
    int height = wgs->font_height, thick = max(1, height / 16);
    int baseline = wgs->descent;
    if (lattr == LATTR_BOT) baseline = baseline * 2 - height;
    baseline = max(0, min(baseline, height-thick));
    int saved = SaveDC(wgs->wintw_hdc);
    if (!saved) return;
    IntersectClipRect(wgs->wintw_hdc, box.left, box.top, box.right, box.bottom);
    HBRUSH brush = GetStockObject(DC_BRUSH);
    SetDCBrushColor(wgs->wintw_hdc, colour);
    if (style <= 2) {
        RECT line = { box.left, box.top+baseline, box.right, box.top+baseline+thick };
        FillRect(wgs->wintw_hdc, &line, brush);
        if (style == 2 && baseline >= 2*thick) {
            line.top -= 2*thick; line.bottom -= 2*thick;
            FillRect(wgs->wintw_hdc, &line, brush);
        }
    } else {
        int amplitude = max(1, height/16), period = 4*amplitude;
        if (style == 3) baseline = max(amplitude, min(baseline, height-thick-amplitude));
        for (int x = box.left; x < box.right; x++) {
            int dx = x - wgs->offset_width, dy = 0;
            if (style == 3) {
                int phase = dx % period;
                dy = phase <= amplitude ? phase :
                    phase <= 3*amplitude ? 2*amplitude-phase : phase-period;
            } else if (style == 4) {
                if (dx % (3*thick) >= thick) continue;
            } else if (style == 5) {
                if (dx % (5*thick) >= 3*thick) continue;
            }
            RECT pixel = { x, box.top+baseline+dy, x+1, box.top+baseline+dy+thick };
            FillRect(wgs->wintw_hdc, &pixel, brush);
        }
    }
    RestoreDC(wgs->wintw_hdc, saved);
}

static void do_text_internal(
    WinGuiSeat *wgs, int x, int y, wchar_t *text, int len,
    unsigned long attr, int lattr, truecolour truecolour)
{
    COLORREF fg, bg, t;
    int nfg, nbg, nfont;
    RECT line_box;
    bool force_manual_underline = false;
    int fnt_width, char_width;
    int text_adjust = 0;
    int xoffset = 0;
    int maxlen, remaining;
    bool opaque;
    bool is_cursor = false;
    int *lpDx = NULL;
    size_t lpDx_len = 0;
    bool use_lpDx;
    wchar_t *wbuf = NULL;
    char *cbuf = NULL;
    size_t wbuflen = 0, cbuflen = 0;
    int len2; /* for SURROGATE PAIR */
    bool whole_cluster = (attr & TATTR_COMBINING) != 0;
    wchar_t cluster_text[2*(CC_LIMIT+1)];
    bool emoji = false, emoji_base = false;

    if (whole_cluster && len > 0 && len <= (int)lenof(cluster_text)) {
        memcpy(cluster_text, text, len*sizeof(*text));
        for (int i=0;i<len;i++) {
            unsigned long cp=cluster_text[i];
            if (i+1<len && IS_SURROGATE_PAIR(cp,cluster_text[i+1])) {
                cp=FROM_SURROGATES(cp,cluster_text[i+1]);i++;
            } else if (DIRECT_FONT(cp)) {
                /* ASCII in the terminal's translated line table can carry
                 * a direct-font marker. Genuine surrogate pairs above must
                 * never enter this legacy font-byte conversion. */
                char byte=(char)(cp&255);wchar_t scalar=0xfffd;
                MultiByteToWideChar((cp&CSET_MASK)==CSET_OEMCP?CP_OEMCP:
                    wgs->ucsdata.font_codepage,0,&byte,1,&scalar,1);
                cp=cluster_text[i]=scalar;
            }
            if (cp==0xfe0e) emoji=false;
            else if ((cp==0xfe0f && emoji_base) || nemo_grapheme_is_emoji(cp,true)) emoji=true;
            emoji_base=nemo_grapheme_is_emoji(cp,false);
        }
        text=cluster_text;
        /* Private icon fonts registered with GDI need not be visible to
         * DirectWrite's system collection. A variation selector alone has
         * no defined emoji presentation for a private-use character: retain
         * its existing GDI/embedded-font glyph and ignore only the selector
         * for drawing, leaving the stored cluster unchanged. */
        unsigned long base=text[0];int base_units=1;
        if (len>1 && IS_SURROGATE_PAIR(text[0],text[1])) {
            base=FROM_SURROGATES(text[0],text[1]);base_units=2;
        }
        if ((base>=0xe000 && base<=0xf8ff) ||
            (base>=0xf0000 && base<=0xffffd) || (base>=0x100000 && base<=0x10fffd)) {
            int end=base_units;
            while (end<len) {
                if (IS_LOW_VARSEL(text[end])) end++;
                else if (end+1<len && IS_HIGH_VARSEL(text[end],text[end+1])) end+=2;
                else break;
            }
            if (end==len && end>base_units) {
                len=base_units;whole_cluster=false;attr&=~TATTR_COMBINING;
            }
        }
    }

    lattr &= LATTR_MODE;

    char_width = fnt_width = wgs->font_width * (1 + (lattr != LATTR_NORM));

    if (attr & ATTR_WIDE)
        char_width *= 2;

    /* Only want the left half of double width lines */
    if (lattr != LATTR_NORM && x*2 >= wgs->term->cols)
        return;

    x *= fnt_width;
    y *= wgs->font_height;
    x += wgs->offset_width;
    y += wgs->offset_height;

    if ((attr & ATTR_ACTCURS) &&
        (wgs->term->cursor_type == CURSOR_BLOCK || wgs->term->big_cursor)) {
        truecolour.fg = truecolour.bg = optionalrgb_none;
        attr &= ~(ATTR_REVERSE|ATTR_BLINK|ATTR_COLOURS|ATTR_DIM);
        /* cursor fg and bg */
        attr |= (260 << ATTR_FGSHIFT) | (261 << ATTR_BGSHIFT);
        is_cursor = true;
    }

    nfont = 0;
    if (wgs->vtmode == VT_POORMAN && lattr != LATTR_NORM) {
        /* Assume a poorman font is borken in other ways too. */
        lattr = LATTR_WIDE;
    } else
        switch (lattr) {
          case LATTR_NORM:
            break;
          case LATTR_WIDE:
            nfont |= FONT_WIDE;
            break;
          default:
            nfont |= FONT_WIDE + FONT_HIGH;
            break;
        }
    if (attr & ATTR_NARROW)
        nfont |= FONT_NARROW;

#ifdef USES_VTLINE_HACK
    /* Special hack for the VT100 linedraw glyphs. */
    if (text[0] >= 0x23BA && text[0] <= 0x23BD) {
        switch ((unsigned char) (text[0])) {
          case 0xBA:
            text_adjust = -2 * wgs->font_height / 5;
            break;
          case 0xBB:
            text_adjust = -1 * wgs->font_height / 5;
            break;
          case 0xBC:
            text_adjust = wgs->font_height / 5;
            break;
          case 0xBD:
            text_adjust = 2 * wgs->font_height / 5;
            break;
        }
        if (lattr == LATTR_TOP || lattr == LATTR_BOT)
            text_adjust *= 2;
        text[0] = wgs->ucsdata.unitab_xterm['q'];
        if (attr & ATTR_UNDER) {
            attr &= ~ATTR_UNDER;
            force_manual_underline = true;
        }
    }
#endif

    /* Anything left as an original character set is unprintable. */
    if (DIRECT_CHAR(text[0]) &&
        (len < 2 || !IS_SURROGATE_PAIR(text[0], text[1]))) {
        int i;
        for (i = 0; i < len; i++)
            text[i] = 0xFFFD;
    }

    /* OEM CP */
    if ((text[0] & CSET_MASK) == CSET_OEMCP)
        nfont |= FONT_OEM;

    nfg = ((attr & ATTR_FGMASK) >> ATTR_FGSHIFT);
    nbg = ((attr & ATTR_BGMASK) >> ATTR_BGSHIFT);
    if (wgs->bold_font_mode == BOLD_FONT && (attr & ATTR_BOLD))
        nfont |= FONT_BOLD;
    if (attr & ATTR_ITALIC) nfont |= FONT_ITALIC;
    another_font(wgs, nfont);
    if (!wgs->fonts[nfont]) {
        if (nfont & FONT_UNDERLINE)
            force_manual_underline = true;
        /* Don't do the same for manual bold, it could be bad news. */

        nfont &= ~(FONT_BOLD | FONT_UNDERLINE | FONT_ITALIC);
    }
    another_font(wgs, nfont);
    if (!wgs->fonts[nfont])
        nfont = FONT_NORMAL;
    if (attr & ATTR_REVERSE) {
        struct optionalrgb trgb;

        t = nfg;
        nfg = nbg;
        nbg = t;

        trgb = truecolour.fg;
        truecolour.fg = truecolour.bg;
        truecolour.bg = trgb;
    }
    if (wgs->bold_colours && (attr & ATTR_BOLD) && !is_cursor) {
        if (nfg < 16) nfg |= 8;
        else if (nfg >= 256) nfg |= 1;
    }
    if (wgs->bold_colours && (attr & ATTR_BLINK)) {
        if (nbg < 16) nbg |= 8;
        else if (nbg >= 256) nbg |= 1;
    }
    if (!wgs->pal && truecolour.fg.enabled)
        fg = RGB(truecolour.fg.r, truecolour.fg.g, truecolour.fg.b);
    else
        fg = wgs->colours[nfg];

    if (!wgs->pal && truecolour.bg.enabled)
        bg = RGB(truecolour.bg.r, truecolour.bg.g, truecolour.bg.b);
    else
        bg = wgs->colours[nbg];

    if (!wgs->pal && (attr & ATTR_DIM)) {
        fg = RGB(GetRValue(fg) * 2 / 3,
                 GetGValue(fg) * 2 / 3,
                 GetBValue(fg) * 2 / 3);
    }

    if (attr & ATTR_CONCEAL) fg = bg;

    SelectObject(wgs->wintw_hdc, wgs->fonts[nfont]);
    SetTextColor(wgs->wintw_hdc, fg);
    SetBkColor(wgs->wintw_hdc, bg);
    if (attr & TATTR_COMBINING)
        SetBkMode(wgs->wintw_hdc, TRANSPARENT);
    else
        SetBkMode(wgs->wintw_hdc, OPAQUE);
    line_box.left = x;
    line_box.top = y;
    line_box.right = x + char_width * len;
    line_box.bottom = y + wgs->font_height;
    /* adjust line_box.right for SURROGATE PAIR & VARIATION SELECTOR */
    {
        int i;
        int rc_width = 0;
        for (i = 0; i < len ; i++) {
            if (i+1 < len && IS_HIGH_VARSEL(text[i], text[i+1])) {
                i++;
            } else if (i+1 < len && IS_SURROGATE_PAIR(text[i], text[i+1])) {
                rc_width += char_width;
                i++;
            } else if (IS_LOW_VARSEL(text[i])) {
                /* do nothing */
            } else {
                rc_width += char_width;
            }
        }
        line_box.right = line_box.left + rc_width;
    }

    /* Only want the left half of double width lines */
    if (whole_cluster) line_box.right = line_box.left + char_width;
    if (line_box.right > wgs->font_width*wgs->term->cols+wgs->offset_width)
        line_box.right = wgs->font_width*wgs->term->cols+wgs->offset_width;

    if (whole_cluster) {
        if (len <= (int)lenof(cluster_text) && nemo_cluster_draw(
                &wgs->cluster_renderer,wgs->wintw_hdc,&line_box,text,len,
                text_adjust-wgs->font_height*(lattr==LATTR_BOT),fg,bg,emoji,
                (lattr==LATTR_WIDE?2.0f:1.0f)*((attr&ATTR_NARROW)?0.5f:1.0f),
                wgs->bold_font_mode==BOLD_SHADOW && (attr&ATTR_BOLD), false))
            goto decorations;
        /* Preserve this cluster's grid width even if a system API/font or
         * the bounded scratch allocation is unavailable. */
        cluster_text[0]=0xfffd;text=cluster_text;len=1;
        attr &= ~TATTR_COMBINING;
        SetBkMode(wgs->wintw_hdc,OPAQUE);
    }

    if (wgs->font_varpitch) {
        /*
         * If we're using a variable-pitch font, we unconditionally
         * draw the glyphs one at a time and centre them in their
         * character cells (which means in particular that we must
         * disable the lpDx mechanism). This gives slightly odd but
         * generally reasonable results.
         */
        xoffset = char_width / 2;
        SetTextAlign(wgs->wintw_hdc, TA_TOP | TA_CENTER | TA_NOUPDATECP);
        use_lpDx = false;
        maxlen = 1;
    } else {
        /*
         * In a fixed-pitch font, we draw the whole string in one go
         * in the normal way.
         */
        xoffset = 0;
        SetTextAlign(wgs->wintw_hdc, TA_TOP | TA_LEFT | TA_NOUPDATECP);
        use_lpDx = true;
        maxlen = len;
    }

    opaque = true;                     /* start by erasing the rectangle */
    for (remaining = len; remaining > 0;
         text += len, remaining -= len, x += char_width * len2) {
        len = (maxlen < remaining ? maxlen : remaining);
        /* don't divide SURROGATE PAIR and VARIATION SELECTOR */
        len2 = len;
        if (maxlen == 1) {
            if (remaining >= 1 && IS_SURROGATE_PAIR(text[0], text[1]))
                len++;
            if (remaining-len >= 1 && IS_LOW_VARSEL(text[len]))
                len++;
            else if (remaining-len >= 2 &&
                     IS_HIGH_VARSEL(text[len], text[len+1]))
                len += 2;
        }

        if (len > lpDx_len)
            sgrowarray(lpDx, lpDx_len, len);

        {
            int i;
            /* only last char has dx width in SURROGATE PAIR and
             * VARIATION sequence */
            for (i = 0; i < len; i++) {
                lpDx[i] = char_width;
                if (i+1 < len && IS_HIGH_VARSEL(text[i], text[i+1])) {
                    if (i > 0) lpDx[i-1] = 0;
                    lpDx[i] = 0;
                    i++;
                    lpDx[i] = char_width;
                } else if (i+1 < len && IS_SURROGATE_PAIR(text[i],text[i+1])) {
                    lpDx[i] = 0;
                    i++;
                    lpDx[i] = char_width;
                } else if (IS_LOW_VARSEL(text[i])) {
                    if (i > 0) lpDx[i-1] = 0;
                    lpDx[i] = char_width;
                }
            }
        }

        /* We're using a private area for direct to font. (512 chars.) */
        if (wgs->ucsdata.dbcs_screenfont &&
            (text[0] & CSET_MASK) == CSET_ACP) {
            /* Ho Hum, dbcs fonts are a PITA! */
            /* To display on W9x I have to convert to UCS */
            int nlen, mptr;

            sgrowarray(wbuf, wbuflen, len);
            for (nlen = mptr = 0; mptr<len; mptr++) {
                wbuf[nlen] = 0xFFFD;
                if (IsDBCSLeadByteEx(wgs->ucsdata.font_codepage,
                                     (BYTE) text[mptr])) {
                    char dbcstext[2];
                    dbcstext[0] = text[mptr] & 0xFF;
                    dbcstext[1] = text[mptr+1] & 0xFF;
                    lpDx[nlen] += char_width;
                    MultiByteToWideChar(
                        wgs->ucsdata.font_codepage, MB_USEGLYPHCHARS,
                        dbcstext, 2, wbuf+nlen, 1);
                    mptr++;
                } else {
                    char dbcstext[1];
                    dbcstext[0] = text[mptr] & 0xFF;
                    MultiByteToWideChar(
                        wgs->ucsdata.font_codepage, MB_USEGLYPHCHARS,
                        dbcstext, 1, wbuf+nlen, 1);
                }
                nlen++;
            }
            if (nlen <= 0)
                goto out;                /* Eeek! */

            ExtTextOutW(
                wgs->wintw_hdc, x + xoffset,
                y - wgs->font_height * (lattr == LATTR_BOT) + text_adjust,
                ETO_CLIPPED | (opaque ? ETO_OPAQUE : 0),
                &line_box, wbuf, nlen, (use_lpDx ? lpDx : NULL));
            if (wgs->bold_font_mode == BOLD_SHADOW && (attr & ATTR_BOLD)) {
                SetBkMode(wgs->wintw_hdc, TRANSPARENT);
                ExtTextOutW(
                    wgs->wintw_hdc, x + xoffset - 1,
                    y - wgs->font_height * (lattr == LATTR_BOT) + text_adjust,
                    ETO_CLIPPED, &line_box, wbuf, nlen,
                    (use_lpDx ? lpDx : NULL));
            }

            lpDx[0] = -1;
        } else if (DIRECT_FONT(text[0])) {
            sgrowarray(cbuf, cbuflen, len);
            for (size_t i = 0; i < len; i++)
                cbuf[i] = text[i] & 0xFF;

            ExtTextOut(
                wgs->wintw_hdc, x + xoffset,
                y - wgs->font_height * (lattr == LATTR_BOT) + text_adjust,
                ETO_CLIPPED | (opaque ? ETO_OPAQUE : 0),
                &line_box, cbuf, len, (use_lpDx ? lpDx : NULL));
            if (wgs->bold_font_mode == BOLD_SHADOW && (attr & ATTR_BOLD)) {
                SetBkMode(wgs->wintw_hdc, TRANSPARENT);

                /* GRR: This draws the character outside its box and
                 * can leave 'droppings' even with the clip box! I
                 * suppose I could loop it one character at a time ...
                 * yuk.
                 *
                 * Or ... I could do a test print with "W", and use +1
                 * or -1 for this shift depending on if the leftmost
                 * column is blank...
                 */
                ExtTextOut(
                    wgs->wintw_hdc, x + xoffset - 1,
                    y - wgs->font_height * (lattr == LATTR_BOT) + text_adjust,
                    ETO_CLIPPED, &line_box, cbuf, len,
                    (use_lpDx ? lpDx : NULL));
            }
        } else {
            /* And 'normal' unicode characters */
            sgrowarray(wbuf, wbuflen, len);
            for (int i = 0; i < len; i++)
                wbuf[i] = text[i];

            /* print Glyphs as they are, without Windows' Shaping*/
            general_textout(
                wgs, wgs->wintw_hdc, x + xoffset,
                y - wgs->font_height * (lattr==LATTR_BOT) + text_adjust,
                &line_box, wbuf, len, lpDx,
                opaque && !(attr & TATTR_COMBINING),
                (lattr==LATTR_WIDE?2.0f:1.0f)*((attr&ATTR_NARROW)?0.5f:1.0f));

            /* And the shadow bold hack. */
            if (wgs->bold_font_mode == BOLD_SHADOW && (attr & ATTR_BOLD)) {
                SetBkMode(wgs->wintw_hdc, TRANSPARENT);
                general_textout(
                    wgs, wgs->wintw_hdc, x + xoffset - 1,
                    y - wgs->font_height * (lattr == LATTR_BOT) + text_adjust,
                    &line_box, wbuf, len, lpDx, false,
                    (lattr==LATTR_WIDE?2.0f:1.0f)*((attr&ATTR_NARROW)?0.5f:1.0f));
            }
        }

        /*
         * If we're looping round again, stop erasing the background
         * rectangle.
         */
        SetBkMode(wgs->wintw_hdc, TRANSPARENT);
        opaque = false;
    }

  decorations:
    if (!(attr & ATTR_CONCEAL) && (force_manual_underline || (attr & ATTR_UNDER))) {
        uint32_t colour = truecolour.decoration & UNDER_COLOUR_MASK;
        COLORREF underline = fg;
        if (colour & UNDER_RGB)
            underline = RGB((colour >> 16) & 255, (colour >> 8) & 255, colour & 255);
        else if (colour & UNDER_INDEXED)
            underline = wgs->colours[colour & 255];
        nemo_draw_underline(wgs, line_box, lattr,
                            max(1, UNDER_STYLE(truecolour)), underline);
    }

    if (attr & ATTR_STRIKE)
        draw_horizontal_line_on_text(wgs, wgs->font_strikethrough_y, lattr,
                                     line_box, fg);

  out:
    sfree(lpDx);
    sfree(wbuf);
    sfree(cbuf);
}

/*
 * Wrapper that handles combining characters.
 */
static void nemo_raster_text(
    TermWin *tw, int x, int y, wchar_t *text, int len,
    unsigned long attr, int lattr, truecolour truecolour)
{
    WinGuiSeat *wgs = container_of(tw, WinGuiSeat, termwin);
    do_text_internal(wgs, x, y, text, len, attr, lattr, truecolour);
}

static void nemo_raster_cursor(
    TermWin *tw, int x, int y, wchar_t *text, int len,
    unsigned long attr, int lattr, truecolour truecolour)
{
    WinGuiSeat *wgs = container_of(tw, WinGuiSeat, termwin);
    int fnt_width;
    int char_width;
    int ctype = wgs->term->cursor_type;

    lattr &= LATTR_MODE;

    if ((attr & ATTR_ACTCURS) &&
        (ctype == CURSOR_BLOCK || wgs->term->big_cursor)) {
        if (*text != UCSWIDE) {
            nemo_raster_text(tw, x, y, text, len, attr, lattr, truecolour);
            return;
        }
        ctype = CURSOR_VERTICAL_LINE;
        attr |= ATTR_RIGHTCURS;
    }

    fnt_width = char_width = wgs->font_width * (1 + (lattr != LATTR_NORM));
    if (attr & ATTR_WIDE)
        char_width *= 2;
    x *= fnt_width;
    y *= wgs->font_height;
    x += wgs->offset_width;
    y += wgs->offset_height;

    if ((attr & ATTR_PASCURS) &&
        (ctype == CURSOR_BLOCK || wgs->term->big_cursor)) {
        POINT pts[5];
        HPEN oldpen;
        pts[0].x = pts[1].x = pts[4].x = x;
        pts[2].x = pts[3].x = x + char_width - 1;
        pts[0].y = pts[3].y = pts[4].y = y;
        pts[1].y = pts[2].y = y + wgs->font_height - 1;
        oldpen = SelectObject(wgs->wintw_hdc,
                              CreatePen(PS_SOLID, 0, wgs->colours[261]));
        Polyline(wgs->wintw_hdc, pts, 5);
        oldpen = SelectObject(wgs->wintw_hdc, oldpen);
        DeleteObject(oldpen);
    } else if ((attr & (ATTR_ACTCURS | ATTR_PASCURS)) &&
               ctype != CURSOR_BLOCK) {
        int startx, starty, dx, dy, length, i;
        if (ctype == CURSOR_UNDERLINE) {
            startx = x;
            starty = y + wgs->descent;
            dx = 1;
            dy = 0;
            length = char_width;
        } else /* ctype == CURSOR_VERTICAL_LINE */ {
            int xadjust = 0;
            if (attr & ATTR_RIGHTCURS)
                xadjust = char_width - 1;
            startx = x + xadjust;
            starty = y;
            dx = 0;
            dy = 1;
            length = wgs->font_height;
        }
        if (attr & ATTR_ACTCURS) {
            HPEN oldpen;
            oldpen =
                SelectObject(wgs->wintw_hdc,
                             CreatePen(PS_SOLID, 0, wgs->colours[261]));
            MoveToEx(wgs->wintw_hdc, startx, starty, NULL);
            LineTo(wgs->wintw_hdc, startx + dx * length, starty + dy * length);
            oldpen = SelectObject(wgs->wintw_hdc, oldpen);
            DeleteObject(oldpen);
        } else {
            for (i = 0; i < length; i++) {
                if (i % 2 == 0) {
                    SetPixel(wgs->wintw_hdc, startx, starty,
                             wgs->colours[261]);
                }
                startx += dx;
                starty += dy;
            }
        }
    }
}

/* Cursor lines need no GPU-to-CPU readback. In Direct2D even a one-cell GetDC
 * can retain a full-frame staging copy. The base cell (including an active
 * block cursor's colors) was already painted by win_draw_text. */
static void nemo_gpu_cursor_fill(WinGuiSeat *wgs, RECT rect, RECT clip,
                                 COLORREF colour)
{
    RECT visible;
    if (IntersectRect(&visible,&rect,&clip)) nemo_gpu_fill_rect(wgs->gpu,visible,colour);
}
static void nemo_gpu_cursor(WinGuiSeat *wgs, RECT box, int cell_width,
                            const wchar_t *text, unsigned long attr)
{
    RECT clip=box;
    box.right=box.left+cell_width;
    int type=wgs->term->cursor_type;
    if ((attr&ATTR_ACTCURS) && (type==CURSOR_BLOCK || wgs->term->big_cursor)) {
        if (*text!=UCSWIDE) return;
        type=CURSOR_VERTICAL_LINE;attr|=ATTR_RIGHTCURS;
    }
    COLORREF colour=wgs->colours[261];
    if ((attr&ATTR_PASCURS) && (type==CURSOR_BLOCK || wgs->term->big_cursor)) {
        RECT edge=box;edge.bottom=edge.top+1;nemo_gpu_cursor_fill(wgs,edge,clip,colour);
        edge=box;edge.top=edge.bottom-1;nemo_gpu_cursor_fill(wgs,edge,clip,colour);
        edge=box;edge.right=edge.left+1;nemo_gpu_cursor_fill(wgs,edge,clip,colour);
        edge=box;edge.left=edge.right-1;nemo_gpu_cursor_fill(wgs,edge,clip,colour);
    } else if ((attr&(ATTR_ACTCURS|ATTR_PASCURS)) && type!=CURSOR_BLOCK) {
        RECT line=box;
        if (type==CURSOR_UNDERLINE) {
            line.top+=wgs->descent;line.bottom=line.top+1;
        } else {
            if (attr&ATTR_RIGHTCURS) line.left=line.right-1;
            line.right=line.left+1;
        }
        if (attr&ATTR_ACTCURS) nemo_gpu_cursor_fill(wgs,line,clip,colour);
        else {
            int length=type==CURSOR_UNDERLINE?line.right-line.left:line.bottom-line.top;
            RECT dot={line.left,line.top,line.left+1,line.top+1};
            for (int i=0;i<length;i+=2) {
                nemo_gpu_cursor_fill(wgs,dot,clip,colour);
                if (type==CURSOR_UNDERLINE) {dot.left+=2;dot.right+=2;}
                else {dot.top+=2;dot.bottom+=2;}
            }
        }
    }
}

/* Cache complete rasterized runs, including combining marks, decoration and
 * fallback fonts. Cache hits do no font work and upload no pixels. */
static void nemo_draw_run(TermWin *tw, int x, int y, wchar_t *text, int len,
                         unsigned long attr, int lattr, truecolour tc, bool cursor)
{
    WinGuiSeat *wgs = container_of(tw, WinGuiSeat, termwin);
    if (!wgs->gpu_drawing) {
        if (cursor) nemo_raster_cursor(tw,x,y,text,len,attr,lattr,tc);
        else nemo_raster_text(tw,x,y,text,len,attr,lattr,tc);
        return;
    }
    int cells=0;
    for (int i=0;i<len;i++) {
        if (i+1<len && IS_HIGH_VARSEL(text[i],text[i+1])) i++;
        else if (IS_LOW_VARSEL(text[i])) continue;
        else {
            cells++;
            if (i+1<len && IS_SURROGATE_PAIR(text[i],text[i+1])) i++;
        }
    }
    if (attr&TATTR_COMBINING) cells=1;
    if (cursor) cells=1;
    int advance=wgs->font_width*(1+((lattr&LATTR_MODE)!=LATTR_NORM));
    RECT box={wgs->offset_width+x*advance,wgs->offset_height+y*wgs->font_height,0,0};
    box.right=min(box.left+cells*advance*((attr&ATTR_WIDE)?2:1),
                  wgs->offset_width+wgs->term->cols*wgs->font_width);
    box.bottom=box.top+wgs->font_height;
    if (box.right<=box.left || box.top<0) return;
    if (cursor) {nemo_gpu_cursor(wgs,box,advance*((attr&ATTR_WIDE)?2:1),text,attr);return;}
    strbuf *key=NULL;
    if (!cursor) {
        key=strbuf_new();
        put_uint32(key,attr);put_uint32(key,lattr);put_uint32(key,tc.decoration);
        /* Rasterized text includes the active block cursor's colours.
         * DECSCUSR changes that rendering without changing ATTR_ACTCURS. */
        put_byte(key,(attr&ATTR_ACTCURS) &&
                 (wgs->term->cursor_type==CURSOR_BLOCK || wgs->term->big_cursor));
        put_uint32(key,tc.fg.enabled);put_byte(key,tc.fg.r);put_byte(key,tc.fg.g);put_byte(key,tc.fg.b);
        put_uint32(key,tc.bg.enabled);put_byte(key,tc.bg.r);put_byte(key,tc.bg.g);put_byte(key,tc.bg.b);
        /* Patterned underlines can depend on absolute x. Ordinary glyphs
         * and solid strike-through do not: share those tiles across columns
         * instead of allocating a GPU bitmap for each repeated cluster. */
        put_uint32(key,(attr&ATTR_UNDER)?box.left:0);
        put_data(key,text,len*sizeof(*text));
        if (nemo_gpu_cached(wgs->gpu,box,ptrlen_from_strbuf(key))) {
            strbuf_free(key);return;
        }
    }
    if (nemo_gpu_begin_run(wgs->gpu,box,cursor)) {
        if (cursor) nemo_raster_cursor(tw,x,y,text,len,attr,lattr,tc);
        else nemo_raster_text(tw,x,y,text,len,attr,lattr,tc);
        nemo_gpu_end_run(wgs->gpu,box,key?ptrlen_from_strbuf(key):make_ptrlen(NULL,0));
    }
    if (key) strbuf_free(key);
}
static void wintw_draw_text(TermWin *tw, int x, int y, wchar_t *text, int len,
                            unsigned long attr, int lattr, truecolour tc)
{
    nemo_draw_run(tw,x,y,text,len,attr,lattr,tc,false);
}
static void wintw_draw_cursor(TermWin *tw, int x, int y, wchar_t *text, int len,
                              unsigned long attr, int lattr, truecolour tc)
{
    nemo_draw_run(tw,x,y,text,len,attr,lattr,tc,true);
}

static void wintw_draw_trust_sigil(TermWin *tw, int x, int y)
{
    WinGuiSeat *wgs = container_of(tw, WinGuiSeat, termwin);

    x *= wgs->font_width;
    y *= wgs->font_height;
    x += wgs->offset_width;
    y += wgs->offset_height;

    RECT box = { x, y, x + wgs->font_width*2, y + wgs->font_height };
    if (wgs->gpu_drawing && !nemo_gpu_begin_run(wgs->gpu, box, true)) return;
    DrawIconEx(wgs->wintw_hdc, x, y, wgs->trust_icon,
               wgs->font_width * 2, wgs->font_height, 0, NULL, DI_NORMAL);
    if (wgs->gpu_drawing) nemo_gpu_end_run(wgs->gpu, box, make_ptrlen(NULL,0));
}

/* This function gets the actual width of a character in the normal font.
 */
static int wintw_char_width(TermWin *tw, int uc)
{
    WinGuiSeat *wgs = container_of(tw, WinGuiSeat, termwin);
    int ibuf = 0;

    /* If the font max is the same as the font ave width then this
     * function is a no-op.
     */
    if (!wgs->font_dualwidth) return 1;

    switch (uc & CSET_MASK) {
      case CSET_ASCII:
        uc = wgs->ucsdata.unitab_line[uc & 0xFF];
        break;
      case CSET_LINEDRW:
        uc = wgs->ucsdata.unitab_xterm[uc & 0xFF];
        break;
      case CSET_SCOACS:
        uc = wgs->ucsdata.unitab_scoacs[uc & 0xFF];
        break;
    }
    if (DIRECT_FONT(uc)) {
        if (wgs->ucsdata.dbcs_screenfont) return 1;

        /* Speedup, I know of no font where ascii is the wrong width */
        if ((uc&~CSET_MASK) >= ' ' && (uc&~CSET_MASK)<= '~')
            return 1;

        if ( (uc & CSET_MASK) == CSET_ACP ) {
            SelectObject(wgs->wintw_hdc, wgs->fonts[FONT_NORMAL]);
        } else if ( (uc & CSET_MASK) == CSET_OEMCP ) {
            another_font(wgs, FONT_OEM);
            if (!wgs->fonts[FONT_OEM]) return 0;

            SelectObject(wgs->wintw_hdc, wgs->fonts[FONT_OEM]);
        } else
            return 0;

        if (GetCharWidth32(wgs->wintw_hdc, uc & ~CSET_MASK,
                           uc & ~CSET_MASK, &ibuf) != 1 &&
            GetCharWidth(wgs->wintw_hdc, uc & ~CSET_MASK,
                         uc & ~CSET_MASK, &ibuf) != 1)
            return 0;
    } else {
        /* Speedup, I know of no font where ascii is the wrong width */
        if (uc >= ' ' && uc <= '~') return 1;

        SelectObject(wgs->wintw_hdc, wgs->fonts[FONT_NORMAL]);
        if (GetCharWidth32W(wgs->wintw_hdc, uc, uc, &ibuf) == 1)
            /* Okay that one worked */ ;
        else if (GetCharWidthW(wgs->wintw_hdc, uc, uc, &ibuf) == 1)
            /* This should work on 9x too, but it's "less accurate" */ ;
        else
            return 0;
    }

    ibuf += wgs->font_width / 2 -1;
    ibuf /= wgs->font_width;

    return ibuf;
}

DECL_WINDOWS_FUNCTION(static, BOOL, FlashWindowEx, (PFLASHWINFO));
DECL_WINDOWS_FUNCTION(static, BOOL, ToUnicodeEx,
                      (UINT, UINT, const BYTE *, LPWSTR, int, UINT, HKL));
DECL_WINDOWS_FUNCTION(static, BOOL, PlaySoundW, (LPCWSTR, HMODULE, DWORD));
DECL_WINDOWS_FUNCTION(static, BOOL, PlaySoundA, (LPCSTR, HMODULE, DWORD));

static void init_winfuncs(void)
{
    HMODULE user32_module = load_system32_dll("user32.dll");
    HMODULE winmm_module = load_system32_dll("winmm.dll");
    HMODULE shcore_module = load_system32_dll("shcore.dll");
    GET_WINDOWS_FUNCTION(user32_module, FlashWindowEx);
    GET_WINDOWS_FUNCTION(user32_module, ToUnicodeEx);
    GET_WINDOWS_FUNCTION(winmm_module, PlaySoundW);
    GET_WINDOWS_FUNCTION(winmm_module, PlaySoundA);
    GET_WINDOWS_FUNCTION_NO_TYPECHECK(user32_module, GetMonitorInfoA);
    GET_WINDOWS_FUNCTION_NO_TYPECHECK(user32_module, MonitorFromPoint);
    GET_WINDOWS_FUNCTION_NO_TYPECHECK(user32_module, MonitorFromWindow);
    GET_WINDOWS_FUNCTION_NO_TYPECHECK(shcore_module, GetDpiForMonitor);
    GET_WINDOWS_FUNCTION_NO_TYPECHECK(user32_module, GetSystemMetricsForDpi);
    GET_WINDOWS_FUNCTION_NO_TYPECHECK(user32_module, AdjustWindowRectExForDpi);
}

/*
 * Translate a WM_(SYS)?KEY(UP|DOWN) message into a string of ASCII
 * codes. Returns number of bytes used, zero to drop the message,
 * -1 to forward the message to Windows, or another negative number
 * to indicate a NUL-terminated "special" string.
 */
static int TranslateKey(WinGuiSeat *wgs, UINT message, WPARAM wParam,
                        LPARAM lParam, unsigned char *output)
{
    WPARAM original_key = wParam;
    bool enhanced = (nemo_keyboard_flags(
        &wgs->term->keyboard[wgs->term->alt_which != 0]) &
        (NEMO_KEY_DISAMBIGUATE | NEMO_KEY_EVENTS | NEMO_KEY_ALL)) != 0 ||
        nemo_win32_input_active(wgs);
    BYTE keystate[256];
    int scan, shift_state;
    bool left_alt = false, key_down;
    int r, i;
    unsigned char *p = output;
    int funky_type = conf_get_int(wgs->conf, CONF_funky_type);
    bool no_applic_k = conf_get_bool(wgs->conf, CONF_no_applic_k);
    bool ctrlaltkeys = conf_get_bool(wgs->conf, CONF_ctrlaltkeys);
    bool nethack_keypad = conf_get_bool(wgs->conf, CONF_nethack_keypad);
    char keypad_key = '\0';

    HKL kbd_layout = GetKeyboardLayout(0);

    r = GetKeyboardState(keystate);
    if (!r)
        memset(keystate, 0, sizeof(keystate));
    else {
#if 0
#define SHOW_TOASCII_RESULT
        {                              /* Tell us all about key events */
            static BYTE oldstate[256];
            static int first = 1;
            static int scan;
            int ch;
            if (first)
                memcpy(oldstate, keystate, sizeof(oldstate));
            first = 0;

            if ((HIWORD(lParam) & (KF_UP | KF_REPEAT)) == KF_REPEAT) {
                debug("+");
            } else if ((HIWORD(lParam) & KF_UP)
                       && scan == (HIWORD(lParam) & 0xFF)) {
                debug(". U");
            } else {
                debug(".\n");
                if (wParam >= VK_F1 && wParam <= VK_F20)
                    debug("K_F%d", wParam + 1 - VK_F1);
                else
                    switch (wParam) {
                      case VK_SHIFT:
                        debug("SHIFT");
                        break;
                      case VK_CONTROL:
                        debug("CTRL");
                        break;
                      case VK_MENU:
                        debug("ALT");
                        break;
                      default:
                        debug("VK_%02x", wParam);
                    }
                if (message == WM_SYSKEYDOWN || message == WM_SYSKEYUP)
                    debug("*");
                debug(", S%02x", scan = (HIWORD(lParam) & 0xFF));

                ch = MapVirtualKeyEx(wParam, 2, kbd_layout);
                if (ch >= ' ' && ch <= '~')
                    debug(", '%c'", ch);
                else if (ch)
                    debug(", $%02x", ch);

                if ((keystate[VK_SHIFT] & 0x80) != 0)
                    debug(", S");
                if ((keystate[VK_CONTROL] & 0x80) != 0)
                    debug(", C");
                if ((HIWORD(lParam) & KF_EXTENDED))
                    debug(", E");
                if ((HIWORD(lParam) & KF_UP))
                    debug(", U");
            }

            if ((HIWORD(lParam) & (KF_UP | KF_REPEAT)) == KF_REPEAT);
            else if ((HIWORD(lParam) & KF_UP))
                oldstate[wParam & 0xFF] ^= 0x80;
            else
                oldstate[wParam & 0xFF] ^= 0x81;

            for (ch = 0; ch < 256; ch++)
                if (oldstate[ch] != keystate[ch])
                    debug(", M%02x=%02x", ch, keystate[ch]);

            memcpy(oldstate, keystate, sizeof(oldstate));
        }
#endif

        if (wParam == VK_MENU && (HIWORD(lParam) & KF_EXTENDED)) {
            keystate[VK_RMENU] = keystate[VK_MENU];
        }


        /* Nastiness with NUMLock - Shift-NUMLock is left alone though */
        if (!enhanced && (funky_type == FUNKY_VT400 ||
             (funky_type <= FUNKY_LINUX && wgs->term->app_keypad_keys &&
              !no_applic_k))
            && wParam == VK_NUMLOCK && !(keystate[VK_SHIFT] & 0x80)) {

            wParam = VK_EXECUTE;

            /* UnToggle NUMLock */
            if ((HIWORD(lParam) & (KF_UP | KF_REPEAT)) == 0)
                keystate[VK_NUMLOCK] ^= 1;
        }

        /* And write back the 'adjusted' state */
        SetKeyboardState(keystate);
    }

    nemo_keyboard_prepare(wgs, message, original_key, lParam, keystate);
    BYTE protocol_keystate[256];
    memcpy(protocol_keystate, keystate, sizeof(protocol_keystate));

    /* Disable Auto repeat if required */
    if (wgs->term->repeat_off &&
        (HIWORD(lParam) & (KF_UP | KF_REPEAT)) == KF_REPEAT)
        return 0;

    if ((HIWORD(lParam) & KF_ALTDOWN) && (keystate[VK_RMENU] & 0x80) == 0)
        left_alt = true;

    key_down = ((HIWORD(lParam) & KF_UP) == 0);
    if (wgs->tabbed && !key_down && original_key<256 && tab_host.consumed_keys[original_key]) {
        tab_host.consumed_keys[original_key]=0;
        return 0;
    }

    /* User bindings precede built-in scrolling and application key protocols.
     * AltGr and compose input retain their text-entry path. Modifier state is
     * read before the legacy Ctrl+Alt/AltGr conversion below. */
    if (key_down && !(keystate[VK_RMENU] & 0x80) && !wgs->compose_state) {
        unsigned modifiers = ((keystate[VK_SHIFT] & 0x80) ? NEMO_BIND_SHIFT : 0) |
            ((keystate[VK_CONTROL] & 0x80) ? NEMO_BIND_CTRL : 0) |
            (left_alt ? NEMO_BIND_ALT : 0);
        if (nemo_host_binding(wgs,original_key,modifiers)) return 0;
        int action = nemo_binding_matches(conf_get_int(wgs->conf, CONF_nemo_copy_binding), original_key, modifiers) ? 1 :
            nemo_binding_matches(conf_get_int(wgs->conf, CONF_nemo_paste_binding), original_key, modifiers) ? 2 :
            nemo_binding_matches(conf_get_int(wgs->conf, CONF_nemo_copy_paste_binding), original_key, modifiers) ? 3 :
            nemo_binding_matches(conf_get_int(wgs->conf, CONF_nemo_previous_prompt_binding), original_key, modifiers) ? 4 :
            nemo_binding_matches(conf_get_int(wgs->conf, CONF_nemo_next_prompt_binding), original_key, modifiers) ? 5 :
            nemo_binding_matches(conf_get_int(wgs->conf, CONF_nemo_select_command_binding), original_key, modifiers) ? 6 :
            nemo_binding_matches(conf_get_int(wgs->conf, CONF_nemo_select_output_binding), original_key, modifiers) ? 7 : 0;
        if (action >= 4) {
            if (action <= 5) term_shell_mark_navigate(wgs->term, action == 4 ? -1 : 1);
            else term_shell_mark_select(wgs->term, action == 7);
            return 0;
        }
        if (action == 3) {
            term_request_copy(wgs->term, clips_system, lenof(clips_system));
            term_request_paste(wgs->term, CLIP_LOCAL);
            return 0;
        }
        if (action) {
            int clipboard = conf_get_int(wgs->conf, CONF_ctrlshiftcv);
            if (action == 1 && clipboard == CLIPUI_EXPLICIT)
                term_request_copy(wgs->term, clips_system, lenof(clips_system));
            if (action == 2 && clipboard == CLIPUI_EXPLICIT)
                term_request_paste(wgs->term, CLIP_SYSTEM);
            if (action == 2 && clipboard == CLIPUI_IMPLICIT)
                term_request_paste(wgs->term, CLIP_LOCAL);
            return 0;
        }
    }

    /* Make sure Ctrl-ALT is not the same as AltGr for ToAscii unless told. */
    if (!enhanced && left_alt && (keystate[VK_CONTROL] & 0x80)) {
        if (ctrlaltkeys)
            keystate[VK_MENU] = 0;
        else {
            keystate[VK_RMENU] = 0x80;
            left_alt = false;
        }
    }

    scan = (HIWORD(lParam) & (KF_UP | KF_EXTENDED | 0xFF));
    shift_state = ((keystate[VK_SHIFT] & 0x80) != 0)
        + ((keystate[VK_CONTROL] & 0x80) != 0) * 2;

    /* Note if AltGr was pressed and if it was used as a compose key */
    if (!enhanced) {
        if (!wgs->compose_state) {
            wgs->compose_keycode = 0x100;
            if (conf_get_bool(wgs->conf, CONF_compose_key)) {
                if (wParam == VK_MENU && (HIWORD(lParam) & KF_EXTENDED))
                    wgs->compose_keycode = wParam;
            }
            if (wParam == VK_APPS)
                wgs->compose_keycode = wParam;
        }

        if (wParam == wgs->compose_keycode) {
            if (wgs->compose_state == 0 &&
                (HIWORD(lParam) & (KF_UP | KF_REPEAT)) == 0)
                wgs->compose_state = 1;
            else if (wgs->compose_state == 1 && (HIWORD(lParam) & KF_UP))
                wgs->compose_state = 2;
            else
                wgs->compose_state = 0;
        } else if (wgs->compose_state == 1 && wParam != VK_CONTROL)
            wgs->compose_state = 0;

        if (wgs->compose_state > 1 && left_alt)
            wgs->compose_state = 0;
    }

    /* Sanitize the number pad if not using a PC NumPad */
    if (!enhanced && (left_alt || (wgs->term->app_keypad_keys && !no_applic_k
                     && funky_type != FUNKY_XTERM) ||
        funky_type == FUNKY_VT400 || nethack_keypad || wgs->compose_state)) {
        if ((HIWORD(lParam) & KF_EXTENDED) == 0) {
            int nParam = 0;
            switch (wParam) {
              case VK_INSERT:
                nParam = VK_NUMPAD0;
                break;
              case VK_END:
                nParam = VK_NUMPAD1;
                break;
              case VK_DOWN:
                nParam = VK_NUMPAD2;
                break;
              case VK_NEXT:
                nParam = VK_NUMPAD3;
                break;
              case VK_LEFT:
                nParam = VK_NUMPAD4;
                break;
              case VK_CLEAR:
                nParam = VK_NUMPAD5;
                break;
              case VK_RIGHT:
                nParam = VK_NUMPAD6;
                break;
              case VK_HOME:
                nParam = VK_NUMPAD7;
                break;
              case VK_UP:
                nParam = VK_NUMPAD8;
                break;
              case VK_PRIOR:
                nParam = VK_NUMPAD9;
                break;
              case VK_DELETE:
                nParam = VK_DECIMAL;
                break;
            }
            if (nParam) {
                if (keystate[VK_NUMLOCK] & 1)
                    shift_state |= 1;
                wParam = nParam;
            }
        }
    }

    /* If a key is pressed and AltGr is not active */
    if (key_down && (keystate[VK_RMENU] & 0x80) == 0 && !wgs->compose_state) {
        /* Okay, prepare for most alts then ... */
        if (left_alt)
            *p++ = '\033';

        /* Lets see if it's a pattern we know all about ... */
        if (wParam == VK_PRIOR && shift_state == 1) {
            SendMessage(wgs->term_hwnd, WM_VSCROLL, SB_PAGEUP, 0);
            return 0;
        }
        if (wParam == VK_PRIOR && shift_state == 3) { /* ctrl-shift-pageup */
            SendMessage(wgs->term_hwnd, WM_VSCROLL, SB_TOP, 0);
            return 0;
        }
        if (wParam == VK_NEXT && shift_state == 3) { /* ctrl-shift-pagedown */
            SendMessage(wgs->term_hwnd, WM_VSCROLL, SB_BOTTOM, 0);
            return 0;
        }

        if (wParam == VK_PRIOR && shift_state == 2 && funky_type != FUNKY_XTERM_216) {
            SendMessage(wgs->term_hwnd, WM_VSCROLL, SB_LINEUP, 0);
            return 0;
        }
        if (wParam == VK_NEXT && shift_state == 1) {
            SendMessage(wgs->term_hwnd, WM_VSCROLL, SB_PAGEDOWN, 0);
            return 0;
        }
        if (wParam == VK_NEXT && shift_state == 2 && funky_type != FUNKY_XTERM_216) {
            SendMessage(wgs->term_hwnd, WM_VSCROLL, SB_LINEDOWN, 0);
            return 0;
        }
        if ((wParam == VK_PRIOR || wParam == VK_NEXT) && shift_state == 3) {
            term_scroll_to_selection(wgs->term, (wParam == VK_PRIOR ? 0 : 1));
            return 0;
        }
        if (wParam == VK_INSERT && shift_state == 2) {
            switch (conf_get_int(wgs->conf, CONF_ctrlshiftins)) {
              case CLIPUI_IMPLICIT:
                break;          /* no need to re-copy to CLIP_LOCAL */
              case CLIPUI_EXPLICIT:
                term_request_copy(wgs->term, clips_system,
                                  lenof(clips_system));
                break;
              default:
                break;
            }
            return 0;
        }
        if (wParam == VK_INSERT && shift_state == 1) {
            switch (conf_get_int(wgs->conf, CONF_ctrlshiftins)) {
              case CLIPUI_IMPLICIT:
                term_request_paste(wgs->term, CLIP_LOCAL);
                break;
              case CLIPUI_EXPLICIT:
                term_request_paste(wgs->term, CLIP_SYSTEM);
                break;
              default:
                break;
            }
            return 0;
        }
        if (left_alt && wParam == VK_F4 &&
            conf_get_bool(wgs->conf, CONF_alt_f4)) {
            return -1;
        }
        if (left_alt && wParam == VK_SPACE &&
            conf_get_bool(wgs->conf, CONF_alt_space)) {
            SendMessage(wgs->term_hwnd, WM_SYSCOMMAND, SC_KEYMENU, 0);
            return -1;
        }
        if (left_alt && wParam == VK_RETURN &&
            conf_get_bool(wgs->conf, CONF_fullscreenonaltenter) &&
            (conf_get_int(wgs->conf, CONF_resize_action) != RESIZE_DISABLED)) {
            if ((HIWORD(lParam) & (KF_UP | KF_REPEAT)) != KF_REPEAT)
                flip_full_screen(wgs);
            return -1;
        }
        /* Control-Numlock for app-keypad mode switch */
        if (!enhanced && wParam == VK_PAUSE && shift_state == 2) {
            wgs->term->app_keypad_keys = !wgs->term->app_keypad_keys;
            return 0;
        }
    }

    if (nemo_keyboard_input(wgs, message, original_key, lParam, protocol_keystate, kbd_layout)) {
        show_mouseptr(wgs, false);
        return 0;
    }

    if (key_down && (keystate[VK_RMENU] & 0x80) == 0 && !wgs->compose_state) {
        if (wParam == VK_BACK && shift_state == 0) {    /* Backspace */
            *p++ = (conf_get_bool(wgs->conf, CONF_bksp_is_delete) ?
                    0x7F : 0x08);
            *p++ = 0;
            return -2;
        }
        if (wParam == VK_BACK && shift_state == 1) {    /* Shift Backspace */
            /* We do the opposite of what is configured */
            *p++ = (conf_get_bool(wgs->conf, CONF_bksp_is_delete) ?
                    0x08 : 0x7F);
            *p++ = 0;
            return -2;
        }
        if (wParam == VK_TAB && shift_state == 1) {     /* Shift tab */
            *p++ = 0x1B;
            *p++ = '[';
            *p++ = 'Z';
            return p - output;
        }
        if (wParam == VK_SPACE && shift_state == 2) {   /* Ctrl-Space */
            *p++ = 0;
            return p - output;
        }
        if (wParam == VK_SPACE && shift_state == 3) {   /* Ctrl-Shift-Space */
            *p++ = 160;
            return p - output;
        }
        if (wParam == VK_CANCEL && shift_state == 2) {  /* Ctrl-Break */
            if (wgs->backend)
                backend_special(wgs->backend, SS_BRK, 0);
            return 0;
        }
        if (wParam == VK_PAUSE) {      /* Break/Pause */
            *p++ = 26;
            *p++ = 0;
            return -2;
        }
        /* Control-2 to Control-8 are special */
        if (shift_state == 2 && wParam >= '2' && wParam <= '8') {
            *p++ = "\000\033\034\035\036\037\177"[wParam - '2'];
            return p - output;
        }
        if (shift_state == 2 && (wParam == 0xBD || wParam == 0xBF)) {
            *p++ = 0x1F;
            return p - output;
        }
        if (shift_state == 2 && (wParam == 0xDF || wParam == 0xDC)) {
            *p++ = 0x1C;
            return p - output;
        }
        if (shift_state == 3 && wParam == 0xDE) {
            *p++ = 0x1E;               /* Ctrl-~ == Ctrl-^ in xterm at least */
            return p - output;
        }

        switch (wParam) {
            bool consumed_alt;

          case VK_NUMPAD0: keypad_key = '0'; goto numeric_keypad;
          case VK_NUMPAD1: keypad_key = '1'; goto numeric_keypad;
          case VK_NUMPAD2: keypad_key = '2'; goto numeric_keypad;
          case VK_NUMPAD3: keypad_key = '3'; goto numeric_keypad;
          case VK_NUMPAD4: keypad_key = '4'; goto numeric_keypad;
          case VK_NUMPAD5: keypad_key = '5'; goto numeric_keypad;
          case VK_NUMPAD6: keypad_key = '6'; goto numeric_keypad;
          case VK_NUMPAD7: keypad_key = '7'; goto numeric_keypad;
          case VK_NUMPAD8: keypad_key = '8'; goto numeric_keypad;
          case VK_NUMPAD9: keypad_key = '9'; goto numeric_keypad;
          case VK_DECIMAL: keypad_key = '.'; goto numeric_keypad;
          case VK_ADD: keypad_key = '+'; goto numeric_keypad;
          case VK_SUBTRACT: keypad_key = '-'; goto numeric_keypad;
          case VK_MULTIPLY: keypad_key = '*'; goto numeric_keypad;
          case VK_DIVIDE: keypad_key = '/'; goto numeric_keypad;
          case VK_SEPARATOR: keypad_key = ','; goto numeric_keypad;
          case VK_EXECUTE: keypad_key = 'G'; goto numeric_keypad;
            /* also the case for VK_RETURN below can sometimes come here */
          numeric_keypad:
            /* Left Alt overrides all numeric keypad usage to act as
             * numeric character code input */
            if (left_alt) {
                if (keypad_key >= '0' && keypad_key <= '9')
                    wgs->alt_numberpad_accumulator =
                        wgs->alt_numberpad_accumulator * 10 + keypad_key - '0';
                else
                    wgs->alt_numberpad_accumulator = 0;
                break;
            }

            {
                int nchars = format_numeric_keypad_key(
                    (char *)p, wgs->term, keypad_key,
                    shift_state & 1, shift_state & 2);
                if (!nchars) {
                    /*
                     * If we didn't get an escape sequence out of the
                     * numeric keypad key, then that must be because
                     * we're in Num Lock mode without application
                     * keypad enabled. In that situation we leave this
                     * keypress to the ToUnicode/ToAsciiEx handler
                     * below, which will translate it according to the
                     * appropriate keypad layout (e.g. so that what a
                     * Brit thinks of as keypad '.' can become ',' in
                     * the German layout).
                     *
                     * An exception is the keypad Return key: if we
                     * didn't get an escape sequence for that, we
                     * treat it like ordinary Return, taking into
                     * account Telnet special new line codes and
                     * config options.
                     */
                    if (keypad_key == '\r')
                        goto ordinary_return_key;
                    break;
                }

                p += nchars;
                return p - output;
            }

            int fkey_number;
          case VK_F1: fkey_number = 1; goto numbered_function_key;
          case VK_F2: fkey_number = 2; goto numbered_function_key;
          case VK_F3: fkey_number = 3; goto numbered_function_key;
          case VK_F4: fkey_number = 4; goto numbered_function_key;
          case VK_F5: fkey_number = 5; goto numbered_function_key;
          case VK_F6: fkey_number = 6; goto numbered_function_key;
          case VK_F7: fkey_number = 7; goto numbered_function_key;
          case VK_F8: fkey_number = 8; goto numbered_function_key;
          case VK_F9: fkey_number = 9; goto numbered_function_key;
          case VK_F10: fkey_number = 10; goto numbered_function_key;
          case VK_F11: fkey_number = 11; goto numbered_function_key;
          case VK_F12: fkey_number = 12; goto numbered_function_key;
          case VK_F13: fkey_number = 13; goto numbered_function_key;
          case VK_F14: fkey_number = 14; goto numbered_function_key;
          case VK_F15: fkey_number = 15; goto numbered_function_key;
          case VK_F16: fkey_number = 16; goto numbered_function_key;
          case VK_F17: fkey_number = 17; goto numbered_function_key;
          case VK_F18: fkey_number = 18; goto numbered_function_key;
          case VK_F19: fkey_number = 19; goto numbered_function_key;
          case VK_F20: fkey_number = 20; goto numbered_function_key;
          case VK_F21: fkey_number = 21; goto numbered_function_key;
          case VK_F22: fkey_number = 22; goto numbered_function_key;
          case VK_F23: fkey_number = 23; goto numbered_function_key;
          case VK_F24: fkey_number = 24; goto numbered_function_key;
          numbered_function_key:
            consumed_alt = false;
            p += format_function_key((char *)p, wgs->term, fkey_number,
                                     shift_state & 1, shift_state & 2,
                                     left_alt, &consumed_alt);
            if (consumed_alt) {
                /* supersedes the usual prefixing of Esc */
                p -= 1;
                memmove(output, output + 1, p - output);
            }
            return p - output;

            SmallKeypadKey sk_key;
          case VK_HOME: sk_key = SKK_HOME; goto small_keypad_key;
          case VK_END: sk_key = SKK_END; goto small_keypad_key;
          case VK_INSERT: sk_key = SKK_INSERT; goto small_keypad_key;
          case VK_DELETE: sk_key = SKK_DELETE; goto small_keypad_key;
          case VK_PRIOR: sk_key = SKK_PGUP; goto small_keypad_key;
          case VK_NEXT: sk_key = SKK_PGDN; goto small_keypad_key;
          case VK_SELECT: sk_key = SKK_SELECT; goto small_keypad_key;
          case VK_HELP: sk_key = SKK_HELP; goto small_keypad_key;
          small_keypad_key:
            /* Retain the old local behaviour in legacy keyboard modes. */
            if ((shift_state & 2) && funky_type != FUNKY_XTERM_216)
                break;

            consumed_alt = false;
            p += format_small_keypad_key((char *)p, wgs->term, sk_key,
                                         shift_state & 1, shift_state & 2,
                                         left_alt, &consumed_alt);
            if (consumed_alt) {
                /* supersedes the usual prefixing of Esc */
                p -= 1;
                memmove(output, output + 1, p - output);
            }
            return p - output;

            char xkey;
          case VK_UP: xkey = 'A'; goto arrow_key;
          case VK_DOWN: xkey = 'B'; goto arrow_key;
          case VK_RIGHT: xkey = 'C'; goto arrow_key;
          case VK_LEFT: xkey = 'D'; goto arrow_key;
          case VK_CLEAR: xkey = 'G'; goto arrow_key; /* close enough */
          arrow_key:
            consumed_alt = false;
            p += format_arrow_key((char *)p, wgs->term, xkey, shift_state & 1,
                                  shift_state & 2, left_alt, &consumed_alt);
            if (consumed_alt) {
                /* supersedes the usual prefixing of Esc */
                p -= 1;
                memmove(output, output + 1, p - output);
            }
            return p - output;

          case VK_RETURN:
            if (HIWORD(lParam) & KF_EXTENDED) {
                keypad_key = '\r';
                goto numeric_keypad;
            }
          ordinary_return_key:
            if (shift_state == 0 && wgs->term->cr_lf_return) {
                *p++ = '\r';
                *p++ = '\n';
                return p - output;
            } else {
                *p++ = 0x0D;
                *p++ = 0;
                return -2;
            }
        }
    }

    /* Okay we've done everything interesting; let windows deal with
     * the boring stuff */
    {
        bool capsOn = false;

        /* helg: clear CAPS LOCK state if caps lock switches to cyrillic */
        if (keystate[VK_CAPITAL] != 0 &&
            conf_get_bool(wgs->conf, CONF_xlat_capslockcyr)) {
            capsOn = !left_alt;
            keystate[VK_CAPITAL] = 0;
        }

        wchar_t keys_unicode[3];

        /* XXX how do we know what the max size of the keys array should
         * be is? There's indication on MS' website of an Inquire/InquireEx
         * functioning returning a KBINFO structure which tells us. */
        if (osPlatformId == VER_PLATFORM_WIN32_NT && p_ToUnicodeEx) {
            r = p_ToUnicodeEx(wParam, scan, keystate, keys_unicode,
                              lenof(keys_unicode), 0, kbd_layout);
        } else {
            /* XXX 'keys' parameter is declared in MSDN documentation as
             * 'LPWORD lpChar'.
             * The experience of a French user indicates that on
             * Win98, WORD[] should be passed in, but on Win2K, it should
             * be BYTE[]. German WinXP and my Win2K with "US International"
             * driver corroborate this.
             * Experimentally I've conditionalised the behaviour on the
             * Win9x/NT split, but I suspect it's worse than that.
             * See wishlist item `win-dead-keys' for more horrible detail
             * and speculations. */
            int i;
            WORD keys[3];
            BYTE keysb[3];
            r = ToAsciiEx(wParam, scan, keystate, keys, 0, kbd_layout);
            if (r > 0) {
                for (i = 0; i < r; i++) {
                    keysb[i] = (BYTE)keys[i];
                }
                MultiByteToWideChar(CP_ACP, 0, (LPCSTR)keysb, r,
                                    keys_unicode, lenof(keys_unicode));
            }
        }
#ifdef SHOW_TOASCII_RESULT
        if (r == 1 && !key_down) {
            if (wgs->alt_numberpad_accumulator) {
                if (in_utf(term) || ucsdata.dbcs_screenfont)
                    debug(", (U+%04x)", wgs->alt_numberpad_accumulator);
                else
                    debug(", LCH(%d)", wgs->alt_numberpad_accumulator);
            } else {
                debug(", ACH(%d)", keys_unicode[0]);
            }
        } else if (r > 0) {
            int r1;
            debug(", ASC(");
            for (r1 = 0; r1 < r; r1++) {
                debug("%s%d", r1 ? "," : "", keys_unicode[r1]);
            }
            debug(")");
        }
#endif
        if (r > 0) {
            WCHAR keybuf;

            p = output;
            for (i = 0; i < r; i++) {
                wchar_t wch = keys_unicode[i];

                if (wgs->compose_state == 2 && wch >= ' ' && wch < 0x80) {
                    wgs->compose_char = wch;
                    wgs->compose_state++;
                    continue;
                }
                if (wgs->compose_state == 3 && wch >= ' ' && wch < 0x80) {
                    int nc;
                    wgs->compose_state = 0;

                    if ((nc = check_compose(wgs->compose_char, wch)) == -1) {
                        MessageBeep(MB_ICONHAND);
                        return 0;
                    }
                    keybuf = nc;
                    term_keyinputw(wgs->term, &keybuf, 1);
                    continue;
                }

                wgs->compose_state = 0;

                if (!key_down) {
                    if (wgs->alt_numberpad_accumulator) {
                        if (in_utf(wgs->term) ||
                            wgs->ucsdata.dbcs_screenfont) {
                            keybuf = wgs->alt_numberpad_accumulator;
                            term_keyinputw(wgs->term, &keybuf, 1);
                        } else {
                            char ch = (char) wgs->alt_numberpad_accumulator;
                            /*
                             * We need not bother about stdin
                             * backlogs here, because in GUI PuTTY
                             * we can't do anything about it
                             * anyway; there's no means of asking
                             * Windows to hold off on KEYDOWN
                             * messages. We _have_ to buffer
                             * everything we're sent.
                             */
                            term_keyinput(wgs->term, -1, &ch, 1);
                        }
                        wgs->alt_numberpad_accumulator = 0;
                    } else {
                        term_keyinputw(wgs->term, &wch, 1);
                    }
                } else {
                    if (capsOn && wch < 0x80) {
                        WCHAR cbuf[2];
                        cbuf[0] = 27;
                        cbuf[1] = xlat_uskbd2cyrllic(wch);
                        term_keyinputw(
                            wgs->term, cbuf+!left_alt, 1+!!left_alt);
                    } else {
                        WCHAR cbuf[2];
                        cbuf[0] = '\033';
                        cbuf[1] = wch;
                        term_keyinputw(
                            wgs->term, cbuf +!left_alt, 1+!!left_alt);
                    }
                }
                show_mouseptr(wgs, false);
            }

            return p - output;
        }
    }

    /*
     * ALT alone may or may not want to bring up the System menu.
     * If it's not meant to, we return 0 on presses or releases of
     * ALT, to show that we've swallowed the keystroke. Otherwise
     * we return -1, which means Windows will give the keystroke
     * its default handling (i.e. bring up the System menu).
     */
    if (wParam == VK_MENU && !conf_get_bool(wgs->conf, CONF_alt_only))
        return 0;

    return -1;
}

static void wintw_set_title(TermWin *tw, const char *title, int codepage)
{
    WinGuiSeat *wgs = container_of(tw, WinGuiSeat, termwin);
    wchar_t *new_window_name = dup_mb_to_wc(codepage, title);
    if (!wcscmp(new_window_name, wgs->window_name)) {
        sfree(new_window_name);
        return;
    }
    sfree(wgs->window_name);
    wgs->window_name = new_window_name;
    nemo_host_title(wgs);
    if (conf_get_bool(wgs->conf, CONF_win_name_always) ||
        !IsIconic(wgs_window(wgs)))
        sw_SetWindowText(wgs->term_hwnd, wgs->window_name);
}

static void wintw_set_icon_title(TermWin *tw, const char *title, int codepage)
{
    WinGuiSeat *wgs = container_of(tw, WinGuiSeat, termwin);
    wchar_t *new_icon_name = dup_mb_to_wc(codepage, title);
    if (!wcscmp(new_icon_name, wgs->icon_name)) {
        sfree(new_icon_name);
        return;
    }
    sfree(wgs->icon_name);
    wgs->icon_name = new_icon_name;
    if (!conf_get_bool(wgs->conf, CONF_win_name_always) &&
        IsIconic(wgs_window(wgs)))
        sw_SetWindowText(wgs->term_hwnd, wgs->icon_name);
}

static void wintw_set_scrollbar(TermWin *tw, int total, int start, int page)
{
    WinGuiSeat *wgs = container_of(tw, WinGuiSeat, termwin);
    SCROLLINFO si;

    if (!conf_get_bool(wgs->conf, is_full_screen(wgs) ?
                       CONF_scrollbar_in_fullscreen : CONF_scrollbar))
        return;

    si.cbSize = sizeof(si);
    si.fMask = SIF_ALL | SIF_DISABLENOSCROLL;
    si.nMin = 0;
    si.nMax = total - 1;
    si.nPage = page;
    si.nPos = start;
    if (wgs->term_hwnd)
        SetScrollInfo(wgs->term_hwnd, SB_VERT, &si, true);
}

/* Snapshot only the presentation at BEGIN, in small compressed bands. No
 * retained full-window raw bitmap and no live terminal reads during repaint. */
static bool nemo_render_snapshot_band(HDC dc, int top, int height, void *ctx)
{
    WinGuiSeat *wgs = ctx;
    RECT rect;
    if (!GetClientRect(wgs->term_hwnd, &rect)) return false;
    rect.top = top; rect.bottom = top + height;
    HBRUSH brush = CreateSolidBrush(wgs->colours[ATTR_DEFBG >> ATTR_BGSHIFT]);
    if (!brush) return false;
    bool ok = FillRect(dc, &rect, brush) != 0;
    DeleteObject(brush);
    if (!ok) return false;
    if (wgs->pal) { SelectPalette(dc, wgs->pal, false); RealizePalette(dc); }
    assert(!wgs->wintw_hdc);
    wgs->wintw_hdc = dc;
    term_paint(wgs->term, 0, (top-wgs->offset_height)/wgs->font_height-1,
               wgs->term->cols-1,
               (top+height-wgs->offset_height)/wgs->font_height+1, true);
    nemo_paint_images(wgs);
    wgs->wintw_hdc = NULL;
    return true;
}

static bool wintw_set_synchronized_update(TermWin *tw, bool enabled)
{
    WinGuiSeat *wgs = container_of(tw, WinGuiSeat, termwin);
    /* The retained GPU frame is already an immutable presentation while
     * synchronized output suppresses the terminal's paint callbacks. */
    if (enabled && wgs->gpu) return true;
    if (!enabled) {
        nemo_snapshot_free(wgs->sync_snapshot);
        wgs->sync_snapshot = NULL;
        if (wgs->tabbed && wgs_active(wgs) && !wgs->closing && !wgs->gpu && tab_host.gpu) {
            wgs->gpu=tab_host.gpu;term_invalidate(wgs->term);
            SetWindowLongPtr(wgs->term_hwnd,GWL_STYLE,
                GetWindowLongPtr(wgs->term_hwnd,GWL_STYLE)|WS_CLIPCHILDREN);
            SetPropW(wgs->term_hwnd,L"NemotermRenderer",(HANDLE)(UINT_PTR)(tab_host.gpu_kind+1));
        }
        if (wgs->term_hwnd) InvalidateRect(wgs->term_hwnd, NULL, false);
        return true;
    }
    RECT rect;
    if (!wgs->term_hwnd || !GetClientRect(wgs->term_hwnd, &rect) ||
        rect.right <= 0 || rect.bottom <= 0 ||
        wgs->term->rows <= 0 || wgs->term->cols <= 0)
        return false;
    NemoSnapshotError error;
    wgs->sync_snapshot = nemo_snapshot_create(
        rect.right, rect.bottom, 8U*1024U*1024U,
        nemo_render_snapshot_band, wgs, &error);
    /* Capturing changed the terminal's display cache but not window pixels. */
    term_invalidate(wgs->term);
    if (!wgs->sync_snapshot) {
        if (!wgs->sync_capture_failed)
            logeventf(wgs->logctx, "Synchronized update not started: %s (%lu)",
                      error.stage, (unsigned long)error.win32_error);
        wgs->sync_capture_failed = true;
        return false;
    }
    wgs->sync_capture_failed = false;
    return true;
}

static void nemo_renderer_configure(WinGuiSeat *wgs)
{
    if (wgs->tabbed) {nemo_host_renderer(wgs);return;}
    nemo_gpu_free(wgs->gpu);wgs->gpu=NULL;wgs->gpu_drawing=false;
    int mode=conf_get_int(wgs->conf,CONF_nemo_renderer);
    if ((mode==1 || mode==2) && !wgs->gpu_failed) {
        wgs->gpu=nemo_gpu_create(wgs->term_hwnd,mode);
        if (wgs->gpu) logeventf(wgs->logctx,"GPU renderer: %s",nemo_gpu_device(wgs->gpu));
    }
    if ((mode==1 || mode==2) && !wgs->gpu)
        logevent(wgs->logctx,"Selected GPU renderer unavailable; using GDI renderer");
    if (!mode) wgs->gpu_failed=false;
    LONG_PTR style=GetWindowLongPtr(wgs->term_hwnd,GWL_STYLE);
    SetWindowLongPtr(wgs->term_hwnd,GWL_STYLE,
                     wgs->gpu ? style|WS_CLIPCHILDREN : style&~WS_CLIPCHILDREN);
    SetPropW(wgs->term_hwnd,L"NemotermRenderer",(HANDLE)(UINT_PTR)(wgs->gpu?mode+1:1));
    term_invalidate(wgs->term);
    InvalidateRect(wgs->term_hwnd,NULL,false);
}
static bool nemo_renderer_begin(WinGuiSeat *wgs)
{
    int result=nemo_gpu_frame(wgs->gpu,wgs->colours[ATTR_DEFBG>>ATTR_BGSHIFT]);
    if (!result) {
        wgs->gpu_failed=true;nemo_renderer_configure(wgs);return false;
    }
    if (result==2) term_invalidate(wgs->term);
    wgs->wintw_hdc=nemo_gpu_dc(wgs->gpu);wgs->gpu_drawing=true;
    return true;
}
static void nemo_renderer_finish(WinGuiSeat *wgs)
{
    nemo_paint_images(wgs);
    RECT text={wgs->offset_width,wgs->offset_height,
        wgs->offset_width+wgs->font_width*wgs->term->cols,
        wgs->offset_height+wgs->font_height*wgs->term->rows};
    nemo_gpu_borders(wgs->gpu,text,wgs->colours[ATTR_DEFBG>>ATTR_BGSHIFT]);
    bool ok=nemo_gpu_present(wgs->gpu);
    wgs->wintw_hdc=NULL;wgs->gpu_drawing=false;
    if (!ok) { wgs->gpu_failed=true;nemo_renderer_configure(wgs); }
}

static bool wintw_setup_draw_ctx(TermWin *tw)
{
    WinGuiSeat *wgs = container_of(tw, WinGuiSeat, termwin);
    assert(!wgs->wintw_hdc);
    if (!wgs_active(wgs) || IsIconic(wgs_window(wgs))) return false;
    if (wgs->gpu && nemo_renderer_begin(wgs)) return true;
    wgs->wintw_hdc = make_hdc(wgs);
    return wgs->wintw_hdc != NULL;
}

static void wintw_free_draw_ctx(TermWin *tw)
{
    WinGuiSeat *wgs = container_of(tw, WinGuiSeat, termwin);
    assert(wgs->wintw_hdc);
    if (wgs->gpu_drawing) {
        nemo_renderer_finish(wgs);
        nemo_link_refresh(wgs);
        return;
    }
    nemo_paint_images(wgs);
    free_hdc(wgs, wgs->wintw_hdc);
    wgs->wintw_hdc = NULL;
    nemo_link_refresh(wgs);
}

/* Compose Sixel over the character grid without a full-window backbuffer.
 * The only temporary pixel storage is one bounded scanline. Transparent
 * spans (including cells erased by subsequent text) leave the grid visible. */
static void nemo_paint_images(WinGuiSeat *wgs)
{
    Terminal *term = wgs->term;
    if (!term || !term->images || !wgs->wintw_hdc)
        return;
    uint32_t row[NEMO_SIXEL_MAX_DIMENSION];
    HDC dc = wgs->wintw_hdc;
    int saved = wgs->gpu_drawing ? 0 : SaveDC(dc);
    if (!saved && !wgs->gpu_drawing)
        return;
    RECT paint_clip;
    int clip_kind;
    if (wgs->gpu_drawing) {
        GetClientRect(wgs->term_hwnd, &paint_clip);
        paint_clip.left = wgs->offset_width;
        paint_clip.top = wgs->offset_height;
        paint_clip.right = min(paint_clip.right, wgs->offset_width + term->cols*wgs->font_width);
        paint_clip.bottom = min(paint_clip.bottom, wgs->offset_height + term->rows*wgs->font_height);
        clip_kind = SIMPLEREGION;
    } else clip_kind = GetClipBox(dc, &paint_clip);
    if (clip_kind == ERROR || clip_kind == NULLREGION) {
        RestoreDC(dc, saved);
        return;
    }
    IntersectClipRect(dc, wgs->offset_width, wgs->offset_height,
                     wgs->offset_width + term->cols * wgs->font_width,
                     wgs->offset_height + term->rows * wgs->font_height);
    SetStretchBltMode(dc, COLORONCOLOR);
    for (NemoTermImage *img = term->images; img; img = img->next) {
        if (img->screen != term->alt_which)
            continue;
        NemoSixelStats stats = nemo_sixel_stats(img->source->bitmap);
        if (stats.status != NEMO_SIXEL_OK || !stats.width || !stats.height ||
            stats.width > NEMO_SIXEL_MAX_DIMENSION ||
            img->pixel_width <= 0 || img->pixel_height <= 0)
            continue;
        int64_t left64 = wgs->offset_width + (int64_t)img->x * wgs->font_width + img->pixel_x;
        if (left64 >= paint_clip.right || left64 + img->pixel_width <= paint_clip.left)
            continue;
        int left = (int)left64;
        BITMAPINFO bi = {0};
        bi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
        bi.bmiHeader.biWidth = img->pixel_width;
        bi.bmiHeader.biHeight = -1;
        bi.bmiHeader.biPlanes = 1;
        bi.bmiHeader.biBitCount = 32;
        bi.bmiHeader.biCompression = BI_RGB;
        for (int y = 0; y < img->pixel_height; y++) {
            int64_t dest = term_image_pixel_y(img, y, wgs->font_height);
            if (dest == INT64_MIN) continue;
            int64_t y64 = wgs->offset_height + dest -
                (int64_t)term->disptop * wgs->font_height;
            if (y64 < paint_clip.top || y64 >= paint_clip.bottom ||
                y64 < wgs->offset_height || y64 >= wgs->offset_height +
                (int64_t)term->rows * wgs->font_height)
                continue;
            int y0 = (int)y64;
            size_t n = term_image_read_row(img, y, 0, row, img->pixel_width);
            for (unsigned x = 0; x < n;) {
                if (!(row[x] >> 24)) { x++; continue; }
                unsigned end = x+1;
                while (end < n && (row[end] >> 24)) end++;
                int x0 = left + x;
                int x1 = left + end;
                if (x1 > x0 && wgs->gpu_drawing) {
                    int a = max(x0, paint_clip.left), b = min(x1, paint_clip.right);
                    if (b > a) nemo_gpu_row(wgs->gpu, a, y0, b-a, row + x + a-x0);
                } else if (x1 > x0)
                    StretchDIBits(dc, x0, y0, x1-x0, 1,
                                  x, 0, end-x, 1, row, &bi, DIB_RGB_COLORS, SRCCOPY);
                x = end;
            }
        }
    }
    if (saved) RestoreDC(dc, saved);
}

/*
 * Set up the colour palette.
 */
static void init_palette(WinGuiSeat *wgs)
{
    wgs->pal = NULL;
    wgs->logpal = snew_plus(
        LOGPALETTE, (OSC4_NCOLOURS - 1) * sizeof(PALETTEENTRY));
    wgs->logpal->palVersion = 0x300;
    wgs->logpal->palNumEntries = OSC4_NCOLOURS;
    for (unsigned i = 0; i < OSC4_NCOLOURS; i++)
        wgs->logpal->palPalEntry[i].peFlags = PC_NOCOLLAPSE;
}

static void wintw_palette_set(TermWin *tw, unsigned start,
                              unsigned ncolours, const rgb *colours_in)
{
    WinGuiSeat *wgs = container_of(tw, WinGuiSeat, termwin);
    nemo_gpu_clear_cache(wgs->gpu);
    assert(start <= OSC4_NCOLOURS);
    assert(ncolours <= OSC4_NCOLOURS - start);

    for (unsigned i = 0; i < ncolours; i++) {
        const rgb *in = &colours_in[i];
        PALETTEENTRY *out = &wgs->logpal->palPalEntry[i + start];
        out->peRed = in->r;
        out->peGreen = in->g;
        out->peBlue = in->b;
        wgs->colours[i + start] =
            RGB(in->r, in->g, in->b) ^ wgs->colorref_modifier;
    }

    bool got_new_palette = false;

    if (!wgs->tried_pal && conf_get_bool(wgs->conf, CONF_try_palette)) {
        HDC hdc = GetDC(wgs->term_hwnd);
        if (GetDeviceCaps(hdc, RASTERCAPS) & RC_PALETTE) {
            wgs->pal = CreatePalette(wgs->logpal);
            if (wgs->pal) {
                SelectPalette(hdc, wgs->pal, false);
                RealizePalette(hdc);
                SelectPalette(hdc, GetStockObject(DEFAULT_PALETTE), false);

                /* Convert all RGB() values in colours[] into PALETTERGB(),
                 * and ensure we stick to that later */
                wgs->colorref_modifier = PALETTERGB(0, 0, 0) ^ RGB(0, 0, 0);
                for (unsigned i = 0; i < OSC4_NCOLOURS; i++)
                    wgs->colours[i] ^= wgs->colorref_modifier;

                /* Inhibit the SetPaletteEntries call below */
                got_new_palette = true;
            }
        }
        ReleaseDC(wgs->term_hwnd, hdc);
        wgs->tried_pal = true;
    }

    if (wgs->pal && !got_new_palette) {
        /* We already had a palette, so replace the changed colours in the
         * existing one. */
        SetPaletteEntries(wgs->pal, start, ncolours,
                          wgs->logpal->palPalEntry + start);

        HDC hdc = make_hdc(wgs);
        UnrealizeObject(wgs->pal);
        RealizePalette(hdc);
        free_hdc(wgs, hdc);
    }

    if (start <= OSC4_COLOUR_bg && OSC4_COLOUR_bg < start + ncolours) {
        /* If Default Background changes, we need to ensure any space between
         * the text area and the window border is redrawn. */
        InvalidateRect(wgs->term_hwnd, NULL, true);
    }
}

void write_aclip(HWND hwnd, int clipboard, char *data, int len)
{
    HGLOBAL clipdata;
    void *lock;

    if (clipboard != CLIP_SYSTEM)
        return;

    clipdata = GlobalAlloc(GMEM_DDESHARE | GMEM_MOVEABLE, len + 1);
    if (!clipdata)
        return;
    lock = GlobalLock(clipdata);
    if (!lock)
        return;
    memcpy(lock, data, len);
    ((unsigned char *) lock)[len] = 0;
    GlobalUnlock(clipdata);

    if (nemo_open_clipboard(hwnd)) {
        EmptyClipboard();
        SetClipboardData(CF_TEXT, clipdata);
        CloseClipboard();
    } else
        GlobalFree(clipdata);
}

typedef struct _rgbindex {
    int index;
    COLORREF ref;
} rgbindex;

int cmpCOLORREF(void *va, void *vb)
{
    COLORREF a = ((rgbindex *)va)->ref;
    COLORREF b = ((rgbindex *)vb)->ref;
    return (a < b) ? -1 : (a > b) ? +1 : 0;
}

/*
 * Note: unlike write_aclip() this will not append a nul.
 */
static void wintw_clip_write(
    TermWin *tw, int clipboard, wchar_t *data, int *attr,
    truecolour *truecolour, int len, bool must_deselect)
{
    WinGuiSeat *wgs = container_of(tw, WinGuiSeat, termwin);
    HGLOBAL clipdata, clipdata2, clipdata3;
    int len2;
    void *lock, *lock2, *lock3;

    if (clipboard != CLIP_SYSTEM)
        return;

    len2 = WideCharToMultiByte(CP_ACP, 0, data, len, 0, 0, NULL, NULL);

    clipdata = GlobalAlloc(GMEM_DDESHARE | GMEM_MOVEABLE,
                           len * sizeof(wchar_t));
    clipdata2 = GlobalAlloc(GMEM_DDESHARE | GMEM_MOVEABLE, len2);

    if (!clipdata || !clipdata2) {
        if (clipdata)
            GlobalFree(clipdata);
        if (clipdata2)
            GlobalFree(clipdata2);
        return;
    }
    if (!(lock = GlobalLock(clipdata))) {
        GlobalFree(clipdata);
        GlobalFree(clipdata2);
        return;
    }
    if (!(lock2 = GlobalLock(clipdata2))) {
        GlobalUnlock(clipdata);
        GlobalFree(clipdata);
        GlobalFree(clipdata2);
        return;
    }

    memcpy(lock, data, len * sizeof(wchar_t));
    WideCharToMultiByte(CP_ACP, 0, data, len, lock2, len2, NULL, NULL);

    if (conf_get_bool(wgs->conf, CONF_rtf_paste)) {
        wchar_t unitab[256];
        strbuf *rtf = strbuf_new();
        unsigned char *tdata = (unsigned char *)lock2;
        wchar_t *udata = (wchar_t *)lock;
        int uindex = 0, tindex = 0;
        int multilen, blen, alen, i;
        char before[16], after[4];
        int fgcolour,  lastfgcolour  = -1;
        int bgcolour,  lastbgcolour  = -1;
        COLORREF fg,   lastfg = -1;
        COLORREF bg,   lastbg = -1;
        int attrBold,  lastAttrBold  = 0;
        int attrUnder, lastAttrUnder = 0;
        int palette[OSC4_NCOLOURS];
        int numcolours;
        tree234 *rgbtree = NULL;
        FontSpec *font = conf_get_fontspec(wgs->conf, CONF_font);

        get_unitab(CP_ACP, unitab, 0);

        put_fmt(
            rtf, "{\\rtf1\\ansi\\deff0{\\fonttbl\\f0\\fmodern %s;}\\f0\\fs%d",
            font->name, font->height*2);

        /*
         * Add colour palette
         * {\colortbl ;\red255\green0\blue0;\red0\green0\blue128;}
         */

        /*
         * First - Determine all colours in use
         *    o  Foregound and background colours share the same palette
         */
        if (attr) {
            memset(palette, 0, sizeof(palette));
            for (i = 0; i < (len-1); i++) {
                fgcolour = ((attr[i] & ATTR_FGMASK) >> ATTR_FGSHIFT);
                bgcolour = ((attr[i] & ATTR_BGMASK) >> ATTR_BGSHIFT);

                if (attr[i] & ATTR_REVERSE) {
                    int tmpcolour = fgcolour;   /* Swap foreground and background */
                    fgcolour = bgcolour;
                    bgcolour = tmpcolour;
                }

                if (wgs->bold_colours && (attr[i] & ATTR_BOLD)) {
                    if (fgcolour  <   8)        /* ANSI colours */
                        fgcolour +=   8;
                    else if (fgcolour >= 256)   /* Default colours */
                        fgcolour ++;
                }

                if ((attr[i] & ATTR_BLINK)) {
                    if (bgcolour  <   8)        /* ANSI colours */
                        bgcolour +=   8;
                    else if (bgcolour >= 256)   /* Default colours */
                        bgcolour ++;
                }

                palette[fgcolour]++;
                palette[bgcolour]++;
            }

            if (truecolour) {
                rgbtree = newtree234(cmpCOLORREF);
                for (i = 0; i < (len-1); i++) {
                    if (truecolour[i].fg.enabled) {
                        rgbindex *rgbp = snew(rgbindex);
                        rgbp->ref = RGB(truecolour[i].fg.r,
                                        truecolour[i].fg.g,
                                        truecolour[i].fg.b);
                        if (add234(rgbtree, rgbp) != rgbp)
                            sfree(rgbp);
                    }
                    if (truecolour[i].bg.enabled) {
                        rgbindex *rgbp = snew(rgbindex);
                        rgbp->ref = RGB(truecolour[i].bg.r,
                                        truecolour[i].bg.g,
                                        truecolour[i].bg.b);
                        if (add234(rgbtree, rgbp) != rgbp)
                            sfree(rgbp);
                    }
                }
            }

            /*
             * Next - Create a reduced palette
             */
            numcolours = 0;
            for (i = 0; i < OSC4_NCOLOURS; i++) {
                if (palette[i] != 0)
                    palette[i]  = ++numcolours;
            }

            if (rgbtree) {
                rgbindex *rgbp;
                for (i = 0; (rgbp = index234(rgbtree, i)) != NULL; i++)
                    rgbp->index = ++numcolours;
            }

            /*
             * Finally - Write the colour table
             */
            put_datapl(rtf, PTRLEN_LITERAL("{\\colortbl ;"));

            for (i = 0; i < OSC4_NCOLOURS; i++) {
                if (palette[i] != 0) {
                    const PALETTEENTRY *pe = &wgs->logpal->palPalEntry[i];
                    put_fmt(rtf, "\\red%d\\green%d\\blue%d;",
                            pe->peRed, pe->peGreen, pe->peBlue);
                }
            }
            if (rgbtree) {
                rgbindex *rgbp;
                for (i = 0; (rgbp = index234(rgbtree, i)) != NULL; i++)
                    put_fmt(rtf, "\\red%d\\green%d\\blue%d;",
                            GetRValue(rgbp->ref), GetGValue(rgbp->ref),
                            GetBValue(rgbp->ref));
            }
            put_datapl(rtf, PTRLEN_LITERAL("}"));
        }

        /*
         * We want to construct a piece of RTF that specifies the
         * same Unicode text. To do this we will read back in
         * parallel from the Unicode data in `udata' and the
         * non-Unicode data in `tdata'. For each character in
         * `tdata' which becomes the right thing in `udata' when
         * looked up in `unitab', we just copy straight over from
         * tdata. For each one that doesn't, we must WCToMB it
         * individually and produce a \u escape sequence.
         *
         * It would probably be more robust to just bite the bullet
         * and WCToMB each individual Unicode character one by one,
         * then MBToWC each one back to see if it was an accurate
         * translation; but that strikes me as a horrifying number
         * of Windows API calls so I want to see if this faster way
         * will work. If it screws up badly we can always revert to
         * the simple and slow way.
         */
        while (tindex < len2 && uindex < len &&
               tdata[tindex] && udata[uindex]) {
            if (tindex + 1 < len2 &&
                tdata[tindex] == '\r' &&
                tdata[tindex+1] == '\n') {
                tindex++;
                uindex++;
            }

            /*
             * Set text attributes
             */
            if (attr) {
                /*
                 * Determine foreground and background colours
                 */
                if (truecolour && truecolour[tindex].fg.enabled) {
                    fgcolour = -1;
                    fg = RGB(truecolour[tindex].fg.r,
                             truecolour[tindex].fg.g,
                             truecolour[tindex].fg.b);
                } else {
                    fgcolour = ((attr[tindex] & ATTR_FGMASK) >> ATTR_FGSHIFT);
                    fg = -1;
                }

                if (truecolour && truecolour[tindex].bg.enabled) {
                    bgcolour = -1;
                    bg = RGB(truecolour[tindex].bg.r,
                             truecolour[tindex].bg.g,
                             truecolour[tindex].bg.b);
                } else {
                    bgcolour = ((attr[tindex] & ATTR_BGMASK) >> ATTR_BGSHIFT);
                    bg = -1;
                }

                if (attr[tindex] & ATTR_REVERSE) {
                    int tmpcolour = fgcolour;       /* Swap foreground and background */
                    fgcolour = bgcolour;
                    bgcolour = tmpcolour;

                    COLORREF tmpref = fg;
                    fg = bg;
                    bg = tmpref;
                }

                if (wgs->bold_colours && (attr[tindex] & ATTR_BOLD) &&
                    (fgcolour >= 0)) {
                    if (fgcolour  <   8)            /* ANSI colours */
                        fgcolour +=   8;
                    else if (fgcolour >= 256)       /* Default colours */
                        fgcolour ++;
                }

                if ((attr[tindex] & ATTR_BLINK) && (bgcolour >= 0)) {
                    if (bgcolour  <   8)            /* ANSI colours */
                        bgcolour +=   8;
                    else if (bgcolour >= 256)       /* Default colours */
                        bgcolour ++;
                }

                /*
                 * Collect other attributes
                 */
                if (wgs->bold_font_mode != BOLD_NONE)
                    attrBold  = attr[tindex] & ATTR_BOLD;
                else
                    attrBold  = 0;

                attrUnder = attr[tindex] & ATTR_UNDER;
                if (truecolour && (truecolour[tindex].decoration & UNDER_DOUBLE_LEGACY))
                    attrUnder = ATTR_UNDER;

                /*
                 * Reverse video
                 *   o  If video isn't reversed, ignore colour attributes for default foregound
                 *      or background.
                 *   o  Special case where bolded text is displayed using the default foregound
                 *      and background colours - force to bolded RTF.
                 */
                if (!(attr[tindex] & ATTR_REVERSE)) {
                    if (bgcolour >= 256)            /* Default color */
                        bgcolour  = -1;             /* No coloring */

                    if (fgcolour >= 256) {          /* Default colour */
                        if (wgs->bold_colours && (fgcolour & 1) &&
                            bgcolour == -1)
                            attrBold = ATTR_BOLD;   /* Emphasize text with bold attribute */

                        fgcolour  = -1;             /* No coloring */
                    }
                }

                /*
                 * Write RTF text attributes
                 */
                if ((lastfgcolour != fgcolour) || (lastfg != fg)) {
                    lastfgcolour  = fgcolour;
                    lastfg        = fg;
                    if (fg == -1) {
                        put_fmt(rtf, "\\cf%d ",
                                (fgcolour >= 0) ? palette[fgcolour] : 0);
                    } else {
                        rgbindex rgb, *rgbp;
                        rgb.ref = fg;
                        if ((rgbp = find234(rgbtree, &rgb, NULL)) != NULL)
                            put_fmt(rtf, "\\cf%d ", rgbp->index);
                    }
                }

                if ((lastbgcolour != bgcolour) || (lastbg != bg)) {
                    lastbgcolour  = bgcolour;
                    lastbg        = bg;
                    if (bg == -1)
                        put_fmt(rtf, "\\highlight%d ",
                                (bgcolour >= 0) ? palette[bgcolour] : 0);
                    else {
                        rgbindex rgb, *rgbp;
                        rgb.ref = bg;
                        if ((rgbp = find234(rgbtree, &rgb, NULL)) != NULL)
                            put_fmt(rtf, "\\highlight%d ", rgbp->index);
                    }
                }

                if (lastAttrBold != attrBold) {
                    lastAttrBold  = attrBold;
                    put_datapl(rtf, attrBold ?
                               PTRLEN_LITERAL("\\b ") :
                               PTRLEN_LITERAL("\\b0 "));
                }

                if (lastAttrUnder != attrUnder) {
                    lastAttrUnder  = attrUnder;
                    put_datapl(rtf, attrUnder ?
                               PTRLEN_LITERAL("\\ul ") :
                               PTRLEN_LITERAL("\\ulnone "));
                }
            }

            if (unitab[tdata[tindex]] == udata[uindex]) {
                multilen = 1;
                before[0] = '\0';
                after[0] = '\0';
                blen = alen = 0;
            } else {
                multilen = WideCharToMultiByte(CP_ACP, 0, unitab+uindex, 1,
                                               NULL, 0, NULL, NULL);
                if (multilen != 1) {
                    blen = sprintf(before, "{\\uc%d\\u%d", (int)multilen,
                                   (int)udata[uindex]);
                    alen = 1; strcpy(after, "}");
                } else {
                    blen = sprintf(before, "\\u%d", (int)udata[uindex]);
                    alen = 0; after[0] = '\0';
                }
            }
            assert(tindex + multilen <= len2);

            put_data(rtf, before, blen);
            for (i = 0; i < multilen; i++) {
                if (tdata[tindex+i] == '\\' ||
                    tdata[tindex+i] == '{' ||
                    tdata[tindex+i] == '}') {
                    put_byte(rtf, '\\');
                    put_byte(rtf, tdata[tindex+i]);
                } else if (tdata[tindex+i] == 0x0D || tdata[tindex+i] == 0x0A) {
                    put_datapl(rtf, PTRLEN_LITERAL("\\par\r\n"));
                } else if (tdata[tindex+i] > 0x7E || tdata[tindex+i] < 0x20) {
                    put_fmt(rtf, "\\'%02x", tdata[tindex+i]);
                } else {
                    put_byte(rtf, tdata[tindex+i]);
                }
            }
            put_data(rtf, after, alen);

            tindex += multilen;
            uindex++;
        }

        put_datapl(rtf, PTRLEN_LITERAL("}\0\0")); /* Terminate RTF stream */

        clipdata3 = GlobalAlloc(GMEM_DDESHARE | GMEM_MOVEABLE, rtf->len);
        if (clipdata3 && (lock3 = GlobalLock(clipdata3)) != NULL) {
            memcpy(lock3, rtf->u, rtf->len);
            GlobalUnlock(clipdata3);
        }
        strbuf_free(rtf);

        if (rgbtree) {
            rgbindex *rgbp;
            while ((rgbp = delpos234(rgbtree, 0)) != NULL)
                sfree(rgbp);
            freetree234(rgbtree);
        }
    } else
        clipdata3 = NULL;

    GlobalUnlock(clipdata);
    GlobalUnlock(clipdata2);

    if (!must_deselect)
        SendMessage(wgs->term_hwnd, WM_IGNORE_CLIP, true, 0);

    if (nemo_open_clipboard(wgs->term_hwnd)) {
        EmptyClipboard();
        SetClipboardData(CF_UNICODETEXT, clipdata);
        SetClipboardData(CF_TEXT, clipdata2);
        if (clipdata3)
            SetClipboardData(RegisterClipboardFormat(CF_RTF), clipdata3);
        CloseClipboard();
    } else {
        GlobalFree(clipdata);
        GlobalFree(clipdata2);
    }

    if (!must_deselect)
        SendMessage(wgs->term_hwnd, WM_IGNORE_CLIP, false, 0);
}

static DWORD WINAPI clipboard_read_threadfunc(void *param)
{
    NemoPasteRequest *request = param;

    if (nemo_open_clipboard(NULL)) {
        request->data = GetClipboardData(CF_HDROP);
        request->files = request->data!=NULL;
        if (!request->data) request->data = GetClipboardData(CF_UNICODETEXT);
        request->unicode = true;
        if (!request->data) {
            request->data = GetClipboardData(CF_TEXT);
            request->unicode = false;
        }
        if (!request->data)
            request->application_paste=IsClipboardFormatAvailable(CF_DIB) ||
                IsClipboardFormatAvailable(CF_DIBV5) || IsClipboardFormatAvailable(CF_BITMAP) ||
                IsClipboardFormatAvailable(RegisterClipboardFormatW(L"PNG"));
        if (request->data)
            SendMessage(request->hwnd, WM_GOT_CLIPDATA,
                        request->session_id, (LPARAM)request);
        CloseClipboard();
        /* The application must be able to open the clipboard immediately. */
        if (request->application_paste)
            SendMessage(request->hwnd,WM_GOT_CLIPDATA,request->session_id,(LPARAM)request);
    }
    sfree(request);
    return 0;
}

static void process_clipdata(WinGuiSeat *wgs, HGLOBAL clipdata, bool unicode)
{
    wchar_t *clipboard_contents = NULL;
    size_t clipboard_length = 0;

    if (unicode) {
        wchar_t *p = GlobalLock(clipdata);

        if (p) {
            size_t capacity = GlobalSize(clipdata) / sizeof(wchar_t);
            while (clipboard_length < capacity && p[clipboard_length])
                clipboard_length++;
            clipboard_contents = snewn(clipboard_length + 1, wchar_t);
            memcpy(clipboard_contents, p, clipboard_length * sizeof(wchar_t));
            clipboard_contents[clipboard_length] = L'\0';
            GlobalUnlock(clipdata);
            term_do_paste(wgs->term, clipboard_contents, clipboard_length);
        }
    } else {
        char *s = GlobalLock(clipdata);
        int i;

        if (s) {
            size_t capacity = GlobalSize(clipdata), length = 0;
            while (length < capacity && s[length]) length++;
            i = length && length <= INT_MAX ?
                MultiByteToWideChar(CP_ACP, 0, s, length, NULL, 0) : 0;
            clipboard_contents = snewn(i + 1, wchar_t);
            if (i) MultiByteToWideChar(CP_ACP, 0, s, length, clipboard_contents, i);
            GlobalUnlock(clipdata);
            clipboard_length = i;
            clipboard_contents[clipboard_length] = L'\0';
            term_do_paste(wgs->term, clipboard_contents, clipboard_length);
        }
    }

    sfree(clipboard_contents);
}

static void wintw_clip_request_paste(TermWin *tw, int clipboard)
{
    WinGuiSeat *wgs = container_of(tw, WinGuiSeat, termwin);
    assert(clipboard == CLIP_SYSTEM);

    /*
     * I always thought pasting was synchronous in Windows; the
     * clipboard access functions certainly _look_ synchronous,
     * unlike the X ones. But in fact it seems that in some
     * situations the contents of the clipboard might not be
     * immediately available, and the clipboard-reading functions
     * may block. This leads to trouble if the application
     * delivering the clipboard data has to get hold of it by -
     * for example - talking over a network connection which is
     * forwarded through this very PuTTY.
     *
     * Hence, we spawn a subthread to read the clipboard, and do
     * our paste when it's finished. The thread will send a
     * message back to our main window when it terminates, and
     * that tells us it's OK to paste.
     */
    DWORD in_threadid; /* required for Win9x */
    if (wgs->closing) return;
    NemoPasteRequest *request = snew(NemoPasteRequest);
    *request = (NemoPasteRequest){ .hwnd = wgs->term_hwnd,
                                 .session_id = wgs->session_id };
    HANDLE hThread = CreateThread(NULL, 0, clipboard_read_threadfunc,
                                  request, 0, &in_threadid);
    if (hThread)
        CloseHandle(hThread);          /* we don't need the thread handle */
    else
        sfree(request);
}

/*
 * Print a modal (Really Bad) message box and perform a fatal exit.
 */
void modalfatalbox(const char *fmt, ...)
{
    va_list ap;
    char *message, *title;

    va_start(ap, fmt);
    message = dupvprintf(fmt, ap);
    va_end(ap);
    show_mouseptr(NULL, true);
    title = dupprintf("%s Fatal Error", appname);
    MessageBox(find_window_for_msgbox(), message, title,
               MB_SYSTEMMODAL | MB_ICONERROR | MB_OK);
    sfree(message);
    sfree(title);
    cleanup_exit(1);
}

/*
 * Print a message box and don't close the connection.
 */
void nonfatal(const char *fmt, ...)
{
    va_list ap;
    char *message, *title;

    va_start(ap, fmt);
    message = dupvprintf(fmt, ap);
    va_end(ap);
    show_mouseptr(NULL, true);
    title = dupprintf("%s Error", appname);
    MessageBox(find_window_for_msgbox(), message, title, MB_ICONERROR | MB_OK);
    sfree(message);
    sfree(title);
}

static bool flash_window_ex(WinGuiSeat *wgs, DWORD dwFlags,
                            UINT uCount, DWORD dwTimeout)
{
    if (p_FlashWindowEx) {
        FLASHWINFO fi;
        fi.cbSize = sizeof(fi);
        fi.hwnd = wgs->term_hwnd;
        fi.dwFlags = dwFlags;
        fi.uCount = uCount;
        fi.dwTimeout = dwTimeout;
        return (*p_FlashWindowEx)(&fi);
    }
    else
        return false; /* shrug */
}

/*
 * Timer for platforms where we must maintain window flashing manually
 * (e.g., Win95).
 */
static void flash_window_timer(void *vctx, unsigned long now)
{
    WinGuiSeat *wgs = (WinGuiSeat *)vctx;
    if (wgs->flashing && now == wgs->next_flash) {
        flash_window(wgs, 1);
    }
}

/*
 * Manage window caption / taskbar flashing, if enabled.
 * 0 = stop, 1 = maintain, 2 = start
 */
static void flash_window(WinGuiSeat *wgs, int mode)
{
    int beep_ind = conf_get_int(wgs->conf, CONF_beep_ind);
    if ((mode == 0) || (beep_ind == B_IND_DISABLED)) {
        /* stop */
        if (wgs->flashing) {
            wgs->flashing = false;
            if (p_FlashWindowEx)
                flash_window_ex(wgs, FLASHW_STOP, 0, 0);
            else
                FlashWindow(wgs->term_hwnd, false);
        }

    } else if (mode == 2) {
        /* start */
        if (!wgs->flashing) {
            wgs->flashing = true;
            if (p_FlashWindowEx) {
                /* For so-called "steady" mode, we use uCount=2, which
                 * seems to be the traditional number of flashes used
                 * by user notifications (e.g., by Explorer).
                 * uCount=0 appears to enable continuous flashing, per
                 * "flashing" mode, although I haven't seen this
                 * documented. */
                flash_window_ex(wgs, FLASHW_ALL | FLASHW_TIMER,
                                (beep_ind == B_IND_FLASH ? 0 : 2),
                                0 /* system cursor blink rate */);
                /* No need to schedule timer */
            } else {
                FlashWindow(wgs->term_hwnd, true);
                wgs->next_flash = schedule_timer(450, flash_window_timer, wgs);
            }
        }

    } else if ((mode == 1) && (beep_ind == B_IND_FLASH)) {
        /* maintain */
        if (wgs->flashing && !p_FlashWindowEx) {
            FlashWindow(wgs->term_hwnd, true);    /* toggle */
            wgs->next_flash = schedule_timer(450, flash_window_timer, wgs);
        }
    }
}

/*
 * Beep.
 */
static void wintw_bell(TermWin *tw, int mode)
{
    WinGuiSeat *wgs = container_of(tw, WinGuiSeat, termwin);
    if (mode == BELL_DEFAULT) {
        /*
         * For MessageBeep style bells, we want to be careful of
         * timing, because they don't have the nice property of
         * PlaySound bells that each one cancels the previous
         * active one. So we limit the rate to one per 50ms or so.
         */
        long beepdiff;

        beepdiff = GetTickCount() - wgs->last_beep_time;
        if (beepdiff >= 0 && beepdiff < 50)
            return;
        MessageBeep(MB_OK);
        /*
         * The above MessageBeep call takes time, so we record the
         * time _after_ it finishes rather than before it starts.
         */
        wgs->last_beep_time = GetTickCount();
    } else if (mode == BELL_WAVEFILE) {
        Filename *bell_wavefile = conf_get_filename(
            wgs->conf, CONF_bell_wavefile);
        bool success = (
            p_PlaySoundW ? p_PlaySoundW(bell_wavefile->wpath, NULL,
                                        SND_ASYNC | SND_FILENAME) :
            p_PlaySoundA ? p_PlaySoundA(bell_wavefile->cpath, NULL,
                                        SND_ASYNC | SND_FILENAME) : false);
        if (!success) {
            char *buf, *otherbuf;
            show_mouseptr(wgs, true);
            buf = dupprintf(
                "Unable to play sound file\n%s\nUsing default sound instead",
                bell_wavefile->utf8path);
            otherbuf = dupprintf("%s Sound Error", appname);
            message_box(wgs->term_hwnd, buf, otherbuf,
                        MB_OK | MB_ICONEXCLAMATION, true, 0);
            sfree(buf);
            sfree(otherbuf);
            conf_set_int(wgs->conf, CONF_beep, BELL_DEFAULT);
        }
    } else if (mode == BELL_PCSPEAKER) {
        long beepdiff;

        beepdiff = GetTickCount() - wgs->last_beep_time;
        if (beepdiff >= 0 && beepdiff < 50)
            return;

        /*
         * We must beep in different ways depending on whether this
         * is a 95-series or NT-series OS.
         */
        if (osPlatformId == VER_PLATFORM_WIN32_NT)
            Beep(800, 100);
        else
            MessageBeep(-1);
        wgs->last_beep_time = GetTickCount();
    }
    /* Otherwise, either visual bell or disabled; do nothing here */
    if (!wgs->term->has_focus) {
        flash_window(wgs, 2);               /* start */
    }
}

/*
 * Minimise or restore the window in response to a server-side
 * request.
 */
static void wintw_set_minimised(TermWin *tw, bool minimised)
{
    WinGuiSeat *wgs = container_of(tw, WinGuiSeat, termwin);
    if (!wgs_active(wgs)) return;
    if (IsIconic(wgs_window(wgs))) {
        if (!minimised)
            ShowWindow(wgs_window(wgs), SW_RESTORE);
    } else {
        if (minimised)
            ShowWindow(wgs_window(wgs), SW_MINIMIZE);
    }
}

/*
 * Move the window in response to a server-side request.
 */
static void wintw_move(TermWin *tw, int x, int y)
{
    WinGuiSeat *wgs = container_of(tw, WinGuiSeat, termwin);
    if (!wgs_active(wgs)) return;
    int resize_action = conf_get_int(wgs->conf, CONF_resize_action);
    if (resize_action == RESIZE_DISABLED ||
        resize_action == RESIZE_FONT ||
        IsZoomed(wgs_window(wgs)))
        return;

    SetWindowPos(wgs_window(wgs), NULL, x, y, 0, 0, SWP_NOSIZE | SWP_NOZORDER);
}

/*
 * Move the window to the top or bottom of the z-order in response
 * to a server-side request.
 */
static void wintw_set_zorder(TermWin *tw, bool top)
{
    WinGuiSeat *wgs = container_of(tw, WinGuiSeat, termwin);
    if (!wgs_active(wgs)) return;
    if (conf_get_bool(wgs->conf, CONF_alwaysontop))
        return;                        /* ignore */
    SetWindowPos(wgs_window(wgs), top ? HWND_TOP : HWND_BOTTOM, 0, 0, 0, 0,
                 SWP_NOMOVE | SWP_NOSIZE);
}

/*
 * Refresh the window in response to a server-side request.
 */
static void wintw_refresh(TermWin *tw)
{
    WinGuiSeat *wgs = container_of(tw, WinGuiSeat, termwin);
    InvalidateRect(wgs->term_hwnd, NULL, true);
}

/*
 * Maximise or restore the window in response to a server-side
 * request.
 */
static void wintw_set_maximised(TermWin *tw, bool maximised)
{
    WinGuiSeat *wgs = container_of(tw, WinGuiSeat, termwin);
    if (!wgs_active(wgs)) return;
    if (IsZoomed(wgs_window(wgs))) {
        if (!maximised)
            ShowWindow(wgs_window(wgs), SW_RESTORE);
    } else {
        if (maximised)
            ShowWindow(wgs_window(wgs), SW_MAXIMIZE);
    }
}

/*
 * See if we're in full-screen mode.
 */
static bool is_full_screen(WinGuiSeat *wgs)
{
    if (wgs->tabbed) return tab_host.fullscreen;
    if (!IsZoomed(wgs_window(wgs)))
        return false;
    if (GetWindowLongPtr(wgs->term_hwnd, GWL_STYLE) & WS_CAPTION)
        return false;
    return true;
}

/* Get a MONITORINFO structure for the nearest available monitor, if the
 * multimon API is available and returns success. Shared subroutine between
 * get_fullscreen_rect() and get_workingarea_rect(). */
static bool get_monitor_info(WinGuiSeat *wgs, MONITORINFO *mi)
{
#if defined(MONITOR_DEFAULTTONEAREST) && !defined(NO_MULTIMON)
    if (p_GetMonitorInfoA && p_MonitorFromWindow) {
        HMONITOR mon;
        mon = p_MonitorFromWindow(wgs->term_hwnd, MONITOR_DEFAULTTONEAREST);
        mi->cbSize = sizeof(*mi);
        p_GetMonitorInfoA(mon, mi);
        return true;
    }
#endif
    return false;
}


/* Get the rect/size of a full-screen window on the nearest available
 * monitor in multimon systems; default to something sensible if only
 * one monitor is present. */
static bool get_fullscreen_rect(WinGuiSeat *wgs, RECT *ss)
{
#if defined(MONITOR_DEFAULTTONEAREST) && !defined(NO_MULTIMON)
    MONITORINFO mi;
    if (get_monitor_info(wgs, &mi)) {
        /* structure copy */
        *ss = mi.rcMonitor;
        return true;
    }
#endif
/* could also use code like this:
        ss->left = ss->top = 0;
        ss->right = GetSystemMetrics(SM_CXSCREEN);
        ss->bottom = GetSystemMetrics(SM_CYSCREEN);
*/
    return GetClientRect(GetDesktopWindow(), ss);
}


/* Similar to get_fullscreen_rect, but retrieves the working area of the
 * monitor (minus the taskbar) instead of its full extent. */
static bool get_workingarea_rect(WinGuiSeat *wgs, RECT *ss)
{
#if defined(MONITOR_DEFAULTTONEAREST) && !defined(NO_MULTIMON)
    MONITORINFO mi;
    if (get_monitor_info(wgs, &mi)) {
        /* structure copy */
        *ss = mi.rcWork;
        return true;
    }
#endif
    /* Fallback is the same as get_monitor_rect, which is good _enough_:
     * if the window overlaps the taskbar, that's not too bad a failure. */
    return GetClientRect(GetDesktopWindow(), ss);
}


/*
 * Go full-screen. This should only be called when we are already
 * maximised.
 */
static void make_full_screen(WinGuiSeat *wgs)
{
    DWORD style;
    RECT ss;

    assert(IsZoomed(wgs_window(wgs)));

    if (is_full_screen(wgs))
        return;

    /* Remove the window furniture. */
    style = GetWindowLongPtr(wgs->term_hwnd, GWL_STYLE);
    style &= ~(WS_CAPTION | WS_BORDER | WS_THICKFRAME);
    if (conf_get_bool(wgs->conf, CONF_scrollbar_in_fullscreen))
        style |= WS_VSCROLL;
    else
        style &= ~WS_VSCROLL;
    SetWindowLongPtr(wgs->term_hwnd, GWL_STYLE, style);

    /* Resize ourselves to exactly cover the nearest monitor. */
    get_fullscreen_rect(wgs, &ss);
    SetWindowPos(wgs_window(wgs), HWND_TOP, ss.left, ss.top,
                 ss.right - ss.left, ss.bottom - ss.top, SWP_FRAMECHANGED);

    /* We may have changed size as a result */

    reset_window(wgs, 0);

    /* Tick the menu item in the System and context menus. */
    {
        int i;
        for (i = 0; i < lenof(wgs->popup_menus); i++)
            CheckMenuItem(wgs->popup_menus[i].menu,
                          IDM_FULLSCREEN, MF_CHECKED);
    }
}

/*
 * Clear the full-screen attributes.
 */
static void clear_full_screen(WinGuiSeat *wgs)
{
    DWORD oldstyle, style;

    /* Reinstate the window furniture. */
    style = oldstyle = GetWindowLongPtr(wgs->term_hwnd, GWL_STYLE);
    style |= WS_CAPTION | WS_BORDER;
    if (conf_get_int(wgs->conf, CONF_resize_action) == RESIZE_DISABLED)
        style &= ~WS_THICKFRAME;
    else
        style |= WS_THICKFRAME;
    if (conf_get_bool(wgs->conf, CONF_scrollbar))
        style |= WS_VSCROLL;
    else
        style &= ~WS_VSCROLL;
    if (style != oldstyle) {
        SetWindowLongPtr(wgs->term_hwnd, GWL_STYLE, style);
        SetWindowPos(wgs_window(wgs), NULL, 0, 0, 0, 0,
                     SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER |
                     SWP_FRAMECHANGED);
    }

    /* Untick the menu item in the System and context menus. */
    {
        int i;
        for (i = 0; i < lenof(wgs->popup_menus); i++)
            CheckMenuItem(wgs->popup_menus[i].menu,
                          IDM_FULLSCREEN, MF_UNCHECKED);
    }
}

/*
 * Toggle full-screen mode.
 */
static void flip_full_screen(WinGuiSeat *wgs)
{
    if (wgs->tabbed) {nemo_host_fullscreen(!tab_host.fullscreen);return;}
    if (is_full_screen(wgs)) {
        ShowWindow(wgs_window(wgs), SW_RESTORE);
    } else if (IsZoomed(wgs_window(wgs))) {
        make_full_screen(wgs);
    } else {
        SendMessage(wgs->term_hwnd, WM_FULLSCR_ON_MAX, 0, 0);
        ShowWindow(wgs_window(wgs), SW_MAXIMIZE);
    }
}

static size_t win_seat_output(Seat *seat, SeatOutputType type,
                              const void *data, size_t len)
{
    WinGuiSeat *wgs = container_of(seat, WinGuiSeat, seat);
    return term_data(wgs->term, data, len);
}

static void wintw_unthrottle(TermWin *tw, size_t bufsize)
{
    WinGuiSeat *wgs = container_of(tw, WinGuiSeat, termwin);
    if (wgs->backend)
        backend_unthrottle(wgs->backend, bufsize);
}

static bool win_seat_eof(Seat *seat)
{
    return true;   /* do respond to incoming EOF with outgoing */
}

static SeatPromptResult win_seat_get_userpass_input(Seat *seat, prompts_t *p)
{
    WinGuiSeat *wgs = container_of(seat, WinGuiSeat, seat);
    SeatPromptResult spr;
    spr = cmdline_get_passwd_input(p, &wgs->cmdline_get_passwd_state, true);
    if (spr.kind == SPRK_INCOMPLETE)
        spr = term_get_userpass_input(wgs->term, p);
    return spr;
}

static void win_seat_set_trust_status(Seat *seat, bool trusted)
{
    WinGuiSeat *wgs = container_of(seat, WinGuiSeat, seat);
    term_set_trust_status(wgs->term, trusted);
}

static bool win_seat_can_set_trust_status(Seat *seat)
{
    return true;
}

static bool win_seat_get_cursor_position(Seat *seat, int *x, int *y)
{
    WinGuiSeat *wgs = container_of(seat, WinGuiSeat, seat);
    term_get_cursor_position(wgs->term, x, y);
    return true;
}

static bool win_seat_get_window_pixel_size(Seat *seat, int *x, int *y)
{
    WinGuiSeat *wgs = container_of(seat, WinGuiSeat, seat);
    RECT r;
    GetWindowRect(wgs_window(wgs), &r);
    *x = r.right - r.left;
    *y = r.bottom - r.top;
    return true;
}
