/* SPDX-License-Identifier: MIT */
#include "nemo_drop.h"
#include "nemo_shell.h"
#include <wchar.h>

static int drop_shell(Conf *conf)
{
    bool utf8;
    const char *id=conf_get_str(conf,CONF_nemo_shell);
    const char *cmd=conf_get_str_ambi(conf,CONF_remote_cmd,&utf8);
    if (!*cmd && !strcmp(id,"custom")) cmd=conf_get_str_ambi(conf,CONF_nemo_shell_command,&utf8);
    if (*cmd) {
        wchar_t *wide=dup_mb_to_wc(utf8?CP_UTF8:CP_ACP,cmd);
        int argc;wchar_t **argv=CommandLineToArgvW(wide,&argc);sfree(wide);
        int selected=-1;
        if (argv && argc) {
            const wchar_t *name=argv[0];
            for (const wchar_t *p=name;*p;p++) if (*p=='\\' || *p=='/') name=p+1;
            if (!_wcsicmp(name,L"pwsh.exe") || !_wcsicmp(name,L"pwsh")) selected=NEMO_PWSH;
            else if (!_wcsicmp(name,L"powershell.exe") || !_wcsicmp(name,L"powershell")) selected=NEMO_POWERSHELL;
            else if (!_wcsicmp(name,L"cmd.exe") || !_wcsicmp(name,L"cmd")) selected=NEMO_CMD;
            else if (!_wcsicmp(name,L"wsl.exe") || !_wcsicmp(name,L"wsl")) selected=NEMO_WSL_BASH;
            else if (!_wcsicmp(name,L"bash.exe") || !_wcsicmp(name,L"bash")) selected=NEMO_GIT_BASH;
            else if (!_wcsicmp(name,L"busybox.exe") || !_wcsicmp(name,L"ash.exe") ||
                     !_wcsicmp(name,L"sh.exe")) selected=NEMO_BUSYBOX;
        }
        if (argv) LocalFree(argv);
        if (selected>=0) return selected;
    }
    int index=nemo_shell_index(id);
    if (index>=0) return index;
    NemoShellList shells;nemo_shell_detect(&shells);
    const int preferred[]={NEMO_PWSH,NEMO_POWERSHELL,NEMO_CMD,NEMO_BUSYBOX,NEMO_GIT_BASH,NEMO_WSL_BASH};
    index=NEMO_CMD;
    for (size_t i=0;i<lenof(preferred);i++) if (shells.paths[preferred[i]]) {index=preferred[i];break;}
    nemo_shell_free(&shells);return index;
}
static bool append_path(strbuf *out,const wchar_t *path,int shell)
{
    size_t n=wcslen(path);
    if (!n || n>32767) return false;
    for (size_t i=0;i<n;i++) if (path[i]<32 || path[i]==127 || path[i]=='"') return false;
    if (!WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,path,(int)n,NULL,0,NULL,NULL)) return false;
    char *utf8=dup_wc_to_mb(CP_UTF8,path,NULL),*text=utf8;
    bool posix=shell==NEMO_GIT_BASH || shell==NEMO_BUSYBOX || shell==NEMO_WSL_BASH;
    if (out->len) put_byte(out,' ');
    if (posix) {
        for (char *p=utf8;*p;p++) if (*p=='\\') *p='/';
        put_byte(out,'\'');
        if (shell==NEMO_WSL_BASH && strlen(text)>=3 &&
            ((text[0]>='A' && text[0]<='Z') || (text[0]>='a' && text[0]<='z')) &&
            text[1]==':' && text[2]=='/') {
            put_fmt(out,"/mnt/%c",text[0]>='A' && text[0]<='Z'?text[0]+32:text[0]);text+=2;
        }
        for (;*text;text++) {
            if (*text=='\'') put_dataz(out,"'\\''");else put_byte(out,*text);
        }
        put_byte(out,'\'');
    } else if (shell==NEMO_CMD) {
        put_byte(out,'"');put_dataz(out,text);
        /* Preserve a trailing slash when a Windows argv parser consumes the
         * closing quote. Quotes inside Windows filenames were rejected above. */
        for (size_t i=strlen(text);i && text[i-1]=='\\';i--) put_byte(out,'\\');
        put_byte(out,'"');
    } else {
        put_byte(out,'\'');
        for (;*text;text++) {put_byte(out,*text);if (*text=='\'') put_byte(out,'\'');}
        put_byte(out,'\'');
    }
    sfree(utf8);return out->len<=65536;
}
wchar_t *nemo_drop_paths(HDROP drop,Conf *conf,size_t *length)
{
    /* Validate the entire DROPFILES block before asking shell32 to read it.
     * Clipboard data is not necessarily produced by Explorer. */
    typedef struct {DWORD offset;POINT point;BOOL nonclient,wide;} DropHeader;
    SIZE_T bytes=GlobalSize(drop);
    if (bytes<sizeof(DropHeader)+2 || bytes>1024*1024) return NULL;
    const unsigned char *data=GlobalLock(drop);if (!data) return NULL;
    DropHeader header;memcpy(&header,data,sizeof(header));
    bool valid=header.offset>=sizeof(header) && header.offset<bytes;
    unsigned unit=header.wide?2:1;
    if (header.wide && (header.offset&1)) valid=false;
    size_t start=header.offset,at=start,count=0;
    bool ended=false;
    while (valid && at+unit<=bytes) {
        unsigned ch=data[at];if (unit==2) ch|=(unsigned)data[at+1]<<8;
        at+=unit;
        if (ch) continue;
        if (at-unit==start) {ended=true;break;}
        if (++count>1024 || (at-start)/unit>32768) {valid=false;break;}
        start=at;
    }
    GlobalUnlock(drop);
    if (!valid || !ended || !count || DragQueryFileW(drop,0xffffffff,NULL,0)!=count) return NULL;
    strbuf *out=strbuf_new();int shell=drop_shell(conf);
    for (UINT i=0;i<count;i++) {
        UINT n=DragQueryFileW(drop,i,NULL,0);
        if (!n || n>32767) {valid=false;break;}
        wchar_t *path=snewn((size_t)n+1,wchar_t);
        bool ok=DragQueryFileW(drop,i,path,n+1)==n && append_path(out,path,shell);
        sfree(path);if (!ok) {valid=false;break;}
    }
    wchar_t *result=valid?dup_mb_to_wc(CP_UTF8,out->s):NULL;
    strbuf_free(out);
    if (result) *length=wcslen(result);
    return result;
}
