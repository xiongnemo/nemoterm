/* SPDX-License-Identifier: MIT */
#include "putty.h"
#include "nemo_cwd.h"
#include <ctype.h>

static bool utf8_path(const char *s, size_t n)
{
    if (n > NEMO_CWD_PATH_MAX) return false;
    for (size_t i=0; i<n;) {
        unsigned c=(unsigned char)s[i++], value, count, minimum;
        if (c < 32 || c == 127) return false;
        if (c < 128) continue;
        if (c >= 0xc2 && c <= 0xdf) { value=c&31; count=1; minimum=0x80; }
        else if (c >= 0xe0 && c <= 0xef) { value=c&15; count=2; minimum=0x800; }
        else if (c >= 0xf0 && c <= 0xf4) { value=c&7; count=3; minimum=0x10000; }
        else return false;
        if (count > n-i) return false;
        while (count--) {
            c=(unsigned char)s[i++]; if ((c&0xc0)!=0x80) return false;
            value=(value<<6)|(c&63);
        }
        if (value < minimum || value > 0x10ffff ||
            (value >= 0xd800 && value <= 0xdfff)) return false;
    }
    return true;
}
static int hex(unsigned char c)
{
    if (c >= '0' && c <= '9') return c-'0';
    if (c >= 'a' && c <= 'f') return c-'a'+10;
    if (c >= 'A' && c <= 'F') return c-'A'+10;
    return -1;
}
/* URI percent encoding and VS Code's \\ / \xHH escaping are single-pass. */
static char *decode(const char *s, size_t n, int mode)
{
    if (n > NEMO_CWD_OSC_MAX) return NULL;
    char *out=snewn(n+1,char); size_t used=0;
    for (size_t i=0; i<n; i++) {
        unsigned char c=s[i];
        if (mode==1 && c=='%') {
            if (n-i<3 || hex(s[i+1])<0 || hex(s[i+2])<0) goto bad;
            c=(hex(s[i+1])<<4)|hex(s[i+2]); i+=2;
        } else if (mode==2 && c=='\\') {
            if (i+1<n && s[i+1]=='\\') { c='\\'; i++; }
            else if (n-i>=4 && (s[i+1]=='x'||s[i+1]=='X') && hex(s[i+2])>=0 && hex(s[i+3])>=0) {
                c=(hex(s[i+2])<<4)|hex(s[i+3]); i+=3;
            } else goto bad;
        }
        out[used++]=c;
    }
    out[used]=0;
    if (!utf8_path(out,used)) goto bad;
    return out;
  bad:
    sfree(out); return NULL;
}
static bool host_valid(const char *s, size_t n)
{
    if (n>NEMO_CWD_HOST_MAX) return false;
    if (n && s[0]=='[') {
        if (n<4 || s[n-1]!=']') return false;
        for (size_t i=1;i+1<n;i++)
            if (hex(s[i])<0 && s[i]!=':' && s[i]!='.') return false;
        return true;
    }
    for (size_t i=0;i<n;i++) {
        unsigned c=(unsigned char)s[i];
        if (!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='.'||c=='-'||c=='_')) return false;
    }
    return true;
}
static bool drive_path(const char *s)
{
    return s && strlen(s)>=3 && ((s[0]>='A'&&s[0]<='Z')||(s[0]>='a'&&s[0]<='z')) &&
        s[1]==':' && (s[2]=='/'||s[2]=='\\');
}
static bool absolute_path(const char *s)
{
    return !*s || s[0]=='/' || drive_path(s); /* UNC cannot become a local cwd. */
}
void nemo_cwd_clear(NemoCwd *cwd)
{
    sfree(cwd->path); sfree(cwd->host); memset(cwd,0,sizeof(*cwd));
}
size_t nemo_cwd_memory(const NemoCwd *cwd)
{
    return (cwd->path ? strlen(cwd->path)+1 : 0)+(cwd->host ? strlen(cwd->host)+1 : 0);
}
bool nemo_cwd_update(NemoCwd *cwd, unsigned osc, const char *s, size_t n)
{
    char *path=NULL,*host=NULL; bool replace_host=false;
    if (n>NEMO_CWD_OSC_MAX || memchr(s,0,n)) return false;
    if (osc==7) {
        if (n<8 || memcmp(s,"file://",7)) return false;
        const char *slash=memchr(s+7,'/',n-7);
        if (!slash || memchr(s,'?',n) || memchr(s,'#',n) || memchr(s,'\\',n)) return false;
        size_t h=(size_t)(slash-(s+7));
        if (!host_valid(s+7,h)) return false;
        host=mkstr(make_ptrlen(s+7,h)); replace_host=true;
        path=decode(slash,n-(size_t)(slash-s),1);
    } else if (osc==9) {
        if (n<2 || memcmp(s,"9;",2)) return false;
        s+=2;n-=2;
        if (n>=2 && s[0]=='"' && s[n-1]=='"') { s++;n-=2; }
        path=decode(s,n,0); host=dupstr("");replace_host=true;
    } else if (osc==633) {
        static const char prefix[]="P;Cwd=";
        if (n<sizeof(prefix)-1 || memcmp(s,prefix,sizeof(prefix)-1)) return false;
        s+=sizeof(prefix)-1;n-=sizeof(prefix)-1;
        /* A following nonce is metadata, never part of the path or a command. */
        const char *sep=memchr(s,';',n); if (sep) n=(size_t)(sep-s);
        path=decode(s,n,2); host=dupstr("");replace_host=true;
    } else if (osc==1337) {
        if (n>=11 && !memcmp(s,"CurrentDir=",11)) path=decode(s+11,n-11,0);
        else if (n>=11 && !memcmp(s,"RemoteHost=",11)) {
            s+=11;n-=11;const char *at=memchr(s,'@',n);
            if (at) { n-=(size_t)(at+1-s);s=at+1; }
            if (!host_valid(s,n)) return false;
            host=mkstr(make_ptrlen(s,n));sfree(cwd->host);cwd->host=host;return true;
        } else return false;
    } else return false;
    if (!path || !absolute_path(path)) { sfree(path);sfree(host);return false; }
    sfree(cwd->path);cwd->path=path;
    if (replace_host) { sfree(cwd->host);cwd->host=host; }
    return true;
}
bool nemo_cwd_local(const NemoCwd *cwd, const char *hostname, const char *fqdn)
{
    const char *h=cwd->host;
    return !h || !*h || !stricmp(h,"localhost") || !strcmp(h,"127.0.0.1") || !strcmp(h,"[::1]") ||
        (hostname && *hostname && !stricmp(h,hostname)) || (fqdn && *fqdn && !stricmp(h,fqdn));
}
char *nemo_cwd_uri(const NemoCwd *cwd)
{
    if (!cwd->path || !*cwd->path) return NULL;
    const char *host=cwd->host?cwd->host:"", *path=cwd->path;
    bool drive=drive_path(path);
    char *out=snewn(8+strlen(host)+1+3*strlen(path)+1,char),*p=out;
    p+=sprintf(p,"file://%s%s",host,drive?"/":"");
    static const char digits[]="0123456789ABCDEF";
    for (;*path;path++) {
        unsigned char c=*path;if (drive && c=='\\') c='/';
        if ((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||strchr("-._~/:",c)) *p++=c;
        else { *p++='%';*p++=digits[c>>4];*p++=digits[c&15]; }
    }
    *p=0;return out;
}
char *nemo_cwd_native(const NemoCwd *cwd, const char *hostname, const char *fqdn, bool msys)
{
    if (!cwd->path || !nemo_cwd_local(cwd,hostname,fqdn)) return NULL;
    const char *p=cwd->path;
    if (p[0]=='/' && drive_path(p+1)) p++;
    char *out=NULL;
    if (drive_path(p)) out=dupstr(p);
    else if (msys && strlen(p)>=3 && p[0]=='/' && ((p[1]>='a'&&p[1]<='z')||(p[1]>='A'&&p[1]<='Z')) && p[2]=='/') {
        out=dupprintf("%c:%s",p[1],p+2);
    }
    if (!out) return NULL;
    for (size_t i=2;out[i];i++) {
        if (strchr("<>:\"|?*",out[i])) { sfree(out);return NULL; }
        if (out[i]=='/') out[i]='\\';
    }
    return out;
}
