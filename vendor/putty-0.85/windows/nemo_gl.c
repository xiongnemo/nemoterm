/* Native, optional GPU composition. GDI rasterizes only uncached text runs
 * into one reusable strip; the retained frame and bounded run cache live on
 * the GPU. No whole-window CPU bitmap, toolkit, shader compiler or GL loader
 * dependency. A separate child surface lets GDI remain usable after fallback.
 */
#include "putty.h"
#include "nemo_gl.h"
#include <GL/gl.h>

#define GL_BGRA 0x80E1
#define GL_FRAMEBUFFER 0x8D40
#define GL_COLOR_ATTACHMENT0 0x8CE0
#define GL_FRAMEBUFFER_COMPLETE 0x8CD5
#define CACHE_COUNT 256
#define CACHE_BYTES (4U*1024U*1024U)
#define FRAME_BYTES (128U*1024U*1024U)

#define GL_API(X) \
 X(void,glGenTextures,(GLsizei n, GLuint *p)) \
 X(void,glDeleteTextures,(GLsizei n, const GLuint *p)) \
 X(void,glBindTexture,(GLenum t, GLuint p)) \
 X(void,glTexParameteri,(GLenum t, GLenum p, GLint v)) \
 X(void,glTexImage2D,(GLenum t, GLint l, GLint f, GLsizei w, GLsizei h, GLint b, GLenum fmt, GLenum ty, const void *v)) \
 X(void,glTexSubImage2D,(GLenum t, GLint l, GLint x, GLint y, GLsizei w, GLsizei h, GLenum f, GLenum ty, const void *v)) \
 X(void,glEnable,(GLenum v)) X(void,glDisable,(GLenum v)) \
 X(void,glViewport,(GLint x, GLint y, GLsizei w, GLsizei h)) \
 X(void,glScissor,(GLint x, GLint y, GLsizei w, GLsizei h)) \
 X(void,glMatrixMode,(GLenum v)) X(void,glLoadIdentity,(void)) \
 X(void,glOrtho,(GLdouble l, GLdouble r, GLdouble b, GLdouble t, GLdouble n, GLdouble f)) \
 X(void,glBegin,(GLenum v)) X(void,glEnd,(void)) \
 X(void,glTexCoord2f,(GLfloat x, GLfloat y)) X(void,glVertex2i,(GLint x, GLint y)) \
 X(void,glColor4ub,(GLubyte r, GLubyte g, GLubyte b, GLubyte a)) \
 X(void,glClearColor,(GLfloat r, GLfloat g, GLfloat b, GLfloat a)) \
 X(void,glClear,(GLbitfield v)) X(void,glReadPixels,(GLint x, GLint y, GLsizei w, GLsizei h, GLenum f, GLenum ty, void *p)) \
 X(void,glGetIntegerv,(GLenum v, GLint *p)) X(GLenum,glGetError,(void)) \
 X(void,glPixelStorei,(GLenum v, GLint p)) \
 X(const GLubyte *,glGetString,(GLenum v)) \
 X(HGLRC,wglCreateContext,(HDC dc)) X(BOOL,wglDeleteContext,(HGLRC rc)) \
 X(BOOL,wglMakeCurrent,(HDC dc, HGLRC rc)) X(PROC,wglGetProcAddress,(LPCSTR name))

struct GLApi {
#define DECL(ret,name,args) ret (APIENTRY *name) args;
    GL_API(DECL)
    DECL(void,glGenFramebuffers,(GLsizei n, GLuint *p))
    DECL(void,glDeleteFramebuffers,(GLsizei n, const GLuint *p))
    DECL(void,glBindFramebuffer,(GLenum t, GLuint p))
    DECL(void,glFramebufferTexture2D,(GLenum t, GLenum a, GLenum tt, GLuint p, GLint l))
    DECL(GLenum,glCheckFramebufferStatus,(GLenum t))
#undef DECL
};
typedef struct Run {
    GLuint texture;
    unsigned bytes;
    uint64_t hash, used;
    strbuf *key;
    int width, height;
} Run;
struct NemoGL {
    HWND parent, surface;
    HMODULE module;
    HDC dc, scratch;
    HGLRC context;
    HBITMAP bitmap;
    HGDIOBJ oldbitmap;
    uint32_t *pixels;
    int strip_width, strip_height, width, height, limit;
    GLuint frame, framebuffer, upload;
    struct GLApi api;
    Run cache[CACHE_COUNT];
    unsigned cache_bytes;
    uint64_t tick;
    bool failed;
    char device[256];
};

