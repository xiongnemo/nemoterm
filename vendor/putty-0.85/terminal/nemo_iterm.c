/* SPDX-License-Identifier: MIT */
#include "nemo_iterm.h"

static uint64_t dimension_pixels(NemoItermDimension d, unsigned cell, unsigned count)
{
    switch (d.unit) {
      case NEMO_ITERM_PIXELS: return d.value;
      case NEMO_ITERM_CELLS: return (uint64_t)d.value * cell;
      case NEMO_ITERM_PERCENT:
        /* Check multiplication before the percentage conversion. */
        if (cell && (uint64_t)d.value * count > UINT64_MAX / cell)
            return UINT64_MAX;
        return (uint64_t)d.value * count * cell / 100;
      default: return 0;
    }
}

bool nemo_iterm_size(const NemoItermPacket *p, unsigned nw, unsigned nh,
                    unsigned cw, unsigned ch, unsigned cols, unsigned rows,
                    unsigned limit, unsigned *width, unsigned *height)
{
    if (!p || !nw || !nh || !cw || !ch || !cols || !rows || !limit) return false;
    bool aw = p->width.unit == NEMO_ITERM_AUTO;
    bool ah = p->height.unit == NEMO_ITERM_AUTO;
    uint64_t w = aw ? nw : dimension_pixels(p->width, cw, cols);
    uint64_t h = ah ? nh : dimension_pixels(p->height, ch, rows);
    if (!w || !h || (!aw && w > limit) || (!ah && h > limit)) return false;
    if (aw && ah) {
        uint64_t viewport = (uint64_t)cw * cols;
        if (w > viewport) { w = viewport; h = (uint64_t)nh * w / nw; }
    } else if (aw) {
        w = (uint64_t)nw * h / nh;
    } else if (ah) {
        h = (uint64_t)nh * w / nw;
    } else if (p->preserve_aspect) {
        if (w * nh < h * nw) h = w * nh / nw;
        else w = h * nw / nh;
    }
    if (!w) w = 1;
    if (!h) h = 1;
    if (w > limit || h > limit) return false;
    *width = (unsigned)w; *height = (unsigned)h;
    return true;
}
#include <stdlib.h>
#include <string.h>

struct NemoIterm {
    size_t budget, capacity, length, encoded, part_chars, header_len;
    NemoItermAdmission admit;
    void *ctx;
    unsigned char *data;
    unsigned quad[4], quad_count;
    NemoItermCommand command;
    NemoItermStatus status;
    NemoItermDimension width, height;
    bool multipart, header_done, padded, sequence, completed, preserve_aspect;
    char header[NEMO_ITERM_HEADER_MAX+1];
};

size_t nemo_iterm_memory(const NemoIterm *s)
{ return s ? sizeof(*s)+s->capacity : 0; }

NemoItermStatus nemo_iterm_status(const NemoIterm *s)
{ return s ? s->status : NEMO_ITERM_OUT_OF_MEMORY; }

static bool fail(NemoIterm *s, NemoItermStatus status)
{
    s->status = status;
    free(s->data);
    s->data = NULL; s->length = s->capacity = 0;
    s->multipart = s->completed = false;
    return false;
}

void nemo_iterm_cancel(NemoIterm *s)
{
    if (!s) return;
    size_t budget = s->budget;
    NemoItermAdmission admit = s->admit;
    void *ctx = s->ctx;
    free(s->data);
    memset(s, 0, sizeof(*s));
    s->budget = budget; s->admit = admit; s->ctx = ctx;
    s->preserve_aspect = true;
}

NemoIterm *nemo_iterm_new(size_t budget, NemoItermAdmission admit, void *ctx)
{
    if (budget < sizeof(NemoIterm) ||
        (admit && !admit(ctx, 0, sizeof(NemoIterm)))) return NULL;
    NemoIterm *s = calloc(1, sizeof(*s));
    if (s) {
        s->budget = budget; s->admit = admit; s->ctx = ctx;
        s->preserve_aspect = true;
    }
    return s;
}

void nemo_iterm_free(NemoIterm *s)
{ if (s) { free(s->data); free(s); } }

bool nemo_iterm_begin(NemoIterm *s, NemoItermCommand command)
{
    if (!s) return false;
    if (command == NEMO_ITERM_FILE || command == NEMO_ITERM_MULTIPART) {
        nemo_iterm_cancel(s);
        s->multipart = command == NEMO_ITERM_MULTIPART;
    } else if ((command != NEMO_ITERM_PART && command != NEMO_ITERM_END) ||
               !s->multipart || !s->header_done || s->sequence ||
               s->status != NEMO_ITERM_OK || s->completed) {
        return fail(s, NEMO_ITERM_MALFORMED);
    }
    s->command = command; s->sequence = true; s->part_chars = 0;
    return true;
}

static bool dimension(const char *text, NemoItermDimension *out)
{
    if (!strcmp(text, "auto")) { *out = (NemoItermDimension){0}; return true; }
    uint32_t value = 0;
    const char *p = text;
    while (*p >= '0' && *p <= '9') {
        unsigned digit = *p++ - '0';
        if (value > (UINT32_MAX-digit)/10) return false;
        value = value*10+digit;
    }
    if (p == text) return false;
    NemoItermUnit unit = !*p ? NEMO_ITERM_CELLS : !strcmp(p,"px") ?
        NEMO_ITERM_PIXELS : !strcmp(p,"%") ? NEMO_ITERM_PERCENT : NEMO_ITERM_AUTO;
    if (unit == NEMO_ITERM_AUTO) return false;
    *out = (NemoItermDimension){unit, value};
    return true;
}

