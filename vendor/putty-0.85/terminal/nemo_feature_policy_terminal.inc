/* SPDX-License-Identifier: MIT
 * Read current permissions on demand: no per-terminal allocation or cached
 * policy which can become stale after reconfiguration. Unlike XTerm resources,
 * Nemo's permissions are independent gates, with no master override.
 */
static void nemo_report_feature_policy(Terminal *term, bool bel)
{
    if (!term->ldisc || term->osc_overflow) return;
    NemoFeaturePolicy p = {0};
    const TermWinVtable *vt = term->win->vt;
#define BIT(n) NEMO_FEATURE_BIT(n)
    p.supported[NEMO_FEATURE_COLOR] = BIT(1)|BIT(2)|BIT(3);
    p.supported[NEMO_FEATURE_TCAP] = BIT(2); /* XTGETTCAP, not XTSETTCAP */
    if (!conf_get_bool(term->conf, CONF_nemo_allow_get_tcap))
        p.restricted[NEMO_FEATURE_TCAP] = BIT(2);
    p.supported[NEMO_FEATURE_MOUSE] = (BIT(12)-1) & ~BIT(0);
    if (!vt->get_pointer) p.supported[NEMO_FEATURE_MOUSE] &= ~BIT(2);
    /* The local gate suppresses tracking/focus reports. Encoding selection and
     * alternate-screen wheel-to-key conversion remain available. */
    if (term->no_mouse_rep)
        p.restricted[NEMO_FEATURE_MOUSE] = (BIT(8)-1) & ~BIT(0);
    p.supported[NEMO_FEATURE_PASTE] = (BIT(34)-1); /* C0, DEL; no STTY filter */
    if (!conf_get_bool(term->conf, CONF_paste_controls))
        p.restricted[NEMO_FEATURE_PASTE] = (BIT(32)-1) &
            ~(BIT(8)|BIT(9)|BIT(10)|BIT(13));

#define SUPPORT(op, condition) do { \
    if (condition) p.supported[NEMO_FEATURE_WINDOW] |= BIT(NEMO_FW_##op); \
} while (0)
    SUPPORT(RESTORE, vt->set_minimised);
    SUPPORT(MINIMIZE, vt->set_minimised);
    SUPPORT(POSITION, vt->move);
    SUPPORT(SIZE_PIXELS, vt->request_window_resize);
    SUPPORT(RAISE, vt->set_zorder);
    SUPPORT(LOWER, vt->set_zorder);
    SUPPORT(REFRESH, vt->refresh);
    SUPPORT(SIZE_CHARS, vt->request_window_resize || vt->request_resize);
    SUPPORT(MAXIMIZE, vt->set_maximised);
    SUPPORT(STATE, true);
    SUPPORT(GET_POSITION, true);
    SUPPORT(GET_PIXELS, true);
    SUPPORT(GET_CHARS, true);
    SUPPORT(SCREEN_CHARS, vt->get_geometry);
    SUPPORT(ICON_TITLE, true);
    SUPPORT(WIN_TITLE, true);
    SUPPORT(PUSH_TITLE, true);
    SUPPORT(POP_TITLE, true);
    SUPPORT(LINES, vt->request_window_resize || vt->request_resize);
    SUPPORT(COLUMNS, vt->request_resize);
    /* Primary selection and cut buffers work without a system clipboard
     * callback. OSC 52 settings gate all of these selection targets. */
    SUPPORT(GET_SELECTION, true);
    SUPPORT(SET_SELECTION, true);
    SUPPORT(GET_CHECKSUM, true);
    SUPPORT(SET_CHECKSUM, true);
#undef SUPPORT
#define DENY(op) (p.restricted[NEMO_FEATURE_WINDOW] |= BIT(NEMO_FW_##op))
    if (term->no_remote_resize) {
        DENY(POSITION); DENY(SIZE_PIXELS); DENY(SIZE_CHARS);
        DENY(LINES); DENY(COLUMNS);
    }
    /* An empty title response is supported, but discloses no title. */
    if (term->remote_qtitle_action != TITLE_REAL) {
        DENY(ICON_TITLE); DENY(WIN_TITLE);
    }
    if (term->no_remote_wintitle) { DENY(PUSH_TITLE); DENY(POP_TITLE); }
    if (!conf_get_bool(term->conf, CONF_nemo_osc52_read)) DENY(GET_SELECTION);
    if (!conf_get_bool(term->conf, CONF_nemo_osc52_write)) DENY(SET_SELECTION);
    if (!conf_get_bool(term->conf, CONF_nemo_allow_checksum)) {
        DENY(GET_CHECKSUM); DENY(SET_CHECKSUM);
    }
#undef DENY
    for (unsigned i=0; i<NEMO_FEATURE_COUNT; i++) {
        p.restricted[i] &= p.supported[i];
        if (p.supported[i] && !p.restricted[i]) p.enabled |= 1u << i;
    }
    /* XTerm has a title master but no title subcategory table. */
    if (!term->no_remote_wintitle) p.enabled |= 1u << NEMO_FEATURE_TITLE;
#undef BIT
    char reply[NEMO_FEATURE_POLICY_REPLY_MAX];
    size_t length = nemo_feature_policy_reply(&p, term->esc_args[0],
        term->osc_string, term->osc_strlen, in_utf(term), bel,
        reply, sizeof(reply));
    if (length) nemo_protocol_send(term, reply, (int)length);
}
