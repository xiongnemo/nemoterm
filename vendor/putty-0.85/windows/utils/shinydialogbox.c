/*
 * PuTTY's own reimplementation of DialogBox() and EndDialog() which
 * provide extra capabilities.
 *
 * Originally introduced in 2003 to work around a problem with our
 * message loops, in which keystrokes pressed in the 'Change Settings'
 * dialog in mid-session would _also_ be delivered to the main
 * terminal window.
 *
 * But once we had our own wrapper it was convenient to put further
 * things into it. In particular, this system allows you to provide a
 * context pointer at setup time that's easy to retrieve from the
 * window procedure.
 */

#include "putty.h"

struct WinModalState {
    HWND owner, *disabled;
    size_t count;
    struct WinModalState *previous;
};
static THREADLOCAL unsigned modal_depth;
static THREADLOCAL WinModalState *modal_current;
static THREADLOCAL UINT modal_focus_message;

static void modal_disable(WinModalState *state, HWND hwnd)
{
    if (!hwnd || !IsWindowEnabled(hwnd)) return;
    state->disabled=sresize(state->disabled,state->count+1,HWND);
    state->disabled[state->count++]=hwnd;
    EnableWindow(hwnd,FALSE);
}

static BOOL CALLBACK modal_disable_terminal(HWND hwnd, LPARAM context)
{
    char name[64];
    if (GetClassNameA(hwnd,name,sizeof(name)) &&
        (!strcmp(name,"Nemoterm") || !strcmp(name,"NemotermHost")))
        modal_disable((WinModalState *)context,hwnd);
    return TRUE;
}

WinModalState *win_modal_begin(HWND owner)
{
    WinModalState *state=snew(WinModalState);
    memset(state,0,sizeof(*state));
    state->owner=owner ? GetAncestor(owner,GA_ROOT) : NULL;
    state->previous=modal_current;modal_current=state;
    if (!modal_focus_message)
        modal_focus_message=RegisterWindowMessageA("Nemoterm.ModalFocus");
    modal_depth++;
    /* Save enabled state, so closing a nested dialog cannot enable its
     * terminal or an outer dialog prematurely. Other applications are free. */
    modal_disable(state,state->owner);
    EnumThreadWindows(GetCurrentThreadId(),modal_disable_terminal,(LPARAM)state);
    return state;
}

void win_modal_end(WinModalState *state)
{
    assert(modal_depth);modal_depth--;
    assert(modal_current==state);modal_current=state->previous;
    for (size_t i=0;i<state->count;i++)
        if (IsWindow(state->disabled[i])) EnableWindow(state->disabled[i],TRUE);
    if (state->owner && IsWindowEnabled(state->owner)) SetActiveWindow(state->owner);
    sfree(state->disabled);sfree(state);
}

bool win_modal_active(void) { return modal_depth!=0; }

static BOOL CALLBACK modal_find_dialog(HWND hwnd, LPARAM context)
{
    char name[64];
    if (IsWindowVisible(hwnd) && IsWindowEnabled(hwnd) &&
        GetClassNameA(hwnd,name,sizeof(name)) &&
        (!strcmp(name,"#32770") || !strcmp(name,"PuTTYConfigBox") ||
         !strcmp(name,"PuTTYHostKeyDialog"))) {
        *(HWND *)context=hwnd;return FALSE;
    }
    return TRUE;
}

bool win_modal_redirect_activation(HWND hwnd, UINT message, WPARAM wp)
{
    if (!win_modal_active()) return false;
    if (message==WM_MOUSEACTIVATE || message==WM_SETFOCUS ||
        (message==WM_ACTIVATE && LOWORD(wp)!=WA_INACTIVE)) {
        /* SetForegroundWindow can activate even a disabled HWND. Redirect
         * after that activation finishes, rather than re-entering it. */
        if (modal_focus_message) PostMessage(hwnd,modal_focus_message,0,0);
        return true;
    }
    if (!modal_focus_message || message!=modal_focus_message) return false;
    HWND dialog=NULL;
    for (WinModalState *state=modal_current;state && !dialog;state=state->previous) {
        HWND popup=state->owner;
        for (int depth=0;popup && depth<16;depth++) {
            HWND next=GetLastActivePopup(popup);
            if (!next || next==popup) break;
            popup=next;
        }
        if (popup && IsWindowVisible(popup) && IsWindowEnabled(popup)) dialog=popup;
    }
    /* Covers initially unowned dialogs and the short creation interval. */
    if (!dialog) EnumThreadWindows(GetCurrentThreadId(),modal_find_dialog,(LPARAM)&dialog);
    if (dialog) {SetForegroundWindow(dialog);SetActiveWindow(dialog);}
    return true;
}

bool win_modal_blocks_message(UINT message)
{
    return win_modal_active() &&
        ((message>=WM_KEYFIRST && message<=WM_KEYLAST) ||
         (message>=WM_MOUSEFIRST && message<=WM_MOUSELAST) ||
         message==WM_COMMAND || message==WM_SYSCOMMAND ||
         message==WM_PASTE || message==WM_DROPFILES || message==WM_UNICHAR ||
         message==WM_CLOSE);
}

