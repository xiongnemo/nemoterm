/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main
#include "terminal/nemo_feature_policy.h"

typedef struct FeatureReference {
    const char *name;
    unsigned policy, number;
    const char *payload;
    size_t payload_length;
    bool bel;
    const char *reply;
    size_t reply_length;
} FeatureReference;
#include "../../../tests/feature_policy_reference.h"

static void response(Mock *mk, const char *expected, size_t length)
{
    if (mk->to_backend->len != length || memcmp(mk->to_backend->s,expected,length)) {
        report_fail(mk,__FILE__,__LINE__,"reply differs: %zu / %zu bytes",
                    mk->to_backend->len,length);
        printf("actual:");
        for (size_t i=0; i<mk->to_backend->len; i++)
            printf(" %02x",(unsigned char)mk->to_backend->s[i]);
        putchar('\n');
    }
    strbuf_clear(mk->to_backend);
}
#define RESPONSE(mk, expected) response(mk,expected,sizeof(expected)-1)
#define ALL "allowColorOps,allowMouseOps,allowPasteControls,allowTcapOps,allowTitleOps,allowWindowOps"
#define COLORS "SetColor,GetColor,GetAnsiColor"
#define MOUSE "X10,Locator,VT200Click,VT200Hilite,AnyButton,AnyEvent,FocusEvent,Extended,SGR,URXVT,AlternateScroll"
#define WINDOWS "RestoreWin,MinimizeWin,SetWinPosition,SetWinSizePixels,RaiseWin,LowerWin,RefreshWin,SetWinSizeChars,MaximizeWin,GetWinState,GetWinPosition,GetWinSizePixels,GetWinSizeChars,GetScreenSizeChars,GetIconTitle,GetWinTitle,PushTitle,PopTitle,SetWinLines,ColumnMode,GetChecksum,SetChecksum,GetSelection,SetSelection"

static void formatter(Mock *mk)
{
    for (size_t i=0; i<lenof(feature_reference); i++) {
        const FeatureReference *r=&feature_reference[i];
        NemoFeaturePolicy policy=feature_policies[r->policy], before=policy;
        test_context(mk,"independent formatter %s",r->name);
        char reply[NEMO_FEATURE_POLICY_REPLY_MAX];
        memset(reply,0x5a,sizeof(reply));
        size_t length=nemo_feature_policy_reply(&policy,r->number,r->payload,
            r->payload_length,true,r->bel,reply,sizeof(reply));
        IEQUAL(length,r->reply_length);
        if (length==r->reply_length && memcmp(reply,r->reply,length))
            report_fail(mk,__FILE__,__LINE__,"formatter changed original reply bytes");
        IEQUAL(memcmp(&policy,&before,sizeof(policy)),0);
        for (size_t j=length; j<sizeof(reply); j++) IEQUAL(reply[j],0x5a);
        if (!length) continue;
        memset(reply,0x5a,sizeof(reply));
        IEQUAL(nemo_feature_policy_reply(&policy,r->number,r->payload,
            r->payload_length,true,r->bel,reply,length-1),0);
        for (size_t j=0; j<sizeof(reply); j++) IEQUAL(reply[j],0x5a);
        IEQUAL(nemo_feature_policy_reply(&policy,r->number,r->payload,
            r->payload_length,true,r->bel,reply,length),length);
        IEQUAL(memcmp(reply,r->reply,length),0);
    }
    puts("Feature policy formatter: 1780 unchanged XTerm reply streams and bounded writes");
}

static void noop(TermWin *win) {}
static void set_boolean(TermWin *win, bool value) {}
static void move_window(TermWin *win, int x, int y) {}
static void resize_window(TermWin *win, int x, int y, bool pixels) {}
static bool geometry(TermWin *win, TermWindowGeometry *g) { return false; }
static bool pointer(TermWin *win, TermPointerState *p, bool event) { return false; }

