/* SPDX-License-Identifier: MIT */
#ifndef NEMO_TCAP_H
#define NEMO_TCAP_H

#define NEMO_TERM_NAME "xterm-256color"
#define NEMO_DCS_QUERY_SIZE 2048
#include "nemo_tcap_db.h"

/* A failed selection leaves the current database intact. The parser owns
 * permission checks and error-bell handling. No heap allocation is required. */
bool nemo_tcap_set(Terminal *term, const char *encoded_name, bool invalid);
void nemo_tcap_configure(Terminal *term, const char *name);
/* -1 means use the ordinary key formatter; zero is a present empty key. */
int nemo_tcap_key(Terminal *term, char kind, int code, unsigned modifiers,
                  char output[64]);
int nemo_tcap_special_key(Terminal *term, unsigned resource, unsigned codepoint,
                          unsigned modifiers, char output[64]);

/* Complete, bounded XTGETTCAP response, owned by the caller. */
strbuf *nemo_tcap_reply(Terminal *term, const char *query, bool invalid);

#endif
