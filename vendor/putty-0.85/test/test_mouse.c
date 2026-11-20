/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main

/* Protocol expectations come from xterm ctlseqs, Mouse Tracking. Keep these
 * literal: generating expectations with the encoder would hide regressions. */
static void check_mouse_bytes(Mock *mk, const char *file, int line,
                              const char *expected, size_t len)
{
    if (mk->to_backend->len != len ||
        memcmp(mk->to_backend->s, expected, len)) {
        report_fail(mk, file, line, "mouse bytes differ (%zu actual, %zu expected)",
                    mk->to_backend->len, len);
        printf(" actual:");
        for (size_t i = 0; i < mk->to_backend->len; i++)
            printf(" %02x", (unsigned char)mk->to_backend->s[i]);
        printf("\n expect:");
        for (size_t i = 0; i < len; i++)
            printf(" %02x", (unsigned char)expected[i]);
        printf("\n");
    }
    strbuf_clear(mk->to_backend);
}

#define MOUSE_BYTES(s) check_mouse_bytes(mk, __FILE__, __LINE__, s, sizeof(s)-1)

static void send_mouse(Mock *mk, Mouse_Button button, Mouse_Action action,
                        int x, int y, bool shift, bool ctrl, bool alt)
{
    Mouse_Button cooked = button == MBT_NOTHING || button >= MBT_WHEEL_UP ?
        button : MBT_SELECT;
    term_mouse_pixels(mk->term, button, cooked, action, x, y,
                      x * 8 + 3, y * 16 + 7, shift, ctrl, alt);
}

static void mouse_click(Mock *mk, int x, int y)
{
    send_mouse(mk, MBT_LEFT, MA_CLICK, x, y, false, false, false);
}

static void mouse_release(Mock *mk, int x, int y)
{
    send_mouse(mk, MBT_LEFT, MA_RELEASE, x, y, false, false, false);
}

static void mouse_setup(Mock *mk, const char *context, const char *modes)
{
    reset(mk);
    term_set_cell_size(mk->term, 8, 16);
    test_context(mk, "%s", context);
    term_data_fragmented(mk->term, modes);
    strbuf_clear(mk->to_backend);
}

static void test_tracking_modes(Mock *mk)
{
    mouse_setup(mk, "X10 press-only, no modifiers or wheel",
                "\033[?9h");
    send_mouse(mk, MBT_LEFT, MA_CLICK, 2, 3, false, true, true);
    MOUSE_BYTES("\033[M #$");
    send_mouse(mk, MBT_LEFT, MA_DRAG, 3, 3, false, false, false);
    mouse_release(mk, 3, 3);
    send_mouse(mk, MBT_NOTHING, MA_MOVE, 4, 3, false, false, false);
    send_mouse(mk, MBT_WHEEL_UP, MA_CLICK, 4, 3, false, false, false);
    MOUSE_BYTES("");
    send_mouse(mk, MBT_MIDDLE, MA_CLICK, 0, 0, false, true, true);
    send_mouse(mk, MBT_MIDDLE, MA_RELEASE, 0, 0, false, false, false);
    send_mouse(mk, MBT_RIGHT, MA_CLICK, 1, 0, false, true, true);
    send_mouse(mk, MBT_RIGHT, MA_RELEASE, 1, 0, false, false, false);
    MOUSE_BYTES("\033[M!!!\033[M\"\"!");

    mouse_setup(mk, "1000 reports press/release but no motion",
                "\033[?1000h\033[?1006h");
    mouse_click(mk, 2, 3);
    send_mouse(mk, MBT_LEFT, MA_DRAG, 3, 3, false, false, false);
    mouse_release(mk, 3, 3);
    send_mouse(mk, MBT_NOTHING, MA_MOVE, 4, 3, false, false, false);
    MOUSE_BYTES("\033[<0;3;4M\033[<0;4;4m");

    mouse_setup(mk, "1002 suppresses repeated cells and unbuttoned motion",
                "\033[?1002;1006h");
    mouse_click(mk, 2, 3);
    send_mouse(mk, MBT_LEFT, MA_DRAG, 2, 3, false, false, false);
    send_mouse(mk, MBT_LEFT, MA_DRAG, 3, 3, false, false, false);
    send_mouse(mk, MBT_LEFT, MA_DRAG, 3, 3, false, false, false);
    mouse_release(mk, 3, 3);
    send_mouse(mk, MBT_NOTHING, MA_MOVE, 4, 3, false, false, false);
    MOUSE_BYTES("\033[<0;3;4M\033[<32;4;4M\033[<0;4;4m");

    mouse_setup(mk, "1003 reports unbuttoned motion once per cell",
                "\033[?1003;1006h");
    send_mouse(mk, MBT_NOTHING, MA_MOVE, 2, 3, false, false, false);
    send_mouse(mk, MBT_NOTHING, MA_MOVE, 2, 3, false, false, false);
    send_mouse(mk, MBT_NOTHING, MA_MOVE, 3, 3, false, false, false);
    MOUSE_BYTES("\033[<35;3;4M\033[<35;4;4M");
}

static void test_buttons_and_modifiers(Mock *mk)
{
    mouse_setup(mk, "SGR button identity and Alt/Control modifiers",
                "\033[?1002;1006h");
    send_mouse(mk, MBT_LEFT, MA_CLICK, 0, 0, false, true, true);
    send_mouse(mk, MBT_LEFT, MA_DRAG, 1, 0, false, true, true);
    send_mouse(mk, MBT_LEFT, MA_RELEASE, 1, 0, false, true, true);
    send_mouse(mk, MBT_MIDDLE, MA_CLICK, 2, 0, false, false, true);
    send_mouse(mk, MBT_MIDDLE, MA_RELEASE, 2, 0, false, false, true);
    send_mouse(mk, MBT_RIGHT, MA_CLICK, 3, 0, false, true, false);
    send_mouse(mk, MBT_RIGHT, MA_RELEASE, 3, 0, false, true, false);
    MOUSE_BYTES("\033[<24;1;1M\033[<56;2;1M\033[<24;2;1m"
                "\033[<9;3;1M\033[<9;3;1m"
                "\033[<18;4;1M\033[<18;4;1m");

    static const Mouse_Button wheels[] = {
        MBT_WHEEL_UP, MBT_WHEEL_DOWN, MBT_WHEEL_LEFT, MBT_WHEEL_RIGHT
    };
    for (size_t i = 0; i < lenof(wheels); i++) {
        send_mouse(mk, wheels[i], MA_CLICK, 0, 0, false, true, true);
        send_mouse(mk, wheels[i], MA_RELEASE, 0, 0, false, true, true);
    }
    MOUSE_BYTES("\033[<88;1;1M\033[<89;1;1M"
                "\033[<90;1;1M\033[<91;1;1M");

    mouse_setup(mk, "legacy release code retains Alt/Control modifiers",
                "\033[?1000h");
    send_mouse(mk, MBT_RIGHT, MA_CLICK, 0, 0, false, true, true);
    send_mouse(mk, MBT_RIGHT, MA_RELEASE, 0, 0, false, true, true);
    MOUSE_BYTES("\033[M:!!\033[M;!!");

    mouse_setup(mk, "urxvt uses decimal legacy codes", "\033[?1000;1015h");
    send_mouse(mk, MBT_RIGHT, MA_CLICK, 2, 3, false, true, true);
    send_mouse(mk, MBT_RIGHT, MA_RELEASE, 2, 3, false, true, true);
    MOUSE_BYTES("\033[58;3;4M\033[59;3;4M");
}

