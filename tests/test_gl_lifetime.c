/* SPDX-License-Identifier: MIT
 * Fault injection for GL lifetime/preview paths. No windows, driver contexts,
 * graphics DLLs, clipboard or global input are used by these cases. */
#include "putty.h"

static void tracked_strbuf_free(strbuf *key);
static BOOL WINAPI mock_ShowWindow(HWND hwnd, int command);
static HWND WINAPI mock_SetParent(HWND child, HWND parent);
static int WINAPI mock_StretchDIBits(HDC dc, int x, int y, int width, int height,
    int sx, int sy, int sw, int sh, const void *bits, const BITMAPINFO *info,
    UINT usage, DWORD rop);

/* Compile the real implementation with only its external side effects replaced.
 * This also exposes the cache to assertions without adding a product test API. */
#define strbuf_free tracked_strbuf_free
#define ShowWindow mock_ShowWindow
#define SetParent mock_SetParent
#define StretchDIBits mock_StretchDIBits
#include "../vendor/putty-0.85/windows/nemo_gl.c"
#undef strbuf_free
#undef ShowWindow
#undef SetParent
#undef StretchDIBits

#define CHECK(x) do { if (!(x)) { \
    fprintf(stderr,"%s:%d: %s\n",__FILE__,__LINE__,#x); exit(1); \
} } while (0)

void modalfatalbox(const char *format,...)
{
    va_list ap;va_start(ap,format);vfprintf(stderr,format,ap);va_end(ap);
    exit(1);
}

static struct {
    NemoGL *g;
    bool bind_ok, current, parent_ok;
    unsigned binds, unbinds, destroyed, freed, keys, deletes, framebuffers;
    unsigned readbacks, copies, error_checks, attaches, hides;
    strbuf *key[CACHE_COUNT];
    bool key_freed[CACHE_COUNT], texture_deleted[CACHE_COUNT+3];
    uint32_t pixels[8];
} state;
static int context_token, parent_token;

