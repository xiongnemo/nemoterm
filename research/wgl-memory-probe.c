#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <psapi.h>
#include <GL/gl.h>
#include <stdio.h>
#include <stdlib.h>

static void sample(const char *phase)
{
    static ULONG_PTR pages[65537];
    PROCESS_MEMORY_COUNTERS_EX pm = {0};
    SYSTEM_INFO si;
    GetSystemInfo(&si);
    if (!QueryWorkingSet(GetCurrentProcess(), pages, sizeof(pages)) ||
        !GetProcessMemoryInfo(GetCurrentProcess(), (void *)&pm, sizeof(pm))) exit(20);
    size_t private_ws = 0;
    for (size_t i=1; i<=pages[0]; i++) if (!(pages[i]&256)) private_ws+=si.dwPageSize;
    printf("{\"phase\":\"%s\",\"private_ws\":%zu,\"total_ws\":%zu,\"private_commit\":%zu}\n",
           phase,private_ws,(size_t)pm.WorkingSetSize,(size_t)pm.PrivateUsage);
}
int main(void)
{
    HINSTANCE inst=GetModuleHandleW(NULL);
    WNDCLASSW wc={0};wc.style=CS_OWNDC;wc.lpfnWndProc=DefWindowProcW;
    wc.hInstance=inst;wc.lpszClassName=L"NemotermOwnedGLProbe";
    if (!RegisterClassW(&wc)) return 1;
    HWND window=CreateWindowW(wc.lpszClassName,L"",WS_OVERLAPPEDWINDOW,
                             0,0,1280,960,NULL,NULL,inst,NULL);
    if (!window) return 2;
    HDC dc=GetDC(window);
    sample("hidden-window-before-context");
    PIXELFORMATDESCRIPTOR pfd={0};pfd.nSize=sizeof(pfd);pfd.nVersion=1;
    pfd.dwFlags=PFD_DRAW_TO_WINDOW|PFD_SUPPORT_OPENGL|PFD_DOUBLEBUFFER;
    pfd.iPixelType=PFD_TYPE_RGBA;pfd.cColorBits=24;pfd.cAlphaBits=8;
    int format=ChoosePixelFormat(dc,&pfd);
    if (!format || !SetPixelFormat(dc,format,&pfd)) return 3;
    HGLRC context=wglCreateContext(dc);
    if (!context || !wglMakeCurrent(dc,context)) return 4;
    DescribePixelFormat(dc,format,sizeof(pfd),&pfd);
    printf("{\"vendor\":\"%s\",\"renderer\":\"%s\",\"version\":\"%s\",\"generic\":%s}\n",
           glGetString(GL_VENDOR),glGetString(GL_RENDERER),glGetString(GL_VERSION),
           pfd.dwFlags&PFD_GENERIC_FORMAT?"true":"false");
    sample("context-current");
    unsigned char *atlas=malloc(1024*1024*4);
    for(size_t i=0;i<1024*1024*4;i++) atlas[i]=(unsigned char)i;
    GLuint texture;glGenTextures(1,&texture);glBindTexture(GL_TEXTURE_2D,texture);
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_NEAREST);
    glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA,1024,1024,0,GL_RGBA,GL_UNSIGNED_BYTE,atlas);
    free(atlas);
    glViewport(0,0,1280,960);glEnable(GL_TEXTURE_2D);
    for(int frame=0;frame<120;frame++) {
        glClear(GL_COLOR_BUFFER_BIT);
        glBegin(GL_QUADS);
        glTexCoord2f(0,0);glVertex2f(-1,-1);
        glTexCoord2f(1,0);glVertex2f(1,-1);
        glTexCoord2f(1,1);glVertex2f(1,1);
        glTexCoord2f(0,1);glVertex2f(-1,1);
        glEnd();SwapBuffers(dc);
    }
    glFinish();
    unsigned char pixel[4]={0};glReadPixels(0,0,1,1,GL_RGBA,GL_UNSIGNED_BYTE,pixel);
    GLenum error=glGetError();
    printf("{\"gl_error\":%u,\"pixel\":[%u,%u,%u,%u]}\n",error,pixel[0],pixel[1],pixel[2],pixel[3]);
    sample("atlas-and-120-frames");
    glDeleteTextures(1,&texture);wglMakeCurrent(NULL,NULL);wglDeleteContext(context);
    ReleaseDC(window,dc);DestroyWindow(window);UnregisterClassW(wc.lpszClassName,inst);
    sample("after-context-destruction");
    return error?5:0;
}