static void test_tracking_negotiation(Mock *mk)
{
    /* Unlike encoding resets, xterm's tracking resets disable reporting
     * even if a different tracking protocol is currently selected. */
    static const int modes[] = {9, 1000, 1001, 1002, 1003};
    for (size_t active = 0; active < lenof(modes); active++) {
        for (size_t disabled = 0; disabled < lenof(modes); disabled++) {
            mouse_setup(mk, "tracking reset unconditionally disables reporting",
                        "\033[?1006h");
            test_context(mk, "tracking SET %d RESET %d",
                         modes[active], modes[disabled]);
            char sequence[64];
            snprintf(sequence, sizeof(sequence), "\033[?%dh\033[?%dl",
                     modes[active], modes[disabled]);
            term_data_fragmented(mk->term, sequence);
            mouse_click(mk, 2, 3);
            mouse_release(mk, 2, 3);
            send_mouse(mk, MBT_NOTHING, MA_MOVE, 3, 3, false, false, false);
            MOUSE_BYTES("");
        }
    }
    mouse_setup(mk, "last-set tracking protocol controls motion reports",
                "\033[?1003;1000;1006h");
    send_mouse(mk, MBT_NOTHING, MA_MOVE, 2, 3, false, false, false);
    MOUSE_BYTES("");
    term_data_fragmented(mk->term, "\033[?1003h");
    send_mouse(mk, MBT_NOTHING, MA_MOVE, 2, 3, false, false, false);
    MOUSE_BYTES("\033[<35;3;4M");
}

static void test_side_buttons(Mock *mk)
{
    mouse_setup(mk, "side buttons retain identity, motion and modifiers",
                "\033[?1002;1006h");
    send_mouse(mk, MBT_X1, MA_CLICK, 2, 3, false, true, true);
    send_mouse(mk, MBT_X1, MA_CLICK, 2, 3, false, true, true);
    send_mouse(mk, MBT_X1, MA_DRAG, 3, 3, false, true, true);
    send_mouse(mk, MBT_X1, MA_DRAG, 3, 3, false, true, true);
    send_mouse(mk, MBT_X1, MA_RELEASE, 3, 3, false, true, true);
    send_mouse(mk, MBT_X1, MA_RELEASE, 3, 3, false, true, true);
    send_mouse(mk, MBT_X2, MA_CLICK, 2, 3, false, false, false);
    send_mouse(mk, MBT_X2, MA_DRAG, 3, 3, false, false, false);
    send_mouse(mk, MBT_X2, MA_RELEASE, 3, 3, false, false, false);
    MOUSE_BYTES("\033[<152;3;4M\033[<184;4;4M\033[<152;4;4m"
                "\033[<129;3;4M\033[<161;4;4M\033[<129;4;4m");

    mouse_setup(mk, "side buttons use legacy byte and generic release",
                "\033[?1000h");
    send_mouse(mk, MBT_X1, MA_CLICK, 0, 0, false, false, false);
    send_mouse(mk, MBT_X1, MA_RELEASE, 0, 0, false, false, false);
    send_mouse(mk, MBT_X2, MA_CLICK, 0, 0, false, true, true);
    send_mouse(mk, MBT_X2, MA_RELEASE, 0, 0, false, true, true);
    MOUSE_BYTES("\033[M\xa0!!\033[M#!!\033[M\xb9!!\033[M;!!");

    mouse_setup(mk, "1005 encodes side-button code as UTF-8",
                "\033[?1000;1005h");
    send_mouse(mk, MBT_X2, MA_CLICK, 0, 0, false, true, true);
    send_mouse(mk, MBT_X2, MA_RELEASE, 0, 0, false, true, true);
    MOUSE_BYTES("\033[M\xc2\xb9!!\033[M;!!");

    mouse_setup(mk, "urxvt side-button encoding", "\033[?1000;1015h");
    send_mouse(mk, MBT_X1, MA_CLICK, 0, 0, false, false, false);
    send_mouse(mk, MBT_X1, MA_RELEASE, 0, 0, false, false, false);
    MOUSE_BYTES("\033[160;1;1M\033[35;1;1M");

    mouse_setup(mk, "pixel side-button motion and cancellation",
                "\033[?1002;1016h");
    send_mouse(mk, MBT_X1, MA_CLICK, 0, 0, false, false, false);
    send_mouse(mk, MBT_X2, MA_CLICK, 0, 0, false, false, false);
    send_mouse(mk, MBT_X2, MA_DRAG, 1, 1, false, false, false);
    term_mouse_cancel(mk->term);
    term_mouse_cancel(mk->term);
    send_mouse(mk, MBT_X1, MA_RELEASE, 1, 1, false, false, false);
    send_mouse(mk, MBT_X2, MA_RELEASE, 1, 1, false, false, false);
    MOUSE_BYTES("\033[<128;4;8M\033[<129;4;8M\033[<161;12;24M"
                "\033[<128;12;24m\033[<129;12;24m");

    mouse_setup(mk, "Shift cancels side button without making a selection",
                "ABCDE\033[?1002;1006h");
    send_mouse(mk, MBT_X1, MA_CLICK, 0, 0, false, false, false);
    send_mouse(mk, MBT_X1, MA_DRAG, 4, 0, true, false, false);
    send_mouse(mk, MBT_X1, MA_RELEASE, 4, 0, false, false, false);
    MOUSE_BYTES("\033[<128;1;1M\033[<128;1;1m");
    IEQUAL(mk->term->selstate, NO_SELECTION);
    IEQUAL(mk->term->mouse_buttons, 0);

    mouse_setup(mk, "local side buttons do not select or scroll",
                "1\r\n2\r\n3\r\n4\r\n5\r\n6");
    int disptop = mk->term->disptop;
    send_mouse(mk, MBT_X1, MA_CLICK, 0, 0, false, false, false);
    send_mouse(mk, MBT_X1, MA_DRAG, 0, -2, false, false, false);
    send_mouse(mk, MBT_X1, MA_RELEASE, 0, -2, false, false, false);
    send_mouse(mk, MBT_X2, MA_CLICK, 1, 0, true, false, false);
    send_mouse(mk, MBT_X2, MA_DRAG, 3, 0, true, false, false);
    send_mouse(mk, MBT_X2, MA_RELEASE, 3, 0, true, false, false);
    MOUSE_BYTES("");
    IEQUAL(mk->term->selstate, NO_SELECTION);
    IEQUAL(mk->term->disptop, disptop);
}

static void test_encoding_negotiation(Mock *mk)
{
    static const int modes[] = {1005, 1006, 1015, 1016};
    static const char *expected[] = {
        "\033[M #$\033[M##$",
        "\033[<0;3;4M\033[<0;3;4m",
        "\033[32;3;4M\033[35;3;4M",
        "\033[<0;20;56M\033[<0;20;56m"
    };
    for (size_t first = 0; first < lenof(modes); first++) {
        for (size_t last = 0; last < lenof(modes); last++) {
            mouse_setup(mk, "coordinate encodings are last-set, matching-reset",
                        "\033[?1000h");
            test_context(mk, "encoding %d then %d", modes[first], modes[last]);
            char negotiation[96];
            snprintf(negotiation, sizeof(negotiation), "\033[?%d;%dh",
                     modes[first], modes[last]);
            term_data_fragmented(mk->term, negotiation);
            if (first != last) {
                snprintf(negotiation, sizeof(negotiation), "\033[?%dl", modes[first]);
                term_data_fragmented(mk->term, negotiation);
            }
            mouse_click(mk, 2, 3);
            mouse_release(mk, 2, 3);
            check_mouse_bytes(mk, __FILE__, __LINE__, expected[last],
                              strlen(expected[last]));
            snprintf(negotiation, sizeof(negotiation), "\033[?%dl", modes[last]);
            term_data_fragmented(mk->term, negotiation);
            mouse_click(mk, 2, 3);
            mouse_release(mk, 2, 3);
            MOUSE_BYTES("\033[M #$\033[M##$");
        }
    }
}

