/* SPDX-License-Identifier: MIT
 * Real parser, bounded framing and live preferences; no native I/O. */
static unsigned iterm_report_callbacks;
static unsigned iterm_report_bells;
static void iterm_bell_stub(TermWin *tw, int mode)
{
    iterm_report_bells++;
}
static bool iterm_clipboard_stub(TermWin *tw, const char *data, size_t len)
{
    iterm_report_callbacks++;
    return true;
}
static bool iterm_sync_stub(TermWin *tw, bool enabled)
{
    iterm_report_callbacks++;
    return true;
}

static void test_iterm_reports(Mock *mk)
{
    Conf *saved = conf_copy(mk->conf);
    TermWinVtable vt = mock_termwin_vt;
    vt.get_geometry = mock_geometry;
    vt.osc52_write = iterm_clipboard_stub;
    vt.set_synchronized_update = iterm_sync_stub;
    vt.bell = iterm_bell_stub;
    mk->tw.vt = &vt;
    conf_set_bool(mk->conf, CONF_true_colour, true);
    conf_set_bool(mk->conf, CONF_no_mouse_rep, false);
    conf_set_bool(mk->conf, CONF_no_remote_wintitle, false);
    conf_set_bool(mk->conf, CONF_no_remote_hyperlinks, false);
    conf_set_bool(mk->conf, CONF_no_bracketed_paste, false);
    conf_set_bool(mk->conf, CONF_cjk_ambig_wide, false);
    conf_set_bool(mk->conf, CONF_nemo_osc52_write, false);
    term_reconfig(mk->term, mk->conf);
    reset(mk);
    iterm_report_callbacks = 0;
    iterm_report_bells = 0;
    const char *caps = "\033]1337;Capabilities=T1LrMSc3UTs3BGsGoSyHSx\033\\";
    test_context(mk, "iTerm reports: exact spec codes and no ambiguous F");
    term_data_fragmented(mk->term, "\033%G\033]1337;Capabilities\007");
    response(mk, caps);
    term_data_fragmented(mk->term, "\033]1337;Capabilities\033\\");
    response(mk, caps);
    IEQUAL(iterm_report_callbacks, 0);

    test_context(mk, "iTerm reports follow reconfigured permission and width policy");
    conf_set_bool(mk->conf, CONF_nemo_osc52_write, true);
    conf_set_bool(mk->conf, CONF_cjk_ambig_wide, true);
    term_reconfig(mk->term, mk->conf);
    term_data_fragmented(mk->term, "\033]1337;Capabilities\007");
    response(mk, "\033]1337;Capabilities=T1CwLrMSc3UAwTs3BGsGoSyHSx\033\\");
    conf_set_bool(mk->conf, CONF_true_colour, false);
    conf_set_bool(mk->conf, CONF_no_mouse_rep, true);
    conf_set_bool(mk->conf, CONF_no_remote_wintitle, true);
    conf_set_bool(mk->conf, CONF_no_remote_hyperlinks, true);
    conf_set_bool(mk->conf, CONF_no_bracketed_paste, true);
    term_reconfig(mk->term, mk->conf);
    term_data_fragmented(mk->term, "\033]1337;Capabilities\007");
    response(mk, "\033]1337;Capabilities=CwLrSc3UAwGsGoSySx\033\\");
    vt.osc52_write = NULL; vt.set_synchronized_update = NULL;
    term_data_fragmented(mk->term, "\033%@\033]1337;Capabilities\007");
    response(mk, "\033]1337;Capabilities=LrSc3GsGoSx\033\\");
    IEQUAL(iterm_report_callbacks, 0);

    test_context(mk, "iTerm size uses live DPI and locale-independent logical units");
    geometry = (TermWindowGeometry){.cell_width=8, .cell_height=16, .dpi=96};
    term_data_fragmented(mk->term, "\033]1337;ReportCellSize\007");
    response(mk, "\033]1337;ReportCellSize=16.000;8.000;1.000\033\\");
    geometry = (TermWindowGeometry){.cell_width=11, .cell_height=23, .dpi=144};
    term_data_fragmented(mk->term, "\033]1337;ReportCellSize\033\\");
    response(mk, "\033]1337;ReportCellSize=15.333;7.333;1.500\033\\");
    geometry.dpi = 192;
    term_data_fragmented(mk->term, "\033]1337;ReportCellSize\007");
    response(mk, "\033]1337;ReportCellSize=11.500;5.500;2.000\033\\");
    geometry.dpi = 0;
    term_data_fragmented(mk->term, "\033]1337;ReportCellSize\007");
    response(mk, "\033]1337;ReportCellSize=23.000;11.000;1.000\033\\");
    geometry.cell_width = 0;
    term_data_fragmented(mk->term, "\033]1337;ReportCellSize\007\033[5n");
    response(mk, "\033[0n");
    vt.get_geometry = NULL;
    term_set_cell_size(mk->term, 9, 18);
    term_data_fragmented(mk->term, "\033]1337;ReportCellSize\007");
    response(mk, "\033]1337;ReportCellSize=18.000;9.000;1.000\033\\");

    test_context(mk, "iTerm queries reject report echoes, suffixes and cancellation");
    const char *ignored[] = {"Capabilities=F", "Capabilities=", "Capabilities;",
        "capabilities", "CapabilitiesX", "ReportCellSize=1;1;1", "ReportCellSize=",
        "ReportCellSizeX", "ReportCellSize;", "Capabilities\030", "ReportCellSize\032"};
    for (size_t i=0; i<lenof(ignored); i++) {
        char sequence[128];
        sprintf(sequence, "\033]1337;%s\007\033[5n", ignored[i]);
        term_data_fragmented(mk->term, sequence);
        response(mk, "\033[0n");
    }
    /* CAN and SUB end the OSC. The following BEL is then an ordinary bell,
     * not a terminator. A query-only mock still needs that native callback. */
    IEQUAL(iterm_report_bells, 2);
    term_data_fragmented(mk->term, "\033]1337;Capabilities");
    char excess[NEMO_CWD_OSC_MAX + 1]; memset(excess, 'X', sizeof(excess));
    term_data(mk->term, excess, sizeof(excess));
    term_data_fragmented(mk->term, "\033\\\033]1337;ReportCellSize\007");
    response(mk, "\033]1337;ReportCellSize=18.000;9.000;1.000\033\\");

    test_context(mk, "iTerm queries use configured C1 framing and retain BEL-independent ST");
    term_data_fragmented(mk->term, "\033[65;1\"p\033 G\033]1337;ReportCellSize\007");
    response(mk, "\2351337;ReportCellSize=18.000;9.000;1.000\234");
    BackendVtable unicode_backend = mock_backend_vt;
    unicode_backend.flags |= BACKEND_UTF8_C1;
    mk->backend.vt = &unicode_backend;
    term_data_fragmented(mk->term, "\033]1337;ReportCellSize\033\\");
    response(mk, "\302\2351337;ReportCellSize=18.000;9.000;1.000\302\234");
    mk->backend.vt = &mock_backend_vt;
    mk->tw.vt = &mock_termwin_vt;
    conf_copy_into(mk->conf, saved); conf_free(saved);
    term_reconfig(mk->term, mk->conf);
    reset(mk);
}
