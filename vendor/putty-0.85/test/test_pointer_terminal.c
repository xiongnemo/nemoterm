/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main

typedef struct PointerTerminalReference {
    const char *name;
    bool reset;
    const char *wire;
    size_t wire_length;
    const char *reply;
    size_t reply_length;
    const char *current;
    const unsigned short *chunks;
    size_t chunk_count;
} PointerTerminalReference;
#include "../../../tests/pointer_terminal_reference.h"

static unsigned presented_shape;
static unsigned presentation_calls;
static void pointer_present(TermWin *win, unsigned shape)
{
    (void)win;
    presented_shape = shape;
    presentation_calls++;
}

static void pointer_response(Mock *mk, const char *expected, size_t length)
{
    if (mk->to_backend->len != length ||
        memcmp(mk->to_backend->s, expected, length)) {
        report_fail(mk, __FILE__, __LINE__, "pointer reply mismatch");
        printf(" actual:");
        for (size_t i = 0; i < mk->to_backend->len; i++)
            printf(" %02x", (unsigned char)mk->to_backend->s[i]);
        printf("\n oracle:");
        for (size_t i = 0; i < length; i++)
            printf(" %02x", (unsigned char)expected[i]);
        puts("");
    }
    strbuf_clear(mk->to_backend);
}

static void replay_reference(Mock *mk, bool bytewise)
{
    for (size_t i = 0; i < lenof(pointer_terminal_reference); i++) {
        const PointerTerminalReference *ref = &pointer_terminal_reference[i];
        if (ref->reset) reset(mk);
        test_context(mk, "%s / %s", ref->name,
                     bytewise ? "bytewise" : "original chunks");
        size_t offset = 0;
        for (size_t c = 0; offset < ref->wire_length; c++) {
            size_t size = bytewise ? 1 : ref->chunks[c];
            term_data(mk->term, ref->wire + offset, size);
            offset += size;
        }
        term_update(mk->term);
        pointer_response(mk, ref->reply, ref->reply_length);
        SEQUAL(nemo_pointer_name(nemo_pointer_current(mk->term->pointer_shapes,
                       mk->term->alt_which != 0)), ref->current);
        SEQUAL(nemo_pointer_name((NemoPointerShape)presented_shape), ref->current);
    }
}

static void test_ownership(Mock *mk)
{
    reset(mk);
    test_context(mk, "queries and unknown setters allocate no pointer state");
    term_data_fragmented(mk->term, "\033]22;?text,__current__\033\\");
    pointer_response(mk, "\033]22;1,0\033\\", 10);
    IEQUAL(mk->term->pointer_shapes == NULL, true);
    term_data_fragmented(mk->term, "\033]22;not-a-shape\033\\\033]22;<\033\\");
    IEQUAL(mk->term->pointer_shapes == NULL, true);
    term_data_fragmented(mk->term, "\033]22;>pointer\033\\");
    IEQUAL(mk->term->pointer_shapes != NULL, true);
    term_data_fragmented(mk->term, "\033]22;<\033\\");
    IEQUAL(mk->term->pointer_shapes == NULL, true);

    test_context(mk, "reset releases both stacks and updates presentation");
    term_data_fragmented(mk->term, "\033]22;pointer\033\\\033[?1049h\033]22;wait\033\\");
    term_update(mk->term);
    IEQUAL(presented_shape, NEMO_POINTER_WAIT);
    term_data_fragmented(mk->term, "\033[!p");
    term_update(mk->term);
    IEQUAL(mk->term->pointer_shapes == NULL, true);
    IEQUAL(presented_shape, NEMO_POINTER_NONE);

    test_context(mk, "frontend without presentation cannot advertise support");
    mk->tw.vt = &mock_termwin_vt;
    term_data_fragmented(mk->term, "\033]22;pointer\033\\\033]22;?text\033\\");
    pointer_response(mk, "", 0);
    IEQUAL(mk->term->pointer_shapes == NULL, true);
}

int main(void)
{
    Mock *mk = mock_new();
    TermWinVtable pointer_vtable = mock_termwin_vt;
    pointer_vtable.set_pointer_shape = pointer_present;
    mk->tw.vt = &pointer_vtable;
    mk->term = term_init(mk->conf, mk->ucsdata, &mk->tw);
    mk->ldisc = ldisc_create(mk->conf, mk->term, &mk->backend, &mk->seat);
    replay_reference(mk, false);
    replay_reference(mk, true);
    test_ownership(mk);
    bool failed = mk->any_test_failed;
    mock_free(mk);
    printf("Pointer terminal: %zu upstream stages x 2 fragmentation modes; %u presentations; %s\n",
           lenof(pointer_terminal_reference), presentation_calls,
           failed ? "FAILED" : "passed");
    return failed ? 1 : 0;
}