static void test_coordinate_limits(Mock *mk)
{
    mouse_setup(mk, "legacy coordinate 223 is representable", "\033[?1000h");
    term_size(mk->term, 4, 2020, 0);
    mouse_click(mk, 222, 0);
    mouse_release(mk, 222, 0);
    MOUSE_BYTES("\033[M \xff!\033[M#\xff!");
    mouse_click(mk, 223, 0);
    mouse_release(mk, 223, 0);
    MOUSE_BYTES("");

    term_data_fragmented(mk->term, "\033[?1005h");
    test_context(mk, "1005 UTF-8 boundary and maximum coordinate 2015");
    mouse_click(mk, 94, 0);
    mouse_release(mk, 94, 0);
    mouse_click(mk, 95, 0);
    mouse_release(mk, 95, 0);
    mouse_click(mk, 2014, 0);
    mouse_release(mk, 2014, 0);
    MOUSE_BYTES("\033[M \x7f!\033[M#\x7f!"
                "\033[M \xc2\x80!\033[M#\xc2\x80!"
                "\033[M \xdf\xbf!\033[M#\xdf\xbf!");
    /* NemoTerm deliberately drops unrepresentable legacy coordinates;
     * it must never emit three-byte UTF-8, wrapping coordinates or a NUL. */
    mouse_click(mk, 2015, 0);
    mouse_release(mk, 2015, 0);
    MOUSE_BYTES("");

    term_data_fragmented(mk->term, "\033[?1006h");
    mouse_click(mk, 2019, 0);
    mouse_release(mk, 2019, 0);
    MOUSE_BYTES("\033[<0;2020;1M\033[<0;2020;1m");
    term_data_fragmented(mk->term, "\033[?1015h");
    mouse_click(mk, 2019, 0);
    mouse_release(mk, 2019, 0);
    MOUSE_BYTES("\033[32;2020;1M\033[35;2020;1M");

    term_data_fragmented(mk->term, "\033[?1005h");
    term_size(mk->term, 2020, 4, 0);
    mouse_click(mk, 0, 2014);
    mouse_release(mk, 0, 2014);
    MOUSE_BYTES("\033[M !\xdf\xbf\033[M#!\xdf\xbf");
    mouse_click(mk, 0, 2015);
    mouse_release(mk, 0, 2015);
    MOUSE_BYTES("");
}

static void test_pixel_motion(Mock *mk)
{
    mouse_setup(mk, "1016 reports pixel motion within a cell",
                "\033[?1003;1016h");
    term_mouse_pixels(mk->term, MBT_NOTHING, MBT_SELECT, MA_MOVE,
                      2, 3, 19, 55, false, false, false);
    term_mouse_pixels(mk->term, MBT_NOTHING, MBT_SELECT, MA_MOVE,
                      2, 3, 20, 55, false, false, false);
    term_mouse_pixels(mk->term, MBT_NOTHING, MBT_SELECT, MA_MOVE,
                      2, 3, 20, 55, false, false, false);
    MOUSE_BYTES("\033[<35;20;56M\033[<35;21;56M");
    term_mouse_pixels(mk->term, MBT_LEFT, MBT_SELECT, MA_CLICK,
                      2, 3, 20, 55, false, false, false);
    term_mouse_pixels(mk->term, MBT_LEFT, MBT_SELECT, MA_DRAG,
                      2, 3, 21, 55, false, false, false);
    term_mouse_pixels(mk->term, MBT_LEFT, MBT_SELECT, MA_RELEASE,
                      2, 3, 21, 55, false, false, false);
    MOUSE_BYTES("\033[<0;21;56M\033[<32;22;56M\033[<0;22;56m");

    term_data_fragmented(mk->term, "\033[?1006h");
    term_mouse_pixels(mk->term, MBT_NOTHING, MBT_SELECT, MA_MOVE,
                      4, 5, 35, 87, false, false, false);
    term_mouse_pixels(mk->term, MBT_NOTHING, MBT_SELECT, MA_MOVE,
                      4, 5, 36, 87, false, false, false);
    MOUSE_BYTES("\033[<35;5;6M");

    term_data_fragmented(mk->term, "\033[?1016h");
    test_context(mk, "pixel coordinates clamp at content edges after resize");
    term_size(mk->term, 3, 5, 0);
    term_set_cell_size(mk->term, 10, 20);
    term_mouse_pixels(mk->term, MBT_LEFT, MBT_SELECT, MA_CLICK,
                      -1, -1, -5, -7, false, false, false);
    term_mouse_pixels(mk->term, MBT_LEFT, MBT_SELECT, MA_RELEASE,
                      200, 200, 2000, 2000, false, false, false);
    MOUSE_BYTES("\033[<0;1;1M\033[<0;50;60m");
}

static void test_physical_coordinates(Mock *mk)
{
    mouse_setup(mk, "scrollback does not change physical application coordinates",
                "\033[?1003;1006h");
    term_size(mk->term, 4, 20, 100);
    term_data_fragmented(mk->term, "0\r\n1\r\n2\r\n3\r\n4\r\n5\r\n6");
    term_scroll(mk->term, -1, -2);
    IEQUAL(mk->term->disptop, -2);
    send_mouse(mk, MBT_NOTHING, MA_MOVE, 2, 1, false, false, false);
    send_mouse(mk, MBT_NOTHING, MA_MOVE, 2, 1, false, false, false);
    MOUSE_BYTES("\033[<35;3;2M");
    term_scroll(mk->term, -1, -1);
    send_mouse(mk, MBT_NOTHING, MA_MOVE, 2, 1, false, false, false);
    MOUSE_BYTES("");
    mouse_click(mk, 2, 1);
    mouse_release(mk, 2, 1);
    MOUSE_BYTES("\033[<0;3;2M\033[<0;3;2m");

    mouse_setup(mk, "double-width lines do not halve application mouse X",
                "\033[?1000;1006h\033#6");
    mouse_click(mk, 8, 0);
    mouse_release(mk, 8, 0);
    MOUSE_BYTES("\033[<0;9;1M\033[<0;9;1m");
    term_data_fragmented(mk->term, "\033c");
    IEQUAL(get_lineattr(mk->term, 0), LATTR_NORM);
}

