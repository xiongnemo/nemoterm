/* SPDX-License-Identifier: MIT */
#include "putty.h"
#include "nemo_shell_marks.h"

static NemoShellCommand *lookup(NemoShellMarks *m, uint64_t id)
{
    if (id) for (size_t i=0; i<m->count; i++)
        if (m->commands[i].id == id) return &m->commands[i];
    return NULL;
}
const NemoShellCommand *nemo_shell_marks_lookup(const NemoShellMarks *m, uint64_t id)
{
    if (id) for (size_t i=0; i<m->count; i++)
        if (m->commands[i].id == id) return &m->commands[i];
    return NULL;
}
static void drop(NemoShellMarks *m, size_t i)
{
    NemoShellCommand *c = &m->commands[i];
    if (m->active_id == c->id) m->active_id = 0;
    m->text_bytes -= c->text_bytes;
    sfree(c->text);
    memmove(c, c+1, (m->count-i-1)*sizeof(*c));
    m->count--;
}
void nemo_shell_marks_clear(NemoShellMarks *m)
{
    for (size_t i=0; i<m->count; i++) sfree(m->commands[i].text);
    sfree(m->commands);
    memset(m, 0, sizeof(*m));
}
size_t nemo_shell_marks_memory(const NemoShellMarks *m)
{
    return m->capacity*sizeof(*m->commands) + m->text_bytes;
}
static NemoShellCommand *new_command(NemoShellMarks *m)
{
    /* IDs never alias a retained entry, including at the integer boundary. */
    if (m->next_id == UINT64_MAX) nemo_shell_marks_clear(m);
    if (m->count == NEMO_SHELL_MARK_MAX) drop(m, 0);
    if (m->count == m->capacity) {
        m->capacity = min((size_t)NEMO_SHELL_MARK_MAX, max((size_t)4, m->capacity*2));
        m->commands = sresize(m->commands, m->capacity, NemoShellCommand);
    }
    NemoShellCommand *c = &m->commands[m->count++];
    memset(c, 0, sizeof(*c));
    c->id = ++m->next_id;
    c->phase = NEMO_SHELL_NONE;
    return c;
}
static int compare(NemoShellPoint a, NemoShellPoint b)
{
    if (a.y != b.y) return a.y < b.y ? -1 : 1;
    return a.x < b.x ? -1 : a.x > b.x;
}
static void finish(NemoShellCommand *c, NemoShellPoint point)
{
    c->point[NEMO_SHELL_END] = point;
    c->phase = NEMO_SHELL_END;
    c->finished = true;
}
static int hex(unsigned char c)
{
    if (c >= '0' && c <= '9') return c-'0';
    if (c >= 'a' && c <= 'f') return c-'a'+10;
    if (c >= 'A' && c <= 'F') return c-'A'+10;
    return -1;
}
static bool valid_utf8(const char *s, size_t n)
{
    for (size_t i=0; i<n;) {
        unsigned c=(unsigned char)s[i++], value, count, minimum;
        if (!c) return false;
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
static char *command_text(const char *s, size_t n, size_t *bytes)
{
    /* Decode once. The optional nonce is deliberately not authentication. */
    const char *semi = memchr(s, ';', n);
    if (semi) n = semi-s;
    char *out = snewn(min(n, (size_t)NEMO_SHELL_TEXT_MAX)+1, char);
    size_t used=0;
    for (size_t i=0; i<n; i++) {
        unsigned char c=s[i];
        if (c == '\\') {
            if (i+1<n && s[i+1]=='\\') { c='\\'; i++; }
            else if (n-i>=4 && (s[i+1]=='x'||s[i+1]=='X') &&
                     hex(s[i+2])>=0 && hex(s[i+3])>=0) {
                c=(hex(s[i+2])<<4)|hex(s[i+3]); i+=3;
            } else goto bad;
        }
        if (used == NEMO_SHELL_TEXT_MAX || !c) goto bad;
        out[used++] = c;
    }
    out[used]=0;
    if (!valid_utf8(out,used)) goto bad;
    out=sresize(out,used+1,char);
    *bytes=used+1;
    return out;
  bad:
    sfree(out);
    return NULL;
}
static bool exit_code(const char *s, size_t n, int64_t *result)
{
    const char *semi=memchr(s,';',n);
    if (semi) n=semi-s;
    bool negative=n && *s=='-';
    if (n && (*s=='-' || *s=='+')) { s++; n--; }
    if (!n) return false;
    uint64_t value=0, limit=(uint64_t)INT64_MAX+(negative?1:0);
    for (size_t i=0; i<n; i++) {
        if (s[i]<'0' || s[i]>'9') return false;
        unsigned digit=s[i]-'0';
        if (value>limit/10 || (value==limit/10 && digit>limit%10)) return false;
        value=value*10+digit;
    }
    *result=negative ? (value==(uint64_t)INT64_MAX+1 ? INT64_MIN : -(int64_t)value) : (int64_t)value;
    return true;
}
bool nemo_shell_marks_update(NemoShellMarks *m, unsigned osc,
                             const char *s, size_t n, int x, int y)
{
    if (!n || n>NEMO_SHELL_OSC_MAX || memchr(s,0,n) || x<0 || y<0) return false;
    NemoShellPoint point={.x=x,.y=y,.valid=true};
    if (osc==1337) {
        if (n<7 || memcmp(s,"SetMark",7) || (n>7 && s[7]!=';')) return false;
        NemoShellCommand *c=new_command(m);
        c->point[NEMO_SHELL_PROMPT]=point;
        c->phase=NEMO_SHELL_PROMPT; c->finished=true;
        return true;
    }
    if (osc!=133 && osc!=633) return false;
    if (n>1 && s[1]!=';') return false;
    if (osc==633 && s[0]=='P' && n>2) {
        const char *value=NULL; size_t prefix=0; bool *setting=NULL;
        if (n>=12 && !memcmp(s,"P;IsWindows=",12)) {
            prefix=12; setting=&m->is_windows;
        } else if (n>=26 && !memcmp(s,"P;HasRichCommandDetection=",26)) {
            prefix=26; setting=&m->rich_detection;
        }
        if (!setting) return false;
        value=s+prefix; size_t length=n-prefix;
        if (length==4 && !memcmp(value,"True",4)) *setting=true;
        else if (length==5 && !memcmp(value,"False",5)) *setting=false;
        else return false;
        return true;
    }
    if (osc==633 && s[0]=='E' && n>=2) {
        size_t bytes; char *text=command_text(s+2,n-2,&bytes);
        if (!text) return false;
        NemoShellCommand *c=lookup(m,m->active_id);
        if (!c) { c=new_command(m); m->active_id=c->id; }
        while (m->text_bytes-c->text_bytes+bytes>NEMO_SHELL_TEXT_BUDGET) {
            size_t i=0;
            while (i<m->count && m->commands[i].id==m->active_id) i++;
            assert(i<m->count);
            drop(m,i); c=lookup(m,m->active_id);
        }
        m->text_bytes=m->text_bytes-c->text_bytes+bytes;
        sfree(c->text); c->text=text; c->text_bytes=bytes;
        return true;
    }
    if (s[0]<'A' || s[0]>'D') return false;
    enum NemoShellPhase phase=(enum NemoShellPhase)(s[0]-'A');
    NemoShellCommand *c=lookup(m,m->active_id);
    if (phase==NEMO_SHELL_END) {
        if (!c) return true; /* common initial D before the first prompt */
        finish(c,point);
        c->exit_known=n>2 && exit_code(s+2,n-2,&c->exit_code);
        m->active_id=0;
        return true;
    }
    if (phase==NEMO_SHELL_PROMPT && c) {
        if (c->phase==NEMO_SHELL_NONE) {
            /* An explicit E can precede a prompt without inventing its cells. */
        } else if (c->phase<=NEMO_SHELL_COMMAND &&
                   c->point[0].valid && !compare(c->point[0],point)) {
            m->text_bytes-=c->text_bytes; sfree(c->text);
            uint64_t id=c->id; memset(c,0,sizeof(*c)); c->id=id;
        } else { finish(c,point); c=NULL; }
    } else if (phase==NEMO_SHELL_COMMAND && c && c->phase==NEMO_SHELL_OUTPUT) {
        finish(c,point); c=NULL;
    } else if (phase==NEMO_SHELL_OUTPUT && c && c->phase==NEMO_SHELL_OUTPUT) {
        return true; /* a repeated C must not discard earlier command output */
    }
    if (!c) c=new_command(m);
    m->active_id=c->id; c->phase=phase; c->point[phase]=point;
    return true;
}
void nemo_shell_marks_rows(NemoShellMarks *m, int first, int last, int delta)
{
    for (size_t i=0; i<m->count;) {
        NemoShellCommand *c=&m->commands[i]; bool retained=false;
        for (int j=0; j<4; j++) {
            NemoShellPoint *p=&c->point[j];
            if (!p->valid) continue;
            int64_t y=(int64_t)p->y+delta;
            if (p->truncated || y<first) {
                p->y=first==INT_MIN ? INT_MIN : first-1;
                p->x=0; p->truncated=true;
            } else if (y>last) p->valid=false;
            else { p->y=(int)y; retained=true; }
        }
        if (c->finished && !retained) drop(m,i);
        else i++;
    }
}
void nemo_shell_marks_scroll(NemoShellMarks *m, int left, int right,
                            int top, int bottom, int delta,
                            bool full_width, bool into_history)
{
    if (!delta) return;
    for (size_t i=0; i<m->count; i++) for (int j=0; j<4; j++) {
        NemoShellPoint *p=&m->commands[i].point[j];
        if (!p->valid || p->truncated ||
            (!full_width && (p->x<left || p->x>=right))) continue;
        bool history=full_width && into_history && delta<0 && top==0;
        if (p->y>bottom || (!history && p->y<top)) continue;
        int64_t moved=(int64_t)p->y+delta;
        if (moved>bottom || (!history && moved<top)) p->valid=false;
        else p->y=(int)max((int64_t)INT_MIN,moved);
    }
}
bool nemo_shell_marks_range(const NemoShellCommand *c, bool output,
                           int first, int last,
                           NemoShellPoint *start, NemoShellPoint *end)
{
    if (!c || first>last || (output && !c->finished)) return false;
    *start=c->point[output ? NEMO_SHELL_OUTPUT : NEMO_SHELL_COMMAND];
    *end=c->point[output ? NEMO_SHELL_END : NEMO_SHELL_OUTPUT];
    if (!start->valid || !end->valid || start->y>last || end->y<first) return false;
    if (start->y<first) { start->y=first; start->x=0; start->truncated=true; }
    if (end->y>last) { end->y=last+1; end->x=0; end->truncated=true; }
    return compare(*start,*end)<0;
}
uint64_t nemo_shell_marks_neighbour(const NemoShellMarks *m, int direction,
                                  int x, int y, int first, int last,
                                  NemoShellPoint *point)
{
    if (!direction || first>last) return 0;
    uint64_t found=0; NemoShellPoint ref={.x=x,.y=y,.valid=true};
    for (size_t i=0; i<m->count; i++) {
        const NemoShellCommand *c=&m->commands[i];
        NemoShellPoint p={0};
        for (int j=0; j<3; j++) if (c->point[j].valid) { p=c->point[j]; break; }
        if (!p.valid || p.y<first || p.y>last) continue;
        int cmp=compare(p,ref);
        if ((direction<0 && cmp>=0) || (direction>0 && cmp<=0)) continue;
        if (!found || (direction<0 ? compare(p,*point)>0 : compare(p,*point)<0)) {
            *point=p; found=c->id;
        }
    }
    return found;
}
