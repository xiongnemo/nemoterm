/* SPDX-License-Identifier: MIT
 * Included by window.c: tab lifetime operations stay on its message thread.
 * There is one top-level host and one GPU device per process. Child terminal
 * windows retain their own coordinates, scrollbars, IME and input state.
 */
static WinGuiSeat *nemo_host_item(int index)
{
    for (struct WinGuiSeatListNode *n=wgslisthead.next;n!=&wgslisthead;n=n->next) {
        WinGuiSeat *w=container_of(n,WinGuiSeat,wgslistnode);
        if (w->tabbed && w->tab_ready && !w->closing && index--==0) return w;
    }
    return NULL;
}
static int nemo_host_count(void)
{
    int count=0;
    for (struct WinGuiSeatListNode *n=wgslisthead.next;n!=&wgslisthead;n=n->next) {
        WinGuiSeat *w=container_of(n,WinGuiSeat,wgslistnode);
        if (w->tabbed && w->tab_ready && !w->closing) count++;
    }
    return count;
}
static RECT nemo_host_rect(NemoTabRect r)
{
    RECT out={r.x,r.y,r.x+r.width,r.y+r.height};return out;
}
static void nemo_host_hide_preview(void)
{
    if (tab_host.hwnd) KillTimer(tab_host.hwnd,1);
    tab_host.hover=NULL;
    if (tab_host.preview) ShowWindow(tab_host.preview,SW_HIDE);
    if (tab_host.thumbnail) DeleteObject(tab_host.thumbnail);
    tab_host.thumbnail=NULL;
}
static void nemo_host_detach_menu(void)
{
    WinGuiSeat *w=tab_host.active;
    if (!w) return;
    HMENU m=w->popup_menus[SYSMENU].menu;
    /* Preserve the native prefix, including its ID-zero separators. All seat
     * items were appended after it; Restart/Specials may change their count.
     * Remove, never destroy: their submenus belong to the context menu too. */
    for (int i=GetMenuItemCount(m)-1;i>=tab_host.system_menu_items;i--)
        RemoveMenu(m,i,MF_BYPOSITION);
    w->popup_menus[SYSMENU]=(struct PopupMenu){0};
    tab_host.system_menu_items=0;
}
static void nemo_host_attach_menu(WinGuiSeat *w)
{
    HMENU m=GetSystemMenu(tab_host.hwnd,FALSE), source=w->popup_menus[CTXMENU].menu;
    int count=GetMenuItemCount(m);
    if (!m || count<0) return;
    tab_host.system_menu_items=count;
    for (int i=0;i<GetMenuItemCount(source);i++) {
        wchar_t label[256];
        MENUITEMINFOW mi={0};mi.cbSize=sizeof(mi);
        mi.fMask=MIIM_FTYPE|MIIM_STATE|MIIM_ID|MIIM_SUBMENU|MIIM_STRING;
        mi.dwTypeData=label;mi.cch=lenof(label);
        if (GetMenuItemInfoW(source,i,TRUE,&mi))
            InsertMenuItemW(m,GetMenuItemCount(m),TRUE,&mi);
    }
    w->popup_menus[SYSMENU].menu=m;
    w->popup_menus[SYSMENU].shell_menu=w->popup_menus[CTXMENU].shell_menu;
    CheckMenuItem(m,IDM_FULLSCREEN,tab_host.fullscreen?MF_CHECKED:MF_UNCHECKED);
    DrawMenuBar(tab_host.hwnd);
}
static void nemo_host_font(void)
{
    if (tab_host.font) DeleteObject(tab_host.font);
    tab_host.font=CreateFontW(-MulDiv(14,tab_host.dpi,96),0,0,0,FW_NORMAL,
        FALSE,FALSE,FALSE,DEFAULT_CHARSET,OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,
        CLEARTYPE_QUALITY,DEFAULT_PITCH,L"Segoe UI");
}
static void nemo_host_fullscreen(bool enable)
{
    if (enable==tab_host.fullscreen || !tab_host.hwnd) return;
    tab_host.fullscreen=enable;
    if (enable) {
        tab_host.placement.length=sizeof(tab_host.placement);
        GetWindowPlacement(tab_host.hwnd,&tab_host.placement);
        tab_host.normal_style=GetWindowLongPtr(tab_host.hwnd,GWL_STYLE);
        SetWindowLongPtr(tab_host.hwnd,GWL_STYLE,tab_host.normal_style&~(WS_CAPTION|WS_THICKFRAME));
        RECT r;get_fullscreen_rect(tab_host.active,&r);
        SetWindowPos(tab_host.hwnd,NULL,r.left,r.top,r.right-r.left,r.bottom-r.top,
                     SWP_NOZORDER|SWP_FRAMECHANGED);
    } else {
        SetWindowLongPtr(tab_host.hwnd,GWL_STYLE,tab_host.normal_style);
        SetWindowPlacement(tab_host.hwnd,&tab_host.placement);
        SetWindowPos(tab_host.hwnd,NULL,0,0,0,0,SWP_NOMOVE|SWP_NOSIZE|SWP_NOZORDER|SWP_FRAMECHANGED);
    }
    for (int i=0;i<nemo_host_count();i++) {
        WinGuiSeat *w=nemo_host_item(i);
        ShowScrollBar(w->term_hwnd,SB_VERT,conf_get_bool(w->conf,
            enable?CONF_scrollbar_in_fullscreen:CONF_scrollbar));
        for (unsigned j=0;j<lenof(w->popup_menus);j++)
            CheckMenuItem(w->popup_menus[j].menu,IDM_FULLSCREEN,enable?MF_CHECKED:MF_UNCHECKED);
    }
    nemo_host_layout();
}
static bool nemo_host_gpu_band(HDC dc, int top, int height, void *ctx)
{
    return nemo_gpu_print_band(ctx,dc,top,height);
}
static void nemo_host_renderer(WinGuiSeat *w)
{
    if (!wgs_active(w)) return;
    int kind=conf_get_int(w->conf,CONF_nemo_renderer);
    if (w->gpu_failed || kind<0 || kind>2) kind=0;
    w->gpu=NULL;w->gpu_drawing=false;
    if (tab_host.gpu && kind!=tab_host.gpu_kind) {
        nemo_gpu_free(tab_host.gpu);tab_host.gpu=NULL;
    }
    if (tab_host.gpu && !nemo_gpu_attach(tab_host.gpu,w->term_hwnd)) {
        nemo_gpu_free(tab_host.gpu);tab_host.gpu=NULL;
    }
    if (!tab_host.gpu && kind) {
        tab_host.gpu=nemo_gpu_create(w->term_hwnd,kind);
        if (tab_host.gpu)
            logeventf(w->logctx,"Shared tab renderer: %s",nemo_gpu_device(tab_host.gpu));
    }
    tab_host.gpu_kind=kind;
    if (!(w->sync_snapshot && w->term->synchronized_update)) w->gpu=tab_host.gpu;
    LONG_PTR style=GetWindowLongPtr(w->term_hwnd,GWL_STYLE);
    SetWindowLongPtr(w->term_hwnd,GWL_STYLE,
                     w->gpu ? style|WS_CLIPCHILDREN : style&~WS_CLIPCHILDREN);
    SetPropW(w->term_hwnd,L"NemotermRenderer",(HANDLE)(UINT_PTR)(w->gpu?kind+1:1));
    if (!kind) w->gpu_failed=false;
    term_invalidate(w->term);InvalidateRect(w->term_hwnd,NULL,false);
}
static void nemo_host_title(WinGuiSeat *w)
{
    if (!w->tabbed || !tab_host.hwnd) return;
    if (wgs_active(w)) SetWindowTextW(tab_host.hwnd,w->window_name);
    RECT r=nemo_host_rect(tab_host.layout.bar);InvalidateRect(tab_host.hwnd,&r,false);
}
static void nemo_host_resize(WinGuiSeat *w, int reinit)
{
    if (!w->term || w->closing || IsIconic(tab_host.hwnd)) return;
    RECT cr,wr;GetClientRect(w->term_hwnd,&cr);GetWindowRect(tab_host.hwnd,&wr);
    int border=conf_get_int(w->conf,CONF_window_border);
    int width=max(1,cr.right-2*border),height=max(1,cr.bottom-2*border);
    if (reinit>1) {deinit_fonts(w);init_fonts(w,0,0);}
    int action=conf_get_int(w->conf,CONF_resize_action);
    if (!reinit && (action==RESIZE_FONT || (action==RESIZE_EITHER && is_alt_pressed()))) {
        int fw=max(1,width/w->term->cols),fh=max(1,height/w->term->rows);
        if (fw!=w->font_width || fh!=w->font_height) {
            deinit_fonts(w);init_fonts(w,fw,fh);
        }
    } else {
        int cols=max(1,width/max(1,w->font_width)),rows=max(1,height/max(1,w->font_height));
        if (rows!=w->term->rows || cols!=w->term->cols) {
            term_end_synchronized_update(w->term);
            term_size(w->term,rows,cols,conf_get_int(w->conf,CONF_savelines));
        }
    }
    w->offset_width=max(0,(cr.right-w->font_width*w->term->cols)/2);
    w->offset_height=max(0,(cr.bottom-w->font_height*w->term->rows)/2);
    w->extra_width=wr.right-wr.left-cr.right+2*w->offset_width;
    w->extra_height=wr.bottom-wr.top-cr.bottom+2*w->offset_height;
    term_notify_window_size_pixels(w->term,wr.right-wr.left,wr.bottom-wr.top);
    term_invalidate(w->term);InvalidateRect(w->term_hwnd,NULL,TRUE);
    if (wgs_active(w)) sys_cursor_update(w);
}
static void nemo_host_layout(void)
{
    if (!tab_host.hwnd || tab_host.moving || tab_host.destroying) return;
    tab_host.moving=true;
    RECT cr;GetClientRect(tab_host.hwnd,&cr);
    tab_host.layout=nemo_tabs_layout(cr.right,cr.bottom,tab_host.side,
        nemo_tabs_metrics(tab_host.dpi,tab_host.sidebar),nemo_host_count(),tab_host.first);
    tab_host.first=tab_host.layout.first;
    NemoTabRect r=tab_host.layout.content;
    for (struct WinGuiSeatListNode *n=wgslisthead.next;n!=&wgslisthead;n=n->next) {
        WinGuiSeat *w=container_of(n,WinGuiSeat,wgslistnode);
        if (w->tabbed && w->term_hwnd && !w->closing) {
            SetWindowPos(w->term_hwnd,NULL,r.x,r.y,r.width,r.height,SWP_NOACTIVATE|SWP_NOZORDER);
            nemo_host_resize(w,0);
        }
    }
    tab_host.moving=false;
    InvalidateRect(tab_host.hwnd,NULL,FALSE);
}
static void nemo_host_select(WinGuiSeat *w)
{
    if (!w || w->closing || !w->tab_ready || w==tab_host.active) return;
    nemo_host_hide_preview();
    WinGuiSeat *old=tab_host.active;
    if (old) {
        /* A GPU freeze must survive lending the device to another tab. */
        if (!old->closing && old->gpu && old->term->synchronized_update && !old->sync_snapshot) {
            RECT cr;GetClientRect(old->term_hwnd,&cr);NemoSnapshotError error;
            old->sync_snapshot=nemo_snapshot_create(cr.right,cr.bottom,8U*1024U*1024U,
                nemo_host_gpu_band,old->gpu,&error);
            if (!old->sync_snapshot) {
                logeventf(old->logctx,"Tab freeze capture failed: %s",error.stage);
                term_end_synchronized_update(old->term);
            }
        }
        nemo_link_cancel(old);nemo_host_detach_menu();
        if (GetCapture()==old->term_hwnd) ReleaseCapture();
        term_set_focus(old->term,false);old->gpu=NULL;
        ShowWindow(old->term_hwnd,SW_HIDE);
    }
    tab_host.active=w;nemo_host_attach_menu(w);
    int index=0;while (nemo_host_item(index)!=w) index++;
    tab_host.first=nemo_tabs_reveal(&tab_host.layout,index);
    nemo_host_layout();nemo_host_renderer(w);
    ShowWindow(w->term_hwnd,SW_SHOWNOACTIVATE);
    SetFocus(w->term_hwnd);
    term_set_focus(w->term,GetForegroundWindow()==tab_host.hwnd);
    term_invalidate(w->term);InvalidateRect(w->term_hwnd,NULL,TRUE);
    UpdateWindow(w->term_hwnd);nemo_host_title(w);
}
static void nemo_host_remove(WinGuiSeat *w)
{
    if (!w->tabbed) return;
    nemo_host_hide_preview();
    if (tab_host.active==w) {
        WinGuiSeat *next=nemo_host_item(0);
        if (next) nemo_host_select(next);
        else {
            nemo_host_detach_menu();tab_host.active=NULL;
            nemo_gpu_free(tab_host.gpu);tab_host.gpu=NULL;
        }
    }
    w->gpu=NULL;w->tab_ready=false;nemo_host_layout();
    /* Removing an earlier tab shifts the active index. It can now sit just
     * before the scroll origin even though the active seat did not change. */
    if (tab_host.active && !tab_host.active->closing) {
        int index=0,count=nemo_host_count();
        while (index<count && nemo_host_item(index)!=tab_host.active) index++;
        if (index==count) return;
        int first=nemo_tabs_reveal(&tab_host.layout,index);
        if (first!=tab_host.first) {tab_host.first=first;nemo_host_layout();}
    }
}
static void nemo_host_configure(WinGuiSeat *w)
{
    if (!w->tabbed) return;
    tab_host.side=conf_get_int(w->conf,CONF_nemo_tab_side);
    tab_host.sidebar=conf_get_int(w->conf,CONF_nemo_tab_sidebar);
    for (int i=0;i<nemo_host_count();i++) {
        WinGuiSeat *other=nemo_host_item(i);
        conf_set_int(other->conf,CONF_nemo_tab_side,tab_host.side);
        conf_set_int(other->conf,CONF_nemo_tab_sidebar,tab_host.sidebar);
        conf_set_bool(other->conf,CONF_nemo_tab_preview,conf_get_bool(w->conf,CONF_nemo_tab_preview));
    }
    LONG_PTR style=GetWindowLongPtr(tab_host.hwnd,GWL_STYLE);
    bool resize=conf_get_int(w->conf,CONF_resize_action)!=RESIZE_DISABLED;
    if (resize && !tab_host.fullscreen) style|=WS_THICKFRAME|WS_MAXIMIZEBOX;
    else style&=~(WS_THICKFRAME|WS_MAXIMIZEBOX);
    SetWindowLongPtr(tab_host.hwnd,GWL_STYLE,style);
    SetWindowPos(tab_host.hwnd,conf_get_bool(w->conf,CONF_alwaysontop)?HWND_TOPMOST:HWND_NOTOPMOST,
                 0,0,0,0,SWP_NOACTIVATE|SWP_NOMOVE|SWP_NOSIZE|SWP_FRAMECHANGED);
    nemo_host_hide_preview();nemo_host_layout();
}
static void nemo_host_new_tab(WinGuiSeat *w)
{
    Conf *conf=nemo_duplicate_conf(w);
    conf_set_str(conf,CONF_remote_cmd,"");
    wgs_create(conf,SW_SHOWNORMAL);
}
static bool nemo_host_binding(WinGuiSeat *w, unsigned key, unsigned modifiers)
{
    if (!w->tabbed) return false;
    int keys[]={CONF_nemo_new_tab_binding,CONF_nemo_close_tab_binding,
                CONF_nemo_next_tab_binding,CONF_nemo_previous_tab_binding};
    for (unsigned i=0;i<lenof(keys);i++) {
        if (!nemo_binding_matches(conf_get_int(w->conf,keys[i]),key,modifiers)) continue;
        if (key<256 && tab_host.consumed_keys[key]) return true;
        if (key<256) tab_host.consumed_keys[key]=1;
        if (i==0) nemo_host_new_tab(w);
        else if (i==1) PostMessage(w->term_hwnd,WM_CLOSE,0,0);
        else {
            int count=nemo_host_count(),index=0;
            while (nemo_host_item(index)!=w) index++;
            nemo_host_select(nemo_host_item((index+count+(i==2?1:-1))%count));
        }
        return true;
    }
    return false;
}
static bool nemo_host_preview_render(WinGuiSeat *w)
{
    RECT cr;GetClientRect(w->term_hwnd,&cr);
    if (cr.right<=0 || cr.bottom<=0 || cr.right>32768 || cr.bottom>32768) return false;
    int width=320,height=max(1,MulDiv(cr.bottom,width,cr.right));
    if (height>200) {height=200;width=max(1,MulDiv(cr.right,height,cr.bottom));}
    /* One bounded source band, one thumbnail. Rendering never focuses a tab
     * and never retains an uncompressed bitmap the size of the viewport. */
    HDC src=CreateCompatibleDC(NULL),dest=CreateCompatibleDC(NULL);
    BITMAPINFO bi={0};bi.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);
    int band_rows=max(1,min(32,256*1024/(cr.right*4)));
    bi.bmiHeader.biWidth=cr.right;bi.bmiHeader.biHeight=-band_rows;
    bi.bmiHeader.biPlanes=1;bi.bmiHeader.biBitCount=32;bi.bmiHeader.biCompression=BI_RGB;
    void *bits;HBITMAP band=CreateDIBSection(src,&bi,DIB_RGB_COLORS,&bits,NULL,0);
    bi.bmiHeader.biWidth=width;bi.bmiHeader.biHeight=-height;
    HBITMAP thumb=CreateDIBSection(dest,&bi,DIB_RGB_COLORS,&bits,NULL,0);
    bool ok=src && dest && band && thumb;
    HGDIOBJ oldsrc=band?SelectObject(src,band):NULL,olddest=thumb?SelectObject(dest,thumb):NULL;
    SetStretchBltMode(dest,HALFTONE);SetBrushOrgEx(dest,0,0,NULL);
    for (int top=0;ok && top<cr.bottom;top+=band_rows) {
        int lines=min(band_rows,cr.bottom-top),y=MulDiv(top,height,cr.bottom);
        int bottom=MulDiv(top+lines,height,cr.bottom);
        if (bottom<=y) continue;
        int save=SaveDC(src);SetViewportOrgEx(src,0,-top,NULL);
        IntersectClipRect(src,0,top,cr.right,top+lines);
        if (w->sync_snapshot && w->term->synchronized_update) {
            RECT clip={0,top,cr.right,top+lines};
            ok=nemo_snapshot_paint(w->sync_snapshot,src,&clip,NULL);
        } else if (w->gpu) ok=nemo_gpu_print_band(w->gpu,src,top,lines);
        else ok=nemo_render_snapshot_band(src,top,lines,w);
        RestoreDC(src,save);
        if (ok) ok=StretchBlt(dest,0,y,width,bottom-y,src,0,0,cr.right,lines,SRCCOPY)!=0;
    }
    if (oldsrc) SelectObject(src,oldsrc);
    if (olddest) SelectObject(dest,olddest);
    if (band) DeleteObject(band);
    if (src) DeleteDC(src);if (dest) DeleteDC(dest);
    if (!w->gpu) term_invalidate(w->term);
    if (!ok) {if (thumb) DeleteObject(thumb);return false;}
    if (tab_host.thumbnail) DeleteObject(tab_host.thumbnail);
    tab_host.thumbnail=thumb;tab_host.preview_width=width;tab_host.preview_height=height;
    return true;
}
static LRESULT CALLBACK nemo_preview_proc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp)
{
    if (msg==WM_MOUSEACTIVATE) return MA_NOACTIVATE;
    if (msg==WM_NCHITTEST) return HTTRANSPARENT;
    if (msg==WM_PAINT) {
        PAINTSTRUCT p;HDC dc=BeginPaint(hwnd,&p);
        if (tab_host.thumbnail) {
            HDC src=CreateCompatibleDC(dc);HGDIOBJ old=SelectObject(src,tab_host.thumbnail);
            BitBlt(dc,0,0,tab_host.preview_width,tab_host.preview_height,src,0,0,SRCCOPY);
            SelectObject(src,old);DeleteDC(src);
        }
        EndPaint(hwnd,&p);return 0;
    }
    return DefWindowProcW(hwnd,msg,wp,lp);
}
static void nemo_host_preview(void)
{
    WinGuiSeat *w=tab_host.hover;
    if (!w || w->closing || !conf_get_bool(w->conf,CONF_nemo_tab_preview) ||
        !nemo_host_preview_render(w)) {nemo_host_hide_preview();return;}
    if (!tab_host.preview) tab_host.preview=CreateWindowExW(
        WS_EX_NOACTIVATE|WS_EX_TOOLWINDOW,L"NemotermPreview",L"",
        WS_POPUP,0,0,1,1,tab_host.hwnd,NULL,hinst,NULL);
    if (!tab_host.preview) {nemo_host_hide_preview();return;}
    int index=0;while (nemo_host_item(index)!=w) index++;
    NemoTabRect anchor=nemo_tabs_item(&tab_host.layout,index);
    POINT origin={anchor.x,anchor.y};ClientToScreen(tab_host.hwnd,&origin);
    anchor.x=origin.x;anchor.y=origin.y;
    MONITORINFO mi={0};mi.cbSize=sizeof(mi);
    GetMonitorInfoW(MonitorFromWindow(tab_host.hwnd,MONITOR_DEFAULTTONEAREST),&mi);
    RECT work=mi.rcWork;
    NemoTabRect at=nemo_tabs_preview(anchor,tab_host.side,
        (NemoTabRect){work.left,work.top,work.right-work.left,work.bottom-work.top},
        tab_host.preview_width,tab_host.preview_height,4);
    SetWindowPos(tab_host.preview,HWND_TOP,at.x,at.y,at.width,at.height,SWP_NOACTIVATE|SWP_SHOWWINDOW);
    InvalidateRect(tab_host.preview,NULL,FALSE);
    SetTimer(tab_host.hwnd,1,250,NULL);
}
static void nemo_host_draw_label(HDC dc, NemoTabRect box, const wchar_t *text, COLORREF color)
{
    RECT r=nemo_host_rect(box);SetTextColor(dc,color);
    DrawTextW(dc,text,-1,&r,DT_SINGLELINE|DT_VCENTER|DT_CENTER|DT_END_ELLIPSIS|DT_NOPREFIX);
}
static LRESULT CALLBACK nemo_host_proc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp)
{
    WinGuiSeat *active=tab_host.active;
    switch (msg) {
      case WM_DROPFILES: {
        POINT point;WinGuiSeat *target=active;
        if (DragQueryPoint((HDROP)wp,&point)) {
            NemoTabHit hit=nemo_tabs_hit(&tab_host.layout,point.x,point.y);
            if (hit.kind==NEMO_TAB_BODY || hit.kind==NEMO_TAB_CLOSE) target=nemo_host_item(hit.index);
        }
        nemo_paste_drop(target,(HDROP)wp);DragFinish((HDROP)wp);return 0;
      }
      case WM_ERASEBKGND:return 1;
      case WM_PAINT: {
        PAINTSTRUCT p;HDC dc=BeginPaint(hwnd,&p);
        RECT bar=nemo_host_rect(tab_host.layout.bar);
        HBRUSH bg=CreateSolidBrush(RGB(30,32,36));FillRect(dc,&bar,bg);DeleteObject(bg);
        HGDIOBJ old=SelectObject(dc,tab_host.font);SetBkMode(dc,TRANSPARENT);
        for (int i=tab_host.layout.first;i<tab_host.layout.first+tab_host.layout.visible;i++) {
            WinGuiSeat *w=nemo_host_item(i);if (!w) break;
            NemoTabRect box=nemo_tabs_item(&tab_host.layout,i),close=nemo_tabs_close(&tab_host.layout,i);
            RECT r=nemo_host_rect(box);
            bg=CreateSolidBrush(w==active?RGB(64,68,76):w==tab_host.hover?RGB(46,49,55):RGB(30,32,36));
            FillRect(dc,&r,bg);DeleteObject(bg);
            NemoTabRect label=box;label.x+=8;label.width=max(0,label.width-16-close.width);
            nemo_host_draw_label(dc,label,w->window_name,RGB(238,238,240));
            if (close.width) nemo_host_draw_label(dc,close,L"\x00d7",RGB(190,192,198));
        }
        nemo_host_draw_label(dc,tab_host.layout.add,L"+",RGB(238,238,240));
        nemo_host_draw_label(dc,tab_host.layout.previous,L"\x2039",RGB(238,238,240));
        nemo_host_draw_label(dc,tab_host.layout.next,L"\x203a",RGB(238,238,240));
        SelectObject(dc,old);EndPaint(hwnd,&p);return 0;
      }
      case WM_SIZE:
        nemo_host_hide_preview();
        for (int i=0;i<nemo_host_count();i++) term_notify_minimised(nemo_host_item(i)->term,wp==SIZE_MINIMIZED);
        if (wp!=SIZE_MINIMIZED) nemo_host_layout();return 0;
      case WM_SETFOCUS:if (active) SetFocus(active->term_hwnd);return 0;
      case WM_ACTIVATE:
        if (LOWORD(wp)==WA_INACTIVE) memset(tab_host.consumed_keys,0,sizeof(tab_host.consumed_keys));
        break;
      case WM_MOUSEACTIVATE:return MA_ACTIVATE;
      case WM_LBUTTONDOWN:
      case WM_MBUTTONUP: {
        NemoTabHit hit=nemo_tabs_hit(&tab_host.layout,(short)LOWORD(lp),(short)HIWORD(lp));
        WinGuiSeat *w=nemo_host_item(hit.index);
        nemo_host_hide_preview();
        if (hit.kind==NEMO_TAB_BODY && msg==WM_LBUTTONDOWN) nemo_host_select(w);
        else if (w && (hit.kind==NEMO_TAB_CLOSE || (hit.kind==NEMO_TAB_BODY && msg==WM_MBUTTONUP)))
            PostMessage(w->term_hwnd,WM_CLOSE,0,0);
        else if (hit.kind==NEMO_TAB_ADD && active) nemo_host_new_tab(active);
        else if (hit.kind==NEMO_TAB_PREVIOUS || hit.kind==NEMO_TAB_NEXT) {
            tab_host.first+=hit.kind==NEMO_TAB_NEXT?1:-1;nemo_host_layout();
        }
        return 0;
      }
      case WM_MOUSEWHEEL:
        tab_host.first+=(short)HIWORD(wp)>0?-1:1;
        nemo_host_hide_preview();nemo_host_layout();return 0;
      case WM_MOUSEMOVE: {
        NemoTabHit hit=nemo_tabs_hit(&tab_host.layout,(short)LOWORD(lp),(short)HIWORD(lp));
        WinGuiSeat *hover=(hit.kind==NEMO_TAB_BODY || hit.kind==NEMO_TAB_CLOSE)?nemo_host_item(hit.index):NULL;
        if (hover!=tab_host.hover) {
            nemo_host_hide_preview();tab_host.hover=hover;
            if (hover) SetTimer(hwnd,1,400,NULL);
            RECT bar=nemo_host_rect(tab_host.layout.bar);InvalidateRect(hwnd,&bar,FALSE);
        }
        TRACKMOUSEEVENT track={sizeof(track),TME_LEAVE,hwnd,0};TrackMouseEvent(&track);return 0;
      }
      case WM_MOUSELEAVE:nemo_host_hide_preview();InvalidateRect(hwnd,NULL,FALSE);return 0;
      case WM_TIMER:if (wp==1) nemo_host_preview();return 0;
      case WM_DPICHANGED: {
        tab_host.dpi=LOWORD(wp);RECT *r=(RECT *)lp;nemo_host_font();
        for (int i=0;i<nemo_host_count();i++) {
            WinGuiSeat *w=nemo_host_item(i);w->dpi_info.cur_dpi.x=LOWORD(wp);w->dpi_info.cur_dpi.y=HIWORD(wp);
            term_end_synchronized_update(w->term);deinit_fonts(w);init_fonts(w,0,0);
        }
        SetWindowPos(hwnd,NULL,r->left,r->top,r->right-r->left,r->bottom-r->top,SWP_NOZORDER|SWP_NOACTIVATE);
        nemo_host_layout();return 0;
      }
      case WM_COMMAND:case WM_INITMENUPOPUP:
        if (active) return SendMessage(active->term_hwnd,msg,wp,lp);return 0;
      case WM_SYSCOMMAND:
        if (wp<0xF000 && active) return SendMessage(active->term_hwnd,msg,wp,lp);break;
      case WM_SIZING:
        if (active) return SendMessage(active->term_hwnd,msg,wp,lp);break;
      case WM_ENTERSIZEMOVE:case WM_EXITSIZEMOVE:case WM_MOVE:
        if (active) SendMessage(active->term_hwnd,msg,wp,lp);break;
      case WM_CLOSE: {
        bool warn=false;
        for (int i=0;i<nemo_host_count();i++) {
            WinGuiSeat *w=nemo_host_item(i);
            warn|=!w->session_closed && conf_get_bool(w->conf,CONF_warn_on_close);
        }
        if (warn && MessageBoxW(hwnd,L"Close this window and all its terminal tabs?",L"Nemoterm",
                                MB_OKCANCEL|MB_ICONWARNING)!=IDOK) return 0;
        for (int i=nemo_host_count()-1;i>=0;i--) wgs_request_close(nemo_host_item(i));
        return 0;
      }
      case WM_DESTROY:
        tab_host.destroying=true;nemo_host_hide_preview();
        /* Parent WM_DESTROY precedes child destruction. Release borrowed
         * submenus before child WM_DESTROY can free their owning menus.
         * Keep active until seat cleanup retires the shared GPU device. */
        nemo_host_detach_menu();
        for (int i=nemo_host_count()-1;i>=0;i--) wgs_request_close(nemo_host_item(i));
        return 0;
    }
    return DefWindowProcW(hwnd,msg,wp,lp);
}
static bool nemo_host_create(Conf *conf, int width, int height)
{
    if (tab_host.hwnd) return true;
    WNDCLASSW wc={0};wc.hInstance=hinst;wc.hCursor=LoadCursor(NULL,IDC_ARROW);
    wc.hIcon=LoadIcon(hinst,MAKEINTRESOURCE(IDI_MAINICON));
    wc.lpszClassName=L"NemotermHost";wc.lpfnWndProc=nemo_host_proc;RegisterClassW(&wc);
    wc.lpszClassName=L"NemotermPreview";wc.lpfnWndProc=nemo_preview_proc;RegisterClassW(&wc);
    tab_host.side=conf_get_int(conf,CONF_nemo_tab_side);
    tab_host.sidebar=conf_get_int(conf,CONF_nemo_tab_sidebar);tab_host.dpi=96;
    nemo_host_font();
    tab_host.hwnd=CreateWindowExW(WS_EX_ACCEPTFILES|(conf_get_bool(conf,CONF_alwaysontop)?WS_EX_TOPMOST:0),
        L"NemotermHost",L"Nemoterm",WS_OVERLAPPEDWINDOW|WS_CLIPCHILDREN,
        CW_USEDEFAULT,CW_USEDEFAULT,width,height,NULL,NULL,hinst,NULL);
    return tab_host.hwnd!=NULL;
}
