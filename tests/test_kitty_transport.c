/* SPDX-License-Identifier: MIT */
#include "nemo_kitty.h"
#ifdef NDEBUG
#undef NDEBUG
#endif
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define BUDGET (4u * 1024u * 1024u)
static unsigned assertions;
#define CHECK(x) do { assertions++; assert(x); } while (0)

static void feed(NemoKitty *s, const char *text)
{ CHECK(nemo_kitty_feed(s, text, strlen(text))); }

static NemoKittyPacket packet(NemoKitty *s, const void *data, size_t length)
{
    NemoKittyPacket p;
    CHECK(nemo_kitty_finish(s, &p) == NEMO_KITTY_PACKET);
    CHECK(p.length == length);
    CHECK(!length || (p.data && !memcmp(p.data, data, length)));
    return p;
}

static void start(NemoKitty *s, const char *text)
{ CHECK(nemo_kitty_begin(s)); feed(s, text); }

static void more(NemoKitty *s)
{
    NemoKittyPacket p;
    memset(&p, 0x55, sizeof(p));
    CHECK(nemo_kitty_finish(s, &p) == NEMO_KITTY_MORE);
    CHECK(!p.data && !p.length && nemo_kitty_pending(s));
}

static void bad(NemoKitty *s, const char *text, NemoKittyStatus status)
{
    CHECK(nemo_kitty_begin(s));
    nemo_kitty_feed(s, text, strlen(text));
    NemoKittyPacket p;
    CHECK(nemo_kitty_finish(s, &p) == NEMO_KITTY_ERROR);
    CHECK(nemo_kitty_status(s) == status);
    CHECK(!p.data && !p.length && !nemo_kitty_pending(s));
    start(s, "a=q,i=31,f=24,s=1,v=1;AAAA");
    const unsigned char zero[3] = {0};
    packet(s, zero, sizeof(zero));
}

static void vectors(NemoKitty *s)
{
    static const char *encoded[] = {"", "Zg==", "Zm8=", "Zm9v", "Zm9vYg==", "Zm9vYmE=", "Zm9vYmFy", "Zg", "Zm8"};
    static const char *plain[] = {"", "f", "fo", "foo", "foob", "fooba", "foobar", "f", "fo"};
    for (size_t i = 0; i < sizeof(encoded)/sizeof(*encoded); i++) {
        char wire[128];
        snprintf(wire, sizeof(wire), "a=q,i=31,f=100;%s", encoded[i]);
        size_t length = strlen(wire);
        for (size_t cut = 0; cut <= length; cut++) {
            CHECK(nemo_kitty_begin(s));
            CHECK(nemo_kitty_feed(s, wire, cut));
            CHECK(nemo_kitty_feed(s, wire+cut, length-cut));
            NemoKittyPacket p = packet(s, plain[i], strlen(plain[i]));
            CHECK(nemo_kitty_get(&p.command, 'i') == 31);
            CHECK(nemo_kitty_get(&p.command, 'a') == 'q');
            CHECK(nemo_kitty_finish(s, &p) == NEMO_KITTY_ERROR);
            CHECK(!p.data && !p.length && !p.command.present);
            CHECK(!nemo_kitty_feed(s, "A", 1));
        }
    }
    const char *wire = "f=32,s=1,v=1;AP8A/w==";
    CHECK(nemo_kitty_begin(s));
    for (size_t i = 0; i < strlen(wire); i++) CHECK(nemo_kitty_feed(s, wire+i, 1));
    const unsigned char binary[] = {0, 255, 0, 255};
    NemoKittyPacket p = packet(s, binary, sizeof(binary));
    CHECK(nemo_kitty_get(&p.command, 'a') == 't');
    CHECK(nemo_kitty_get(&p.command, 't') == 'd');
    CHECK(!nemo_kitty_has(&p.command, 'a'));
}

