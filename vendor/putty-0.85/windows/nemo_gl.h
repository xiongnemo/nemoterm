/* Optional native OpenGL compositor. No GL objects exist in the GDI path. */
#ifndef NEMO_GL_H
#define NEMO_GL_H
typedef struct NemoGL NemoGL;
NemoGL *nemo_gl_create(HWND parent);
void nemo_gl_free(NemoGL *g);
void nemo_gl_clear_cache(NemoGL *g);
const char *nemo_gl_device(NemoGL *g);
/* 0 failure, 1 retained frame, 2 resized/new frame (caller must repaint all). */
int nemo_gl_frame(NemoGL *g, COLORREF background);
HDC nemo_gl_dc(NemoGL *g);
bool nemo_gl_present(NemoGL *g);
bool nemo_gl_print(NemoGL *g, HDC dc);
bool nemo_gl_attach(NemoGL *, HWND parent);
void nemo_gl_show(NemoGL *, bool visible);
bool nemo_gl_print_band(NemoGL *, HDC, int top, int height);
bool nemo_gl_cached(NemoGL *g, RECT box, ptrlen key);
bool nemo_gl_begin_run(NemoGL *g, RECT box, bool overlay);
void nemo_gl_end_run(NemoGL *g, RECT box, ptrlen key);
void nemo_gl_row(NemoGL *g, int x, int y, int width, const uint32_t *rgba);
void nemo_gl_borders(NemoGL *g, RECT text, COLORREF background);
void nemo_gl_fill_rect(NemoGL *, RECT, COLORREF);
bool nemo_gl_ok(NemoGL *g);
#endif
