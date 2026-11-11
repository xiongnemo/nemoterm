/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main

static struct {
    strbuf *system;
    bool available, asynchronous;
    unsigned reads, writes;
    uint64_t pending;
    size_t backlog;
} clip;

static bool system_write(TermWin *win, const char *text, size_t length)
{
    clip.writes++; clip.available = true;
    strbuf_clear(clip.system); put_data(clip.system, text, length);
    return true;
}
static bool system_read(TermWin *win, uint64_t id)
{
    Mock *mk = container_of(win, Mock, tw);
    clip.reads++; clip.pending = id;
    if (!clip.asynchronous)
        term_osc52_read_result(mk->term, id, clip.system->s, clip.system->len, clip.available);
    return true;
}
static size_t send_backlog(Backend *be) { return clip.backlog; }
static void silent_bell(TermWin *win, int mode) {}

static void sequence(Mock *mk, const char *input, const char *reply)
{
    test_context(mk, "OSC 52 input %.80s", input);
    strbuf_clear(mk->to_backend);
    term_data_fragmented(mk->term, input);
    SEQUAL(mk->to_backend->s, reply);
}

static void permissions(Mock *mk, bool write, bool read)
{
    conf_set_bool(mk->conf, CONF_nemo_osc52_write, write);
    conf_set_bool(mk->conf, CONF_nemo_osc52_read, read);
    term_reconfig(mk->term, mk->conf);
}

static void test_terminal_osc52(Mock *mk)
{
    reset(mk);
    sequence(mk, "\033]52;c;aGVsbG8=\007", "");
    IEQUAL(clip.writes, 1); SEQUAL(clip.system->s, "hello");
    sequence(mk, "\033]52;c;?\007", ""); IEQUAL(clip.reads, 0);
    permissions(mk, true, true);
    sequence(mk, "\033]52;c;?\007", "\033]52;c;aGVsbG8=\007");
    sequence(mk, "\033]52;c;?\033\\", "\033]52;c;aGVsbG8=\033\\");
    sequence(mk, "\033%G\033]52;c;?\302\234", "\033]52;c;aGVsbG8=\033\\");
    sequence(mk, "\033]52;p;5Lit8J+YgA==\007\033]52;p;?\007", "\033]52;p;5Lit8J+YgA==\007");
    SEQUAL(clip.system->s, "hello");
    sequence(mk, "\033]52;q01234567;Y2FjaGU=\007\033]52;q;?\007\033]52;7;?\007",
            "\033]52;q;Y2FjaGU=\007\033]52;7;Y2FjaGU=\007");
    sequence(mk, "\033]52;q;!\007\033]52;q7;?\007", "\033]52;7;Y2FjaGU=\007");
    sequence(mk, "\033]52;;ZGVmYXVsdA==\007\033]52;0;?\007\033]52;s;?\007",
            "\033]52;0;ZGVmYXVsdA==\007\033]52;c;ZGVmYXVsdA==\007");
    sequence(mk, "\033]52;c;\007\033]52;c;?\007", "\033]52;c;\007");
    sequence(mk, "\033]52;c;YQ==\007\033]52;c;AA==\007\033]52;c;?\007", "\033]52;c;YQ==\007");
    unsigned writes = clip.writes;
    sequence(mk, "\033]52Xc;Yg==\007\033]52;x;Yg==\007\033]52;c;Yg\030\007", "");
    sequence(mk, "\033]52;c;Yg\032\007\033]52;c;Yg\r\007\033]52;c;Yg\n\007", "");
    sequence(mk, "\033]52;c;Yg\033[0m\007", "");
    sequence(mk, "\033]52;c;Yg\302\030\007\033]52;c;Yg\302\032\007", "");
    sequence(mk, "\033]52;c;Yg\302\r\007\033]52;c;Yg\302\033[0m\007", "");
    IEQUAL(clip.writes, writes); SEQUAL(clip.system->s, "a");
    permissions(mk, false, true);
    sequence(mk, "\033]52;c;Yg==\007\033]52;c;!\007\033]52;c;?\007", "\033]52;c;YQ==\007");
    IEQUAL(clip.writes, writes);
    permissions(mk, false, false);
    unsigned reads = clip.reads;
    sequence(mk, "\033]52;c;?\007\033]52;p;?\007", ""); IEQUAL(clip.reads, reads);
    permissions(mk, true, true);
    clip.asynchronous = true;
    sequence(mk, "\033]52;c;?\007\033]52;c;?\007", ""); IEQUAL(clip.reads, reads+1);
    uint64_t old = clip.pending;
    permissions(mk, true, false); permissions(mk, true, true);
    term_osc52_read_result(mk->term, old, "secret", 6, true);
    SEQUAL(mk->to_backend->s, "");
    sequence(mk, "\033]52;c;?\007\033c", ""); old = clip.pending;
    term_osc52_read_result(mk->term, old, "secret", 6, true); SEQUAL(mk->to_backend->s, "");
    clip.available = false;
    sequence(mk, "\033]52;c7;?\033\\", "");
    term_osc52_read_result(mk->term, clip.pending, NULL, 0, false);
    SEQUAL(mk->to_backend->s, "\033]52;7;Y2FjaGU=\033\\");
    /* Both pending replies and new requests obey the outgoing backlog bound. */
    sequence(mk, "\033]52;c;?\007", "");
    clip.backlog = 512*1024+1;
    term_osc52_read_result(mk->term, clip.pending, "secret", 6, true);
    SEQUAL(mk->to_backend->s, "");
    reads = clip.reads;
    sequence(mk, "\033]52;c;?\007\033]52;7;?\007", ""); IEQUAL(clip.reads, reads);
    clip.backlog = 0; clip.asynchronous = false; clip.available = true;
    sequence(mk, "\033]52;c;Yg==\007\033]52;c;?\007", "\033]52;c;Yg==\007");
}

