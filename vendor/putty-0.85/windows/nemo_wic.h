/* SPDX-License-Identifier: MIT */
#ifndef NEMO_WIC_H
#define NEMO_WIC_H
#include "terminal/nemo_raster.h"
bool nemo_wic_decode(TermWin *, const void *, size_t, NemoRaster *,
                     NemoRasterAdmission, void *);
#endif
