/* SPDX-License-Identifier: MIT */
#include "nemo_kitty.h"
#include <stdlib.h>
#include <string.h>

static int key_index(char key)
{
    if (key >= 'A' && key <= 'Z') return key - 'A';
    if (key >= 'a' && key <= 'z') return key - 'a' + 26;
    return -1;
}

bool nemo_kitty_has(const NemoKittyCommand *c, char key)
{
    int i = key_index(key);
    return c && i >= 0 && (c->present & (UINT64_C(1) << i));
}

uint32_t nemo_kitty_get(const NemoKittyCommand *c, char key)
{
    if (nemo_kitty_has(c, key)) return c->values[key_index(key)];
    switch (key) {
      case 'a': return 't';
      case 't': return 'd';
      case 'd': return 'a';
      case 'f': return 32;
      default: return 0;
    }
}

int32_t nemo_kitty_signed(const NemoKittyCommand *c, char key)
{
    uint32_t v = nemo_kitty_get(c, key);
    return v <= INT32_MAX ? (int32_t)v :
        (int32_t)(-1 - (int64_t)(UINT32_MAX - v));
}

static void set(NemoKittyCommand *c, char key, uint32_t value)
{
    int i = key_index(key);
    c->present |= UINT64_C(1) << i;
    c->values[i] = value;
}

struct NemoKitty {
    size_t budget, capacity, length, header_length, chunk_chars;
    NemoKittyAdmission admit;
    void *ctx;
    unsigned char *data;
    NemoKittyCommand command, upload;
    NemoKittyStatus status;
    unsigned quad[4], quad_count;
    bool active, parsed, pending, feature_query, data_command, padded;
    char header[NEMO_KITTY_HEADER_MAX];
};

size_t nemo_kitty_memory(const NemoKitty *s)
{ return s ? sizeof(*s) + s->capacity : 0; }
bool nemo_kitty_pending(const NemoKitty *s)
{ return s && s->pending; }
NemoKittyStatus nemo_kitty_status(const NemoKitty *s)
{ return s ? s->status : NEMO_KITTY_OUT_OF_MEMORY; }

static void drop_data(NemoKitty *s)
{
    free(s->data);
    s->data = NULL;
    s->capacity = s->length = 0;
    s->pending = false;
}

static bool fail(NemoKitty *s, NemoKittyStatus status)
{
    s->status = status;
    drop_data(s);
    return false;
}

NemoKitty *nemo_kitty_new(size_t budget, NemoKittyAdmission admit, void *ctx)
{
    if (budget < sizeof(NemoKitty) ||
        (admit && !admit(ctx, 0, sizeof(NemoKitty)))) return NULL;
    NemoKitty *s = calloc(1, sizeof(*s));
    if (s) { s->budget = budget; s->admit = admit; s->ctx = ctx; }
    return s;
}

void nemo_kitty_free(NemoKitty *s)
{ if (s) { free(s->data); free(s); } }

void nemo_kitty_cancel(NemoKitty *s)
{
    if (!s) return;
    size_t budget = s->budget;
    NemoKittyAdmission admit = s->admit;
    void *ctx = s->ctx;
    free(s->data);
    memset(s, 0, sizeof(*s));
    s->budget = budget; s->admit = admit; s->ctx = ctx;
}

bool nemo_kitty_begin(NemoKitty *s)
{
    if (!s) return false;
    if (s->active) nemo_kitty_cancel(s);
    if (!s->pending) drop_data(s);
    memset(&s->command, 0, sizeof(s->command));
    s->header_length = s->chunk_chars = s->quad_count = 0;
    s->parsed = s->feature_query = s->data_command = s->padded = false;
    s->status = NEMO_KITTY_OK;
    s->active = true;
    return true;
}

static bool number(const char *p, size_t n, bool is_signed, uint32_t *out)
{
    bool negative = n && *p == '-';
    if (negative) {
        if (!is_signed) return false;
        p++; n--;
    }
    if (!n) return false;
    uint32_t limit = is_signed ? (negative ? UINT32_C(2147483648) : INT32_MAX) : UINT32_MAX;
    uint32_t value = 0;
    for (size_t i = 0; i < n; i++) {
        unsigned digit = (unsigned char)p[i] - (unsigned)'0';
        if (digit > 9 || value > (limit - digit) / 10) return false;
        value = value * 10 + digit;
    }
    *out = negative ? 0u - value : value;
    return true;
}