static void permit(Mock *mk, bool enabled)
{
    conf_set_bool(mk->conf,CONF_no_mouse_rep,!enabled);
    conf_set_bool(mk->conf,CONF_no_remote_resize,!enabled);
    conf_set_bool(mk->conf,CONF_no_remote_wintitle,!enabled);
    conf_set_bool(mk->conf,CONF_paste_controls,enabled);
    conf_set_bool(mk->conf,CONF_nemo_osc52_write,enabled);
    conf_set_bool(mk->conf,CONF_nemo_osc52_read,enabled);
    conf_set_bool(mk->conf,CONF_nemo_allow_checksum,enabled);
    conf_set_bool(mk->conf,CONF_nemo_allow_set_tcap,enabled);
    conf_set_bool(mk->conf,CONF_nemo_allow_get_tcap,enabled);
    conf_set_int(mk->conf,CONF_remote_qtitle_action,enabled?TITLE_REAL:TITLE_NONE);
    term_reconfig(mk->term,mk->conf);
}

static void initial_state(Mock *mk)
{
    reset(mk);
    /* RIS preserves the selected compatibility level. Establish the same
     * VT525/7-bit baseline for independent whole and fragmented cases. */
    term_data_fragmented(mk->term,"\033[65;1\"p");
}

static void parser(Mock *mk, bool bytewise)
{
    static const struct { const char *input; size_t length; const char *reply; size_t reply_length; } cases[]={
#define CASE(a,b) {a,sizeof(a)-1,b,sizeof(b)-1}
        CASE("\033]60\033\\","\033]60;" ALL "\033\\"),
        CASE("\033]60;\007","\033]60;" ALL "\007"),
        CASE("\033]00060\007","\033]60;" ALL "\007"),
        CASE("\033]60;?\007",""),
        CASE("\033]60x\007",""),
        CASE("\033]60;allowColorOps:false\007\033]60\007","\033]60;" ALL "\007"),
        CASE("\033]61;allowColorOps\007","\033]61\007"),
        CASE("\033]61;allowWindowOps\033\\","\033]61\033\\"),
        CASE("\033]61;unknown\007","\033]61\007"),
        CASE("\033]61;\007\033]62\007",""),
        CASE("\033]62;allowColorOps\007","\033]62;" COLORS "\007"),
        CASE("\033]62;ALLOWCOLOROPS\033\\","\033]62;" COLORS "\033\\"),
        CASE("\033]62; allowColorOps\007","\033]62\007"),
        CASE("\033]62;allowColorOps \007","\033]62\007"),
        CASE("\033]62;allowColorOps;extra\007","\033]62\007"),
        CASE("\033]62;allowFontOps\007","\033]62\007"),
        CASE("\033]62;allowTcapOps\007","\033]62;SetTcap,GetTcap\007"),
        CASE("\033]62;allowTitleOps\007","\033]62\007"),
        CASE("\033]62;allowMouseOps\007","\033]62;" MOUSE "\007"),
        CASE("\033]62;allowWindowOps\007","\033]62;" WINDOWS "\007"),
        CASE("\033]62;allowWinOps\007","\033]62;" WINDOWS "\007"),
        CASE("\033]62;allowColor\0Ops\007","\033]62\007"),
        CASE("\033]62;allowColor\tOps\007",""),
        CASE("\033]62;allowColor\377Ops\007",""),
        CASE("\033]62;\344\270\255\007","\033]62\007"),
        CASE("\033]62;\300\257\007",""),
        CASE("\033]62;\355\240\200\007",""),
        CASE("\033]62;allowColor\030\033\\\033]60\007","\033]60;" ALL "\007"),
        CASE("\033]62;allowColor\032\033\\\033]60\007","\033]60;" ALL "\007"),
        /* Existing PuTTY parsing lets ESC start another OSC. XTerm's original
         * escape-restart capture has no reply; this named difference is not
         * included in the unchanged formatter replay. */
        CASE("\033]62;allowColor\033]60\033\\","\033]60;" ALL "\033\\"),
        CASE("\033 G\033]60\033\\\033]62;allowColorOps\007",
             "\23560;" ALL "\234\23562;" COLORS "\007"),
        CASE("\033c\033]60\007","\033]60;" ALL "\007"),
        CASE("\033[!p\033]60\007","\033]60;" ALL "\007"),
        CASE("\033[65;1\"p\033]60\007","\033]60;" ALL "\007"),
        CASE("\033[?1049h\033]60\007\033[?1049l\033]60\007",
             "\033]60;" ALL "\007\033]60;" ALL "\007"),
        CASE("\033[?2l\033<\033]60\007","\033]60;" ALL "\007"),
#undef CASE
    };
    permit(mk,true);
    for (size_t i=0; i<lenof(cases); i++) {
        initial_state(mk);
        test_context(mk,"native parser %zu / %s",i,bytewise?"bytewise":"whole");
        for (size_t offset=0; offset<cases[i].length;) {
            size_t n=bytewise?1:cases[i].length;
            term_data(mk->term,cases[i].input+offset,n); offset+=n;
        }
        response(mk,cases[i].reply,cases[i].reply_length);
    }
    initial_state(mk);
    test_context(mk,"overflow is rejected and parser recovers");
    term_data_fragmented(mk->term,"\033]62;allowColorOps");
    for (int i=0; i<20000; i++) term_data(mk->term," ",1);
    term_data_fragmented(mk->term,"\007\033]62;allowColorOps\007");
    RESPONSE(mk,"\033]62;" COLORS "\007");
    printf("Feature policy parser: %zu %s cases, overflow and recovery\n",lenof(cases),bytewise?"bytewise":"whole");
}

