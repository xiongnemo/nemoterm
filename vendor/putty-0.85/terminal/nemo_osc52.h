/* SPDX-License-Identifier: MIT */
#ifndef NEMO_OSC52_H
#define NEMO_OSC52_H
#include <stdbool.h>
#include <stddef.h>

#define NEMO_OSC52_TEXT_MAX (256u * 1024u)
#define NEMO_OSC52_CACHE_MAX (1024u * 1024u)
#define NEMO_OSC52_TARGETS_MAX 12

typedef struct NemoOsc52 NemoOsc52;
typedef enum NemoOsc52Action {
    NEMO_OSC52_NONE, NEMO_OSC52_WRITE, NEMO_OSC52_CLEAR, NEMO_OSC52_QUERY
} NemoOsc52Action;
typedef struct NemoOsc52Packet {
    NemoOsc52Action action;
    char targets[NEMO_OSC52_TARGETS_MAX+1];
    const char *text;
    size_t length;
} NemoOsc52Packet;

/* Only the current payload is discarded by begin/cancel; retained selections
 * survive terminal reset. No allocation when both permissions are disabled. */
void nemo_osc52_begin(NemoOsc52 **, bool allow_write, bool allow_read);
void nemo_osc52_feed(NemoOsc52 *, unsigned char);
NemoOsc52Packet nemo_osc52_finish(NemoOsc52 *);
void nemo_osc52_cancel(NemoOsc52 *);
void nemo_osc52_free(NemoOsc52 *);
bool nemo_osc52_utf8(const char *, size_t);

/* q and cut-buffers 0..7 live in a shared, FIFO-bounded UTF-8 cache. A multi-
 * target write shares one immutable allocation. c/p/s are provided by the
 * platform/terminal, so a remote system copy need not replace local selection. */
unsigned nemo_osc52_cache_mask(char target);
bool nemo_osc52_store(NemoOsc52 *, unsigned mask, const char *, size_t);
bool nemo_osc52_get(const NemoOsc52 *, char target, const char **, size_t *);
size_t nemo_osc52_memory(const NemoOsc52 *);
size_t nemo_osc52_cached(const NemoOsc52 *);
#endif
