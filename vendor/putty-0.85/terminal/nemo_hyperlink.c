/* SPDX-License-Identifier: MIT */
#include "nemo_hyperlink.h"
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

typedef struct NemoLink {
    uint32_t handle;
    size_t uri_len, id_len;
    char text[];                 /* URI NUL id NUL */
} NemoLink;

struct NemoHyperlinks {
    NemoLink *entries[NEMO_LINK_COUNT_MAX]; /* FIFO ring, sorted by handle */
    size_t first, count, bytes;
    uint32_t last_handle;        /* do not wrap, even when the ring is empty */
};

static bool alpha(unsigned char c)
{
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z');
}

static bool digit(unsigned char c) { return c >= '0' && c <= '9'; }
static bool hex(unsigned char c)
{
    return digit(c) || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F');
}

static bool valid_uri(const char *uri, size_t len)
{
    if (!len || len > NEMO_LINK_URI_MAX || !alpha(uri[0])) return false;
    size_t scheme = 1;
    while (scheme < len && (alpha(uri[scheme]) || digit(uri[scheme]) ||
                           strchr("+.-", uri[scheme]))) scheme++;
    if (scheme == len || uri[scheme] != ':') return false;
    for (size_t i = scheme + 1; i < len; i++) {
        unsigned char c = uri[i];
        if (c == '%') {
            if (i + 2 >= len || !hex(uri[i+1]) || !hex(uri[i+2])) return false;
            i += 2;
        } else if (!alpha(c) && !digit(c) &&
                   !strchr("-._~:/?#[]@!$&'()*+,;=", c)) {
            return false;
        }
    }
    return true;
}

static NemoLink *entry(const NemoHyperlinks *links, size_t i)
{
    return links->entries[(links->first + i) % NEMO_LINK_COUNT_MAX];
}

static size_t cost(const NemoLink *link)
{
    return sizeof(*link) + link->uri_len + link->id_len + 2;
}

static void evict(NemoHyperlinks *links)
{
    NemoLink *old = entry(links, 0);
    links->bytes -= cost(old);
    free(old);
    links->entries[links->first] = NULL;
    links->first = (links->first + 1) % NEMO_LINK_COUNT_MAX;
    links->count--;
}

uint32_t nemo_hyperlink_parse(NemoHyperlinks **owner,
                            const char *payload, size_t len)
{
    if (!len || len > NEMO_LINK_OSC_MAX) return 0;
    /* Validate by explicit length: an embedded NUL must not truncate a URI. */
    for (size_t i = 0; i < len; i++)
        if ((unsigned char)payload[i] < 32 ||
            (unsigned char)payload[i] > 126) return 0;
    const char *sep = memchr(payload, ';', len);
    if (!sep) return 0;
    size_t params_len = sep - payload, uri_len = len - params_len - 1;
    const char *uri = sep + 1, *id = "";
    size_t id_len = 0;
    bool have_id = false;
    if (!valid_uri(uri, uri_len)) return 0; /* includes an explicit close */
    for (size_t start = 0; start < params_len;) {
        size_t end = start;
        while (end < params_len && payload[end] != ':') end++;
        if (end - start >= 3 && !memcmp(payload + start, "id=", 3)) {
            if (have_id) return 0;
            have_id = true;
            id = payload + start + 3;
            id_len = end - start - 3;
            if (id_len > NEMO_LINK_ID_MAX) return 0;
        }
        start = end + 1;         /* unknown parameters are ignored */
    }

    NemoHyperlinks *links = *owner;
    if (!links) {
        links = calloc(1, sizeof(*links));
        if (!links) return 0;
        links->bytes = sizeof(*links);
        *owner = links;
    }
    if (id_len) {
        for (size_t i = 0; i < links->count; i++) {
            NemoLink *link = entry(links, i);
            if (link->uri_len == uri_len && link->id_len == id_len &&
                !memcmp(link->text, uri, uri_len) &&
                !memcmp(link->text + uri_len + 1, id, id_len))
                return link->handle;
        }
    }
    if (links->last_handle == UINT32_MAX) return 0;
    size_t bytes = sizeof(NemoLink) + uri_len + id_len + 2;
    while (links->count && (links->count == NEMO_LINK_COUNT_MAX ||
                           links->bytes + bytes > NEMO_LINK_BUDGET))
        evict(links);
    NemoLink *link = malloc(bytes);
    if (!link) return 0;
    link->handle = ++links->last_handle;
    link->uri_len = uri_len;
    link->id_len = id_len;
    memcpy(link->text, uri, uri_len);
    link->text[uri_len] = 0;
    memcpy(link->text + uri_len + 1, id, id_len);
    link->text[uri_len + 1 + id_len] = 0;
    links->entries[(links->first + links->count++) % NEMO_LINK_COUNT_MAX] = link;
    links->bytes += bytes;
    return link->handle;
}

const char *nemo_hyperlink_lookup(const NemoHyperlinks *links, uint32_t handle)
{
    if (!links || !handle) return NULL;
    size_t lo = 0, hi = links->count;
    while (lo < hi) {
        size_t mid = lo + (hi - lo) / 2;
        NemoLink *link = entry(links, mid);
        if (link->handle < handle) lo = mid + 1;
        else if (link->handle > handle) hi = mid;
        else return link->text;
    }
    return NULL;
}

size_t nemo_hyperlink_memory(const NemoHyperlinks *links)
{
    return links ? links->bytes : 0;
}

size_t nemo_hyperlink_count(const NemoHyperlinks *links)
{
    return links ? links->count : 0;
}

void nemo_hyperlink_free(NemoHyperlinks *links)
{
    if (!links) return;
    while (links->count) evict(links);
    free(links);
}
