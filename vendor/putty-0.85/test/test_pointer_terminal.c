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
#include "../../../tests/pointer_colour_reference.h"

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
    unsigned policy_differences = 0;
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
        /* Keep the independent bytes intact. Our existing VT parser cancels
         * the unfinished OSC on CAN/SUB or an interrupting escape, then
         * accepts the next complete query. The pinned Kitty parser does not
         * answer that query. Pointer state agrees in all three cases. */
        if (!strcmp(ref->name, "cancel-18/step-1") ||
            !strcmp(ref->name, "cancel-1a/step-1") ||
            !strcmp(ref->name, "cancel-1b5b306d/step-1")) {
            IEQUAL(ref->reply_length, 0);
            pointer_response(mk, "\033]22;text\033\\", 11);
            policy_differences++;
        } else {
            pointer_response(mk, ref->reply, ref->reply_length);
        }
        SEQUAL(nemo_pointer_name(nemo_pointer_current(mk->term->pointer_shapes,
                       mk->term->alt_which != 0)), ref->current);
        SEQUAL(nemo_pointer_name((NemoPointerShape)presented_shape), ref->current);
    }
    IEQUAL(policy_differences, 3);
    printf("%s: 552 exact upstream replies, 3 explicit cancellation-policy replies; 555 matching pointer states\n",
           bytewise ? "bytewise" : "original chunks");
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

    test_context(mk, "overlong setter rejected atomically and parser recovers");
    term_data_fragmented(mk->term, "\033]22;text\033\\\033]22;pointer,");
    char excess[NEMO_POINTER_OSC_MAX];
    memset(excess, 'x', sizeof(excess));
    term_data(mk->term, excess, sizeof(excess));
    term_data_fragmented(mk->term, "\033\\\033]22;?__current__\033\\");
    pointer_response(mk, "\033]22;text\033\\", 11);
    term_update(mk->term);
    IEQUAL(presented_shape, NEMO_POINTER_TEXT);

    test_context(mk, "C1 reply framing follows the existing terminal mode");
    term_data_fragmented(mk->term, "\033 G\033]22;?text\033\\");
    pointer_response(mk, "\23522;1\234", 6);
    reset(mk);

    test_context(mk, "frontend without presentation cannot advertise support");
    mk->tw.vt = &mock_termwin_vt;
    term_data_fragmented(mk->term, "\033]22;pointer\033\\\033]22;?text\033\\");
    pointer_response(mk, "", 0);
    IEQUAL(mk->term->pointer_shapes == NULL, true);
}

static bool test_pointer_colours(bool fragmented)
{
    Mock *mk = mock_new();
    TermWinVtable vt = mock_termwin_vt;
    vt.set_pointer_shape = pointer_present;
    mk->tw.vt = &vt;
    mk->term = term_init(mk->conf, mk->ucsdata, &mk->tw);
    mk->ldisc = ldisc_create(mk->conf, mk->term, &mk->backend, &mk->seat);
    reset(mk);
    for (size_t i=0; i<lenof(pointer_colour_reference); i++) {
        const char *wire=pointer_colour_reference[i].wire, *reply=pointer_colour_reference[i].reply;
        test_context(mk, "mouse colour %s / %s", pointer_colour_reference[i].name,
                     fragmented ? "single bytes" : "whole");
        if (fragmented) {
            for (size_t j=0; wire[j]; j++) term_data(mk->term, wire+j, 1);
        } else term_data(mk->term, wire, strlen(wire));
        term_update(mk->term);
        pointer_response(mk, reply, strlen(reply));
    }
    bool failed = mk->any_test_failed;
    mock_free(mk);
    printf("XTerm mouse colours: %zu stages, %s: %s\n", lenof(pointer_colour_reference),
           fragmented ? "single bytes" : "whole", failed ? "FAILED" : "passed");
    return failed;
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
    failed |= test_pointer_colours(false);
    failed |= test_pointer_colours(true);
    printf("Pointer terminal: %zu upstream stages x 2 fragmentation modes; %u presentations; %s\n",
           lenof(pointer_terminal_reference), presentation_calls,
           failed ? "FAILED" : "passed");
    return failed ? 1 : 0;
}
