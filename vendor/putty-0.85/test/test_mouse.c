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
    static const int modes[] = {9, 1000, 1002, 1003};
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
    static const int protocols[] = {9, 1000, 1002, 1003};
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
    test_unencodable_release_cancel(mk);
    test_shift_selection(mk);

    bool failed = mk->any_test_failed;
    mock_free(mk);
    puts(failed ? "Mouse test suite FAILED!" : "Mouse test suite passed");
    return failed ? 1 : 0;
}
