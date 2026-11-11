/* SPDX-License-Identifier: MIT */
#include "nemo_osc52.h"
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef struct Selection {
    struct Selection *next, *prev;
    size_t length;
    unsigned mask;
    char text[];
} Selection;

struct NemoOsc52 {
    Selection *oldest, *newest, *slots[9];
    size_t cached;
    char *text;
    size_t length, capacity, payload_chars;
    unsigned selector_chars, quad_count, quad[4];
    char targets[NEMO_OSC52_TARGETS_MAX+1];
    bool allow_write, allow_read, payload, invalid_header, invalid_data;
    bool overflow, ended, question, finished;
};

bool nemo_osc52_utf8(const char *text, size_t length)
{
    for (size_t i = 0; i < length;) {
        unsigned c = (unsigned char)text[i++], need, minimum;
        if (!c) return false; /* Win32 text cannot represent embedded NUL. */
        if (c < 128) continue;
        if (c >= 0xc2 && c <= 0xdf) { c &= 31; need = 1; minimum = 0x80; }
        else if (c >= 0xe0 && c <= 0xef) { c &= 15; need = 2; minimum = 0x800; }
        else if (c >= 0xf0 && c <= 0xf4) { c &= 7; need = 3; minimum = 0x10000; }
        else return false;
        if (need > length-i) return false;
        while (need--) {
            unsigned next = (unsigned char)text[i++];
            if ((next & 0xc0) != 0x80) return false;
            c = (c << 6) | (next & 63);
        }
        if (c < minimum || c > 0x10ffff || (c >= 0xd800 && c <= 0xdfff)) return false;
    }
    return true;
}

void nemo_osc52_cancel(NemoOsc52 *s)
{
    if (!s) return;
    free(s->text);
    s->text = NULL; s->length = s->capacity = s->payload_chars = 0;
    s->selector_chars = s->quad_count = 0;
    memset(s->targets, 0, sizeof(s->targets));
    s->allow_write = s->allow_read = s->payload = s->invalid_header = false;
    s->invalid_data = s->overflow = s->ended = s->question = s->finished = false;
}

void nemo_osc52_begin(NemoOsc52 **state, bool write, bool read)
{
    if (!*state && (write || read)) *state = calloc(1, sizeof(**state));
    nemo_osc52_cancel(*state);
    if (*state) { (*state)->allow_write = write; (*state)->allow_read = read; }
}

static void append(NemoOsc52 *s, const unsigned char *bytes, size_t count)
{
    if (count > NEMO_OSC52_TEXT_MAX-s->length) { s->overflow = true; return; }
    if (s->allow_write && s->length+count > s->capacity) {
        size_t capacity = s->capacity ? s->capacity*2 : 64;
        if (capacity > NEMO_OSC52_TEXT_MAX) capacity = NEMO_OSC52_TEXT_MAX;
        char *new_text = realloc(s->text, capacity+1);
        if (!new_text) { s->overflow = true; return; }
        s->text = new_text; s->capacity = capacity;
    }
    if (s->allow_write) memcpy(s->text+s->length, bytes, count);
    s->length += count;
}

static void decode(NemoOsc52 *s, bool final)
{
    unsigned n = s->quad_count, *q = s->quad;
    if (!n) return;
    if (n == 1 || q[0] >= 64 || q[1] >= 64 ||
        (!final && n != 4) || (n == 3 && q[2] == 64) ||
        (n == 4 && q[2] == 64 && q[3] != 64)) {
        s->invalid_data = true; return;
    }
    unsigned count = n-1;
    if (n == 4 && q[3] == 64) count--;
    if (n == 4 && q[2] == 64) count--;
    if ((count == 1 && (q[1] & 15)) || (count == 2 && (q[2] & 3))) {
        s->invalid_data = true; return;
    }
    unsigned char bytes[3] = {
        (q[0]<<2) | (q[1]>>4), (q[1]<<4) | (q[2]>>2), (q[2]<<6) | q[3]
    };
    append(s, bytes, count);
    s->ended = count != 3;
    s->quad_count = 0;
    memset(q, 0, sizeof(s->quad));
}

