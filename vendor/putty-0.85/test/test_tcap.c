/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main

static void response(Mock *mk, const char *expected)
{
    size_t len = strlen(expected);
    if (len != mk->to_backend->len || memcmp(expected, mk->to_backend->s, len))
        report_fail(mk, __FILE__, __LINE__, "capability reply differs: %zu expected, %zu actual bytes",
                    len, mk->to_backend->len);
    strbuf_clear(mk->to_backend);
}

static void hex(strbuf *buf, const char *value)
{
    while (*value) put_fmt(buf, "%02x", (unsigned char)*value++);
}

static void query(Mock *mk, const char *name, const char *value)
{
    test_context(mk, "XTGETTCAP %s", name);
    strbuf *input = strbuf_new(), *expected = strbuf_new();
    put_dataz(input, "\033P+q"); hex(input, name); put_dataz(input, "\033\\");
    put_dataz(expected, value ? "\033P1+r" : "\033P0+r");
    hex(expected, name);
    if (value) { put_byte(expected, '='); hex(expected, value); }
    put_dataz(expected, "\033\\");
    term_data_fragmented(mk->term, input->s);
    response(mk, expected->s);
    strbuf_free(input); strbuf_free(expected);
}

static void test_queries_and_bounds(Mock *mk)
{
    reset(mk);
    query(mk, "TN", "xterm-256color"); query(mk, "name", "xterm-256color");
    query(mk, "Co", "256"); query(mk, "colors", "256"); query(mk, "RGB", "8");
    query(mk, "kund", NULL);
    term_data_fragmented(mk->term, "\033P+q436F;524742;544E\033\\");
    response(mk, "\033P1+r436F=323536;524742=38;544E=787465726d2d323536636f6c6f72\033\\");
    term_data_fragmented(mk->term, "\033P+q637570;436f\033\\\033P+q436f;637570;524742\033\\");
    response(mk, "\033P0+r\033\\\033P1+r436f=323536;\033\\");
    term_data_fragmented(mk->term, "\033P+q436f;2678;524742\033\\");
    response(mk, "\033P1+r436f=323536;\033\\"); /* &x is unknown */
    term_data_fragmented(mk->term, "\033P+q436f;2638;524742\033\\");
    response(mk, "\033P1+r436f=323536;2638\033\\"); /* &8 known, unavailable */
    static const char *bad[] = {"", "1", "gg", "00", "1b", "7f", "80", ";436f",
        "436f;;524742", "436f;ff", "666666666666666666666666666666666666666666666666666666666666666666"};
    for (size_t i = 0; i < lenof(bad); i++) {
        strbuf *input = strbuf_new();
        put_fmt(input, "\033P+q%s\033\\", bad[i]);
        test_context(mk, "invalid encoded names %s", bad[i]);
        term_data_fragmented(mk->term, input->s); response(mk, "\033P0+r\033\\");
        strbuf_free(input);
    }
    term_data_fragmented(mk->term, "\033P+q436f;\033\\");
    response(mk, "\033P1+r436f=323536;\033\\");
    term_data_fragmented(mk->term, "\033P+q");
    for (int i = 0; i < 10000; i++) term_data(mk->term, "5", 1);
    IEQUAL(mk->term->dcs_query_len, NEMO_DCS_QUERY_SIZE-1);
    term_data_fragmented(mk->term, "\033\\A"); response(mk, "\033P0+r\033\\");
    IEQUAL(get_termchar(mk->term, 0, 0).chr, CSET_ASCII|'A');
    /* Maximum response expansion, and direct-call input bounds. */
    strbuf *many = strbuf_new();
    for (int i = 0; i < 409; i++) put_dataz(many, "544e;");
    strbuf *reply = nemo_tcap_reply(mk->term, many->s, false);
    IEQUAL(reply->len, 7+409*34);
    IEQUAL(reply->len < 14*1024, true); strbuf_free(reply);
    put_dataz(many, "544e");
    reply = nemo_tcap_reply(mk->term, many->s, false);
    SEQUAL(reply->s, "\033P0+r\033\\");
    strbuf_free(reply); strbuf_free(many);

    term_data_fragmented(mk->term, "\033P+q436f\030B\033P+q436f\032C"
                         "\033P+q436f\033[31m\033P+q524742\033\\");
    response(mk, "\033P1+r524742=38\033\\");
    IEQUAL(get_termchar(mk->term, 1, 0).chr, CSET_ASCII|'B');
    IEQUAL(get_termchar(mk->term, 2, 0).chr, CSET_ASCII|'C');
    term_data_fragmented(mk->term, "\033P0+q436f\033\\\033P+x436f\033\\"); response(mk, "");
    term_data_fragmented(mk->term, "\033P+q436f\x9c\033P+q436f\xc2\x9c");
    response(mk, "\033P1+r436f=323536\033\\\033P1+r436f=323536\033\\");
    term_data_fragmented(mk->term, "\033P+q436f"); term_pwron(mk->term, true);
    term_data_fragmented(mk->term, "Z\033P$qm\033\\\033P+q524742\033\\");
    response(mk, "\033P1$r0m\033\\\033P1+r524742=38\033\\");
    term_data_fragmented(mk->term, "\033P0;1q#1;2;100;0;0#1~\033\\");
    IEQUAL(mk->term->images != NULL, true);
    size_t bytes = mk->term->image_bytes;
    query(mk, "Co", "256"); IEQUAL(mk->term->image_bytes, bytes);
    conf_set_bool(mk->conf, CONF_true_colour, false);
    conf_set_bool(mk->conf, CONF_xterm_256_colour, false);
    term_reconfig(mk->term, mk->conf);
    query(mk, "RGB", "-1"); query(mk, "Co", "16");
    conf_set_bool(mk->conf, CONF_ansi_colour, false); term_reconfig(mk->term, mk->conf);
    query(mk, "Co", "2");
}