static void commands(NemoKitty *s)
{
    const char *wire = "a=p,i=4294967295,p=4294967295,x=1,y=2,w=3,h=4,X=5,Y=6,"
        "c=7,r=8,C=1,U=1,z=-2147483648,P=9,Q=10,H=2147483647,V=-123,N=15,q=2";
    start(s, wire);
    NemoKittyPacket p = packet(s, NULL, 0);
    CHECK(nemo_kitty_get(&p.command, 'i') == UINT32_MAX);
    CHECK(nemo_kitty_get(&p.command, 'p') == UINT32_MAX);
    CHECK(nemo_kitty_signed(&p.command, 'z') == INT32_MIN);
    CHECK(nemo_kitty_signed(&p.command, 'H') == INT32_MAX);
    CHECK(nemo_kitty_signed(&p.command, 'V') == -123);
    CHECK(nemo_kitty_get(&p.command, 'N') == 15);
    CHECK(nemo_kitty_get(&p.command, 'f') == 32);
    CHECK(nemo_kitty_get(&p.command, 'X') == 5 && nemo_kitty_get(&p.command, 'x') == 1);
    start(s, "a=t,t=f,f=100,O=4294967295,S=4294967295,I=7;Zm9v");
    p = packet(s, "foo", 3);
    CHECK(nemo_kitty_get(&p.command, 't') == 'f');
    CHECK(nemo_kitty_get(&p.command, 'O') == UINT32_MAX);
    CHECK(nemo_kitty_get(&p.command, 'I') == 7);
    /* Transport preserves media/format metadata; it never opens that name. */
    start(s, "a=d,d=Z,z=-1");
    p = packet(s, NULL, 0);
    CHECK(nemo_kitty_get(&p.command, 'd') == 'Z');
    CHECK(nemo_kitty_signed(&p.command, 'z') == -1);
    start(s, "a=a,i=1,s=2,v=3,z=-0,r=0,c=1");
    p = packet(s, NULL, 0);
    CHECK(nemo_kitty_signed(&p.command, 'z') == 0 && nemo_kitty_has(&p.command, 'r'));
    start(s, "a=c,i=1,r=1,c=2,C=1;");
    packet(s, NULL, 0);
    start(s, "a=p,i=000000000000000000000000000000001,i=2,j=18");
    p = packet(s, NULL, 0);
    CHECK(nemo_kitty_get(&p.command, 'i') == 2 && nemo_kitty_get(&p.command, 'j') == 18);
    CHECK(!nemo_kitty_has(&p.command, '!') && !nemo_kitty_get(&p.command, '!'));
}

static void chunks(NemoKitty *s)
{
    start(s, "a=T,i=9,p=4,f=24,s=2,v=1,q=2,m=1;Zm9v");
    more(s);
    start(s, "m=0;YmFy");
    NemoKittyPacket p = packet(s, "foobar", 6);
    CHECK(nemo_kitty_get(&p.command, 'i') == 9 && nemo_kitty_get(&p.command, 'p') == 4);
    CHECK(nemo_kitty_get(&p.command, 'a') == 'T' && nemo_kitty_get(&p.command, 'q') == 2);
    CHECK(!nemo_kitty_pending(s));
    start(s, "i=8,m=1;Zm9v"); more(s);
    start(s, "m=1,q=1;YmFy"); more(s);
    start(s, ";Zg==");
    p = packet(s, "foobarf", 7);
    CHECK(nemo_kitty_get(&p.command, 'q') == 1);
    start(s, "a=f,i=9,r=2,m=1;Zm9v"); more(s);
    start(s, "a=f,m=0;YmFy");
    p = packet(s, "foobar", 6);
    CHECK(nemo_kitty_get(&p.command, 'a') == 'f' && nemo_kitty_get(&p.command, 'r') == 2);
    start(s, "i=8,m=1;"); more(s);
    start(s, "m=0;Zm9v"); packet(s, "foo", 3);

    /* Feature queries neither append to, complete, nor discard a transmission. */
    start(s, "a=T,i=9,m=1;Zm9v"); more(s);
    size_t memory = nemo_kitty_memory(s);
    start(s, "a=q,i=31,e=T,U=1,C=1;");
    unsigned char ignored[NEMO_KITTY_CHUNK_MAX + 1];
    memset(ignored, 0xff, sizeof(ignored));
    CHECK(nemo_kitty_feed(s, ignored, sizeof(ignored)));
    p = packet(s, NULL, 0);
    CHECK(nemo_kitty_get(&p.command, 'e') == 'T' && nemo_kitty_get(&p.command, 'i') == 31);
    CHECK(nemo_kitty_pending(s) && nemo_kitty_memory(s) == memory);
    start(s, "a=q,i=32,e=f,r=1"); packet(s, NULL, 0);
    CHECK(nemo_kitty_pending(s));
    start(s, "m=0;YmFy");
    p = packet(s, "foobar", 6);
    CHECK(nemo_kitty_get(&p.command, 'i') == 9 && !nemo_kitty_has(&p.command, 'e'));

    start(s, "i=7,m=1;Zm9v"); more(s);
    start(s, "a=d,d=A");
    p = packet(s, NULL, 0);
    CHECK(!nemo_kitty_pending(s) && nemo_kitty_get(&p.command, 'a') == 'd');
    start(s, "i=8;YmFy"); packet(s, "bar", 3);
    start(s, "i=7,m=1;Zm9v"); more(s);
    nemo_kitty_cancel(s);
    CHECK(!nemo_kitty_pending(s));
    start(s, "i=8;YmFy"); packet(s, "bar", 3);
    /* A second begin interrupts an unfinished APC and its upload. */
    start(s, "i=7,m=1;Zm9v"); more(s);
    start(s, "m=1;Ym");
    start(s, "i=8;Zg=="); packet(s, "f", 1);
}

