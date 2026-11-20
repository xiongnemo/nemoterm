#ifndef PUTTY_NEMO_WSL_IMAGE_H
#define PUTTY_NEMO_WSL_IMAGE_H
#include "putty.h"

typedef struct NemoWslImage {
    wchar_t *path;
    HANDLE reader;
    BY_HANDLE_FILE_INFORMATION identity;
} NemoWslImage;

/* Shared GUI code is also linked into binaries without this resource. */
static inline HRSRC nemo_wsl_image_resource(void)
{
    return FindResourceW(GetModuleHandleW(NULL), MAKEINTRESOURCEW(40003), MAKEINTRESOURCEW(10));
}

/* Visible text area in Linux winsize units (0 means unavailable). */
void nemo_wsl_text_pixels(Seat *, int cols, int rows, unsigned *x, unsigned *y);

/* Materialize RCDATA 40003 as a regular, locked, session-local ELF. */
DWORD nemo_wsl_image_open(NemoWslImage *);
DWORD nemo_wsl_image_close(NemoWslImage *);
#endif
