/* SPDX-License-Identifier: MIT
 * DECUDK storage is lazy and independent of the fixed function-key buffer.
 * A complete string commits atomically; cancellation leaves old values intact.
 */
#define NEMO_UDK_KEYS 35
#define NEMO_UDK_INPUT_LIMIT 65536u
#define NEMO_UDK_STORAGE_LIMIT (1024u * 1024u)

struct NemoUdk {
    strbuf *value[NEMO_UDK_KEYS];
    size_t bytes;
};

static void nemo_udk_buffer_free(strbuf *buffer)
{
    if (buffer) strbuf_free(buffer);
}

static void nemo_udk_cancel(Terminal *term)
{
    nemo_udk_buffer_free(term->udk_pending);
    term->udk_pending = NULL;
}

static void nemo_udk_clear(Terminal *term)
{
    if (!term->udk) return;
    for (size_t i = 0; i < NEMO_UDK_KEYS; i++)
        nemo_udk_buffer_free(term->udk->value[i]);
    sfree(term->udk);
    term->udk = NULL;
}

static int nemo_udk_hex(unsigned char c)
{
    if (c >= '0' && c <= '9') return c-'0';
    if (c >= 'a' && c <= 'f') return c-'a'+10;
    if (c >= 'A' && c <= 'F') return c-'A'+10;
    return -1;
}

static void nemo_udk_finish(Terminal *term)
{
    if (!term->udk_pending) return;
    strbuf *updates[NEMO_UDK_KEYS] = {0};
    const unsigned char *p = (const unsigned char *)term->udk_pending->s;
    bool clear = term->sixel_header[0] == 0, valid = true;
    size_t total = !clear && term->udk ? term->udk->bytes : 0;
    while (*p) {
        const unsigned char *start = p;
        unsigned key = 0;
        while (*p >= '0' && *p <= '9') {
            unsigned digit = *p++-'0';
            key = key <= (UINT_MAX-digit)/10 ? key*10+digit : UINT_MAX;
        }
        if (*p == '/') {
            p++;
            int hi = -1;
            strbuf *value = key < NEMO_UDK_KEYS ? strbuf_new() : NULL;
            while (*p && *p != ';') {
                int digit = nemo_udk_hex(*p++);
                if (digit < 0) continue;
                if (hi < 0) hi = digit;
                else {
                    if (value) put_byte(value, (hi << 4) | digit);
                    hi = -1;
                }
            }
            if (value && value->len) {
                strbuf *old = updates[key] ? updates[key] :
                    !clear && term->udk ? term->udk->value[key] : NULL;
                size_t next = total-(old ? old->len : 0)+value->len;
                if (next > NEMO_UDK_STORAGE_LIMIT) {
                    nemo_udk_buffer_free(value); valid = false; break;
                }
                total = next;
                nemo_udk_buffer_free(updates[key]);
                updates[key] = value;
            } else nemo_udk_buffer_free(value);
        }
        if (*p == ';') p++;
        if (p == start) break;
    }
    if (valid) {
        if (clear) nemo_udk_clear(term);
        for (size_t i = 0; i < NEMO_UDK_KEYS; i++) {
            if (!updates[i]) continue;
            if (!term->udk) {
                term->udk = snew(struct NemoUdk);
                memset(term->udk, 0, sizeof(*term->udk));
            }
            nemo_udk_buffer_free(term->udk->value[i]);
            term->udk->value[i] = updates[i];
            updates[i] = NULL;
        }
        if (term->udk) term->udk->bytes = total;
    }
    for (size_t i = 0; i < NEMO_UDK_KEYS; i++) nemo_udk_buffer_free(updates[i]);
    nemo_udk_cancel(term);
}

/* Call after local bindings and negotiated keyboard protocols. Values are raw
 * application input, never protocol framing, even when they contain CSI/ST. */
bool term_send_udk(Terminal *term, int number, bool shift, bool ctrl)
{
    static const unsigned codes[] = {
        11,12,13,14,15,17,18,19,20,21,23,24,25,26,28,29,31,32,33,34
    };
    if (term->funky_type != FUNKY_VT220 || !shift || !term->udk) return false;
    if (number < 1 || number > 63) return false;
    if (ctrl) number += 12;
    if (number < 1 || number > (int)lenof(codes)) return false;
    strbuf *value = term->udk->value[codes[number-1]];
    if (!value) return false;
    term_keyinput(term, -1, value->s, value->len);
    return true;
}
