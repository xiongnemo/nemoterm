/* Application progress belongs to the session, including when it is hidden.
 * Coalesce shell updates on the window queue, outside terminal parsing. */
static void schedule_progress(HWND hwnd, NemoTaskbarButton *button)
{
    if (hwnd && button->ready && !button->pending)
        button->pending = PostMessage(hwnd, WM_NEMO_PROGRESS, 0, 0);
}

static void wintw_progress_changed(TermWin *tw)
{
    WinGuiSeat *w = container_of(tw, WinGuiSeat, termwin);
    if (w->closing) return;
    if (w->tabbed && tab_host.hwnd) {
        NemoTabRect bar = tab_host.layout.bar;
        RECT rect = {bar.x, bar.y, bar.x+bar.width, bar.y+bar.height};
        InvalidateRect(tab_host.hwnd, &rect, FALSE);
    }
    schedule_progress(wgs_window(w), w->tabbed ? &tab_host.task_button : &w->task_button);
}

/* Tabs share a taskbar button. Prefer errors, then pauses, then determinate
 * work, then busy. The active tab wins ties; otherwise retain tab order. */
static bool progress_message(HWND hwnd, UINT msg, WinGuiSeat *standalone)
{
    NemoTaskbarButton *button = standalone ? &standalone->task_button : &tab_host.task_button;
    if (taskbar_button_created && msg == taskbar_button_created) {
        button->ready = TRUE;
        button->attempted = FALSE;
        schedule_progress(hwnd, button);
        return true;
    }
    if (msg != WM_NEMO_PROGRESS) return false;
    button->pending = FALSE;
    if (!button->ready) return true;
    unsigned state = 0, value = 0;
    if (standalone) {
        if (standalone->term && !standalone->closing) {
            state = standalone->term->progress_state;
            value = standalone->term->progress_value;
        }
    } else {
        static const unsigned rank[] = {0, 2, 4, 1, 3};
        for (struct WinGuiSeatListNode *n=wgslisthead.next; n!=&wgslisthead; n=n->next) {
            WinGuiSeat *w = container_of(n, WinGuiSeat, wgslistnode);
            if (!w->tabbed || !w->tab_ready || w->closing || !w->term) continue;
            unsigned s = w->term->progress_state;
            if (rank[s] > rank[state] || (s == state && w == tab_host.active)) {
                state = s; value = w->term->progress_value;
            }
        }
    }
    if (!state && !button->attempted) return true; /* no shell allocation on startup */
    if (button->attempted && state == button->state && value == button->value &&
        SUCCEEDED(button->result)) return true;
    button->state = state; button->value = value; button->attempted = TRUE;
    button->result = nemo_shell_progress(hwnd, state, value);
    return true;
}

static void draw_tab_progress(HDC dc, RECT r, const Terminal *term)
{
    static const COLORREF colours[] = {0, RGB(16,160,96), RGB(224,72,72),
                                       RGB(72,160,224), RGB(224,176,54)};
    unsigned state = term->progress_state;
    if (!state || IsRectEmpty(&r)) return;
    int width = r.right-r.left;
    r.top = max(r.top, r.bottom-max(2,MulDiv(3, tab_host.dpi, 96)));
    HBRUSH brush = GetStockObject(DC_BRUSH);
    COLORREF old = SetDCBrushColor(dc, colours[state]);
    if (state == 3) {
        /* Static stripes denote an unknown length without running a UI timer. */
        int end = r.right;
        for (; r.left < end; r.left += 8) { r.right=min(end,r.left+4); FillRect(dc,&r,brush); }
    } else {
        r.right = r.left + (int)((int64_t)width*term->progress_value/100);
        if (r.right > r.left) FillRect(dc,&r,brush);
    }
    SetDCBrushColor(dc, old);
}
