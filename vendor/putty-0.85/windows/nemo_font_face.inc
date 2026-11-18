/* SPDX-License-Identifier: MIT. Profile permissions are enforced in terminal.c. */
static bool nemo_mapped_face(WinGuiSeat *wgs, HFONT font, wchar_t face[LF_FACESIZE])
{
    if (!font) return false;
    HDC dc = GetDC(wgs->term_hwnd);
    if (!dc) return false;
    HGDIOBJ old = SelectObject(dc,font);
    bool ok = old && old != HGDI_ERROR && GetTextFaceW(dc,LF_FACESIZE,face) > 0;
    if (old && old != HGDI_ERROR) SelectObject(dc,old);
    ReleaseDC(wgs->term_hwnd,dc);
    return ok;
}

static bool nemo_safe_face(const wchar_t *name)
{
    if (!*name) return false;
    for (; *name; name++)
        if (*name < 32 || (*name >= 127 && *name <= 159)) return false;
    return true;
}

static bool wintw_get_font_face(TermWin *tw, char *utf8, size_t capacity)
{
    WinGuiSeat *wgs = container_of(tw,WinGuiSeat,termwin);
    wchar_t face[LF_FACESIZE];
    return nemo_mapped_face(wgs,wgs->fonts[FONT_NORMAL],face) && nemo_safe_face(face) &&
        WideCharToMultiByte(CP_UTF8,0,face,-1,utf8,(int)capacity,NULL,NULL)>0;
}

static void wintw_set_font_face(TermWin *tw, const char *utf8)
{
    WinGuiSeat *wgs = container_of(tw,WinGuiSeat,termwin);
    wchar_t requested[LF_FACESIZE], mapped[LF_FACESIZE];
    if (!wgs->term || wgs->closing ||
        !MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,utf8,-1,requested,LF_FACESIZE) ||
        !nemo_safe_face(requested)) return;
    if (nemo_mapped_face(wgs,wgs->fonts[FONT_NORMAL],mapped) && !_wcsicmp(mapped,requested)) return;
    /* GDI silently supplies a substitute for a missing family. Validate the
     * new realization before dropping the live fonts, caches or selection. */
    LOGFONTW lf;
    if (!GetObjectW(wgs->fonts[FONT_NORMAL],sizeof(lf),&lf)) return;
    wcscpy(lf.lfFaceName,requested);
    HFONT probe = CreateFontIndirectW(&lf);
    if (!probe) return;
    bool match = nemo_mapped_face(wgs,probe,mapped) && !_wcsicmp(mapped,requested);
    DeleteObject(probe);
    if (!match) return;
    wcscpy(wgs->app_font_face,mapped);
    nemo_rebuild_view_font(wgs);
}
