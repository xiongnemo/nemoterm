/* SPDX-License-Identifier: MIT
 * UI-thread half of the opt-in automation interface. No clipboard or focus
 * changes. Never retain a seat pointer across requests or pump messages here.
 */
static void nemo_debug_json_string(strbuf *out, const char *value)
{
    put_byte(out,'"');
    for (const unsigned char *p=(const unsigned char *)value;*p;p++) {
        if (*p=='"' || *p=='\\') put_byte(out,'\\');
        if (*p<32) put_fmt(out,"\\u%04x",*p);else put_byte(out,*p);
    }
    put_byte(out,'"');
}
static void nemo_debug_error(NemoDebugRequest *r,unsigned status,const char *message)
{
    r->status=status;r->kind=1;strbuf_clear(r->output);
    put_dataz(r->output,"{\"error\":");nemo_debug_json_string(r->output,message);
    put_byte(r->output,'}');
}
static bool nemo_debug_screen(WinGuiSeat *wgs,strbuf *out)
{
    Terminal *term=wgs->term;
    /* Logical visible rows, including combining characters and wide cells.
     * Use the same legacy character-set maps as clipboard extraction. */
    for (int y=0;y<term->rows;y++) {
        termline *line=term_get_line(term,term->disptop+y);
        for (int x=0;x<min(term->cols,line->cols);x++) {
            int index=x;
            if (line->chars[index].chr==UCSWIDE) continue;
            do {
                unsigned uc=line->chars[index].chr;
                switch (uc&CSET_MASK) {
                  case CSET_LINEDRW: uc=term->ucsdata->unitab_xterm[uc&255];break;
                  case CSET_ASCII: uc=term->ucsdata->unitab_line[uc&255];break;
                  case CSET_SCOACS: uc=term->ucsdata->unitab_scoacs[uc&255];break;
                }
                switch (uc&CSET_MASK) {
                  case CSET_ACP: uc=term->ucsdata->unitab_font[uc&255];break;
                  case CSET_OEMCP: uc=term->ucsdata->unitab_oemcp[uc&255];break;
                }
                if (DIRECT_FONT(uc)) {
                    char byte=(char)(uc&255);wchar_t wide=0xfffd;
                    MultiByteToWideChar((uc&CSET_MASK)==CSET_OEMCP?CP_OEMCP:
                        term->ucsdata->font_codepage,0,&byte,1,&wide,1);uc=wide;
                }
                if (uc>0x10ffff || (uc>=0xd800 && uc<=0xdfff)) uc=0xfffd;
                put_utf8_char(out,uc);
                if (out->len>1024*1024) {term_release_line(line);return false;}
                if (!line->chars[index].cc_next) break;
                index+=line->chars[index].cc_next;
            } while (true);
        }
        put_byte(out,'\n');term_release_line(line);
    }
    return true;
}
static bool nemo_debug_image(WinGuiSeat *wgs,strbuf *out)
{
    RECT rect;if (!GetClientRect(wgs->term_hwnd,&rect)) return false;
    int width=rect.right,height=rect.bottom;
    if (width<=0 || height<=0 || width>8192 || height>8192 ||
        (size_t)width*height*4>NEMO_DEBUG_MAX_OUTPUT-54) return false;
    size_t bytes=(size_t)width*height*4;
    BITMAPINFO bi={0};bi.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);
    bi.bmiHeader.biWidth=width;bi.bmiHeader.biHeight=-height;
    bi.bmiHeader.biPlanes=1;bi.bmiHeader.biBitCount=32;
    HDC dc=CreateCompatibleDC(NULL);if (!dc) return false;
    void *pixels=NULL;
    HBITMAP bitmap=CreateDIBSection(dc,&bi,DIB_RGB_COLORS,&pixels,NULL,0);
    if (!bitmap) {DeleteDC(dc);return false;}
    HGDIOBJ old=SelectObject(dc,bitmap);
    bool ok=old && old!=HGDI_ERROR;
    if (ok) {
        memset(pixels,0,bytes);
        if (wgs_active(wgs))
            SendMessageW(wgs->term_hwnd,WM_PRINTCLIENT,(WPARAM)dc,PRF_CLIENT);
        else {
            ok=nemo_render_snapshot_band(dc,0,height,wgs);
            term_invalidate(wgs->term);
        }
        GdiFlush();
        if (ok) {
            unsigned char header[54]={0};header[0]='B';header[1]='M';
            PUT_32BIT_LSB_FIRST(header+2,54+bytes);PUT_32BIT_LSB_FIRST(header+10,54);
            PUT_32BIT_LSB_FIRST(header+14,40);PUT_32BIT_LSB_FIRST(header+18,width);
            PUT_32BIT_LSB_FIRST(header+22,-height);PUT_16BIT_LSB_FIRST(header+26,1);
            PUT_16BIT_LSB_FIRST(header+28,32);PUT_32BIT_LSB_FIRST(header+34,bytes);
            put_data(out,header,sizeof(header));put_data(out,pixels,bytes);
        }
        SelectObject(dc,old);
    }
    DeleteObject(bitmap);DeleteDC(dc);return ok;
}
static void nemo_debug_ui(NemoDebugRequest *r)
{
    if (r->op==NDBG_LIST) {
        if (r->session || r->input->len) {
            nemo_debug_error(r,1,"list expects no session or payload");return;
        }
        put_fmt(r->output,"{\"version\":1,\"pid\":%lu,\"sessions\":[",GetCurrentProcessId());
        bool first=true;
        for (struct WinGuiSeatListNode *n=wgslisthead.next;n!=&wgslisthead;n=n->next) {
            WinGuiSeat *wgs=container_of(n,WinGuiSeat,wgslistnode);
            if (wgs->closing || !wgs->term || !wgs->term_hwnd) continue;
            if (r->output->len>1024*1024) {
                nemo_debug_error(r,3,"session list exceeds size limit");return;
            }
            if (!first) put_byte(r->output,',');first=false;
            put_fmt(r->output,"{\"id\":%llu,\"hwnd\":%llu,\"window\":%llu,"
                "\"active\":%s,\"cols\":%d,\"rows\":%d,\"renderer\":%d,\"title\":",
                (unsigned long long)wgs->session_id,(unsigned long long)(UINT_PTR)wgs->term_hwnd,
                (unsigned long long)(UINT_PTR)wgs_window(wgs),wgs_active(wgs)?"true":"false",
                wgs->term->cols,wgs->term->rows,
                (int)(UINT_PTR)GetPropW(wgs->term_hwnd,L"NemotermRenderer")-1);
            wchar_t title[1024];GetWindowTextW(wgs->term_hwnd,title,lenof(title));
            char *utf8=dup_wc_to_mb(CP_UTF8,title,NULL);nemo_debug_json_string(r->output,utf8);sfree(utf8);
            put_byte(r->output,'}');
        }
        put_dataz(r->output,"]}");return;
    }
    WinGuiSeat *wgs=NULL;
    for (struct WinGuiSeatListNode *n=wgslisthead.next;n!=&wgslisthead;n=n->next) {
        WinGuiSeat *candidate=container_of(n,WinGuiSeat,wgslistnode);
        if (candidate->session_id==r->session && !candidate->closing && candidate->term)
            wgs=candidate;
    }
    if (!wgs) {nemo_debug_error(r,2,"session no longer exists");return;}
    if (r->op==NDBG_TEXT || r->op==NDBG_IMAGE) {
        if (r->input->len) {nemo_debug_error(r,1,"capture expects no payload");return;}
        r->kind=r->op==NDBG_TEXT?3:2;
        bool ok=r->op==NDBG_TEXT?nemo_debug_screen(wgs,r->output):nemo_debug_image(wgs,r->output);
        if (!ok) nemo_debug_error(r,3,"capture failed or exceeds size limit");
        return;
    }
    if (!wgs->backend || !wgs->ldisc || wgs->session_closed) {
        nemo_debug_error(r,2,"session input is closed");return;
    }
    if (r->op==NDBG_INPUT || r->op==NDBG_PASTE) {
        if (r->input->len) {
            int count=MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,r->input->s,
                (int)r->input->len,NULL,0);
            if (!count) {nemo_debug_error(r,1,"input must be valid UTF-8");return;}
            wchar_t *text=snewn(count,wchar_t);
            MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,r->input->s,(int)r->input->len,text,count);
            if (r->op==NDBG_PASTE) term_do_paste(wgs->term,text,count);
            else term_keyinputw(wgs->term,text,count);
            sfree(text);
        }
    } else if (r->op==NDBG_KEY) {
        if (r->input->len!=8) {nemo_debug_error(r,1,"key expects virtual key and modifiers");return;}
        unsigned vk=GET_32BIT_LSB_FIRST(r->input->s),mods=GET_32BIT_LSB_FIRST(r->input->s+4);
        if (!vk || vk>=256 || mods>7 || vk==VK_PACKET || vk==VK_PROCESSKEY) {
            nemo_debug_error(r,1,"unsupported key or modifiers");return;
        }
        BYTE saved[256],state[256]={0};
        if (!GetKeyboardState(saved)) {nemo_debug_error(r,3,"keyboard state unavailable");return;}
        if (mods&1) state[VK_SHIFT]=state[VK_LSHIFT]=0x80;
        if (mods&2) state[VK_CONTROL]=state[VK_LCONTROL]=0x80;
        if (mods&4) state[VK_MENU]=state[VK_LMENU]=0x80;
        unsigned scan=MapVirtualKeyExW(vk,MAPVK_VK_TO_VSC_EX,GetKeyboardLayout(0));
        LPARAM lp=1|((scan&255)<<16)|((scan&0xff00)?1<<24:0)|((mods&4)?1<<29:0);
        state[vk]=0x80;
        if (!SetKeyboardState(state)) {nemo_debug_error(r,3,"keyboard state unavailable");return;}
        SendMessageW(wgs->term_hwnd,(mods&4)?WM_SYSKEYDOWN:WM_KEYDOWN,vk,lp);
        state[vk]=0;SetKeyboardState(state);
        SendMessageW(wgs->term_hwnd,(mods&4)?WM_SYSKEYUP:WM_KEYUP,vk,lp|(LPARAM)0xc0000000);
        SetKeyboardState(saved);
    } else {nemo_debug_error(r,1,"unknown operation");return;}
    put_dataz(r->output,"{\"accepted\":true}");
}