static void invalid(NemoKitty *s)
{
    static const char *bad_headers[] = {
        "a", "aa=p", "a=", "a=pp", ",a=p", "a=p,", "a=p,,i=1", "i =1", "i= 1",
        "i=+1", "i=-1", "i=4294967296", "i=9999999999999999999999999999999999999",
        "z=2147483648", "z=-2147483649", "z=--1", "H=-", "V=NaN", "x=1.5",
        "q=3", "m=2", "i=1,I=1", "i=0,I=0", "a=p,m=1", "t=f,m=1",
        "e=T", "a=q,e=T", "a=q,i=0,e=T", "a=q,i=1,e=T,m=1", "a=p,i=1;AAAA"
    };
    for (size_t i = 0; i < sizeof(bad_headers)/sizeof(*bad_headers); i++)
        bad(s, bad_headers[i], NEMO_KITTY_MALFORMED);
    static const char *bad_base64[] = {
        ";A", ";=AAA", ";A=AA", ";AA=A", ";AA=", ";A===", ";====", ";Zh==",
        ";Zm9=", ";AB", ";AAB", ";Zm 9v", ";Zm9v\n", ";Zm9v-", ";Zg==AA==",
        "m=1;Zg==", "m=1;Zg", "m=1;Zm8", ";Zg===="
    };
    for (size_t i = 0; i < sizeof(bad_base64)/sizeof(*bad_base64); i++)
        bad(s, bad_base64[i], NEMO_KITTY_MALFORMED);
    start(s, "i=1,m=1;Zm9v"); more(s);
    bad(s, "m=0,i=1;YmFy", NEMO_KITTY_MALFORMED);
    start(s, "a=f,i=1,m=1;Zm9v"); more(s);
    bad(s, "m=0;YmFy", NEMO_KITTY_MALFORMED);
    start(s, ";");
    CHECK(!nemo_kitty_feed(s, NULL, 1));
    NemoKittyPacket p;
    CHECK(nemo_kitty_finish(s, &p) == NEMO_KITTY_ERROR);
    const unsigned char nul_header[] = {'i', '=', '1', 0, ';'};
    CHECK(nemo_kitty_begin(s));
    CHECK(!nemo_kitty_feed(s, nul_header, sizeof(nul_header)));
    CHECK(nemo_kitty_finish(s, &p) == NEMO_KITTY_ERROR);
    CHECK(nemo_kitty_status(s) == NEMO_KITTY_MALFORMED);
}

typedef struct Guard { size_t limit, peak; unsigned calls; } Guard;
static bool admit(void *ctx, size_t current, size_t extra)
{
    Guard *g = ctx;
    g->calls++;
    CHECK(current <= BUDGET && extra <= BUDGET - current);
    if (current + extra > g->peak) g->peak = current + extra;
    return current <= g->limit && extra <= g->limit - current;
}

static void bounds(void)
{
    CHECK(!nemo_kitty_new(1, NULL, NULL));
    Guard g = {0};
    CHECK(!nemo_kitty_new(BUDGET, admit, &g));
    g.limit = BUDGET;
    NemoKitty *s = nemo_kitty_new(BUDGET, admit, &g);
    CHECK(s);
    char header[NEMO_KITTY_HEADER_MAX + 2];
    for (size_t i = 0; i < NEMO_KITTY_HEADER_MAX - 4; i += 4) memcpy(header+i, "x=0,", 4);
    memcpy(header+NEMO_KITTY_HEADER_MAX-4, "x=00", 4);
    header[NEMO_KITTY_HEADER_MAX] = 0;
    start(s, header); packet(s, NULL, 0);
    header[NEMO_KITTY_HEADER_MAX] = '0'; header[NEMO_KITTY_HEADER_MAX+1] = 0;
    bad(s, header, NEMO_KITTY_LIMIT);
    char encoded[NEMO_KITTY_CHUNK_MAX + 1];
    memset(encoded, 'A', sizeof(encoded));
    start(s, "i=1,m=1;");
    CHECK(nemo_kitty_feed(s, encoded, NEMO_KITTY_CHUNK_MAX)); more(s);
    const unsigned char zero[NEMO_KITTY_CHUNK_MAX / 4 * 3] = {0};
    start(s, "m=0;"); packet(s, zero, sizeof(zero));
    nemo_kitty_free(s);
}

