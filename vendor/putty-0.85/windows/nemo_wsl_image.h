#ifndef PUTTY_NEMO_WSL_IMAGE_H
#define PUTTY_NEMO_WSL_IMAGE_H
#include "putty.h"

typedef struct NemoWslImage {
    wchar_t *path;
    HANDLE reader;
    BY_HANDLE_FILE_INFORMATION identity;
} NemoWslImage;

/* Materialize RCDATA 40003 as a regular, locked, session-local ELF. */
DWORD nemo_wsl_image_open(NemoWslImage *);
DWORD nemo_wsl_image_close(NemoWslImage *);
#endif