static bool parse_header(NemoKitty *s)
{
    s->parsed = true;
    const char *p = s->header, *end = p + s->header_length;
    while (p < end) {
        const char *next = memchr(p, ',', (size_t)(end - p));
        const char *stop = next ? next : end;
        if (stop - p < 3 || key_index(p[0]) < 0 || p[1] != '=')
            return fail(s, NEMO_KITTY_MALFORMED);
        char key = p[0];
        uint32_t value;
        if (key == 'a' || key == 'd' || key == 'e' || key == 't' || key == 'o') {
            if (stop - p != 3 || p[2] < '!' || p[2] > '~')
                return fail(s, NEMO_KITTY_MALFORMED);
            value = (unsigned char)p[2];
        } else if (!number(p + 2, (size_t)(stop - p - 2),
                           key == 'z' || key == 'H' || key == 'V', &value)) {
            return fail(s, NEMO_KITTY_MALFORMED);
        }
        set(&s->command, key, value);
        if (next && next + 1 == end) return fail(s, NEMO_KITTY_MALFORMED);
        p = next ? next + 1 : end;
    }
    NemoKittyCommand *c = &s->command;
    if (nemo_kitty_get(c, 'm') > 1 || nemo_kitty_get(c, 'q') > 2 ||
        (nemo_kitty_has(c, 'i') && nemo_kitty_has(c, 'I')))
        return fail(s, NEMO_KITTY_MALFORMED);
    uint32_t action = nemo_kitty_get(c, 'a');
    if (nemo_kitty_has(c, 'e')) {
        if (action != 'q' || !nemo_kitty_get(c, 'i') || nemo_kitty_get(c, 'm'))
            return fail(s, NEMO_KITTY_MALFORMED);
        s->feature_query = true;
        return true;
    }
    if (action == 'd') drop_data(s);
    if (s->pending) {
        uint64_t allowed = (UINT64_C(1) << key_index('m')) |
            (UINT64_C(1) << key_index('q'));
        if (nemo_kitty_get(&s->upload, 'a') == 'f') {
            allowed |= UINT64_C(1) << key_index('a');
            if (action != 'f') return fail(s, NEMO_KITTY_MALFORMED);
        }
        if (c->present & ~allowed) return fail(s, NEMO_KITTY_MALFORMED);
        uint32_t more = nemo_kitty_get(c, 'm');
        bool quiet_present = nemo_kitty_has(c, 'q');
        uint32_t quiet = nemo_kitty_get(c, 'q');
        *c = s->upload;
        set(c, 'm', more);
        if (quiet_present) set(c, 'q', quiet);
        action = nemo_kitty_get(c, 'a');
    }
    s->data_command = action == 't' || action == 'T' || action == 'q' || action == 'f';
    if (nemo_kitty_get(c, 'm') &&
        (!s->data_command || nemo_kitty_get(c, 't') != 'd'))
        return fail(s, NEMO_KITTY_MALFORMED);
    return true;
}

static bool reserve(NemoKitty *s, size_t count)
{
    if (count > NEMO_KITTY_DATA_MAX - s->length)
        return fail(s, NEMO_KITTY_LIMIT);
    size_t needed = s->length + count;
    if (needed <= s->capacity) return true;
    size_t current = nemo_kitty_memory(s);
    size_t available = s->budget - current;
    if (needed > available) return fail(s, NEMO_KITTY_LIMIT);
    size_t capacity = s->capacity ? s->capacity : 256;
    while (capacity < needed) capacity *= 2;
    if (capacity > NEMO_KITTY_DATA_MAX) capacity = NEMO_KITTY_DATA_MAX;
    if (capacity > available) capacity = available;
    if (s->admit && !s->admit(s->ctx, current, capacity))
        return fail(s, NEMO_KITTY_LIMIT);
    unsigned char *data = malloc(capacity);
    if (!data) return fail(s, NEMO_KITTY_OUT_OF_MEMORY);
    if (s->length) memcpy(data, s->data, s->length);
    free(s->data);
    s->data = data; s->capacity = capacity;
    return true;
}

