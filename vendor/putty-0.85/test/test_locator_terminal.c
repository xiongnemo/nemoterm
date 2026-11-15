/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main

typedef struct LocatorAction {
    int kind, button, press, x, y;
    unsigned mask;
    bool consumed_by_upstream_binding;
} LocatorAction;
typedef struct LocatorReference {
    const char *name;
    bool reset;
    const char *wire;
    size_t wire_length;
    const char *reply;
    size_t reply_length;
    const LocatorAction *actions;
    size_t action_count;
} LocatorReference;
#include "../../../tests/locator_reference.h"

static TermPointerState pointer;
static bool pointer_available = true;
static unsigned pointer_queries;
static bool get_pointer(TermWin *win, TermPointerState *p, bool for_event)
{
    (void)win;
    (void)for_event;
    pointer_queries++;
    *p = pointer;
    return pointer_available;
}

static void response(Mock *mk, const char *expected, size_t length)
{
    if (mk->to_backend->len != length || memcmp(mk->to_backend->s, expected, length)) {
        report_fail(mk, __FILE__, __LINE__, "locator reply mismatch");
        printf(" actual:");
        for (size_t i = 0; i < mk->to_backend->len; i++)
            printf(" %02x", (unsigned char)mk->to_backend->s[i]);
        printf("\n oracle:");
        for (size_t i = 0; i < length; i++) printf(" %02x", (unsigned char)expected[i]);
        puts("");
    }
    strbuf_clear(mk->to_backend);
}

static void replay_reference(Mock *mk, bool bytewise)
{
    static const Mouse_Button buttons[] = {
        MBT_NOTHING, MBT_LEFT, MBT_MIDDLE, MBT_RIGHT, MBT_X1, MBT_X2
    };
    unsigned intercepted = 0;
    for (size_t i = 0; i < lenof(locator_reference); i++) {
        const LocatorReference *ref = &locator_reference[i];
        if (ref->reset) {
            reset(mk);
            term_set_cell_size(mk->term, 6, 13);
            pointer = (TermPointerState){.x=71, .y=86, .text_x=2, .text_y=2};
            term_data_fragmented(mk->term, "\033[65;1\"p");
        }
        test_context(mk, "%s / %s", ref->name, bytewise ? "bytewise" : "whole");
        for (size_t offset = 0; offset < ref->wire_length;) {
            size_t length = bytewise ? 1 : ref->wire_length;
            term_data(mk->term, ref->wire + offset, length);
            offset += length;
        }
        for (size_t j = 0; j < ref->action_count; j++) {
            const LocatorAction *a = &ref->actions[j];
            pointer.x = a->x; pointer.y = a->y; pointer.buttons = (a->mask >> 8) & 31;
            if (a->consumed_by_upstream_binding) { intercepted++; continue; }
            if (!a->kind) continue;
            Mouse_Button button = buttons[a->button];
            Mouse_Action action = a->kind == 2 ? (a->press ? MA_CLICK : MA_RELEASE) : MA_MOVE;
            Mouse_Button cooked = button == MBT_LEFT ? MBT_SELECT : button;
            if (a->kind == 1 && pointer.buttons) {
                action = MA_DRAG;
                for (unsigned k = 0; k < 5; k++) if (pointer.buttons & (1u << k)) {
                    button = buttons[k+1]; cooked = button == MBT_LEFT ? MBT_SELECT : button; break;
                }
            }
            int px = a->x-2, py = a->y-2;
            term_mouse_pixels(mk->term, button, cooked, action, px/6, py/13, px, py,
                              (a->mask & 1) != 0, (a->mask & 4) != 0, (a->mask & 8) != 0);
        }
        term_update(mk->term);
        response(mk, ref->reply, ref->reply_length);
    }
    printf("Locator %s: %zu unchanged replies, %u upstream binding interceptions\n",
           bytewise ? "bytewise" : "whole", lenof(locator_reference), intercepted);
}

static void direct_checks(Mock *mk)
{
    reset(mk);
    term_set_cell_size(mk->term, 6, 13);
    pointer = (TermPointerState){.x=71,.y=86,.text_x=2,.text_y=2};
    test_context(mk, "unavailable pointer, once mode and disabled reporting");
    term_data_fragmented(mk->term, "\033[2'z");
    pointer_available = false;
    term_data_fragmented(mk->term, "\033['|");
    response(mk, "\033[0&w", 5);
    IEQUAL(mk->term->xterm_mouse, 0);
    pointer_available = true;
    conf_set_bool(mk->conf, CONF_no_mouse_rep, true);
    term_reconfig(mk->term, mk->conf);
    unsigned before = pointer_queries;
    term_data_fragmented(mk->term, "\033[1'z\033['|");
    response(mk, "\033[0&w", 5);
    IEQUAL(pointer_queries, before);
    conf_set_bool(mk->conf, CONF_no_mouse_rep, false);
    term_reconfig(mk->term, mk->conf);

    test_context(mk, "Shift cancels a reported press and takes over selection");
    term_data_fragmented(mk->term, "\033[1'z\033[1;3'{");
    pointer.buttons = 1;
    term_mouse_pixels(mk->term, MBT_LEFT, MBT_SELECT, MA_CLICK, 11, 6, 69, 84, false, false, false);
    response(mk, "\033[2;4;7;12&w", 12);
    term_mouse_pixels(mk->term, MBT_LEFT, MBT_SELECT, MA_DRAG, 12, 6, 75, 84, true, false, false);
    response(mk, "\033[3;0;7;12&w", 12);
    IEQUAL(mk->term->mouse_buttons, 0);
    IEQUAL(mk->term->selstate, ABOUT_TO);
    term_mouse_pixels(mk->term, MBT_LEFT, MBT_SELECT, MA_DRAG, 16, 6, 99, 84, true, false, false);
    IEQUAL(mk->term->selstate, DRAGGING);
    term_mouse_pixels(mk->term, MBT_LEFT, MBT_SELECT, MA_RELEASE, 16, 6, 99, 84, true, false, false);
    response(mk, "", 0);
    IEQUAL(mk->term->selstate, SELECTED);
    pointer.buttons = 0;
}

int main(void)
{
    Mock *mk = mock_new();
    TermWinVtable vt = mock_termwin_vt;
    vt.get_pointer = get_pointer;
    mk->tw.vt = &vt;
    mk->term = term_init(mk->conf, mk->ucsdata, &mk->tw);
    mk->ldisc = ldisc_create(mk->conf, mk->term, &mk->backend, &mk->seat);
    replay_reference(mk, false);
    replay_reference(mk, true);
    direct_checks(mk);
    bool failed = mk->any_test_failed;
    mock_free(mk);
    printf("Locator terminal: %s\n", failed ? "FAILED" : "passed");
    return failed ? 1 : 0;
}
