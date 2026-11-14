/* SPDX-License-Identifier: MIT */
static unsigned observed_bells;
static int observed_bell_mode;
static void counted_bell(TermWin *win, int mode)
{
    observed_bells++;
    observed_bell_mode = mode;
}

static void test_bell_policy(Mock *mk)
{
    Conf *saved = conf_copy(mk->conf);
    const TermWinVtable *previous = mk->tw.vt;
    TermWinVtable vt = *previous;
    vt.bell = counted_bell;
    mk->tw.vt = &vt;
    const int modes[] = {BELL_DISABLED, BELL_DEFAULT, BELL_VISUAL};
    for (size_t i=0; i<lenof(modes); i++) {
        conf_set_int(mk->conf, CONF_beep, modes[i]);
        conf_set_bool(mk->conf, CONF_bellovl, false);
        term_reconfig(mk->term, mk->conf);
        reset(mk); observed_bells = 0;
        test_context(mk, "BEL selects configured sound/visual policy %d", modes[i]);
        term_data_fragmented(mk->term, "\033]2;title\007");
        IEQUAL(observed_bells, 0); /* OSC terminator is not an audible bell. */
        term_data_fragmented(mk->term, "\007");
        IEQUAL(observed_bells, 1); IEQUAL(observed_bell_mode, modes[i]);
        IEQUAL(mk->term->in_vbell, modes[i] == BELL_VISUAL);
        IEQUAL(mk->term->nbeeps, 0);
        IEQUAL(mk->term->beephead == NULL, true);
    }
    test_context(mk, "disabled overload accounting retains no per-BEL allocation");
    conf_set_int(mk->conf, CONF_beep, BELL_DISABLED);
    term_reconfig(mk->term, mk->conf); reset(mk); observed_bells = 0;
    for (int i=0; i<10000; i++) term_data_fragmented(mk->term, "\007");
    IEQUAL(observed_bells, 10000); IEQUAL(mk->term->nbeeps, 0);
    IEQUAL(mk->term->beephead == NULL, true);

    test_context(mk, "overload suppresses repeated bells and retains bounded records");
    conf_set_bool(mk->conf, CONF_bellovl, true);
    conf_set_int(mk->conf, CONF_bellovl_n, 3);
    conf_set_int(mk->conf, CONF_bellovl_t, 60000);
    conf_set_int(mk->conf, CONF_bellovl_s, 60000);
    term_reconfig(mk->term, mk->conf); reset(mk); observed_bells = 0;
    for (int i=0; i<100; i++) term_data_fragmented(mk->term, "\007");
    IEQUAL(observed_bells, 2); IEQUAL(mk->term->beep_overloaded, true);
    IEQUAL(mk->term->nbeeps, 3);
    conf_set_bool(mk->conf, CONF_bellovl, false);
    term_reconfig(mk->term, mk->conf);
    term_data_fragmented(mk->term, "\007");
    IEQUAL(observed_bells, 3); IEQUAL(mk->term->nbeeps, 0);
    IEQUAL(mk->term->beephead == NULL, true);
    conf_copy_into(mk->conf, saved); conf_free(saved);
    term_reconfig(mk->term, mk->conf); reset(mk);
    mk->tw.vt = previous;
}
