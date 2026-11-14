/* Private window.c interface: the host owns presentation, seats own sessions. */
#ifndef NEMO_TABS_HOST_H
#define NEMO_TABS_HOST_H
#include "nemo_tabs_layout.h"
typedef struct NemoTabHost {
    HWND hwnd, preview;
    WinGuiSeat *active, *hover;
    NemoTabLayout layout;
    NemoGPU *gpu;
    int gpu_kind, side, sidebar, first, dpi, system_menu_items;
    bool moving, destroying;
    bool fullscreen;
    WINDOWPLACEMENT placement;
    LONG_PTR normal_style;
    unsigned char consumed_keys[256];
    HFONT font;
    HBITMAP thumbnail;
    int preview_width, preview_height;
} NemoTabHost;
static NemoTabHost tab_host;
static HWND wgs_window(WinGuiSeat *wgs)
{
    return wgs->tabbed && tab_host.hwnd ? tab_host.hwnd : wgs->term_hwnd;
}
static bool wgs_active(WinGuiSeat *wgs)
{
    return !wgs->tabbed || tab_host.active==wgs;
}
static void nemo_host_font(void);
static bool nemo_host_create(Conf *, int, int);
static void nemo_host_layout(void);
static void nemo_host_select(WinGuiSeat *);
static void nemo_host_remove(WinGuiSeat *);
static void nemo_host_configure(WinGuiSeat *);
static void nemo_host_renderer(WinGuiSeat *);
static void nemo_host_title(WinGuiSeat *);
static void nemo_host_resize(WinGuiSeat *, int);
static void nemo_host_new_tab(WinGuiSeat *);
static bool nemo_host_binding(WinGuiSeat *, unsigned, unsigned);
static void nemo_host_fullscreen(bool);
static bool nemo_render_snapshot_band(HDC, int, int, void *);
#endif
