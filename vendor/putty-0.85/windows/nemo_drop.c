/* SPDX-License-Identifier: MIT */
/* CompareStringOrdinal compares Explorer share names without using the UI locale. */
#if !defined(_WIN32_WINNT) || _WIN32_WINNT < 0x0600
#undef _WIN32_WINNT
#define _WIN32_WINNT 0x0600
#endif
#include "nemo_drop.h"
#include "nemo_shell.h"
#include <wchar.h>

/* Only use the profile to break a tie for an unrecognized command (for
 * example a TUI started directly, with --shell specifying its syntax). */
static int profile_shell(Conf *conf)
{
    const char *id=conf_get_str(conf,CONF_nemo_shell);
    int index=nemo_shell_index(id);
    if (index>=0) return index;
    NemoShellList shells;nemo_shell_detect(&shells);
    const int preferred[]={NEMO_PWSH,NEMO_POWERSHELL,NEMO_CMD,NEMO_BUSYBOX,NEMO_GIT_BASH,NEMO_WSL_BASH};
    index=NEMO_CMD;
    for (size_t i=0;i<lenof(preferred);i++) if (shells.paths[preferred[i]]) {index=preferred[i];break;}
    nemo_shell_free(&shells);return index;
}
static wchar_t *launch_distro(wchar_t *const *argv, int argc)
{
    const wchar_t *distro=NULL;
    for (int i=1;i<argc;i++) {
        const wchar_t *arg=argv[i];
        /* Options after a command or --exec belong to the Linux program. */
        if (!wcscmp(arg,L"--exec") || !wcscmp(arg,L"-e") || !wcscmp(arg,L"--") || *arg!=L'-') break;
        if (!wcscmp(arg,L"-d") || !wcscmp(arg,L"--distribution")) {
            if (distro || ++i>=argc || !*argv[i]) return NULL;
            distro=argv[i];continue;
        }
        if (!wcscmp(arg,L"--cd") || !wcscmp(arg,L"--user") || !wcscmp(arg,L"-u") || !wcscmp(arg,L"--shell-type")) {
            if (++i>=argc) return NULL;
            continue;
        }
        if (!wcscmp(arg,L"--login")) continue;
        /* --system, --debug-shell or an unknown launch mode: no identity. */
        return NULL;
    }
    return distro?dupwcs(distro):nemo_shell_default_wsl_distribution();
}

void nemo_drop_target_init(NemoDropTarget *t,Conf *conf,const wchar_t *command,int shell)
{
    int argc=0;wchar_t **argv=command?CommandLineToArgvW(command,&argc):NULL;
    bool wsl_command=false;
    sfree(t->distro);t->distro=NULL;
    if (argv && argc) {
        const wchar_t *name=argv[0];
        for (const wchar_t *p=name;*p;p++) if (*p==L'\\' || *p==L'/') name=p+1;
        wsl_command=!_wcsicmp(name,L"wsl.exe") || !_wcsicmp(name,L"wsl");
        if (shell<0) {
            if (wsl_command) shell=NEMO_WSL_BASH;
            else if (!_wcsicmp(name,L"pwsh.exe") || !_wcsicmp(name,L"pwsh")) shell=NEMO_PWSH;
            else if (!_wcsicmp(name,L"powershell.exe") || !_wcsicmp(name,L"powershell")) shell=NEMO_POWERSHELL;
            else if (!_wcsicmp(name,L"cmd.exe") || !_wcsicmp(name,L"cmd")) shell=NEMO_CMD;
            else if (!_wcsicmp(name,L"bash.exe") || !_wcsicmp(name,L"bash")) shell=NEMO_GIT_BASH;
            else if (!_wcsicmp(name,L"busybox.exe") || !_wcsicmp(name,L"ash.exe") || !_wcsicmp(name,L"sh.exe")) shell=NEMO_BUSYBOX;
        }
    }
    t->shell=shell>=0?shell:profile_shell(conf);
    if (wsl_command && t->shell==NEMO_WSL_BASH) t->distro=launch_distro(argv,argc);
    if (argv) LocalFree(argv);
    t->ready=true;
}

/* Resolve only Explorer's two WSL namespaces. Never strip a foreign
 * distribution or treat similarly named remote servers as the local root. */
static const wchar_t *wsl_share_path(const wchar_t *path,const wchar_t *distro)
{
    const wchar_t *p=path;
    if (!_wcsnicmp(p,L"\\\\?\\UNC\\",8)) p+=8;
    else if (p[0]==L'\\' && p[1]==L'\\') p+=2;
    else return path;
    size_t n=wcscspn(p,L"\\/");
    if (!((n==4 && !_wcsnicmp(p,L"wsl$",4)) || (n==13 && !_wcsnicmp(p,L"wsl.localhost",13)))) return path;
    if (!p[n] || !distro) return NULL;
    p+=n+1;n=wcscspn(p,L"\\/");
    if (!n || n!=wcslen(distro) || CompareStringOrdinal(p,(int)n,distro,(int)n,TRUE)!=CSTR_EQUAL) return NULL;
    return p[n]?p+n:L"/";
}
static bool append_path(strbuf *out,const wchar_t *path,int shell,const wchar_t *distro)
{
    size_t n=wcslen(path);
    if (!n || n>32767) return false;
    for (size_t i=0;i<n;i++) if (path[i]<32 || path[i]==127 || path[i]=='"') return false;
    if (!WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,path,(int)n,NULL,0,NULL,NULL)) return false;
    if (shell==NEMO_WSL_BASH) {
        path=wsl_share_path(path,distro);
        if (!path) return false;
    }
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
wchar_t *nemo_drop_paths(HDROP drop,Conf *conf,const NemoDropTarget *target,size_t *length)
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
    strbuf *out=strbuf_new();int shell=target->ready?target->shell:profile_shell(conf);
    for (UINT i=0;i<count;i++) {
        UINT n=DragQueryFileW(drop,i,NULL,0);
        if (!n || n>32767) {valid=false;break;}
        wchar_t *path=snewn((size_t)n+1,wchar_t);
        bool ok=DragQueryFileW(drop,i,path,n+1)==n && append_path(out,path,shell,target->distro);
        sfree(path);if (!ok) {valid=false;break;}
    }
    wchar_t *result=valid?dup_mb_to_wc(CP_UTF8,out->s):NULL;
    strbuf_free(out);
    if (result) *length=wcslen(result);
    return result;
}