static void permissions(Mock *mk)
{
    permit(mk,false); initial_state(mk);
    test_context(mk,"live restrictions and actual denied operations");
    term_data_fragmented(mk->term,"\033]60\007\033]61;allowMouseOps\007\033]61;allowWindowOps\007");
    RESPONSE(mk,"\033]60;allowColorOps\007"
        "\033]61;X10,Locator,VT200Click,VT200Hilite,AnyButton,AnyEvent,FocusEvent\007"
        "\033]61;SetWinPosition,SetWinSizePixels,SetWinSizeChars,GetIconTitle,GetWinTitle,PushTitle,PopTitle,SetWinLines,ColumnMode,GetSelection,SetSelection,GetChecksum,SetChecksum\007");
    term_data_fragmented(mk->term,"\033[8;30;100t\033]2;blocked\007\033[21t\033[17#y\033[?1004h");
    IEQUAL(mk->term->win_resize_pending,WIN_RESIZE_NO);
    IEQUAL(mk->term->checksum_flags,0);
    term_set_focus(mk->term,false); term_set_focus(mk->term,true);
    RESPONSE(mk,"");
    term_data_fragmented(mk->term,"\033]52;0;YQ==\007\033]52;0;?\007"); RESPONSE(mk,"");
    term_do_paste(mk->term,L"\1\b\tQ\177",5); RESPONSE(mk,"\b\tQ\177");

    test_context(mk,"reconfiguration applies immediately without reset");
    permit(mk,true);
    term_data_fragmented(mk->term,"\033]60\007\033]61;allowWindowOps\007");
    RESPONSE(mk,"\033]60;" ALL "\007\033]61\007");
    term_data_fragmented(mk->term,"\033]2;allowed\007\033[21t\033[17#y");
    RESPONSE(mk,"\033]lallowed\033\\"); IEQUAL(mk->term->checksum_flags,17);
    term_set_focus(mk->term,false); RESPONSE(mk,"\033[O");
    term_do_paste(mk->term,L"\1\b\tQ\177",5); RESPONSE(mk,"\1\b\tQ\177");
    term_data_fragmented(mk->term,"\033]52;0;YQ==\007\033]52;0;?\007");
    RESPONSE(mk,"\033]52;0;YQ==\007");

    test_context(mk,"independent read/write permissions and empty title privacy");
    conf_set_bool(mk->conf,CONF_nemo_osc52_write,false);
    conf_set_int(mk->conf,CONF_remote_qtitle_action,TITLE_EMPTY);
    term_reconfig(mk->term,mk->conf);
    term_data_fragmented(mk->term,"\033]61;allowWindowOps\007\033[21t"
        "\033]52;0;Yg==\007\033]52;0;?\007");
    RESPONSE(mk,"\033]61;GetIconTitle,GetWinTitle,SetSelection\007\033]l\033\\\033]52;0;YQ==\007");
    conf_set_bool(mk->conf,CONF_nemo_osc52_write,true);
    conf_set_bool(mk->conf,CONF_nemo_osc52_read,false);
    term_reconfig(mk->term,mk->conf);
    term_data_fragmented(mk->term,"\033]61;allowWindowOps\007\033]52;0;Yg==\007\033]52;0;?\007");
    RESPONSE(mk,"\033]61;GetIconTitle,GetWinTitle,GetSelection\007");
    permit(mk,true);
    term_data_fragmented(mk->term,"\033]52;0;?\007\033[8;30;100t");
    RESPONSE(mk,"\033]52;0;Yg==\007");
    IEQUAL(mk->term->win_resize_pending,WIN_RESIZE_NEED_SEND);
    IEQUAL(mk->term->win_resize_pending_w,100); IEQUAL(mk->term->win_resize_pending_h,30);
    puts("Feature policy permissions: actual title, resize, focus, paste and selection gates");
}