static LRESULT CALLBACK surface_proc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp)
{
    if (msg == WM_NCHITTEST) return HTTRANSPARENT;
    if (msg == WM_MOUSEACTIVATE) return MA_NOACTIVATE;
    if (msg == WM_ERASEBKGND) return 1;
    if (msg == WM_PAINT) {
        ValidateRect(hwnd, NULL);
        InvalidateRect(GetParent(hwnd), NULL, false);
        return 0;
    }
    return DefWindowProcW(hwnd, msg, wp, lp);
}
static void evict(NemoGL *g, Run *r)
{
    if (r->texture) g->api.glDeleteTextures(1, &r->texture);
    if (r->key) strbuf_free(r->key);
    g->cache_bytes -= r->bytes;
    memset(r, 0, sizeof(*r));
}
void nemo_gl_clear_cache(NemoGL *g)
{
    if (!g || !g->context) return;
    if (!g->api.wglMakeCurrent(g->dc,g->context)) { g->failed=true; return; }
    for (unsigned i=0; i<CACHE_COUNT; i++) evict(g,&g->cache[i]);
}
void nemo_gl_free(NemoGL *g)
{
    if (!g) return;
    if (g->context) {
        nemo_gl_clear_cache(g);
        if (g->api.glDeleteFramebuffers && g->framebuffer)
            g->api.glDeleteFramebuffers(1,&g->framebuffer);
        g->api.glDeleteTextures(1,&g->frame);
        g->api.glDeleteTextures(1,&g->upload);
        g->api.wglMakeCurrent(NULL,NULL);
        g->api.wglDeleteContext(g->context);
    }
    if (g->bitmap) {
        SelectObject(g->scratch,g->oldbitmap);
        DeleteObject(g->bitmap);
    }
    if (g->scratch) DeleteDC(g->scratch);
    if (g->dc) ReleaseDC(g->surface,g->dc);
    if (g->surface) DestroyWindow(g->surface);
    if (g->module) FreeLibrary(g->module);
    sfree(g);
}
static bool extension(PROC p)
{
    return p && (uintptr_t)p>3 && (uintptr_t)p!=UINTPTR_MAX;
}
NemoGL *nemo_gl_create(HWND parent)
{
    NemoGL *g=snew(NemoGL);
    memset(g,0,sizeof(*g));g->parent=parent;
    g->module=load_system32_dll("opengl32.dll");
    if (!g->module) goto fail;
#define LOAD(ret,name,args) do { \
    *(FARPROC *)&g->api.name=GetProcAddress(g->module,#name); \
    if (!g->api.name) goto fail; \
} while (0);
    GL_API(LOAD)
#undef LOAD
    WNDCLASSW wc={0};
    wc.style=CS_OWNDC;wc.lpfnWndProc=surface_proc;
    wc.hInstance=GetModuleHandle(NULL);wc.lpszClassName=L"NemotermOpenGL";
    if (!RegisterClassW(&wc) && GetLastError()!=ERROR_CLASS_ALREADY_EXISTS) goto fail;
    g->surface=CreateWindowExW(0,wc.lpszClassName,L"",WS_CHILD|WS_CLIPSIBLINGS,
                               0,0,1,1,parent,NULL,wc.hInstance,NULL);
    if (!g->surface) goto fail;
    g->dc=GetDC(g->surface);g->scratch=CreateCompatibleDC(NULL);
    if (!g->dc || !g->scratch) goto fail;
    PIXELFORMATDESCRIPTOR pfd={0};
    pfd.nSize=sizeof(pfd);pfd.nVersion=1;
    pfd.dwFlags=PFD_DRAW_TO_WINDOW|PFD_SUPPORT_OPENGL|PFD_DOUBLEBUFFER;
    pfd.iPixelType=PFD_TYPE_RGBA;pfd.cColorBits=24;pfd.cAlphaBits=8;
    int pf=ChoosePixelFormat(g->dc,&pfd);
    if (!pf || !DescribePixelFormat(g->dc,pf,sizeof(pfd),&pfd) ||
        (pfd.dwFlags&PFD_GENERIC_FORMAT) || !SetPixelFormat(g->dc,pf,&pfd)) goto fail;
    g->context=g->api.wglCreateContext(g->dc);
    if (!g->context || !g->api.wglMakeCurrent(g->dc,g->context)) goto fail;
#define EXT(name) do { \
    PROC p=g->api.wglGetProcAddress(#name); \
    if (!extension(p)) p=g->api.wglGetProcAddress(#name "EXT"); \
    if (!extension(p)) goto fail; \
    *(PROC *)&g->api.name=p; \
} while (0)
    EXT(glGenFramebuffers);EXT(glDeleteFramebuffers);EXT(glBindFramebuffer);
    EXT(glFramebufferTexture2D);EXT(glCheckFramebufferStatus);
#undef EXT
    const char *renderer=(const char *)g->api.glGetString(GL_RENDERER);
    const char *version=(const char *)g->api.glGetString(GL_VERSION);
    if (!renderer || !version || atoi(version)<2) goto fail;
    snprintf(g->device,sizeof(g->device),"%s; OpenGL %s",renderer,version);
    g->api.glGetIntegerv(GL_MAX_TEXTURE_SIZE,&g->limit);
    g->api.glGenFramebuffers(1,&g->framebuffer);
    g->api.glGenTextures(1,&g->frame);
    g->api.glGenTextures(1,&g->upload);
    g->api.glDisable(GL_DITHER);
    g->api.glDisable(GL_BLEND);
    return g;
  fail:
    nemo_gl_free(g);return NULL;
}
const char *nemo_gl_device(NemoGL *g) { return g->device; }
HDC nemo_gl_dc(NemoGL *g) { return g->scratch; }
static void projection(NemoGL *g, int width, int height)
{
    g->api.glViewport(0,0,width,height);
    g->api.glMatrixMode(GL_PROJECTION);g->api.glLoadIdentity();
    g->api.glOrtho(0,width,height,0,-1,1);
    g->api.glMatrixMode(GL_MODELVIEW);g->api.glLoadIdentity();
}
static void texture(NemoGL *g, GLuint id, int w, int h, const void *data)
{
    g->api.glBindTexture(GL_TEXTURE_2D,id);
    g->api.glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_NEAREST);
    g->api.glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_NEAREST);
    g->api.glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,GL_CLAMP);
    g->api.glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,GL_CLAMP);
    g->api.glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA,w,h,0,GL_BGRA,GL_UNSIGNED_BYTE,data);
}
static void quad(NemoGL *g, GLuint id, RECT r, bool flip)
{
    g->api.glEnable(GL_TEXTURE_2D);g->api.glBindTexture(GL_TEXTURE_2D,id);
    g->api.glColor4ub(255,255,255,255);
    g->api.glBegin(GL_QUADS);
    g->api.glTexCoord2f(0,flip?1:0);g->api.glVertex2i(r.left,r.top);
    g->api.glTexCoord2f(1,flip?1:0);g->api.glVertex2i(r.right,r.top);
    g->api.glTexCoord2f(1,flip?0:1);g->api.glVertex2i(r.right,r.bottom);
    g->api.glTexCoord2f(0,flip?0:1);g->api.glVertex2i(r.left,r.bottom);
    g->api.glEnd();
}
int nemo_gl_frame(NemoGL *g, COLORREF background)
{
    RECT r;
    if (!GetClientRect(g->parent,&r) || r.right<=0 || r.bottom<=0) return 0;
    if (r.right>g->limit || r.bottom>g->limit ||
        (uint64_t)r.right*r.bottom*4>FRAME_BYTES ||
        !g->api.wglMakeCurrent(g->dc,g->context)) { g->failed=true; return 0; }
    bool changed=r.right!=g->width || r.bottom!=g->height;
    if (changed) {
        g->width=r.right;g->height=r.bottom;
        SetWindowPos(g->surface,NULL,0,0,g->width,g->height,SWP_NOACTIVATE|SWP_NOZORDER);
        texture(g,g->frame,g->width,g->height,NULL);
    }
    g->api.glBindFramebuffer(GL_FRAMEBUFFER,g->framebuffer);
    g->api.glFramebufferTexture2D(GL_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_TEXTURE_2D,g->frame,0);
    if (g->api.glCheckFramebufferStatus(GL_FRAMEBUFFER)!=GL_FRAMEBUFFER_COMPLETE) {
        g->failed=true;return 0;
    }
    projection(g,g->width,g->height);
    if (changed) {
        g->api.glClearColor(GetRValue(background)/255.f,GetGValue(background)/255.f,
                            GetBValue(background)/255.f,1);
        g->api.glClear(GL_COLOR_BUFFER_BIT);
    }
    return changed?2:1;
}
bool nemo_gl_ok(NemoGL *g)
{
    if (g->api.glGetError()!=GL_NO_ERROR) g->failed=true;
    return !g->failed;
}
bool nemo_gl_present(NemoGL *g)
{
    if (!g->width || !g->height) return false;
    g->api.glBindFramebuffer(GL_FRAMEBUFFER,0);
    RECT r;GetClientRect(g->parent,&r);
    projection(g,r.right,r.bottom);
    quad(g,g->frame,r,true);
    bool ok=nemo_gl_ok(g) && SwapBuffers(g->dc);
    g->api.glBindFramebuffer(GL_FRAMEBUFFER,g->framebuffer);
    projection(g,g->width,g->height);
    if (ok && !IsWindowVisible(g->surface)) ShowWindow(g->surface,SW_SHOWNOACTIVATE);
    return ok;
}
static bool strip(NemoGL *g, int width, int height)
{
    if (width<=0 || height<=0 || width>g->limit || height>g->limit ||
        (uint64_t)width*height*4>CACHE_BYTES) { g->failed=true;return false; }
    if (width<=g->strip_width && height<=g->strip_height) return true;
    width=max(width,g->strip_width);height=max(height,g->strip_height);
    if ((uint64_t)width*height*4>CACHE_BYTES) { g->failed=true;return false; }
    if (g->bitmap) {
        SelectObject(g->scratch,g->oldbitmap);DeleteObject(g->bitmap);g->bitmap=NULL;
    }
    BITMAPINFO bi={0};bi.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);
    bi.bmiHeader.biWidth=width;bi.bmiHeader.biHeight=-height;
    bi.bmiHeader.biPlanes=1;bi.bmiHeader.biBitCount=32;bi.bmiHeader.biCompression=BI_RGB;
    g->bitmap=CreateDIBSection(g->scratch,&bi,DIB_RGB_COLORS,(void **)&g->pixels,NULL,0);
    if (!g->bitmap) { g->failed=true;return false; }
    g->oldbitmap=SelectObject(g->scratch,g->bitmap);
    g->strip_width=width;g->strip_height=height;
    return true;
}
static uint64_t keyhash(ptrlen key)
{
    uint64_t hash=UINT64_C(14695981039346656037);
    const unsigned char *p=key.ptr;
    for (size_t i=0;i<key.len;i++) hash=(hash^p[i])*UINT64_C(1099511628211);
    return hash;
}
bool nemo_gl_cached(NemoGL *g, RECT box, ptrlen key)
{
    uint64_t hash=keyhash(key);
    for (unsigned i=0;i<CACHE_COUNT;i++) {
        Run *r=&g->cache[i];
        if (r->key && r->hash==hash && r->width==box.right-box.left &&
            r->height==box.bottom-box.top && ptrlen_eq_ptrlen(ptrlen_from_strbuf(r->key),key)) {
            r->used=++g->tick;quad(g,r->texture,box,false);return true;
        }
    }
    return false;
}
bool nemo_gl_begin_run(NemoGL *g, RECT box, bool overlay)
{
    int width=box.right-box.left,height=box.bottom-box.top;
    if (!strip(g,width,height)) return false;
    SelectClipRgn(g->scratch,NULL);SetViewportOrgEx(g->scratch,-box.left,-box.top,NULL);
    IntersectClipRect(g->scratch,box.left,box.top,box.right,box.bottom);
    if (overlay) {
        /* Small cursor/sigil overlays only. Text runs never read the GPU. */
        for (int y=0;y<height;y++)
            g->api.glReadPixels(box.left,g->height-1-box.top-y,width,1,GL_BGRA,
                                GL_UNSIGNED_BYTE,g->pixels+(size_t)y*g->strip_width);
    } else memset(g->pixels,0,(size_t)g->strip_width*height*4);
    return true;
}
void nemo_gl_end_run(NemoGL *g, RECT box, ptrlen key)
{
    GdiFlush();
    unsigned bytes=(unsigned)(box.right-box.left)*(box.bottom-box.top)*4;
    GLuint id=g->upload;
    if (key.len && bytes<=CACHE_BYTES && key.len<=16384) {
        Run *r=NULL;
        for (unsigned i=0;i<CACHE_COUNT;i++)
            if (!r || g->cache[i].used<r->used) r=&g->cache[i];
        evict(g,r);
        while (g->cache_bytes+bytes>CACHE_BYTES) {
            Run *old=NULL;
            for (unsigned i=0;i<CACHE_COUNT;i++)
                if (g->cache[i].texture && (!old || g->cache[i].used<old->used)) old=&g->cache[i];
            if (!old) break;
            evict(g,old);
        }
        g->api.glGenTextures(1,&r->texture);id=r->texture;
        r->bytes=bytes;g->cache_bytes+=bytes;r->used=++g->tick;r->hash=keyhash(key);
        r->width=box.right-box.left;r->height=box.bottom-box.top;
        r->key=strbuf_new();put_datapl(r->key,key);
    }
    g->api.glPixelStorei(GL_UNPACK_ROW_LENGTH,g->strip_width);
    texture(g,id,box.right-box.left,box.bottom-box.top,g->pixels);
    g->api.glPixelStorei(GL_UNPACK_ROW_LENGTH,0);
    quad(g,id,box,false);
}
void nemo_gl_row(NemoGL *g, int x, int y, int width, const uint32_t *pixels)
{
    RECT r={x,y,x+width,y+1};
    texture(g,g->upload,width,1,pixels);quad(g,g->upload,r,false);
}
static void fill(NemoGL *g, RECT r, COLORREF colour)
{
    if (r.right<=r.left || r.bottom<=r.top) return;
    g->api.glDisable(GL_TEXTURE_2D);
    g->api.glColor4ub(GetRValue(colour),GetGValue(colour),GetBValue(colour),255);
    g->api.glBegin(GL_QUADS);
    g->api.glVertex2i(r.left,r.top);g->api.glVertex2i(r.right,r.top);
    g->api.glVertex2i(r.right,r.bottom);g->api.glVertex2i(r.left,r.bottom);
    g->api.glEnd();
}
void nemo_gl_borders(NemoGL *g, RECT text, COLORREF colour)
{
    RECT r={0,0,g->width,text.top};fill(g,r,colour);
    r.top=text.bottom;r.bottom=g->height;fill(g,r,colour);
    r.top=text.top;r.bottom=text.bottom;r.right=text.left;fill(g,r,colour);
    r.left=text.right;r.right=g->width;fill(g,r,colour);
}
bool nemo_gl_print(NemoGL *g, HDC dc)
{
    return nemo_gl_print_band(g,dc,0,g->height);
}
void nemo_gl_fill_rect(NemoGL *g, RECT rect, COLORREF colour)
{
    if (!g->failed) fill(g,rect,colour);
}
bool nemo_gl_attach(NemoGL *g, HWND parent)
{
    ShowWindow(g->surface,SW_HIDE);
    SetLastError(0);
    if (!SetParent(g->surface,parent) && GetLastError()) return false;
    g->parent=parent;nemo_gl_clear_cache(g);return true;
}
void nemo_gl_show(NemoGL *g, bool visible)
{
    ShowWindow(g->surface,visible ? SW_SHOWNOACTIVATE : SW_HIDE);
}
bool nemo_gl_print_band(NemoGL *g, HDC dc, int top, int height)
{
    if (!g->width || !g->height || !strip(g,g->width,1)) return false;
    g->api.wglMakeCurrent(g->dc,g->context);
    g->api.glBindFramebuffer(GL_FRAMEBUFFER,g->framebuffer);
    BITMAPINFO bi={0};bi.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);
    bi.bmiHeader.biWidth=g->width;bi.bmiHeader.biHeight=-1;
    bi.bmiHeader.biPlanes=1;bi.bmiHeader.biBitCount=32;bi.bmiHeader.biCompression=BI_RGB;
    for (int y=max(0,top);y<min(g->height,top+height);y++) {
        g->api.glReadPixels(0,g->height-1-y,g->width,1,GL_BGRA,GL_UNSIGNED_BYTE,g->pixels);
        int copied=StretchDIBits(dc,0,y,g->width,1,0,0,g->width,1,g->pixels,&bi,DIB_RGB_COLORS,SRCCOPY);
        if (!copied || copied==GDI_ERROR) return false;
    }
    return nemo_gl_ok(g);
}