static void test_focus_and_reset(Mock *mk)
{
    mouse_setup(mk, "focus reporting is independent of mouse tracking", "");
    term_set_focus(mk->term, false);
    term_data_fragmented(mk->term, "\033[?1004h");
    MOUSE_BYTES("");
    term_set_focus(mk->term, true);
    term_set_focus(mk->term, true);
    term_set_focus(mk->term, false);
    term_set_focus(mk->term, false);
    MOUSE_BYTES("\033[I\033[O");
    term_data_fragmented(mk->term, "\033[?1004l");
    term_set_focus(mk->term, true);
    term_set_focus(mk->term, false);
    MOUSE_BYTES("");

    term_data_fragmented(mk->term, "\033[?1003;1016;1004;1007h\033c");
    term_set_focus(mk->term, true);
    mouse_click(mk, 2, 3);
    mouse_release(mk, 2, 3);
    send_mouse(mk, MBT_NOTHING, MA_MOVE, 3, 3, false, false, false);
    MOUSE_BYTES("");
    /* RIS clears both reporting and the selected extended encoding. */
    term_data_fragmented(mk->term, "\033[?1000h");
    mouse_click(mk, 2, 3);
    mouse_release(mk, 2, 3);
    MOUSE_BYTES("\033[M #$\033[M##$");
}

static void test_alternate_scroll(Mock *mk)
{
    mouse_setup(mk, "1007 is limited to the alternate buffer", "\033[?1007h");
    send_mouse(mk, MBT_WHEEL_UP, MA_CLICK, 0, 0, false, false, false);
    send_mouse(mk, MBT_WHEEL_DOWN, MA_CLICK, 0, 0, false, false, false);
    MOUSE_BYTES("");
    term_data_fragmented(mk->term, "\033[?1049h\033[?1l");
    send_mouse(mk, MBT_WHEEL_UP, MA_CLICK, 0, 0, false, false, false);
    send_mouse(mk, MBT_WHEEL_DOWN, MA_CLICK, 0, 0, false, false, false);
    MOUSE_BYTES("\033[A\033[B");
    term_data_fragmented(mk->term, "\033[?1h");
    send_mouse(mk, MBT_WHEEL_UP, MA_CLICK, 0, 0, false, false, false);
    send_mouse(mk, MBT_WHEEL_DOWN, MA_CLICK, 0, 0, false, false, false);
    MOUSE_BYTES("\033OA\033OB");
    send_mouse(mk, MBT_WHEEL_UP, MA_CLICK, 0, 0, true, false, false);
    send_mouse(mk, MBT_WHEEL_DOWN, MA_CLICK, 0, 0, true, false, false);
    MOUSE_BYTES("");

    /* An application asking for mouse input receives mouse wheel reports,
     * even when alternate scrolling is enabled. */
    term_data_fragmented(mk->term, "\033[?1000;1006h");
    send_mouse(mk, MBT_WHEEL_UP, MA_CLICK, 2, 3, false, false, false);
    send_mouse(mk, MBT_WHEEL_DOWN, MA_CLICK, 2, 3, false, false, false);
    MOUSE_BYTES("\033[<64;3;4M\033[<65;3;4M");
    term_data_fragmented(mk->term, "\033[?1000l\033[?1007l");
    send_mouse(mk, MBT_WHEEL_UP, MA_CLICK, 0, 0, false, false, false);
    MOUSE_BYTES("");
    term_data_fragmented(mk->term, "\033[?1007h\033[?1049l");
    send_mouse(mk, MBT_WHEEL_DOWN, MA_CLICK, 0, 0, false, false, false);
    MOUSE_BYTES("");
}

static void test_cancel_reported_buttons(Mock *mk)
{
    mouse_setup(mk, "capture loss releases each reported button exactly once",
                "\033[?1002;1006h");
    mouse_click(mk, 2, 3);
    send_mouse(mk, MBT_RIGHT, MA_CLICK, 2, 3, false, false, false);
    MOUSE_BYTES("\033[<0;3;4M\033[<2;3;4M");
    term_mouse_cancel(mk->term);
    term_mouse_cancel(mk->term);
    MOUSE_BYTES("\033[<0;3;4m\033[<2;3;4m");
    mouse_release(mk, 2, 3);
    send_mouse(mk, MBT_RIGHT, MA_RELEASE, 2, 3, false, false, false);
    send_mouse(mk, MBT_LEFT, MA_DRAG, 3, 3, false, false, false);
    MOUSE_BYTES("");
    mouse_click(mk, 3, 3);
    mouse_release(mk, 3, 3);
    MOUSE_BYTES("\033[<0;4;4M\033[<0;4;4m");

    test_context(mk, "cancel remembers modifiers and last reported position");
    send_mouse(mk, MBT_MIDDLE, MA_CLICK, 0, 0, false, true, true);
    send_mouse(mk, MBT_MIDDLE, MA_DRAG, 1, 2, false, true, true);
    MOUSE_BYTES("\033[<25;1;1M\033[<57;2;3M");
    term_mouse_cancel(mk->term);
    MOUSE_BYTES("\033[<25;2;3m");

    test_context(mk, "focus loss cancels a drag before reporting FocusOut");
    term_set_focus(mk->term, true);
    term_data_fragmented(mk->term, "\033[?1004h");
    mouse_click(mk, 2, 3);
    MOUSE_BYTES("\033[<0;3;4M");
    term_set_focus(mk->term, false);
    term_set_focus(mk->term, false);
    MOUSE_BYTES("\033[<0;3;4m\033[O");
    mouse_release(mk, 2, 3);
    MOUSE_BYTES("");

    mouse_setup(mk, "X10 cancellation never synthesizes an unsupported release",
                "\033[?9;1006h");
    mouse_click(mk, 0, 0);
    MOUSE_BYTES("\033[<0;1;1M");
    term_mouse_cancel(mk->term);
    mouse_release(mk, 0, 0);
    MOUSE_BYTES("");
}

static void test_shift_takeover(Mock *mk)
{
    mouse_setup(mk, "Shift takes over a reported drag without leaving it stuck",
                "ABCDE\033[?1002;1006h");
    mouse_click(mk, 0, 0);
    MOUSE_BYTES("\033[<0;1;1M");
    send_mouse(mk, MBT_LEFT, MA_DRAG, 2, 0, true, false, false);
    MOUSE_BYTES("\033[<0;1;1m");
    send_mouse(mk, MBT_LEFT, MA_DRAG, 4, 0, false, false, false);
    mouse_release(mk, 4, 0);
    MOUSE_BYTES("");
    IEQUAL(mk->term->selstate, SELECTED);
    int clipboard = CLIP_LOCAL + 1;
    term_request_copy(mk->term, &clipboard, 1);
    check_clipboard(mk, L"CDE");

    /* Selection override must cover every reporting/encoding combination,
     * not just the commonly used 1002+1006 pair. */
    static const int protocols[] = {9, 1000, 1001, 1002, 1003};
    static const int encodings[] = {1005, 1006, 1015, 1016};
    for (size_t p = 0; p < lenof(protocols); p++) {
        for (size_t e = 0; e < lenof(encodings); e++) {
            mouse_setup(mk, "Shift selection overrides every mouse encoding", "ABCDE");
            test_context(mk, "Shift selection protocol=%d encoding=%d",
                         protocols[p], encodings[e]);
            char sequence[48];
            snprintf(sequence, sizeof(sequence), "\033[?%d;%dh",
                     protocols[p], encodings[e]);
            term_data_fragmented(mk->term, sequence);
            send_mouse(mk, MBT_LEFT, MA_CLICK, 0, 0, true, false, false);
            send_mouse(mk, MBT_LEFT, MA_DRAG, 4, 0, true, false, false);
            mouse_release(mk, 4, 0);
            MOUSE_BYTES("");
            IEQUAL(mk->term->selstate, SELECTED);
            term_request_copy(mk->term, &clipboard, 1);
            check_clipboard(mk, L"ABCDE");
        }
    }
    mouse_setup(mk, "cancelling a local selection never reports an app release",
                "ABCDE\033[?1002;1006h");
    send_mouse(mk, MBT_LEFT, MA_CLICK, 0, 0, true, false, false);
    send_mouse(mk, MBT_LEFT, MA_DRAG, 4, 0, true, false, false);
    term_mouse_cancel(mk->term);
    mouse_release(mk, 4, 0);
    MOUSE_BYTES("");
}