static void termcap_permissions(Mock *mk)
{
    static const char *restrictions[] = {"SetTcap,GetTcap", "GetTcap", "SetTcap", ""};
    conf_set_int(mk->conf, CONF_funky_type, FUNKY_TCAP);
    for (unsigned mask = 0; mask < 4; mask++) {
        conf_set_bool(mk->conf, CONF_nemo_allow_set_tcap, mask & 1);
        conf_set_bool(mk->conf, CONF_nemo_allow_get_tcap, mask & 2);
        term_reconfig(mk->term, mk->conf); initial_state(mk);
        nemo_tcap_configure(mk->term, "xterm-256color");
        test_context(mk, "independent termcap permissions %u", mask);
        term_data_fragmented(mk->term, "\033]61;allowTcapOps\007\033]62;allowTcapOps\007");
        strbuf *expected = strbuf_new();
        put_fmt(expected, "\033]61%s%s\007\033]62;SetTcap,GetTcap\007",
                *restrictions[mask] ? ";" : "", restrictions[mask]);
        response(mk, expected->s, expected->len); strbuf_free(expected);
        term_data_fragmented(mk->term, "\033P+p6c696e7578\033\\\033P+q6b6631\033\\\033[5n");
        if (!(mask & 2)) RESPONSE(mk, "\033[0n");
        else if (mask & 1) RESPONSE(mk, "\033P1+r6b6631=1b5b5b41\033\\\033[0n");
        else RESPONSE(mk, "\033P1+r6b6631=1b4f50\033\\\033[0n");
    }
}

int main(void)
{
    Mock *mk=mock_new();
    TermWinVtable vt=mock_termwin_vt;
    vt.refresh=noop; vt.set_minimised=vt.set_maximised=vt.set_zorder=set_boolean;
    vt.move=vt.request_resize=move_window; vt.request_window_resize=resize_window;
    vt.get_geometry=geometry; vt.get_pointer=pointer;
    mk->tw.vt=&vt; mk->ucsdata->line_codepage=CP_UTF8;
    conf_set_int(mk->conf,CONF_beep,BELL_DISABLED);
    mk->term=term_init(mk->conf,mk->ucsdata,&mk->tw);
    mk->ldisc=ldisc_create(mk->conf,mk->term,&mk->backend,&mk->seat);
    formatter(mk); parser(mk,false); parser(mk,true); permissions(mk); termcap_permissions(mk);
    bool failed=mk->any_test_failed; mock_free(mk);
    puts(failed?"Feature policy FAILED":"Feature policy passed");
    return failed?1:0;
}
