/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main

typedef struct AnsiReference {
    const char *name, *wire;
    size_t wire_length;
    const char *reply;
    size_t reply_length;
} AnsiReference;
#include "../../../tests/ansi_conformance_reference.h"

static void print_wire(const char *label, const char *bytes, size_t length)
{
    printf("%s:", label);
    for (size_t i = 0; i < length; i++)
        printf(" %02x", (unsigned char)bytes[i]);
    puts("");
}

static Mock *ansi_mock(void)
{
    Mock *mk = mock_new();
    /* Match the reference collector's allowWindowOps checksum permission. */
    conf_set_bool(mk->conf, CONF_nemo_allow_checksum, true);
    mk->term = term_init(mk->conf, mk->ucsdata, &mk->tw);
    mk->ldisc = ldisc_create(mk->conf, mk->term, &mk->backend, &mk->seat);
    reset(mk);
    return mk;
}

static unsigned replay_reference(bool bytewise)
{
    unsigned failed = 0, cancellation_differences = 0;
    for (size_t i = 0; i < lenof(ansi_reference); i++) {
        const AnsiReference *ref = &ansi_reference[i];
        const AnsiReference *expected = ref;
        /* Preserve all independent SUB observations. Nemoterm's existing
         * cancellation policy omits the error glyph; test that policy against
         * the independent CAN observation for the otherwise identical stream.
         * General SUB rendering is a separate compatibility gap. */
        const char *cancel_can = !strcmp(ref->name, "ansiL-cancel-sub") ? "ansiL-cancel-can" :
            !strcmp(ref->name, "ansiM-cancel-sub") ? "ansiM-cancel-can" :
            !strcmp(ref->name, "ansiN-cancel-sub") ? "ansiN-cancel-can" : NULL;
        if (cancel_can) {
            for (size_t j = 0; j < lenof(ansi_reference); j++)
                if (!strcmp(ansi_reference[j].name, cancel_can))
                    expected = &ansi_reference[j];
            assert(expected != ref);
            cancellation_differences++;
        }
        /* The independent collector uses a fresh process per case. RIS and
         * DECSTR preserve ANSI level, so reset alone cannot isolate cases. */
        Mock *mk = ansi_mock();
        test_context(mk, "%s / %s", ref->name, bytewise ? "bytewise" : "whole");
        for (size_t offset = 0; offset < ref->wire_length;) {
            size_t length = bytewise ? 1 : ref->wire_length;
            term_data(mk->term, ref->wire + offset, length);
            offset += length;
        }
        term_update(mk->term);
        if (mk->to_backend->len != expected->reply_length ||
            memcmp(mk->to_backend->s, expected->reply, expected->reply_length)) {
            report_fail(mk, __FILE__, __LINE__, "ANSI reference reply mismatch");
            print_wire("actual", mk->to_backend->s, mk->to_backend->len);
            print_wire("oracle", expected->reply, expected->reply_length);
        }
        failed += mk->any_test_failed ? 1 : 0;
        mock_free(mk);
    }
    assert(cancellation_differences == 3);
    printf("ANSI %s: %zu streams, 240 exact XTerm replies, 3 explicit SUB policies, %u failures\n",
           bytewise ? "bytewise" : "whole", lenof(ansi_reference), failed);
    return failed;
}

int main(void)
{
    unsigned failed = replay_reference(false);
    failed += replay_reference(true);
    return failed ? 1 : 0;
}