/* A release can be delivered to either terminal after Win32 switches tabs.
 * Copy has its own cached text. Verify the live highlight separately. */
static void test_unmatched_local_release(Mock *mk)
{
    for (int tracking = 0; tracking <= 1; tracking++) {
        mouse_setup(mk, "unmatched release in destination with a selection",
                    tracking ? "ABCDE\033[?1002;1006h" : "ABCDE");
        send_mouse(mk, MBT_LEFT, MA_CLICK, 1, 0, true, false, false);
        send_mouse(mk, MBT_LEFT, MA_RELEASE, 3, 0, true, false, false);
        IEQUAL(mk->term->selstate, SELECTED);
        /* Locally bound left button; then a locally bound extend button. */
        send_mouse(mk, MBT_LEFT, MA_RELEASE, 4, 1, tracking, false, false);
        term_mouse(mk->term, MBT_RIGHT, MBT_EXTEND, MA_RELEASE,
                   0, 1, tracking, false, false);
        IEQUAL(mk->term->selstate, SELECTED);
        IEQUAL(mk->term->selstart.x, 1); IEQUAL(mk->term->selend.x, 4);
        IEQUAL(mk->term->selstart.y, 0); IEQUAL(mk->term->selend.y, 0);
        int clipboard = CLIP_LOCAL + 1;
        term_request_copy(mk->term, &clipboard, 1);
        check_clipboard(mk, L"BCD");
        /* A real stationary click still clears the highlight. */
        send_mouse(mk, MBT_LEFT, MA_CLICK, 4, 0, true, false, false);
        send_mouse(mk, MBT_LEFT, MA_RELEASE, 4, 0, true, false, false);
        IEQUAL(mk->term->selstate, NO_SELECTION);
        MOUSE_BYTES("");
    }
}

static void test_unencodable_release_cancel(Mock *mk)
{
    mouse_setup(mk, "capture cancellation recovers an out-of-range legacy release",
                "\033[?1002h");
    term_size(mk->term, 4, 2020, 0);
    mouse_click(mk, 0, 0);
    send_mouse(mk, MBT_LEFT, MA_DRAG, 222, 0, false, false, false);
    MOUSE_BYTES("\033[M !!\033[M@\xff!");
    mouse_release(mk, 223, 0);
    MOUSE_BYTES("");
    term_mouse_cancel(mk->term);
    MOUSE_BYTES("\033[M#\xff!");
    mouse_release(mk, 222, 0);
    MOUSE_BYTES("");
    mouse_click(mk, 0, 0);
    mouse_release(mk, 0, 0);
    MOUSE_BYTES("\033[M !!\033[M#!!");

    test_context(mk, "capture cancellation recovers an out-of-range UTF-8 release");
    term_data_fragmented(mk->term, "\033[?1005h");
    mouse_click(mk, 0, 0);
    send_mouse(mk, MBT_LEFT, MA_DRAG, 2014, 0, false, false, false);
    MOUSE_BYTES("\033[M !!\033[M@\xdf\xbf!");
    mouse_release(mk, 2015, 0);
    MOUSE_BYTES("");
    term_mouse_cancel(mk->term);
    MOUSE_BYTES("\033[M#\xdf\xbf!");
    mouse_release(mk, 2014, 0);
    MOUSE_BYTES("");
    mouse_click(mk, 0, 0);
    mouse_release(mk, 0, 0);
    MOUSE_BYTES("\033[M !!\033[M#!!");
}

static void test_selection_cursor_traffic(Mock *mk)
{
    static const struct {
        const char *name, *before, *update; int cursor; bool keep;
    } cases[] = {
        {"position inside", "\033[1G", "\033[6G", 5, true},
        {"tab across", "\033[1G", "\t", 8, true},
        {"CHT across", "\033[1G", "\033[I", 8, true},
        {"CBT across", "\033[10G", "\033[2Z", 0, true},
        {"print immediately left", "\033[4G", "x", 4, true},
        {"overwrite inside", "\033[6G", "x", 6, false},
        {"wide overlaps from left", "\033[4G", "\xe4\xb8\xad", 5, false},
        {"append mark to last selected base", "\033[8G", "\xcc\x81", 7, false},
        {"append mark to unselected neighbour", "\033[5G", "\xcc\x81", 4, true},
    };
    for (size_t i = 0; i < lenof(cases); i++) for (int block = 0; block < 2; block++) {
        mk->ucsdata->line_codepage = CP_UTF8;
        mouse_setup(mk, cases[i].name, "\033%G\033[?2027lABCDEFGHIJKLM\033[?1002;1006h");
        term_data_fragmented(mk->term, cases[i].before);
        send_mouse(mk, MBT_LEFT, MA_CLICK, 4, 0, true, block, false);
        send_mouse(mk, MBT_LEFT, MA_DRAG, 6, 0, true, block, false);
        send_mouse(mk, MBT_LEFT, MA_RELEASE, 6, 0, true, block, false);
        IEQUAL(mk->term->selstate, SELECTED);
        term_data_fragmented(mk->term, cases[i].update);
        IEQUAL(mk->term->curs.x, cases[i].cursor);
        IEQUAL(mk->term->selstate, cases[i].keep ? SELECTED : NO_SELECTION);
        if (cases[i].keep) {
            int clipboard = CLIP_LOCAL + 1;
            term_request_copy(mk->term, &clipboard, 1);
            check_clipboard(mk, L"EFG");
        }
        MOUSE_BYTES("");
    }
}

#ifdef _WIN32
#define BLOCK_NL L"\r\n"
#else
#define BLOCK_NL L"\n"
#endif

/* Six glyph columns fit on a doubled 12-column row. In the bidi case,
 * visual columns 4 and 5 come from source columns 7 and 6 respectively. */
static void test_scaled_visual_copy(Mock *mk)
{
    static const struct { int width; const char *line; const wchar_t *copy; } cases[] = {
        {13, "ABCDEFGHIJ\033#6\r\nEND|", L"EFG" BLOCK_NL L"END"}, /* G is half visible */
        {12, "ABCDEFGHIJ\033#6\r\nEND|", L"EF" BLOCK_NL L"END"},
        {12, "ABCDE HIJ\033#4\r\nEND|", L"E" BLOCK_NL L"END"},
        {12, "ABCD\xd7\x90\xd7\x91\xd7\x92\xd6\xb0\xd7\x93Z\033#3\r\nEND|",
         L"\x5d2\x5b0\x5d3" BLOCK_NL L"END"},
        {12, "\033#6ABCDEFEND|", L"EFEND"}, /* soft wrap */
    };
    const int clipboard = CLIP_LOCAL + 1;
    for (size_t i=0; i<lenof(cases); i++) {
        mouse_setup(mk, "Shift-copy only the painted columns of a sized row", "");
        test_context(mk, "scaled Shift-copy case %zu (%d columns)", i, cases[i].width);
        term_size(mk->term, 3, cases[i].width, 100);
        mk->ucsdata->line_codepage = CP_UTF8;
        mk->term->no_bidi = false;
        mk->term->rect_select = false;
        term_data_fragmented(mk->term, "\033%G\033[?7h\033[?1002;1006h");
        term_data_fragmented(mk->term, cases[i].line);
        send_mouse(mk, MBT_LEFT, MA_CLICK, 8, 0, true, false, false);
        mouse_release(mk, 2, 1);
        IEQUAL(mk->term->seltype, VISUAL_STREAM);
        term_request_copy(mk->term, &clipboard, 1);
        check_clipboard(mk, cases[i].copy);
        MOUSE_BYTES("");
    }
}