static void test_renditions(Mock *mk)
{
    conf_set_bool(mk->conf, CONF_true_colour, true);
    conf_set_bool(mk->conf, CONF_ansi_colour, true);
    conf_set_bool(mk->conf, CONF_xterm_256_colour, true);
    term_reconfig(mk->term, mk->conf);
    reset(mk);
    term_data_fragmented(mk->term, "\033[3;4:3;9;53;38:2::11:22:33;58:5:6m\033[3;7H");
    unsigned long attr = mk->term->curr_attr;
    truecolour colour = mk->term->curr_truecolour;
    static const struct { const char *name, *value; } cases[] = {
        {"smul", "\033[4m"}, {"us", "\033[4m"},
        {"rmul", "\033[24m"}, {"ue", "\033[24m"},
        {"sitm", "\033[3m"}, {"ZH", "\033[3m"},
        {"ritm", "\033[23m"}, {"ZR", "\033[23m"},
        {"smxx", "\033[9m"}, {"rmxx", "\033[29m"},
        {"Smol", "\033[53m"}, {"Rmol", "\033[55m"},
    };
    for (size_t i = 0; i < lenof(cases); i++) {
        query(mk, cases[i].name, cases[i].value);
        IEQUAL(mk->term->curr_attr, attr);
        IEQUAL(truecolour_equal(mk->term->curr_truecolour, colour), true);
        IEQUAL(mk->term->curs.x, 6); IEQUAL(mk->term->curs.y, 2);
    }
    /* Extended names are case sensitive; unsupported parameter programs do
     * not acquire a misleading positive response from the new whitelist. */
    static const char *unknown[] = {"smol", "rmol", "SMOL", "Smulx", "Setulc", "Su"};
    for (size_t i = 0; i < lenof(unknown); i++) {
        strbuf *input = strbuf_new();
        put_dataz(input, "\033P+q"); hex(input, unknown[i]); put_dataz(input, "\033\\");
        term_data_fragmented(mk->term, input->s); response(mk, "\033P0+r\033\\");
        strbuf_free(input);
    }
    term_data_fragmented(mk->term, "\033P+q536D6F6C;526D6F6C;436f\033\\");
    response(mk, "\033P1+r536D6F6C=1b5b35336d;526D6F6C=1b5b35356d;436f=323536\033\\");
    term_data_fragmented(mk->term, "\033P+q536d6f6c;736d6f6c;526d6f6c\033\\");
    response(mk, "\033P1+r536d6f6c=1b5b35336d;\033\\");
    conf_set_bool(mk->conf, CONF_true_colour, false);
    conf_set_bool(mk->conf, CONF_ansi_colour, false);
    term_reconfig(mk->term, mk->conf);
    for (size_t i = 0; i < lenof(cases); i++) query(mk, cases[i].name, cases[i].value);
}