static void quota(void)
{
    Guard g = {BUDGET, 0, 0};
    NemoKitty *s = nemo_kitty_new(BUDGET, admit, &g);
    CHECK(s);
    size_t empty = nemo_kitty_memory(s);
    char encoded[NEMO_KITTY_CHUNK_MAX + 1];
    memset(encoded, 'A', sizeof(encoded));
    start(s, ";");
    CHECK(!nemo_kitty_feed(s, encoded, sizeof(encoded)));
    CHECK(nemo_kitty_status(s) == NEMO_KITTY_LIMIT && nemo_kitty_memory(s) == empty);
    NemoKittyPacket p;
    CHECK(nemo_kitty_finish(s, &p) == NEMO_KITTY_ERROR);
    size_t sent = 0;
    while (NEMO_KITTY_DATA_MAX - sent >= NEMO_KITTY_CHUNK_MAX / 4 * 3) {
        start(s, sent ? "m=1;" : "i=7,m=1;");
        CHECK(nemo_kitty_feed(s, encoded, NEMO_KITTY_CHUNK_MAX)); more(s);
        sent += NEMO_KITTY_CHUNK_MAX / 4 * 3;
    }
    size_t remaining = NEMO_KITTY_DATA_MAX - sent;
    size_t chars = (remaining + 2) / 3 * 4;
    if (remaining % 3) encoded[chars-1] = '=';
    if (remaining % 3 == 1) encoded[chars-2] = '=';
    start(s, "m=0;");
    CHECK(nemo_kitty_feed(s, encoded, chars));
    CHECK(nemo_kitty_finish(s, &p) == NEMO_KITTY_PACKET);
    CHECK(p.length == NEMO_KITTY_DATA_MAX);
    for (size_t i = 0; i < p.length; i++) CHECK(p.data[i] == 0);
    CHECK(g.peak > nemo_kitty_memory(s) && g.peak <= BUDGET);
    nemo_kitty_cancel(s);
    CHECK(nemo_kitty_memory(s) == empty);
    /* One byte beyond the cumulative ceiling fails even though every APC
     * independently respects the 4096-character chunk limit. */
    memset(encoded, 'A', sizeof(encoded));
    sent = 0;
    while (NEMO_KITTY_DATA_MAX - sent >= NEMO_KITTY_CHUNK_MAX / 4 * 3) {
        start(s, sent ? "m=1;" : "i=7,m=1;");
        CHECK(nemo_kitty_feed(s, encoded, NEMO_KITTY_CHUNK_MAX)); more(s);
        sent += NEMO_KITTY_CHUNK_MAX / 4 * 3;
    }
    start(s, "m=0;");
    CHECK(!nemo_kitty_feed(s, encoded, (NEMO_KITTY_DATA_MAX - sent + 3) / 3 * 4));
    CHECK(nemo_kitty_finish(s, &p) == NEMO_KITTY_ERROR);
    CHECK(nemo_kitty_status(s) == NEMO_KITTY_LIMIT && nemo_kitty_memory(s) == empty);
    g.limit = empty + 100;
    start(s, ";");
    CHECK(!nemo_kitty_feed(s, "AAAA", 4));
    CHECK(nemo_kitty_status(s) == NEMO_KITTY_LIMIT && nemo_kitty_memory(s) == empty);
    nemo_kitty_free(s);
    s = nemo_kitty_new(empty + 1, NULL, NULL);
    CHECK(s);
    start(s, ";Zg=="); packet(s, "f", 1);
    nemo_kitty_free(s);
}

static void fragmented_noise(NemoKitty *s)
{
    uint32_t state = 0x286a91c5;
    for (unsigned run = 0; run < 2000; run++) {
        CHECK(nemo_kitty_begin(s));
        if (run & 1) feed(s, "i=3;");
        for (unsigned i = 0; i < 200; i++) {
            state ^= state << 13; state ^= state >> 17; state ^= state << 5;
            unsigned char b = (unsigned char)state;
            if (!nemo_kitty_feed(s, &b, 1)) break;
        }
        NemoKittyPacket p;
        nemo_kitty_finish(s, &p);
        CHECK(nemo_kitty_memory(s) <= BUDGET);
        nemo_kitty_cancel(s);
    }
    start(s, "a=q,i=31,f=24,s=1,v=1;AAAA");
    const unsigned char zero[3] = {0}; packet(s, zero, 3);
}

int main(void)
{
    NemoKitty *s = nemo_kitty_new(BUDGET, NULL, NULL);
    CHECK(s);
    vectors(s); commands(s); chunks(s); invalid(s); fragmented_noise(s);
    nemo_kitty_free(s);
    bounds(); quota();
    nemo_kitty_free(NULL); nemo_kitty_cancel(NULL);
    CHECK(!nemo_kitty_begin(NULL) && !nemo_kitty_pending(NULL));
    CHECK(!nemo_kitty_memory(NULL));
    CHECK(nemo_kitty_status(NULL) == NEMO_KITTY_OUT_OF_MEMORY);
    printf("Kitty transport: %u assertions passed\n", assertions);
    return 0;
}