static void test_press_across_line_rendition(Mock *mk)
{
    const int clipboard = CLIP_LOCAL + 1;
    const struct { const char *initial, *edit; int x, release, anchor; bool block;
                   const wchar_t *copy; } cases[] = {
        {"ABCDEFGHIJK", "\033#6", 3, 10, 6, true, L"DEF"},
        {"ABCDEFGHIJK\033#6", "\033#5", 7, 5, 3, true, L"DEF"},
        {"ABCDEFGHIJK\033#6", "\033[?69h", 7, 5, 3, true, L"DEF"},
        {"ABCDEFGHIJK", "\033#3", 7, 4, -1, false, NULL},
        {"ABCDEFGHIJK", "\033#4", 7, 4, -1, true, NULL},
        {"ABCDX\xe4\xb8\xadY", "\033#6", 6, 8, 10, true, L"X\x4e2d"},
        {"ABCDX\xe4\xb8\xadY", "\033#6", 6, 8, 5, false, L"X\x4e2d"},
    };
    for (size_t i = 0; i < lenof(cases); i++) {
        mouse_setup(mk, "held press across DEC line sizing", "");
        test_context(mk, "held press across DEC line sizing, case %zu", i);
        term_size(mk->term, 3, 12, 0);
        mk->ucsdata->line_codepage = CP_UTF8;
        mk->term->rect_select = false;
        term_data_fragmented(mk->term, "\033%G\033[?1002;1006h");
        term_data_fragmented(mk->term, cases[i].initial);
        send_mouse(mk, MBT_LEFT, MA_CLICK, cases[i].x, 0, true, cases[i].block, false);
        term_data_fragmented(mk->term, cases[i].edit);
        IEQUAL(mk->term->selstate, cases[i].copy ? ABOUT_TO : NO_SELECTION);
        if (cases[i].copy) IEQUAL(mk->term->selanchor.x, cases[i].anchor);
        send_mouse(mk, MBT_LEFT, MA_DRAG, cases[i].release, 0, false, false, false);
        mouse_release(mk, cases[i].release, 0);
        MOUSE_BYTES("");
        IEQUAL(mk->term->selstate, cases[i].copy ? SELECTED : NO_SELECTION);
        if (cases[i].copy) {
            term_request_copy(mk->term, &clipboard, 1);
            check_clipboard(mk, cases[i].copy);
        }
        mouse_click(mk, 0, 2); mouse_release(mk, 0, 2);
        MOUSE_BYTES("\033[<0;1;3M\033[<0;1;3m");
    }
    /* Enabling margins also restores ordinary width outside the cursor row.
     * A finished block must not claim a right click over different text. */
    mouse_setup(mk, "DECLRMM invalidates a finished block on a resized row",
                "ABCDEFGHIJK\033#6\033[?1002;1006h");
    send_mouse(mk, MBT_LEFT, MA_CLICK, 2, 0, true, true, false);
    mouse_release(mk, 5, 0);
    IEQUAL(mk->term->selstate, SELECTED);
    term_data_fragmented(mk->term, "\033[2;1H\033[?69h");
    IEQUAL(mk->term->selstate, NO_SELECTION);
}

