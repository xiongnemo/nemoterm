/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main

typedef struct BellReference {
    const char *name;
    bool fresh, urgent, raise;
    const char *wire;
    size_t wire_length;
    const char *reply;
    size_t reply_length;
    int focus;
    bool cover, before_urgent, before_above, before_focus;
    bool after_urgent, after_above, after_focus;
} BellReference;
#include "../../../tests/bell_modes_reference.h"

static bool urgent, above;
static unsigned sounds, attention_requests, raises;
static void sound(TermWin *win, int mode) { sounds++; }
static void attention(TermWin *win, bool request, bool raise)
{
    if (request) { urgent = true; attention_requests++; }
    if (raise) { above = true; raises++; }
}

static Mock *fresh(TermWinVtable *vt, bool initial_urgent, bool initial_raise)
{
    Mock *mk = mock_new();
    mk->tw.vt = vt;
    conf_set_int(mk->conf,CONF_beep,BELL_DISABLED);
    conf_set_bool(mk->conf,CONF_bellovl,false);
    conf_set_int(mk->conf,CONF_beep_ind,initial_urgent?B_IND_FLASH:B_IND_DISABLED);
    conf_set_bool(mk->conf,CONF_nemo_bell_raise,initial_raise);
    conf_set_bool(mk->conf,CONF_nemo_bell_on_reset,true); /* XTerm reference resource */
    mk->term = term_init(mk->conf,mk->ucsdata,&mk->tw);
    mk->ldisc = ldisc_create(mk->conf,mk->term,&mk->backend,&mk->seat);
    reset(mk);
    term_set_focus(mk->term,false);
    urgent = above = false;
    sounds = attention_requests = raises = 0;
    return mk;
}

static bool replay(TermWinVtable *vt, bool bytewise)
{
    Mock *mk = NULL;
    bool failed = false;
    for (size_t i = 0; i < lenof(bell_reference); i++) {
        const BellReference *r = &bell_reference[i];
        if (r->fresh) {
            if (mk) { failed |= mk->any_test_failed; mock_free(mk); }
            mk = fresh(vt,r->urgent,r->raise);
        }
        test_context(mk,"%s / %s",r->name,bytewise?"bytewise":"whole");
        if (r->cover) above = false;
        if (r->focus >= 0) {
            /* This adapter models the captured X11 focus/stacking policy.
             * Real Windows API effects require the separate native fixture. */
            if (r->focus && !mk->term->has_focus && mk->term->bell_is_urgent)
                urgent = false;
            term_set_focus(mk->term,r->focus != 0);
        }
        IEQUAL(urgent,r->before_urgent); IEQUAL(above,r->before_above);
        IEQUAL(mk->term->has_focus,r->before_focus);
        for (size_t offset = 0; offset < r->wire_length;) {
            size_t length = bytewise ? 1 : r->wire_length;
            term_data(mk->term,r->wire+offset,length);
            offset += length;
        }
        if (mk->to_backend->len != r->reply_length ||
            memcmp(mk->to_backend->s,r->reply,r->reply_length))
            report_fail(mk,__FILE__,__LINE__,"bell reply differs: %zu / %zu bytes",
                        mk->to_backend->len,r->reply_length);
        strbuf_clear(mk->to_backend);
        IEQUAL(urgent,r->after_urgent); IEQUAL(above,r->after_above);
        IEQUAL(mk->term->has_focus,r->after_focus);
    }
    failed |= mk->any_test_failed; mock_free(mk);
    printf("Bell %s: 112 fresh cases / 192 unchanged replies and modeled window states\n",
           bytewise?"bytewise":"whole");
    return failed;
}

static bool policies(TermWinVtable *vt)
{
    Mock *mk = fresh(vt,false,false);
    test_context(mk,"attention still occurs under sound/raise overload suppression");
    conf_set_bool(mk->conf,CONF_bellovl,true);
    conf_set_int(mk->conf,CONF_bellovl_n,3);
    conf_set_int(mk->conf,CONF_bellovl_t,60000);
    conf_set_int(mk->conf,CONF_bellovl_s,60000);
    term_reconfig(mk->term,mk->conf);
    term_data_fragmented(mk->term,"\033[?1042;1043h");
    for (int i=0;i<100;i++) term_data_fragmented(mk->term,"\007");
    IEQUAL(sounds,2); IEQUAL(raises,2); IEQUAL(attention_requests,100);
    IEQUAL(mk->term->nbeeps,3);

    test_context(mk,"unrelated reconfiguration preserves downloaded mode values");
    term_reconfig(mk->term,mk->conf);
    IEQUAL(mk->term->bell_is_urgent,true); IEQUAL(mk->term->bell_raise,true);
    conf_set_int(mk->conf,CONF_beep_ind,B_IND_FLASH);
    conf_set_bool(mk->conf,CONF_nemo_bell_raise,true);
    term_reconfig(mk->term,mk->conf);
    conf_set_int(mk->conf,CONF_beep_ind,B_IND_DISABLED);
    conf_set_bool(mk->conf,CONF_nemo_bell_raise,false);
    term_reconfig(mk->term,mk->conf);
    IEQUAL(mk->term->bell_is_urgent,false); IEQUAL(mk->term->bell_raise,false);

    test_context(mk,"reset bell is opt-in and OSC BEL never rings");
    conf_set_bool(mk->conf,CONF_bellovl,false);
    conf_set_bool(mk->conf,CONF_nemo_bell_on_reset,false);
    term_reconfig(mk->term,mk->conf); sounds = 0;
    term_data_fragmented(mk->term,"\033c\033]2;silent\007");
    IEQUAL(sounds,0);
    conf_set_bool(mk->conf,CONF_nemo_bell_on_reset,true);
    term_reconfig(mk->term,mk->conf);
    term_data_fragmented(mk->term,"\033c"); IEQUAL(sounds,1);
    bool failed = mk->any_test_failed; mock_free(mk);
    return failed;
}

int main(void)
{
    TermWinVtable vt = mock_termwin_vt;
    vt.bell = sound; vt.bell_attention = attention;
    bool failed = replay(&vt,false);
    failed |= replay(&vt,true);
    failed |= policies(&vt);
    printf("Bell modes terminal: %s\n",failed?"FAILED":"passed");
    return failed ? 1 : 0;
}
