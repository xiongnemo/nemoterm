/* Optional Direct2D hardware compositor; no device exists in the GDI path. */
#ifndef NEMO_D2D_H
#define NEMO_D2D_H
typedef struct NemoD2D NemoD2D;
NemoD2D *nemo_d2d_create(HWND parent);
void nemo_d2d_free(NemoD2D *);
void nemo_d2d_clear_cache(NemoD2D *);
const char *nemo_d2d_device(NemoD2D *);
int nemo_d2d_frame(NemoD2D *, COLORREF background);
HDC nemo_d2d_dc(NemoD2D *);
bool nemo_d2d_present(NemoD2D *);
bool nemo_d2d_print(NemoD2D *, HDC);
bool nemo_d2d_cached(NemoD2D *, RECT, ptrlen);
bool nemo_d2d_begin_run(NemoD2D *, RECT, bool overlay);
void nemo_d2d_end_run(NemoD2D *, RECT, ptrlen);
void nemo_d2d_row(NemoD2D *, int x, int y, int width, const uint32_t *);
void nemo_d2d_borders(NemoD2D *, RECT, COLORREF);
#endif
