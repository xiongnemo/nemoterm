/* SPDX-License-Identifier: MIT */
#ifndef NEMO_TCAP_DB_H
#define NEMO_TCAP_DB_H
#include <stddef.h>

/* Read-only, allocation-free database. Zero is the xterm-256color profile.
 * Selection returns -1 for an unknown name. Values are borrowed static strings;
 * NULL means absent, while a non-NULL empty string is a present capability. */
int nemo_tcap_db_find(const char *name, size_t length);
const char *nemo_tcap_db_value(unsigned profile, const char *capability);

#endif
