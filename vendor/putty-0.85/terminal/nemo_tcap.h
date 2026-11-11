/* SPDX-License-Identifier: MIT */
#ifndef NEMO_TCAP_H
#define NEMO_TCAP_H

#define NEMO_TERM_NAME "xterm-256color"
#define NEMO_DCS_QUERY_SIZE 2048

/* Complete, bounded XTGETTCAP response, owned by the caller. */
strbuf *nemo_tcap_reply(Terminal *term, const char *query, bool invalid);

#endif
