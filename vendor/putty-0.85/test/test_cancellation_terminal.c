/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main

typedef struct CancellationReference {
    const char *name, *wire;
    size_t wire_length;
    const char *reply;
    size_t reply_length;
} CancellationReference;
#include "../../../tests/control_cancellation_reference.h"

static Mock *cancellation_mock(void)
{
    Mock *mk = mock_new();
    conf_set_bool(mk->conf, CONF_nemo_allow_checksum, true);
    mk->term = term_init(mk->conf, mk->ucsdata, &mk->tw);
    mk->ldisc = ldisc_create(mk->conf, mk->term, &mk->backend, &mk->seat);
    reset(mk);
    return mk;
}

static void print_wire(const char *label, const char *bytes, size_t length)
{
    printf("%s:", label);
    for (size_t i = 0; i < length; i++) printf(" %02x", (unsigned char)bytes[i]);
    puts("");
}

static unsigned replay_reference(bool bytewise)
{
    unsigned failed = 0;
    for (size_t i = 0; i < lenof(cancellation_reference); i++) {
        const CancellationReference *ref = &cancellation_reference[i];
        Mock *mk = cancellation_mock();
        test_context(mk, "%s / %s", ref->name, bytewise ? "bytewise" : "whole");
        for (size_t offset = 0; offset < ref->wire_length;) {
            size_t length = bytewise ? 1 : ref->wire_length;
            term_data(mk->term, ref->wire + offset, length);
            offset += length;
        }
        term_update(mk->term);
        if (mk->to_backend->len != ref->reply_length ||
            memcmp(mk->to_backend->s, ref->reply, ref->reply_length)) {
            report_fail(mk, __FILE__, __LINE__, "cancellation reference mismatch");
            print_wire("actual", mk->to_backend->s, mk->to_backend->len);
            print_wire("oracle", ref->reply, ref->reply_length);
        }
        failed += mk->any_test_failed ? 1 : 0;
        mock_free(mk);
    }
    printf("Cancellation %s: %zu streams, %u failures\n",
           bytewise ? "bytewise" : "whole", lenof(cancellation_reference), failed);
    return failed;
}

static unsigned test_payload_lifetimes(void)
{
    Mock *mk = cancellation_mock();
    conf_set_bool(mk->conf, CONF_nemo_osc52_write, true);
    term_reconfig(mk->term, mk->conf);
    nemo_osc52_begin(&mk->term->osc52, true, false);
    nemo_osc52_cancel(mk->term->osc52);
    IEQUAL(nemo_osc52_store(mk->term->osc52, nemo_osc52_cache_mask('q'), "kept", 4), true);
    size_t retained = nemo_osc52_memory(mk->term->osc52);
    for (unsigned cycle = 0; cycle < 64; cycle++) {
        char cancel = cycle & 1 ? 0x1a : 0x18;
        test_context(mk, "cancel owned parser storage / cycle %u", cycle);
        term_data_fragmented(mk->term, "\033[H\033P2$t2/7");
        IEQUAL(mk->term->dcs_tabs_pending != NULL, true);
        term_data(mk->term, &cancel, 1);
        IEQUAL(mk->term->dcs_tabs_pending == NULL, true);
        IEQUAL(mk->term->dcs_query_active, false);
        term_data_fragmented(mk->term, "\033P0;1q#1;2;100;0;0~");
        IEQUAL(mk->term->sixel_pending != NULL, true);
        term_data(mk->term, &cancel, 1);
        IEQUAL(mk->term->sixel_pending == NULL, true);
        IEQUAL(mk->term->images == NULL, true);
        term_data_fragmented(mk->term, "\033]52;q;QUJD");
        IEQUAL(nemo_osc52_memory(mk->term->osc52) > retained, true);
        term_data(mk->term, &cancel, 1);
        IEQUAL(nemo_osc52_memory(mk->term->osc52), retained);
        const char *text = NULL; size_t length = 0;
        IEQUAL(nemo_osc52_get(mk->term->osc52, 'q', &text, &length), true);
        IEQUAL(length, 4);
        IEQUAL(text && !memcmp(text, "kept", 4), true);
        IEQUAL(mk->term->termstate, TOPLEVEL);
        IEQUAL(mk->clipboard_writes, 0);
    }
    unsigned failed = mk->any_test_failed ? 1 : 0;
    mock_free(mk);
    printf("Cancellation: 64 payload lifetime cycles, %u failures\n", failed);
    return failed;
}

int main(void)
{
    unsigned failed = replay_reference(false);
    failed += replay_reference(true);
    failed += test_payload_lifetimes();
    return failed ? 1 : 0;
}
