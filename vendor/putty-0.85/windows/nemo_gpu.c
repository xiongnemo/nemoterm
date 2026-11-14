/* SPDX-License-Identifier: MIT */
#include "putty.h"
#include "nemo_gpu.h"
#include "nemo_gl.h"
#include "nemo_d3d11.h"
struct NemoGPU {int kind;void *backend;};
NemoGPU *nemo_gpu_create(HWND parent, int kind)
{
    if (kind!=1 && kind!=2) return NULL;
    void *backend=kind==1 ? (void *)nemo_gl_create(parent) : (void *)nemo_d3d11_create(parent);
    if (!backend) return NULL;
    NemoGPU *g=snew(NemoGPU);g->kind=kind;g->backend=backend;return g;
}
void nemo_gpu_free(NemoGPU *g)
{
    if (!g) return;
    if (g->kind==1) nemo_gl_free(g->backend);else nemo_d3d11_free(g->backend);
    sfree(g);
}
void nemo_gpu_clear_cache(NemoGPU *g)
{
    if (!g) return;
    if (g->kind==1) nemo_gl_clear_cache(g->backend);else nemo_d3d11_clear_cache(g->backend);
}
#define METHOD(ret,name,params,args) ret nemo_gpu_##name params { \
    return g->kind==1 ? nemo_gl_##name args : nemo_d3d11_##name args; }
#define ACTION(name,params,args) void nemo_gpu_##name params { \
    if (g->kind==1) nemo_gl_##name args; else nemo_d3d11_##name args; }
METHOD(const char *,device,(NemoGPU *g),(g->backend))
METHOD(int,frame,(NemoGPU *g,COLORREF background),(g->backend,background))
METHOD(HDC,dc,(NemoGPU *g),(g->backend))
METHOD(bool,present,(NemoGPU *g),(g->backend))
METHOD(bool,print,(NemoGPU *g,HDC dc),(g->backend,dc))
METHOD(bool,attach,(NemoGPU *g,HWND parent),(g->backend,parent))
ACTION(show,(NemoGPU *g,bool visible),(g->backend,visible))
METHOD(bool,print_band,(NemoGPU *g,HDC dc,int top,int height),(g->backend,dc,top,height))
METHOD(bool,cached,(NemoGPU *g,RECT box,ptrlen key),(g->backend,box,key))
METHOD(bool,begin_run,(NemoGPU *g,RECT box,bool overlay),(g->backend,box,overlay))
ACTION(end_run,(NemoGPU *g,RECT box,ptrlen key),(g->backend,box,key))
ACTION(row,(NemoGPU *g,int x,int y,int width,const uint32_t *pixels),(g->backend,x,y,width,pixels))
ACTION(borders,(NemoGPU *g,RECT text,COLORREF background),(g->backend,text,background))
ACTION(fill_rect,(NemoGPU *g,RECT rect,COLORREF colour),(g->backend,rect,colour))
