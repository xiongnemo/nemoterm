/* Shared strip/cache contract for optional native GPU compositors. */
#ifndef NEMO_GPU_H
#define NEMO_GPU_H
typedef struct NemoGPU NemoGPU;
/* Stored renderer IDs: 1 OpenGL, 2 Direct2D. GDI never creates this object. */
NemoGPU *nemo_gpu_create(HWND parent, int kind);
void nemo_gpu_free(NemoGPU *);
void nemo_gpu_clear_cache(NemoGPU *);
const char *nemo_gpu_device(NemoGPU *);
int nemo_gpu_frame(NemoGPU *, COLORREF background);
HDC nemo_gpu_dc(NemoGPU *);
bool nemo_gpu_present(NemoGPU *);
bool nemo_gpu_print(NemoGPU *, HDC);
/* A host keeps one device while moving its surface between tab views. */
bool nemo_gpu_attach(NemoGPU *, HWND parent);
void nemo_gpu_show(NemoGPU *, bool visible);
bool nemo_gpu_print_band(NemoGPU *, HDC, int top, int height);
bool nemo_gpu_cached(NemoGPU *, RECT, ptrlen);
bool nemo_gpu_begin_run(NemoGPU *, RECT, bool overlay);
void nemo_gpu_end_run(NemoGPU *, RECT, ptrlen);
void nemo_gpu_row(NemoGPU *, int x, int y, int width, const uint32_t *);
void nemo_gpu_borders(NemoGPU *, RECT, COLORREF);
void nemo_gpu_fill_rect(NemoGPU *, RECT, COLORREF);
#endif
