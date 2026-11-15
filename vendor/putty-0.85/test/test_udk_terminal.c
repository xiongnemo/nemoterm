/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main

typedef struct UdkReference {
    const char *name;
    bool reset;
    int profile;
    const char *wire;
    size_t wire_length;
    const char *reply;
    size_t reply_length;
    int key, modifiers;
} UdkReference;
#include "../../../tests/udk_reference.h"

static void response(Mock *mk, const void *expected, size_t length)
{
    if (mk->to_backend->len != length || memcmp(mk->to_backend->s,expected,length)) {
        report_fail(mk,__FILE__,__LINE__,"UDK reply mismatch: got %zu, expected %zu bytes",
                    mk->to_backend->len,length);
        printf("actual:");
        for (size_t i = 0; i < min(mk->to_backend->len,32); i++)
            printf(" %02x",(unsigned char)mk->to_backend->s[i]);
        puts("");
    }
    strbuf_clear(mk->to_backend);
}

static void profile(Mock *mk, int type)
{
    conf_set_int(mk->conf,CONF_funky_type,type);
    term_reconfig(mk->term,mk->conf);
}

static void key(Mock *mk, int number, unsigned mods)
{
    if (term_send_udk(mk->term,number,mods&1,mods&2)) return;
    char output[64];
    bool consumed = false;
    int length = format_function_key(output,mk->term,number,mods&1,mods&2,mods&4,&consumed);
    if ((mods&4) && !consumed) term_keyinput(mk->term,-1,"\033",1);
    term_keyinput(mk->term,-1,output,length);
}

static void replay(Mock *mk, bool bytewise)
{
    for (size_t i = 0; i < lenof(udk_reference); i++) {
        const UdkReference *r = &udk_reference[i];
        if (r->reset) {
            reset(mk);
            profile(mk,r->profile);
            term_data_fragmented(mk->term,"\033[65;1\"p");
        }
        test_context(mk,"%s / %s",r->name,bytewise?"bytewise":"whole");
        for (size_t offset = 0; offset < r->wire_length;) {
            size_t length = bytewise ? 1 : r->wire_length;
            term_data(mk->term,r->wire+offset,length);
            offset += length;
        }
        if (r->key) key(mk,r->key,r->modifiers);
        response(mk,r->reply,r->reply_length);
    }
    printf("UDK %s: %zu unchanged reference replies\n",bytewise?"bytewise":"whole",lenof(udk_reference));
}

static void download(Mock *mk, unsigned code, size_t length, char hex)
{
    strbuf *wire = strbuf_new();
    put_fmt(wire,"\033P1;1|%u/",code);
    for (size_t i = 0; i < length; i++) { put_byte(wire,'4'); put_byte(wire,hex); }
    put_dataz(wire,"\033\\");
    term_data(mk->term,wire->s,wire->len);
    strbuf_free(wire);
}

static void direct_checks(Mock *mk)
{
    reset(mk); profile(mk,FUNKY_VT220);
    test_context(mk,"lazy allocation, cancellation and input budget");
    IEQUAL(mk->term->udk == NULL,true);
    IEQUAL(mk->term->udk_pending == NULL,true);
    term_data_fragmented(mk->term,"\033P0;1|17/41\033\\\033P0;1|17/42");
    key(mk,6,1); response(mk,"A",1);
    term_data_fragmented(mk->term,"\030");
    IEQUAL(mk->term->udk_pending == NULL,true);
    key(mk,6,1); response(mk,"A",1);
    strbuf *oversize = strbuf_new();
    put_dataz(oversize,"\033P0;1|17/");
    for (size_t i = 0; i < 65537; i++) put_byte(oversize,'4');
    put_dataz(oversize,"\033\\");
    term_data(mk->term,oversize->s,oversize->len);
    strbuf_free(oversize);
    IEQUAL(mk->term->udk_pending == NULL,true);
    key(mk,6,1); response(mk,"A",1);

    test_context(mk,"aggregate storage limit rejects a definition and retains prior values");
    for (unsigned code = 0; code < 32; code++) download(mk,code,32760,'1');
    download(mk,32,257,'2'); /* 32*32760+257 > 1 MiB */
    IEQUAL(term_send_udk(mk->term,18,true,false),false);
    IEQUAL(term_send_udk(mk->term,6,true,false),true);
    IEQUAL(mk->to_backend->len,32760);
    for (size_t i = 0; i < mk->to_backend->len; i++) IEQUAL(mk->to_backend->s[i],'A');
    strbuf_clear(mk->to_backend);
    term_data_fragmented(mk->term,"\033c");
    IEQUAL(mk->term->udk == NULL,true);

    test_context(mk,"profile changes preserve definitions and raw bytes bypass C1 conversion");
    term_data_fragmented(mk->term,"\033P0;1|17/1b5b31376d00ff\033\\\033 G");
    profile(mk,FUNKY_XTERM_216);
    IEQUAL(term_send_udk(mk->term,6,true,false),false);
    profile(mk,FUNKY_VT220);
    key(mk,6,1); response(mk,"\033[17m\000\377",7);
    IEQUAL(term_send_udk(mk->term,INT_MAX,true,true),false);

    test_context(mk,"64 complete/cancelled reset cycles release owned payloads");
    for (unsigned i = 0; i < 64; i++) {
        term_data_fragmented(mk->term,"\033 F\033P0;1|17/41\033\\\033P0;1|18/42\032");
        key(mk,6,1); response(mk,"A",1);
        term_data_fragmented(mk->term,"\033c");
        IEQUAL(mk->term->udk == NULL,true);
        IEQUAL(mk->term->udk_pending == NULL,true);
    }
    /* ASan/LSan also verifies destruction while both kinds of payload exist. */
    term_data_fragmented(mk->term,"\033P0;1|17/41\033\\\033P0;1|18/42");
    puts("UDK lifetime: input/aggregate budgets, raw bytes and 64 reset cycles checked");
}

int main(void)
{
    Mock *mk = mock_new();
    mk->ucsdata->line_codepage = CP_UTF8;
    mk->term = term_init(mk->conf,mk->ucsdata,&mk->tw);
    mk->ldisc = ldisc_create(mk->conf,mk->term,&mk->backend,&mk->seat);
    replay(mk,false);
    replay(mk,true);
    direct_checks(mk);
    bool failed = mk->any_test_failed;
    mock_free(mk);
    printf("UDK terminal: %s\n",failed?"FAILED":"passed");
    return failed ? 1 : 0;
}