static NemoOsc52Packet parse(NemoOsc52 **s, const char *input, bool write, bool read)
{
    nemo_osc52_begin(s, write, read);
    for (const unsigned char *p = (const unsigned char *)input; *p; p++) nemo_osc52_feed(*s, *p);
    return nemo_osc52_finish(*s);
}

static void test_codec(Mock *mk)
{
    NemoOsc52 *s = NULL;
    parse(&s, "c;?", false, false); IEQUAL(s == NULL, true);
    static const struct { const char *input; NemoOsc52Action action; const char *text; } cases[] = {
        {"c;",NEMO_OSC52_CLEAR,""}, {"c;!",NEMO_OSC52_CLEAR,""},
        {"c;YQ==",NEMO_OSC52_WRITE,"a"}, {"c;YWI=",NEMO_OSC52_WRITE,"ab"},
        {"c;YWJj",NEMO_OSC52_WRITE,"abc"}, {"c;YQ",NEMO_OSC52_WRITE,"a"},
        {"c;YWI",NEMO_OSC52_WRITE,"ab"}, {"c;YWJjZA",NEMO_OSC52_WRITE,"abcd"},
        {"c;YR==",NEMO_OSC52_CLEAR,""}, {"c;YWL=",NEMO_OSC52_CLEAR,""},
        {"c;Y",NEMO_OSC52_CLEAR,""}, {"c;Y===",NEMO_OSC52_CLEAR,""},
        {"c;YQ=",NEMO_OSC52_CLEAR,""}, {"c;YQ==YQ==",NEMO_OSC52_CLEAR,""},
        {"c;?",NEMO_OSC52_QUERY,""}, {"c;?x",NEMO_OSC52_CLEAR,""},
        {"c;AA==",NEMO_OSC52_NONE,""}, {"c;/w==",NEMO_OSC52_NONE,""},
        {"c;wIA=",NEMO_OSC52_NONE,""}, {"c;7aCA",NEMO_OSC52_NONE,""},
        {"c;9JCAgA==",NEMO_OSC52_NONE,""}, {"c;5Lit8J+YgA==",NEMO_OSC52_WRITE,"\xe4\xb8\xad\xf0\x9f\x98\x80"},
        {"c;DQoJGw==",NEMO_OSC52_WRITE,"\r\n\t\033"},
        {"x;YQ==",NEMO_OSC52_NONE,""}, {"c",NEMO_OSC52_NONE,""},
    };
    for (size_t i = 0; i < lenof(cases); i++) {
        test_context(mk, "OSC 52 codec %s", cases[i].input);
        NemoOsc52Packet p = parse(&s, cases[i].input, true, true);
        IEQUAL(p.action, cases[i].action);
        if (p.action == NEMO_OSC52_WRITE) { IEQUAL(p.length, strlen(cases[i].text)); SEQUAL(p.text, cases[i].text); }
    }
    NemoOsc52Packet p = parse(&s, "ccppssq7766554433221100;?", true, true);
    SEQUAL(p.targets, "cpsq76543210");
    p = parse(&s, ";?", true, true); SEQUAL(p.targets, "s0");
    p = parse(&s, "c;YQ==", false, true); IEQUAL(p.action, NEMO_OSC52_NONE);
    p = parse(&s, "c;?", true, false); IEQUAL(p.action, NEMO_OSC52_NONE);
    char *large = snewn(NEMO_OSC52_TEXT_MAX+2, char);
    memset(large, 'a', NEMO_OSC52_TEXT_MAX+1); large[NEMO_OSC52_TEXT_MAX+1] = 0;
    for (unsigned extra = 0; extra < 2; extra++) {
        strbuf *base64 = base64_encode_sb(make_ptrlen(large, NEMO_OSC52_TEXT_MAX+extra), 0);
        nemo_osc52_begin(&s, true, true); nemo_osc52_feed(s, 'c'); nemo_osc52_feed(s, ';');
        for (size_t i = 0; i < base64->len; i++) nemo_osc52_feed(s, base64->u[i]);
        p = nemo_osc52_finish(s);
        IEQUAL(p.action, extra ? NEMO_OSC52_NONE : NEMO_OSC52_WRITE);
        if (!extra) IEQUAL(p.length, NEMO_OSC52_TEXT_MAX);
        strbuf_free(base64);
    }
    nemo_osc52_cancel(s);
    IEQUAL(nemo_osc52_memory(s) < 1024, true);
    for (unsigned i = 0; i < 100; i++) {
        unsigned mask = 1u << (i%9);
        IEQUAL(nemo_osc52_store(s, mask, large, NEMO_OSC52_TEXT_MAX), true);
        IEQUAL(nemo_osc52_cached(s) <= NEMO_OSC52_CACHE_MAX, true);
        IEQUAL(nemo_osc52_memory(s) <= NEMO_OSC52_CACHE_MAX+1024, true);
    }
    IEQUAL(nemo_osc52_store(s, 511, "shared", 6), true);
    size_t shared = nemo_osc52_cached(s);
    IEQUAL(shared < 128, true);
    for (const char *target = "q01234567"; *target; target++) {
        const char *text; size_t length;
        IEQUAL(nemo_osc52_get(s, *target, &text, &length), true);
        SEQUAL(text, "shared"); IEQUAL(length, 6);
    }
    nemo_osc52_store(s, 1, "new", 3);
    nemo_osc52_store(s, 510, "", 0);
    IEQUAL(nemo_osc52_cached(s) < shared, true);
    nemo_osc52_store(s, 1, "", 0); IEQUAL(nemo_osc52_cached(s), 0);
    sfree(large); nemo_osc52_free(s);
}

int main(void)
{
    Mock *mk = mock_new();
    TermWinVtable tw = mock_termwin_vt;
    tw.osc52_write = system_write; tw.osc52_read = system_read;
    tw.bell = silent_bell;
    BackendVtable be = mock_backend_vt; be.sendbuffer = send_backlog;
    mk->tw.vt = &tw; mk->backend.vt = &be;
    clip.system = strbuf_new();
    mk->term = term_init(mk->conf, mk->ucsdata, &mk->tw);
    mk->ldisc = ldisc_create(mk->conf, mk->term, &mk->backend, &mk->seat);
    test_codec(mk); test_terminal_osc52(mk);
    bool failed = mk->any_test_failed;
    mock_free(mk); strbuf_free(clip.system);
    puts(failed ? "OSC 52 suite FAILED" : "OSC 52 suite passed");
    return failed ? 1 : 0;
}