static bool header(NemoIterm *s)
{
    bool inline_image = false;
    s->header[s->header_len] = 0;
    for (char *field = s->header; field;) {
        char *next = strchr(field, ';');
        if (next) *next++ = 0;
        char *value = strchr(field, '=');
        if (value) {
            *value++ = 0;
            if (!strcmp(field, "width")) {
                if (!dimension(value, &s->width)) return fail(s, NEMO_ITERM_MALFORMED);
            } else if (!strcmp(field, "height")) {
                if (!dimension(value, &s->height)) return fail(s, NEMO_ITERM_MALFORMED);
            } else if (!strcmp(field, "inline") || !strcmp(field, "preserveAspectRatio")) {
                if (strcmp(value, "0") && strcmp(value, "1"))
                    return fail(s, NEMO_ITERM_MALFORMED);
                if (!strcmp(field, "inline")) inline_image = *value == '1';
                else s->preserve_aspect = *value == '1';
            }
            /* name/size are metadata, never paths or allocation authorities.
             * Unknown optional keys do not affect the decoded image. */
        }
        field = next;
    }
    if (!inline_image) return fail(s, NEMO_ITERM_NOT_INLINE);
    s->header_done = true;
    return true;
}

static bool append(NemoIterm *s, const unsigned char *bytes, size_t count)
{
    if (count > NEMO_ITERM_FILE_MAX-s->length) return fail(s, NEMO_ITERM_LIMIT);
    if (s->length+count > s->capacity) {
        size_t capacity = s->capacity ? s->capacity*2 : 4096;
        if (capacity > NEMO_ITERM_FILE_MAX) capacity = NEMO_ITERM_FILE_MAX;
        size_t current = nemo_iterm_memory(s);
        if (current > s->budget || capacity > s->budget-current ||
            (s->admit && !s->admit(s->ctx, current, capacity)))
            return fail(s, NEMO_ITERM_LIMIT);
        unsigned char *data = malloc(capacity);
        if (!data) return fail(s, NEMO_ITERM_OUT_OF_MEMORY);
        if (s->length) memcpy(data, s->data, s->length);
        free(s->data); s->data = data; s->capacity = capacity;
    }
    memcpy(s->data+s->length, bytes, count); s->length += count;
    return true;
}

static bool decode(NemoIterm *s, bool final)
{
    unsigned n = s->quad_count, *q = s->quad;
    if (!n) return true;
    if (n == 1 || q[0] >= 64 || q[1] >= 64 || (!final && n != 4) ||
        (n == 3 && q[2] == 64) || (n == 4 && q[2] == 64 && q[3] != 64))
        return fail(s, NEMO_ITERM_MALFORMED);
    unsigned count = n-1;
    if (n == 4 && q[3] == 64) count--;
    if (n == 4 && q[2] == 64) count--;
    if ((count == 1 && (q[1]&15)) || (count == 2 && (q[2]&3)))
        return fail(s, NEMO_ITERM_MALFORMED);
    unsigned char bytes[3] = {
        (unsigned char)((q[0]<<2) | (q[1]>>4)),
        (unsigned char)((q[1]<<4) | (q[2]>>2)),
        (unsigned char)((q[2]<<6) | q[3])
    };
    if (!append(s, bytes, count)) return false;
    s->padded = count != 3; s->quad_count = 0;
    memset(q, 0, sizeof(s->quad));
    return true;
}

bool nemo_iterm_feed(NemoIterm *s, const void *input, size_t length)
{
    if (!s || s->status != NEMO_ITERM_OK) return false;
    if (!s->sequence || (length && (!input || s->command == NEMO_ITERM_END)))
        return fail(s, NEMO_ITERM_MALFORMED);
    const unsigned char *bytes = input;
    for (size_t i = 0; i < length; i++) {
        unsigned char c = bytes[i];
        if (!s->header_done) {
            if (c == ':' && s->command == NEMO_ITERM_FILE) {
                if (!header(s)) return false;
            } else {
                if (c < 32 || c > 126) return fail(s, NEMO_ITERM_MALFORMED);
                if (s->header_len == NEMO_ITERM_HEADER_MAX) return fail(s, NEMO_ITERM_LIMIT);
                s->header[s->header_len++] = (char)c;
            }
            continue;
        }
        if (s->padded) return fail(s, NEMO_ITERM_MALFORMED);
        if (s->encoded == ((NEMO_ITERM_FILE_MAX+2u)/3u)*4u ||
            (s->command == NEMO_ITERM_PART && s->part_chars == NEMO_ITERM_PART_MAX))
            return fail(s, NEMO_ITERM_LIMIT);
        s->encoded++; s->part_chars++;
        unsigned value = c >= 'A' && c <= 'Z' ? c-'A' : c >= 'a' && c <= 'z' ?
            c-'a'+26 : c >= '0' && c <= '9' ? c-'0'+52 :
            c == '+' ? 62 : c == '/' ? 63 : c == '=' ? 64 : 255;
        if (value == 255) return fail(s, NEMO_ITERM_MALFORMED);
        s->quad[s->quad_count++] = value;
        if (s->quad_count == 4 && !decode(s, false)) return false;
    }
    return true;
}

bool nemo_iterm_finish(NemoIterm *s, NemoItermPacket *out)
{
    if (out) memset(out, 0, sizeof(*out));
    if (!s || s->status != NEMO_ITERM_OK || !s->sequence) return false;
    s->sequence = false;
    if (s->command == NEMO_ITERM_MULTIPART) { header(s); return false; }
    if (s->command == NEMO_ITERM_PART) return false;
    if (!s->header_done || !decode(s, true) || !s->length)
        return fail(s, s->status == NEMO_ITERM_OK ? NEMO_ITERM_MALFORMED : s->status);
    s->completed = true; s->multipart = false;
    if (out) *out = (NemoItermPacket){s->data, s->length, s->width, s->height, s->preserve_aspect};
    return true;
}