INT_PTR win_modal_dialog_box(HINSTANCE instance, LPCTSTR resource, HWND owner, DLGPROC proc)
{
    WinModalState *state=win_modal_begin(owner);
    INT_PTR result=DialogBoxW(instance,(LPCWSTR)resource,state->owner,proc);
    win_modal_end(state);return result;
}

int win_modal_message_box(HWND owner, LPCSTR text, LPCSTR caption, UINT style)
{
    WinModalState *state=win_modal_begin(owner);
    wchar_t *wide_text = dup_mb_to_wc(CP_UTF8, text ? text : "");
    wchar_t *wide_caption = dup_mb_to_wc(CP_UTF8, caption ? caption : "");
    int result=MessageBoxW(state->owner,wide_text,wide_caption,style);
    sfree(wide_text); sfree(wide_caption);
    win_modal_end(state);return result;
}

int win_modal_message_box_w(HWND owner, LPCWSTR text, LPCWSTR caption, UINT style)
{
    WinModalState *state=win_modal_begin(owner);
    int result=MessageBoxW(state->owner,text,caption,style);
    win_modal_end(state);return result;
}

struct ShinyDialogBoxState {
    bool ended;
    int result;
    ShinyDlgProc proc;
    void *ctx;
};

/*
 * For use in re-entrant calls to the dialog procedure from
 * CreateDialog itself, temporarily store the state pointer that we
 * won't store in the usual window-memory slot until later.
 *
 * I don't _intend_ that this system will need to be used in multiple
 * threads at all, let alone concurrently, but just in case, declaring
 * sdb_tempstate as thread-local will protect against that possibility.
 */
static THREADLOCAL struct ShinyDialogBoxState *sdb_tempstate;

static inline struct ShinyDialogBoxState *ShinyDialogGetState(HWND hwnd)
{
    if (sdb_tempstate)
        return sdb_tempstate;
    return (struct ShinyDialogBoxState *)GetWindowLongPtr(
        hwnd, DLGWINDOWEXTRA);
}

static INT_PTR CALLBACK ShinyRealDlgProc(HWND hwnd, UINT msg,
                                         WPARAM wParam, LPARAM lParam)
{
    struct ShinyDialogBoxState *state = ShinyDialogGetState(hwnd);
    return state->proc(hwnd, msg, wParam, lParam, state->ctx);
}

int ShinyDialogBox(HINSTANCE hinst, LPCTSTR tmpl, const char *winclass,
                   HWND hwndparent, ShinyDlgProc proc, void *ctx)
{
    /*
     * Register the window class ourselves in such a way that we
     * allocate an extra word of window memory to store the state
     * pointer.
     *
     * It would be nice in principle to load the dialog template
     * resource and dig the class name out of it. But DLGTEMPLATEEX is
     * a nasty variable-layout structure not declared conveniently in
     * a header file, so I think that's too much effort. Callers of
     * this function will just have to provide the right window class
     * name to match their template resource via the 'winclass'
     * parameter.
     */
    WNDCLASSW wc;
    wchar_t *wide_class = dup_mb_to_wc(CP_UTF8, winclass);
    wc.style = CS_DBLCLKS | CS_SAVEBITS | CS_BYTEALIGNWINDOW;
    wc.lpfnWndProc = DefDlgProcW;
    wc.cbClsExtra = 0;
    wc.cbWndExtra = DLGWINDOWEXTRA + sizeof(LONG_PTR);
    wc.hInstance = hinst;
    wc.hIcon = NULL;
    wc.hCursor = LoadCursor(NULL, IDC_ARROW);
    wc.hbrBackground = (HBRUSH) (COLOR_BACKGROUND +1);
    wc.lpszMenuName = NULL;
    wc.lpszClassName = wide_class;
    RegisterClassW(&wc);
    sfree(wide_class);

    struct ShinyDialogBoxState state[1];
    state->ended = false;
    state->result = 0;
    state->proc = proc;
    state->ctx = ctx;

    WinModalState *modal=win_modal_begin(hwndparent);
    sdb_tempstate = state;
    HWND hwnd = CreateDialogW(hinst, (LPCWSTR)tmpl, modal->owner, ShinyRealDlgProc);
    if (!hwnd) { sdb_tempstate=NULL;win_modal_end(modal);return -1; }
    SetWindowLongPtr(hwnd, DLGWINDOWEXTRA, (LONG_PTR)state);
    sdb_tempstate = NULL;

    MSG msg;
    int gm;
    while ((gm = GetMessageW(&msg, NULL, 0, 0)) > 0) {
        if (!state->ended && !IsDialogMessageW(hwnd, &msg))
            DispatchMessageW(&msg);
        if (state->ended)
            break;
    }

    if (gm == 0)
        PostQuitMessage(msg.wParam); /* We got a WM_QUIT, pass it on */

    DestroyWindow(hwnd);
    win_modal_end(modal);
    return state->result;
}

void ShinyEndDialog(HWND hwnd, int ret)
{
    struct ShinyDialogBoxState *state = ShinyDialogGetState(hwnd);
    state->result = ret;
    state->ended = true;
}