static bool emit_quad(NemoKitty *s)
{
    unsigned *q = s->quad;
    unsigned n = s->quad_count;
    if (n < 2 || q[0] >= 64 || q[1] >= 64)
        return fail(s, NEMO_KITTY_MALFORMED);
    size_t bytes = n == 2 || q[2] == 64 ? 1 : n == 3 || q[3] == 64 ? 2 : 3;
    if ((bytes == 1 && ((q[1] & 15) || (n > 2 && (n != 4 || q[3] != 64)))) ||
        (bytes == 2 && (q[2] & 3))) return fail(s, NEMO_KITTY_MALFORMED);
    if (!reserve(s, bytes)) return false;
    s->data[s->length++] = (unsigned char)((q[0] << 2) | (q[1] >> 4));
    if (bytes > 1) s->data[s->length++] = (unsigned char)((q[1] << 4) | (q[2] >> 2));
    if (bytes > 2) s->data[s->length++] = (unsigned char)((q[2] << 6) | q[3]);
    s->padded = n == 4 && bytes < 3;
    s->quad_count = 0;
    return true;
}

static bool payload(NemoKitty *s, unsigned char ch)
{
    if (s->feature_query) return true;
    if (!s->data_command) return fail(s, NEMO_KITTY_MALFORMED);
    if (++s->chunk_chars > NEMO_KITTY_CHUNK_MAX)
        return fail(s, NEMO_KITTY_LIMIT);
    unsigned value;
    if (ch >= 'A' && ch <= 'Z') value = ch - 'A';
    else if (ch >= 'a' && ch <= 'z') value = ch - 'a' + 26;
    else if (ch >= '0' && ch <= '9') value = ch - '0' + 52;
    else if (ch == '+') value = 62;
    else if (ch == '/') value = 63;
    else if (ch == '=') value = 64;
    else return fail(s, NEMO_KITTY_MALFORMED);
    if (s->padded) return fail(s, NEMO_KITTY_MALFORMED);
    s->quad[s->quad_count++] = value;
    return s->quad_count < 4 || emit_quad(s);
}

bool nemo_kitty_feed(NemoKitty *s, const void *data, size_t length)
{
    if (!s || !s->active || s->status != NEMO_KITTY_OK) return false;
    if (length && !data) return fail(s, NEMO_KITTY_MALFORMED);
    const unsigned char *p = data;
    for (size_t i = 0; i < length; i++) {
        if (s->parsed) {
            if (!payload(s, p[i])) return false;
        } else if (p[i] == ';') {
            if (!parse_header(s)) return false;
        } else {
            if (s->header_length == NEMO_KITTY_HEADER_MAX)
                return fail(s, NEMO_KITTY_LIMIT);
            s->header[s->header_length++] = (char)p[i];
        }
    }
    return true;
}

NemoKittyResult nemo_kitty_finish(NemoKitty *s, NemoKittyPacket *packet)
{
    if (packet) memset(packet, 0, sizeof(*packet));
    if (!s || !s->active) return NEMO_KITTY_ERROR;
    if (s->status == NEMO_KITTY_OK && !s->parsed) parse_header(s);
    if (packet) packet->command = s->command;
    s->active = false;
    if (s->status != NEMO_KITTY_OK) return NEMO_KITTY_ERROR;
    if (s->feature_query) return NEMO_KITTY_PACKET;
    if (nemo_kitty_get(&s->command, 'm')) {
        if (s->quad_count || s->padded) {
            fail(s, NEMO_KITTY_MALFORMED);
            return NEMO_KITTY_ERROR;
        }
        s->upload = s->command;
        s->pending = true;
        return NEMO_KITTY_MORE;
    }
    if (s->quad_count && !emit_quad(s)) return NEMO_KITTY_ERROR;
    s->pending = false;
    if (packet) { packet->data = s->data; packet->length = s->length; }
    return NEMO_KITTY_PACKET;
}