static void cache_empty(void)
{
    Run empty;memset(&empty,0,sizeof(empty));
    CHECK(state.g->cache_bytes==0);
    for (unsigned i=0;i<CACHE_COUNT;i++)
        CHECK(!memcmp(&state.g->cache[i],&empty,sizeof(empty)));
    CHECK(state.freed==state.keys);
}
static void tracked_strbuf_free(strbuf *key)
{
    unsigned i;
    for (i=0;i<state.keys;i++) if (state.key[i]==key) break;
    CHECK(i<state.keys && !state.key_freed[i]);
    state.key_freed[i]=true;state.freed++;
    strbuf_free(key);
}
static BOOL APIENTRY mock_bind(HDC dc,HGLRC context)
{
    CHECK(!dc && !state.destroyed);
    if (!context) {
        CHECK(state.current);state.unbinds++;state.current=false;return TRUE;
    }
    CHECK(context==state.g->context);
    state.binds++;
    /* WGL failure leaves the calling thread without a current context. */
    state.current=state.bind_ok;
    return state.bind_ok;
}
static BOOL APIENTRY mock_destroy(HGLRC context)
{
    CHECK(context==state.g->context && !state.current && !state.destroyed);
    cache_empty();state.destroyed++;return TRUE;
}
static void APIENTRY mock_delete(GLsizei count,const GLuint *ids)
{
    CHECK(state.current && !state.destroyed);
    for (GLsizei i=0;i<count;i++) {
        CHECK(ids[i]>0 && ids[i]<lenof(state.texture_deleted));
        CHECK(!state.texture_deleted[ids[i]]);
        state.texture_deleted[ids[i]]=true;state.deletes++;
    }
}
static void APIENTRY mock_delete_framebuffers(GLsizei count,const GLuint *ids)
{
    CHECK(state.current && !state.destroyed && count==1 && *ids==1000);
    CHECK(!state.framebuffers);state.framebuffers++;
}
static void APIENTRY mock_framebuffer(GLenum target,GLuint id)
{
    CHECK(state.current && target==GL_FRAMEBUFFER && id==1000);
}
static void APIENTRY mock_read(GLint x,GLint y,GLsizei w,GLsizei h,
                              GLenum format,GLenum type,void *pixels)
{
    CHECK(state.current && !x && y>=0 && y<3 && w==8 && h==1);
    CHECK(format==GL_BGRA && type==GL_UNSIGNED_BYTE && pixels==state.pixels);
    state.readbacks++;
}
static GLenum APIENTRY mock_error(void)
{
    CHECK(state.current);state.error_checks++;return GL_NO_ERROR;
}
static BOOL WINAPI mock_ShowWindow(HWND hwnd,int command)
{
    CHECK(!hwnd && command==SW_HIDE);state.hides++;return FALSE;
}
static HWND WINAPI mock_SetParent(HWND child,HWND parent)
{
    CHECK(!child && parent==(HWND)&parent_token);state.attaches++;
    if (!state.parent_ok) SetLastError(ERROR_ACCESS_DENIED);
    return NULL;
}
static int WINAPI mock_StretchDIBits(HDC dc,int x,int y,int w,int h,
    int sx,int sy,int sw,int sh,const void *bits,const BITMAPINFO *info,
    UINT usage,DWORD rop)
{
    CHECK(state.current && !dc && !x && y>=0 && y<3 && w==8 && h==1);
    CHECK(!sx && !sy && sw==8 && sh==1 && bits==state.pixels);
    CHECK(info->bmiHeader.biWidth==8 && info->bmiHeader.biHeight==-1);
    CHECK(usage==DIB_RGB_COLORS && rop==SRCCOPY);
    state.copies++;return 1;
}
static NemoGL *fixture(unsigned keys)
{
    memset(&state,0,sizeof(state));
    NemoGL *g=snew(NemoGL);memset(g,0,sizeof(*g));state.g=g;
    state.bind_ok=state.parent_ok=true;
    g->context=(HGLRC)&context_token;
    g->frame=CACHE_COUNT+1;g->upload=CACHE_COUNT+2;g->framebuffer=1000;
    g->api.wglMakeCurrent=mock_bind;g->api.wglDeleteContext=mock_destroy;
    g->api.glDeleteTextures=mock_delete;
    g->api.glDeleteFramebuffers=mock_delete_framebuffers;
    g->api.glBindFramebuffer=mock_framebuffer;g->api.glReadPixels=mock_read;
    g->api.glGetError=mock_error;
    g->width=g->strip_width=8;g->height=3;g->strip_height=1;g->limit=16;
    g->pixels=state.pixels;
    CHECK(keys<=CACHE_COUNT);state.keys=keys;
    for (unsigned i=0;i<keys;i++) {
        Run *r=&g->cache[i];r->key=state.key[i]=strbuf_new();
        put_fmt(r->key,"key-%u",i);r->texture=i+1;r->bytes=(i+1)*4;
        r->hash=i+1;r->used=i+2;r->width=i+1;r->height=1;
        g->cache_bytes+=r->bytes;
    }
    return g;
}
static void free_full_cache(bool bind_ok)
{
    NemoGL *g=fixture(CACHE_COUNT);state.bind_ok=bind_ok;
    nemo_gl_free(g);
    CHECK(state.freed==CACHE_COUNT && state.destroyed==1 && state.binds==1);
    CHECK(state.deletes==(bind_ok ? CACHE_COUNT+2 : 0));
    CHECK(state.framebuffers==(unsigned)bind_ok);
    CHECK(state.unbinds==(unsigned)bind_ok);
}
static void clear_then_free(bool first_bind,bool final_bind)
{
    NemoGL *g=fixture(CACHE_COUNT);state.bind_ok=first_bind;
    nemo_gl_clear_cache(g);cache_empty();
    CHECK(g->failed==!first_bind && state.deletes==(first_bind ? CACHE_COUNT : 0));
    state.bind_ok=final_bind;nemo_gl_clear_cache(g);cache_empty();
    CHECK(g->failed==(!first_bind || !final_bind));
    nemo_gl_free(g);
    CHECK(state.freed==CACHE_COUNT && state.destroyed==1 && state.binds==3);
    CHECK(state.deletes==(first_bind ? CACHE_COUNT : 0)+(final_bind ? 2 : 0));
    CHECK(state.unbinds==(unsigned)final_bind);
}
static void partial_creation(void)
{
    NemoGL *g=fixture(3);g->context=NULL;
    /* No WGL/GL entry points need exist before creation reaches a context. */
    memset(&g->api,0,sizeof(g->api));nemo_gl_clear_cache(g);cache_empty();
    nemo_gl_free(g);CHECK(state.freed==3 && !state.destroyed && !state.binds);

    g=fixture(0);g->frame=g->upload=g->framebuffer=0;
    g->api.glDeleteFramebuffers=NULL;nemo_gl_free(g);
    CHECK(state.destroyed==1 && !state.deletes && !state.framebuffers);
}
static void previews(void)
{
    NemoGL *g=fixture(1);state.bind_ok=false;
    CHECK(!nemo_gl_print_band(g,NULL,0,3) && g->failed);
    CHECK(!state.readbacks && !state.copies && !state.error_checks);
    CHECK(!nemo_gl_ok(g) && !state.error_checks);
    state.bind_ok=true;
    CHECK(!nemo_gl_print_band(g,NULL,0,3) && state.binds==1);
    nemo_gl_free(g);CHECK(state.freed==1 && state.destroyed==1);

    g=fixture(0);
    CHECK(nemo_gl_print_band(g,NULL,1,8));
    CHECK(state.readbacks==2 && state.copies==2 && state.error_checks==1);
    nemo_gl_free(g);
}
static void attachment(bool parent_ok,bool bind_ok)
{
    NemoGL *g=fixture(3);state.parent_ok=parent_ok;state.bind_ok=bind_ok;
    CHECK(nemo_gl_attach(g,(HWND)&parent_token)==(parent_ok && bind_ok));
    CHECK(state.hides==1 && state.attaches==1);
    if (parent_ok) {
        cache_empty();CHECK(g->failed==!bind_ok && state.binds==1);
        CHECK(g->parent==(HWND)&parent_token);
    } else {
        CHECK(!state.binds && !state.freed && !g->failed && !g->parent);
    }
    nemo_gl_free(g);CHECK(state.freed==3 && state.destroyed==1);
}
int main(void)
{
    nemo_gl_free(NULL);nemo_gl_clear_cache(NULL);
    free_full_cache(true);free_full_cache(false);
    clear_then_free(true,true);clear_then_free(true,false);
    clear_then_free(false,true);clear_then_free(false,false);
    partial_creation();previews();
    attachment(true,true);attachment(true,false);attachment(false,true);
    puts("OpenGL context failure cleanup and preview checks passed");return 0;
}
