/* SPDX-License-Identifier: MIT */
#ifndef NEMO_HYPERLINK_H
#define NEMO_HYPERLINK_H

#include <stddef.h>
#include <stdint.h>

#define NEMO_LINK_URI_MAX 2083
#define NEMO_LINK_ID_MAX 250
#define NEMO_LINK_OSC_MAX 4096
#define NEMO_LINK_COUNT_MAX 1024
#define NEMO_LINK_BUDGET (256u * 1024u)

typedef struct NemoHyperlinks NemoHyperlinks;

/* Payload is params;URI, without OSC 8 framing. Empty URI, malformed input,
 * or allocation failure returns zero. Allocate the registry lazily. */
uint32_t nemo_hyperlink_parse(NemoHyperlinks **, const char *, size_t);
/* Borrowed until the next parse/free. Handles are never reused, even after
 * eviction; old cells become inactive, never point to a different URI. */
const char *nemo_hyperlink_lookup(const NemoHyperlinks *, uint32_t);
size_t nemo_hyperlink_memory(const NemoHyperlinks *);
size_t nemo_hyperlink_count(const NemoHyperlinks *);
void nemo_hyperlink_free(NemoHyperlinks *);

#endif
