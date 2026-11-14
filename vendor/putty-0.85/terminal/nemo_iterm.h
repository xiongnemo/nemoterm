/* SPDX-License-Identifier: MIT */
#ifndef NEMO_ITERM_H
#define NEMO_ITERM_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define NEMO_ITERM_HEADER_MAX 4096u
#define NEMO_ITERM_FILE_MAX (2u * 1024u * 1024u)
#define NEMO_ITERM_PART_MAX (1024u * 1024u)

typedef struct NemoIterm NemoIterm;
typedef enum NemoItermCommand {
    NEMO_ITERM_FILE, NEMO_ITERM_MULTIPART, NEMO_ITERM_PART, NEMO_ITERM_END
} NemoItermCommand;
typedef enum NemoItermStatus {
    NEMO_ITERM_OK, NEMO_ITERM_MALFORMED, NEMO_ITERM_LIMIT,
    NEMO_ITERM_OUT_OF_MEMORY, NEMO_ITERM_NOT_INLINE
} NemoItermStatus;
typedef enum NemoItermUnit {
    NEMO_ITERM_AUTO, NEMO_ITERM_CELLS, NEMO_ITERM_PIXELS, NEMO_ITERM_PERCENT
} NemoItermUnit;
typedef struct NemoItermDimension {
    NemoItermUnit unit;
    uint32_t value;
} NemoItermDimension;
typedef struct NemoItermPacket {
    const unsigned char *data;
    size_t length;
    NemoItermDimension width, height;
    bool preserve_aspect;
} NemoItermPacket;

/* Admission includes allocation overlap during growth, before allocating.
 * current/extra cover this decoder; the owner may evict other image sources.
 * budget includes the object and owned bytes, excluding allocator metadata. */
typedef bool (*NemoItermAdmission)(void *ctx, size_t current, size_t extra);
NemoIterm *nemo_iterm_new(size_t budget, NemoItermAdmission, void *ctx);
void nemo_iterm_free(NemoIterm *);
void nemo_iterm_cancel(NemoIterm *);
/* Feed bytes after File=/MultipartFile=/FilePart= (FileEnd has no bytes).
 * The enclosing parser handles OSC framing, BEL/ST and CAN/SUB cancellation.
 * Only File contains a colon separating its bounded header from its payload.
 * Multipart base64 quartets may cross FilePart boundaries. */
bool nemo_iterm_begin(NemoIterm *, NemoItermCommand);
bool nemo_iterm_feed(NemoIterm *, const void *, size_t);
/* Finish one OSC. A true result is a completed inline file, consumed once.
 * Packet data is borrowed until the next begin/feed/cancel/free operation.
 * Multipart header and part completion return false with status OK. */
bool nemo_iterm_finish(NemoIterm *, NemoItermPacket *);
NemoItermStatus nemo_iterm_status(const NemoIterm *);
size_t nemo_iterm_memory(const NemoIterm *);
/* Resolve dimensions without allocating. Zero dimensions and overflow fail.
 * Auto/auto uses intrinsic pixels, fitting the viewport width if necessary. */
bool nemo_iterm_size(const NemoItermPacket *, unsigned natural_width,
                    unsigned natural_height, unsigned cell_width,
                    unsigned cell_height, unsigned cols, unsigned rows,
                    unsigned limit, unsigned *width, unsigned *height);

#endif