static void test_ctrl_rectangle(Mock *mk)
{
    const int clipboard = CLIP_LOCAL + 1;
    const int modes[] = {0, 9, 1000, 1001, 1002, 1003};
    mk->ucsdata->line_codepage = CP_UTF8;
    for (size_t mode = 0; mode < lenof(modes); mode++)
        for (unsigned corner = 0; corner < 4; corner++)
            for (int alternate = 0; alternate < 2; alternate++) {
                mouse_setup(mk, "Ctrl rectangle, all directions and mouse owners", "");
                if (alternate) term_data_fragmented(mk->term, "\033[?1049h");
                term_data_fragmented(mk->term,
                    "0123456789\r\nab\xe4\xb8\xad" "e\xcc\x81" "FGHIJ\r\nklmnopqrst");
                if (modes[mode]) {
                    char *s = dupprintf("\033[?%d;1006h", modes[mode]);
                    term_data_fragmented(mk->term, s); sfree(s);
                }
                int x = corner & 1 ? 5 : 1, y = corner & 2 ? 2 : 0;
                bool shift = modes[mode] != 0;
                /* Ctrl stays rectangular even when rectangle is the default,
                 * and releasing modifiers cannot change an ongoing gesture. */
                mk->term->rect_select = !!alternate;
                send_mouse(mk, MBT_LEFT, MA_CLICK, x, y, shift, true, false);
                send_mouse(mk, MBT_LEFT, MA_DRAG, 6-x, 2-y, false, false, false);
                send_mouse(mk, MBT_LEFT, MA_RELEASE, 6-x, 2-y, false, false, false);
                IEQUAL(mk->term->seltype, RECTANGULAR);
                IEQUAL(mk->term->selstate, SELECTED);
                MOUSE_BYTES("");
                term_request_copy(mk->term, &clipboard, 1);
                check_clipboard(mk, L"12345" BLOCK_NL L"b\x4e2d" L"e\x301" L"F" BLOCK_NL L"lmnop");
            }
    for (int reverse = 0; reverse < 2; reverse++) {
        mouse_setup(mk, "Block uses display columns through doubled wide and combining glyphs",
                    "\033[?1002;1006h01234567\r\n\033#6a\xe4\xb8\xad" "e\xcc\x81" "FG");
        int ax = reverse ? 6 : 4, ay = reverse ? 1 : 0;
        send_mouse(mk, MBT_LEFT, MA_CLICK, ax, ay, true, true, false);
        send_mouse(mk, MBT_LEFT, MA_RELEASE, 10-ax, 1-ay, false, false, false);
        MOUSE_BYTES("");
        IEQUAL(mk->term->selstate, SELECTED);
        term_request_copy(mk->term, &clipboard, 1);
        check_clipboard(mk, L"456" BLOCK_NL L"\x4e2d" L"e\x301");
        term_data_fragmented(mk->term, "\033#5");
        IEQUAL(mk->term->selstate, NO_SELECTION);
    }
    /* Drag from retained history through the viewport: off-screen row cache
     * indices cannot be negative, and the selected glyphs keep logical order. */
    for (int bidi = 0; bidi < 2; bidi++) {
        mouse_setup(mk, "Mixed-direction rectangular copy across scrollback", "");
        term_size(mk->term, 3, 12, 100);
        mk->term->no_bidi = !bidi;
        mk->term->no_arabicshaping = true;
        term_data_fragmented(mk->term, "\033[?1002;1006h");
        for (int y = 0; y < 5; y++) {
            char prefix[] = { '0'+y, 0 };
            if (y) term_data_fragmented(mk->term, "\r\n");
            /* A strong LTR prefix fixes the direction of this paragraph. */
            term_data_fragmented(mk->term, "L");
            term_data_fragmented(mk->term, prefix);
            term_data_fragmented(mk->term, "\xd7\x90\xd7\x91\xd7\x92\xd6\xb0Z");
        }
        term_scroll(mk->term, 1, 0);
        IEQUAL(mk->term->disptop, -2);
        send_mouse(mk, MBT_LEFT, MA_CLICK, 1, 0, true, true, false);
        term_scroll(mk->term, -1, 0);
        send_mouse(mk, MBT_LEFT, MA_RELEASE, 2, 2, false, false, false);
        term_request_copy(mk->term, &clipboard, 1);
        check_clipboard(mk, bidi ?
            L"0\x5d2\x5b0" BLOCK_NL L"1\x5d2\x5b0" BLOCK_NL L"2\x5d2\x5b0" BLOCK_NL L"3\x5d2\x5b0" BLOCK_NL L"4\x5d2\x5b0" :
            L"0\x5d0" BLOCK_NL L"1\x5d0" BLOCK_NL L"2\x5d0" BLOCK_NL L"3\x5d0" BLOCK_NL L"4\x5d0");
        MOUSE_BYTES("");
    }
    /* A soft wrap is not a clipboard newline. Shift is released before
     * button-up; preserve the display hit, not the source endpoint hull. */
    for (int reverse = 0; reverse < 2; reverse++) {
        mouse_setup(mk, "Shift stream over a reordered run and soft wrap", "");
        mk->term->rect_select = false; /* previous case exercised the block default */
        term_size(mk->term, 3, 12, 100);
        mk->term->no_bidi = false;
        term_data_fragmented(mk->term, "\033[?1002;1006hA\xd7\x90\xd7\x91\xd7\x92\xd6\xb0Z0123456WXYZ");
        send_mouse(mk, MBT_LEFT, MA_CLICK, reverse ? 0 : 3, reverse, true, false, false);
        send_mouse(mk, MBT_LEFT, MA_RELEASE, reverse ? 3 : 0, 1-reverse, false, false, false);
        IEQUAL(mk->term->seltype, VISUAL_STREAM);
        term_request_copy(mk->term, &clipboard, 1);
        check_clipboard(mk, L"\x5d0Z0123456W");
        MOUSE_BYTES("");
    }
    /* A shell supplies logical text and an application supplies visual text
     * on the very same row. Their visibly identical left edges must copy
     * identically, including the mark, even with mouse reporting active. */
    for (int source = 0; source < 2; source++) {
        mouse_setup(mk, "Shift-copy logical and already ordered writers on one row", "");
        mk->term->rect_select = false;
        mk->term->no_bidi = false;
        term_size(mk->term, 3, 16, 100);
        term_data_fragmented(mk->term, "\033[?1002;1006hA\xd7\x90\xd7\x91\xd7\x92\xd6\xb0Z"
                             "\033]777;nemoterm:visual=1\007A\xd7\x92\xd6\xb0\xd7\x91\xd7\x90Z"
                             "\033]777;nemoterm:visual=0\007");
        int x = 5 * source;
        send_mouse(mk, MBT_LEFT, MA_CLICK, x, 0, true, false, false);
        send_mouse(mk, MBT_LEFT, MA_RELEASE, x+1, 0, false, false, false);
        term_request_copy(mk->term, &clipboard, 1);
        check_clipboard(mk, L"A\x5d2\x5b0");
        MOUSE_BYTES("");
    }
    mouse_setup(mk, "Block copies original Arabic text rather than shaped glyphs", "");
    mk->term->no_bidi = mk->term->no_arabicshaping = false;
    term_data_fragmented(mk->term, "A\xd8\xb3\xd9\x84\xd8\xa7\xd9\x85Z");
    send_mouse(mk, MBT_LEFT, MA_CLICK, 0, 0, true, true, false);
    send_mouse(mk, MBT_LEFT, MA_RELEASE, 5, 0, false, false, false);
    term_request_copy(mk->term, &clipboard, 1);
    check_clipboard(mk, L"A\x633\x644\x627\x645Z");
    mouse_setup(mk, "Ctrl repeated clicks start character blocks", "ABCDE\r\n01234");
    for (Mouse_Action action = MA_2CLK; action <= MA_3CLK; action++) {
        send_mouse(mk, MBT_LEFT, action, 1, 0, false, true, false);
        send_mouse(mk, MBT_LEFT, MA_DRAG, 2, 1, false, true, false);
        send_mouse(mk, MBT_LEFT, MA_RELEASE, 2, 1, false, true, false);
        IEQUAL(mk->term->seltype, RECTANGULAR);
        IEQUAL(mk->term->selmode, SM_CHAR);
        mk->clipboard_writes = 0;
        term_request_copy(mk->term, &clipboard, 1);
        check_clipboard(mk, L"BC" BLOCK_NL L"12");
    }
    mouse_setup(mk, "Ctrl alone retains application mouse modifiers", "\033[?1002;1006h");
    send_mouse(mk, MBT_LEFT, MA_CLICK, 1, 0, false, true, false);
    send_mouse(mk, MBT_LEFT, MA_DRAG, 2, 1, false, true, false);
    send_mouse(mk, MBT_LEFT, MA_RELEASE, 2, 1, false, true, false);
    MOUSE_BYTES("\033[<16;2;1M\033[<48;3;2M\033[<16;3;2m");
    IEQUAL(mk->term->selstate, NO_SELECTION);
    const int bindings[] = {0,1,2,3,4,5,6,7,8};
    for (size_t b=0;b<lenof(bindings);b++)
        for (unsigned pressed=0;pressed<8;pressed++) {
            mouse_setup(mk,"Configured rectangle modifier and invalid values","ABCD\r\n1234");
            mk->term->rect_select=false;
            conf_set_int(mk->term->conf,CONF_nemo_rectangle_modifiers,bindings[b]);
            send_mouse(mk,MBT_LEFT,MA_CLICK,0,0,pressed&1,pressed&2,pressed&4);
            send_mouse(mk,MBT_LEFT,MA_DRAG,1,1,false,false,false);
            send_mouse(mk,MBT_LEFT,MA_RELEASE,1,1,false,false,false);
            bool rectangle=bindings[b]>=2 && bindings[b]<=7 &&
                (pressed & bindings[b])==(unsigned)bindings[b];
            IEQUAL(mk->term->seltype,rectangle?RECTANGULAR:(pressed&1?VISUAL_STREAM:LEXICOGRAPHIC));
        }
    conf_set_int(mk->term->conf,CONF_nemo_rectangle_modifiers,2);
}

/* Both scroll directions, with the drag anchored at either end. Negative
 * history coordinates are exercised separately in the actual Windows UI. */
static void test_block_clipping(Mock *mk)
{
    for (int down = 0; down <= 1; down++) {
        for (int reverse = 0; reverse <= 1; reverse++) {
            mouse_setup(mk, "Block columns survive row eviction", "");
            term_size(mk->term, 4, 12, 0);
            term_data_fragmented(mk->term,
                "row0abcd\r\nrow1efgh\r\nrow2ijkl\r\nrow3mnop\033[?1002;1006h");
            int top = down ? 1 : 0, bot = top + 2;
            send_mouse(mk, MBT_LEFT, MA_CLICK, reverse ? 6 : 3,
                       reverse ? bot : top, true, true, false);
            send_mouse(mk, MBT_LEFT, MA_RELEASE, reverse ? 3 : 6,
                       reverse ? top : bot, false, false, false);
            for (int i = 0; i < 3; i++) {
                IEQUAL(mk->term->selstate, SELECTED);
                IEQUAL(mk->term->selstart.x, 3); IEQUAL(mk->term->selend.x, 7);
                IEQUAL(mk->term->selstart.y, down ? top+i : top);
                IEQUAL(mk->term->selend.y, down ? bot : bot-i);
                term_data_fragmented(mk->term, down ? "\033[1T" : "\033[1S");
            }
            IEQUAL(mk->term->selstate, NO_SELECTION);
            MOUSE_BYTES("");
        }
    }
}