static void test_keyboard(Mock *mk)
{
    reset(mk);
    IEQUAL(mk->term->funky_type, FUNKY_XTERM_216);
    IEQUAL(mk->term->sharrow_type, SHARROW_BITMAP);
    static const struct { const char *name, *value; } basic[] = {
        {"kcuu1", "\033[A"}, {"kd", "\033[B"}, {"kr", "\033[C"}, {"kl", "\033[D"},
        {"kh", "\033[H"}, {"kend", "\033[F"}, {"kich1", "\033[2~"}, {"kdch1", "\033[3~"},
        {"kpp", "\033[5~"}, {"knp", "\033[6~"}, {"kfnd", "\033[1~"}, {"kslt", "\033[4~"},
        {"khlp", "\033[28~"}, {"kcbt", "\033[Z"}, {"kbs", "\177"}, {"kent", "\r"},
    };
    for (size_t i = 0; i < lenof(basic); i++) query(mk, basic[i].name, basic[i].value);
    /* Independent xterm DEC function-key table, including hardware F13..24. */
    static const char *functions[] = {"\033OP", "\033OQ", "\033OR", "\033OS",
        "\033[15~", "\033[17~", "\033[18~", "\033[19~", "\033[20~", "\033[21~",
        "\033[23~", "\033[24~", "\033[25~", "\033[26~", "\033[28~", "\033[29~",
        "\033[31~", "\033[32~", "\033[33~", "\033[34~"};
    for (int i = 1; i <= 63; i++) {
        char name[12], expected[20], encoded[64]; bool consumed = false;
        if (i <= 20) strcpy(expected, functions[i-1]);
        else snprintf(expected, sizeof(expected), "\033[%d~", 21+i);
        snprintf(name, sizeof(name), "kf%d", i); query(mk, name, expected);
        if (i < 10) snprintf(name, sizeof(name), "k%d", i);
        else if (i == 10) strcpy(name, "k;");
        else snprintf(name, sizeof(name), "F%c", i < 20 ? '0'+i-10 : i < 46 ? 'A'+i-20 : 'a'+i-46);
        query(mk, name, expected);
        int len = format_function_key(encoded, mk->term, i, false, false, false, &consumed);
        encoded[len] = '\0'; SEQUAL(encoded, expected);
    }
    for (int app = 0; app <= 1; app++) {
        term_data_fragmented(mk->term, app ? "\033[?1h" : "\033[?1l");
        query(mk, "ku", app ? "\033OA" : "\033[A");
        query(mk, "khome", app ? "\033OH" : "\033[H");
        query(mk, "kend", app ? "\033OF" : "\033[F");
        static const struct { const char *name; char final; } nav[] = {
            {"kUP", 'A'}, {"kDN", 'B'}, {"kRIT", 'C'}, {"kLFT", 'D'}, {"kHOM", 'H'}, {"kEND", 'F'}};
        for (unsigned mod = 1; mod <= 7; mod++) {
            for (size_t j = 0; j < lenof(nav); j++) {
                char name[20], expected[20], encoded[64]; bool consumed = false;
                snprintf(name, sizeof(name), mod == 1 ? "%s" : "%s%u", nav[j].name, mod+1);
                snprintf(expected, sizeof(expected), "\033[1;%u%c", mod+1, nav[j].final);
                query(mk, name, expected);
                int len = format_arrow_key(encoded, mk->term, nav[j].final, mod&1, mod&4, mod&2, &consumed);
                encoded[len] = '\0'; SEQUAL(encoded, expected); IEQUAL(consumed, !!(mod&2));
            }
            static const struct { const char *name; int code; SmallKeypadKey key; } edit[] = {
                {"kIC", 2, SKK_INSERT}, {"kDC", 3, SKK_DELETE}, {"kPRV", 5, SKK_PGUP}, {"kNXT", 6, SKK_PGDN}};
            for (size_t j = 0; j < lenof(edit); j++) {
                char name[20], expected[20], encoded[64]; bool consumed = false;
                snprintf(name, sizeof(name), mod == 1 ? "%s" : "%s%u", edit[j].name, mod+1);
                snprintf(expected, sizeof(expected), "\033[%d;%u~", edit[j].code, mod+1);
                query(mk, name, expected);
                int len = format_small_keypad_key(encoded, mk->term, edit[j].key, mod&1, mod&4, mod&2, &consumed);
                encoded[len] = '\0'; SEQUAL(encoded, expected);
            }
            for (int fn = 1; fn <= 5; fn++) {
                char expected[20], encoded[64]; bool consumed = false;
                if (fn <= 4) snprintf(expected, sizeof(expected), "\033[1;%u%c", mod+1, 'P'+fn-1);
                else snprintf(expected, sizeof(expected), "\033[15;%u~", mod+1);
                int len = format_function_key(encoded, mk->term, fn, mod&1, mod&4, mod&2, &consumed);
                encoded[len] = '\0'; SEQUAL(encoded, expected); IEQUAL(consumed, !!(mod&2));
            }
        }
    }
    term_data_fragmented(mk->term, "\033=");
    query(mk, "kent", "\033OM"); query(mk, "kp1", "\033Oq"); query(mk, "ka1", "\033Ow");
    query(mk, "kpDIV", "\033Oo"); query(mk, "kpMUL", "\033Oj"); query(mk, "kpSUB", "\033Om");
    query(mk, "kpCMA", "\033Ol"); query(mk, "kpADD3", NULL);
    term_data_fragmented(mk->term, "\033>\033[20h"); query(mk, "kent", "\r\n");
    conf_set_bool(mk->conf, CONF_bksp_is_delete, false); term_reconfig(mk->term, mk->conf);
    query(mk, "kb", "\010");
    conf_set_bool(mk->conf, CONF_no_applic_c, true); term_reconfig(mk->term, mk->conf);
    query(mk, "ku", "\033[A");
    /* Saved legacy profiles still select legacy encoders. */
    conf_set_int(mk->conf, CONF_funky_type, FUNKY_TILDE);
    conf_set_int(mk->conf, CONF_sharrow_type, SHARROW_APPLICATION);
    term_reconfig(mk->term, mk->conf);
    query(mk, "kf1", "\033[11~"); query(mk, "kf21", NULL); query(mk, "kh", "\033[1~");
    query(mk, "kIC5", NULL); query(mk, "kUP3", "\033\033[A");
    char encoded[64]; bool consumed = false;
    IEQUAL(format_function_key(encoded, mk->term, 0, false, false, false, &consumed), 0);
    IEQUAL(format_function_key(encoded, mk->term, 64, false, false, false, &consumed), 0);
}

int main(void)
{
    Mock *mk = mock_new();
    mk->term = term_init(mk->conf, mk->ucsdata, &mk->tw);
    mk->ldisc = ldisc_create(mk->conf, mk->term, &mk->backend, &mk->seat);
    test_queries_and_bounds(mk);
    test_renditions(mk);
    test_keyboard(mk);
    bool failed = mk->any_test_failed;
    mock_free(mk);
    puts(failed ? "Capability/keyboard suite FAILED" : "Capability/keyboard suite passed");
    return failed ? 1 : 0;
}
