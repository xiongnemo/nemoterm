/* SPDX-License-Identifier: MIT */
#ifndef NEMO_KITTY_H
#define NEMO_KITTY_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define NEMO_KITTY_HEADER_MAX 1024u
#define NEMO_KITTY_CHUNK_MAX 4096u
#define NEMO_KITTY_DATA_MAX (2u * 1024u * 1024u)

/* Wire keys retain presence separately from their default value. Some keys
 * have different meanings for transmission, placement and animation. */
typedef struct NemoKittyCommand {
    uint64_t present;
    uint32_t values[52];
} NemoKittyCommand;
bool nemo_kitty_has(const NemoKittyCommand *, char key);
uint32_t nemo_kitty_get(const NemoKittyCommand *, char key);
int32_t nemo_kitty_signed(const NemoKittyCommand *, char key);

typedef struct NemoKittyPacket {
    NemoKittyCommand command;
    const unsigned char *data;
    size_t length;
} NemoKittyPacket;
typedef enum NemoKittyStatus {
    NEMO_KITTY_OK, NEMO_KITTY_MALFORMED, NEMO_KITTY_LIMIT,
    NEMO_KITTY_OUT_OF_MEMORY
} NemoKittyStatus;
typedef enum NemoKittyResult {
    NEMO_KITTY_ERROR = -1, NEMO_KITTY_MORE = 0, NEMO_KITTY_PACKET = 1
} NemoKittyResult;
typedef struct NemoKitty NemoKitty;
/* Admission runs before allocating, including overlap with the old buffer
 * during growth. The terminal owner will account for all other image storage. */
typedef bool (*NemoKittyAdmission)(void *, size_t current, size_t extra);
NemoKitty *nemo_kitty_new(size_t budget, NemoKittyAdmission, void *ctx);
void nemo_kitty_free(NemoKitty *);
void nemo_kitty_cancel(NemoKitty *);
size_t nemo_kitty_memory(const NemoKitty *);
bool nemo_kitty_pending(const NemoKitty *);
NemoKittyStatus nemo_kitty_status(const NemoKitty *);

/* The enclosing parser owns APC G/ST framing and cancellation. Feed starts
 * after G. A non-final chunk never exposes image bytes. Finish consumes one
 * APC exactly once; packet bytes are borrowed until begin/cancel/free.
 * Error packets retain parsed command fields for the owner's error response.
 * Valid feature queries preserve an unfinished upload and ignore their payload;
 * delete cancels it. Other commands interleaved with an upload are malformed.
 * This is transport only: the owner must validate formats, decode pixels,
 * manage image/placement lifetime and decide which features it supports. */
bool nemo_kitty_begin(NemoKitty *);
bool nemo_kitty_feed(NemoKitty *, const void *, size_t);
NemoKittyResult nemo_kitty_finish(NemoKitty *, NemoKittyPacket *);
#endif