void nemo_osc52_feed(NemoOsc52 *s, unsigned char c)
{
    if (!s || s->finished || s->overflow) return;
    if (!s->payload) {
        if (c == ';') {
            s->payload = true;
            if (!s->targets[0] && !s->invalid_header) strcpy(s->targets, "s0");
        } else if (++s->selector_chars > 64 || !c || !strchr("cpqs01234567", c)) {
            s->invalid_header = true;
        } else if (!strchr(s->targets, c)) {
            size_t n = strlen(s->targets);
            if (n < NEMO_OSC52_TARGETS_MAX) s->targets[n] = c;
        }
        return;
    }
    if (++s->payload_chars > ((NEMO_OSC52_TEXT_MAX+2)/3)*4) {
        s->overflow = true; return;
    }
    if (c == '?' && s->payload_chars == 1) { s->question = true; return; }
    if (s->question || s->ended) s->invalid_data = true;
    if (s->invalid_data || s->invalid_header) return;
    unsigned v = c >= 'A' && c <= 'Z' ? c-'A' : c >= 'a' && c <= 'z' ? c-'a'+26 :
        c >= '0' && c <= '9' ? c-'0'+52 : c == '+' ? 62 : c == '/' ? 63 : c == '=' ? 64 : 255;
    if (v == 255) { s->invalid_data = true; return; }
    s->quad[s->quad_count++] = v;
    if (s->quad_count == 4) decode(s, false);
}

NemoOsc52Packet nemo_osc52_finish(NemoOsc52 *s)
{
    NemoOsc52Packet packet = {0};
    if (!s || !s->payload || s->invalid_header || s->overflow) return packet;
    if (!s->finished && !s->question && !s->invalid_data) decode(s, true);
    s->finished = true;
    if (s->overflow) return packet;
    memcpy(packet.targets, s->targets, sizeof(packet.targets));
    if (s->question && s->payload_chars == 1) {
        if (s->allow_read) packet.action = NEMO_OSC52_QUERY;
    } else if (s->allow_write) {
        if (s->invalid_data || !s->length) packet.action = NEMO_OSC52_CLEAR;
        else if (nemo_osc52_utf8(s->text, s->length)) {
            s->text[s->length] = 0;
            packet.action = NEMO_OSC52_WRITE;
            packet.text = s->text; packet.length = s->length;
        }
    }
    return packet;
}

unsigned nemo_osc52_cache_mask(char target)
{
    return target == 'q' ? 1 : target >= '0' && target <= '7' ? 2u << (target-'0') : 0;
}

static void remove_selection(NemoOsc52 *s, Selection *value)
{
    for (unsigned i = 0; i < 9; i++) if (s->slots[i] == value) s->slots[i] = NULL;
    if (value->prev) value->prev->next = value->next; else s->oldest = value->next;
    if (value->next) value->next->prev = value->prev; else s->newest = value->prev;
    s->cached -= sizeof(*value)+value->length+1;
    free(value);
}

bool nemo_osc52_store(NemoOsc52 *s, unsigned mask, const char *text, size_t length)
{
    mask &= 511;
    if (!s || !mask || length > NEMO_OSC52_TEXT_MAX || (length && !text)) return false;
    Selection *value = NULL;
    if (length) {
        value = malloc(sizeof(*value)+length+1);
        if (!value) return false;
        *value = (Selection){.length=length, .mask=mask};
        memcpy(value->text, text, length); value->text[length] = 0;
    }
    for (unsigned i = 0; i < 9; i++) {
        if (!(mask & (1u << i)) || !s->slots[i]) continue;
        Selection *old = s->slots[i]; s->slots[i] = NULL;
        old->mask &= ~(1u << i);
        if (!old->mask) remove_selection(s, old);
    }
    if (value) {
        size_t size = sizeof(*value)+length+1;
        while (s->cached+size > NEMO_OSC52_CACHE_MAX) remove_selection(s, s->oldest);
        value->prev = s->newest;
        if (s->newest) s->newest->next = value; else s->oldest = value;
        s->newest = value; s->cached += size;
        for (unsigned i = 0; i < 9; i++) if (mask & (1u << i)) s->slots[i] = value;
    }
    return true;
}

bool nemo_osc52_get(const NemoOsc52 *s, char target, const char **text, size_t *length)
{
    unsigned mask = nemo_osc52_cache_mask(target);
    if (!s || !mask) return false;
    unsigned i = 0; while (!(mask & (1u << i))) i++;
    if (!s->slots[i]) return false;
    *text = s->slots[i]->text; *length = s->slots[i]->length;
    return true;
}

size_t nemo_osc52_cached(const NemoOsc52 *s) { return s ? s->cached : 0; }
size_t nemo_osc52_memory(const NemoOsc52 *s)
{ return s ? sizeof(*s)+s->cached+(s->text ? s->capacity+1 : 0) : 0; }

void nemo_osc52_free(NemoOsc52 *s)
{
    if (!s) return;
    nemo_osc52_cancel(s);
    while (s->oldest) remove_selection(s, s->oldest);
    free(s);
}
