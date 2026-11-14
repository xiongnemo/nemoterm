/* Experimental hardware copy compositor. */
#ifndef NEMO_D3D11_H
#define NEMO_D3D11_H
typedef struct NemoD3D11 NemoD3D11;
NemoD3D11 *nemo_d3d11_create(HWND);
void nemo_d3d11_free(NemoD3D11 *);
void nemo_d3d11_clear_cache(NemoD3D11 *);
const char *nemo_d3d11_device(NemoD3D11 *);
int nemo_d3d11_frame(NemoD3D11 *, COLORREF);
HDC nemo_d3d11_dc(NemoD3D11 *);
bool nemo_d3d11_present(NemoD3D11 *);
bool nemo_d3d11_print(NemoD3D11 *, HDC);
bool nemo_d3d11_attach(NemoD3D11 *, HWND);
void nemo_d3d11_show(NemoD3D11 *, bool);
bool nemo_d3d11_print_band(NemoD3D11 *, HDC, int, int);
bool nemo_d3d11_cached(NemoD3D11 *, RECT, ptrlen);
bool nemo_d3d11_begin_run(NemoD3D11 *, RECT, bool);
void nemo_d3d11_end_run(NemoD3D11 *, RECT, ptrlen);
void nemo_d3d11_row(NemoD3D11 *, int, int, int, const uint32_t *);
void nemo_d3d11_borders(NemoD3D11 *, RECT, COLORREF);
void nemo_d3d11_fill_rect(NemoD3D11 *, RECT, COLORREF);
#endif