static void test_block_crossing_region(Mock *mk)
{
    /* Source rows 2..5 move. In particular, with a four-row scroll the
     * entire pane is replaced: keep a stationary prefix or suffix alone. */
    static const struct { int from, to, lines, first, last; } cases[] = {
        {0,2,1,0,1}, {5,7,-1,6,7}, {1,3,-1,-1,-1}, {4,6,1,-1,-1},
        {1,3,-4,1,1}, {4,6,4,6,6}, {3,4,-1,4,5}, {2,3,2,-1,-1},
        {0,1,-1,0,1}, {6,7,1,6,7}, {0,7,2,-1,-1}, {0,7,-2,-1,-1},
        {1,4,1,1,3}, {3,6,-1,4,6}, {1,4,-99,1,1}, {3,6,99,6,6},
    };
    for (size_t i = 0; i < lenof(cases); i++) {
        for (int reverse = 0; reverse <= 1; reverse++) {
            mouse_setup(mk, "Rectangular selection spanning fixed and moving rows", "");
            term_size(mk->term,8,12,0);
            term_data_fragmented(mk->term,
                "row0abcd\r\nrow1efgh\r\nrow2ijkl\r\nrow3mnop\r\nrow4qrst\r\n"
                "row5uvwx\r\nrow6yzAB\r\nrow7CDEF\033[3;6r\033[?1002;1006h");
            int a = reverse ? cases[i].to : cases[i].from;
            int b = reverse ? cases[i].from : cases[i].to;
            send_mouse(mk,MBT_LEFT,MA_CLICK,3,a,true,true,false);
            send_mouse(mk,MBT_LEFT,MA_RELEASE,6,b,false,false,false);
            IEQUAL(mk->term->selstate,SELECTED);
            char seq[32];
            snprintf(seq,sizeof(seq),"\033[%d%c",abs(cases[i].lines),cases[i].lines>0?'S':'T');
            term_data_fragmented(mk->term,seq);
            if (cases[i].first < 0) {
                IEQUAL(mk->term->selstate,NO_SELECTION);
            } else {
                IEQUAL(mk->term->selstate,SELECTED);
                IEQUAL(mk->term->selstart.y,cases[i].first); IEQUAL(mk->term->selend.y,cases[i].last);
                IEQUAL(mk->term->selstart.x,3); IEQUAL(mk->term->selend.x,7);
                IEQUAL(mk->term->selanchor.y,reverse?cases[i].last:cases[i].first);
            }
            MOUSE_BYTES("");
        }
    }
}

static void test_copy_clipped_block(Mock *mk)
{
    mouse_setup(mk, "Explicit re-copy follows the surviving block; scrolling does not own the clipboard", "");
    term_size(mk->term,5,12,0);
    term_data_fragmented(mk->term,"aONEb\r\naTWOb\r\naSIXb\r\naENDb\033[2;4r\033[?1002;1006h");
    send_mouse(mk,MBT_LEFT,MA_CLICK,1,0,true,true,false);
    send_mouse(mk,MBT_LEFT,MA_RELEASE,3,2,false,false,false);
    const int clip = CLIP_LOCAL + 1;
    term_request_copy(mk->term,&clip,1);
    check_clipboard(mk,L"ONE" BLOCK_NL L"TWO" BLOCK_NL L"SIX");
    term_data_fragmented(mk->term,"\033[S");
    check_clipboard(mk,L"ONE" BLOCK_NL L"TWO" BLOCK_NL L"SIX");
    mk->clipboard_writes=0; term_request_copy(mk->term,&clip,1);
    check_clipboard(mk,L"ONE" BLOCK_NL L"SIX");
    term_request_paste(mk->term,CLIP_LOCAL);drain_paste(mk);
    MOUSE_BYTES("ONE\rSIX");
}

#undef BLOCK_NL

static void test_zoom_policy(Mock *mk)
{
    test_context(mk, "zoom leaves application Ctrl wheels alone; Shift forces local zoom");
    IEQUAL(nemo_zoom_key_binding(0x2bb,0xbb,2),true);
    IEQUAL(nemo_zoom_key_binding(0x2bb,0xbb,3),true);
    IEQUAL(nemo_zoom_key_binding(0x2bb,0x6b,2),true);
    IEQUAL(nemo_zoom_key_binding(0x2bd,0x6d,2),true);
    IEQUAL(nemo_zoom_key_binding(0x2bd,0xbd,2),true);
    IEQUAL(nemo_zoom_key_binding(0x2bd,0xbd,3),false);
    IEQUAL(nemo_zoom_key_binding(0x2bb,0xbb,6),false);
    IEQUAL(nemo_zoom_key_binding(0,0x6b,2),false);
    IEQUAL(nemo_zoom_key_binding(0x37a,0xbb,2),false);
    IEQUAL(nemo_zoom_key_binding(0x37a,0x7a,3),true);
    static const struct { int binding; unsigned keys; bool app, zoom; } cases[] = {
        {2,2,false,true}, {2,3,false,true}, {2,2,true,false}, {2,3,true,true},
        {2,0,false,false}, {2,1,false,false}, {2,6,false,false}, {2,7,true,false},
        {0,3,false,false}, {1,1,false,false}, {8,3,false,false}, {-1,3,false,false},
        {3,2,false,false}, {3,3,true,true}, {4,4,true,false}, {4,5,true,true}
    };
    for (size_t i=0; i<lenof(cases); i++)
        IEQUAL(nemo_zoom_wheel_binding(cases[i].binding,cases[i].keys,cases[i].app),cases[i].zoom);
}

int main(void)
{
    Mock *mk = mock_new();
    mk->term = term_init(mk->conf, mk->ucsdata, &mk->tw);
    mk->ldisc = ldisc_create(mk->conf, mk->term, &mk->backend, &mk->seat);

    test_tracking_modes(mk);
    test_buttons_and_modifiers(mk);
    test_side_buttons(mk);
    test_tracking_negotiation(mk);
    test_encoding_negotiation(mk);
    test_coordinate_limits(mk);
    test_pixel_motion(mk);
    test_physical_coordinates(mk);
    test_focus_and_reset(mk);
    test_alternate_scroll(mk);
    test_cancel_reported_buttons(mk);
    test_shift_takeover(mk);
    test_unmatched_local_release(mk);
    test_unencodable_release_cancel(mk);
    test_shift_selection(mk);
    test_scaled_visual_copy(mk);
    test_press_across_line_rendition(mk);
    test_ctrl_rectangle(mk);
    test_block_clipping(mk);
    test_block_crossing_region(mk);
    test_copy_clipped_block(mk);
    test_selection_cursor_traffic(mk);
    test_zoom_policy(mk);

    bool failed = mk->any_test_failed;
    mock_free(mk);
    puts(failed ? "Mouse test suite FAILED!" : "Mouse test suite passed");
    return failed ? 1 : 0;
}
