/* SPDX-License-Identifier: MIT */
#ifndef NEMO_DROP_H
#define NEMO_DROP_H
#include "putty.h"
#include <shellapi.h>
/* A bounded, quoted path list; caller owns the result. Does not free HDROP. */
wchar_t *nemo_drop_paths(HDROP, Conf *, size_t *length);
#endif
