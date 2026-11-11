#include "putty.h"
#include "terminal.h"

void modalfatalbox(const char *p, ...)
{
    va_list ap;
    fprintf(stderr, "FATAL ERROR: ");
    va_start(ap, p);
    vfprintf(stderr, p, ap);
    va_end(ap);
    fputc('\n', stderr);
    exit(1);
}

const char *const appname = "test_terminal";

char *platform_default_s(const char *name)
{ return NULL; }
bool platform_default_b(const char *name, bool def)
{ return def; }
int platform_default_i(const char *name, int def)
{ return def; }
FontSpec *platform_default_fontspec(const char *name)
{ return fontspec_new_default(); }
Filename *platform_default_filename(const char *name)
{ return filename_from_str(""); }

const struct BackendVtable *const backends[] = { NULL };

typedef struct Mock {
    Terminal *term;
    Conf *conf;
    struct unicode_data ucsdata[1];
    strbuf *title;
    strbuf *to_backend;
    wchar_t *clipboard_text;
    size_t clipboard_len;
    unsigned clipboard_writes;
    Ldisc *ldisc;

    strbuf *context;

    bool any_test_failed;

    TermWin tw;
    Seat seat;
    Backend backend;
} Mock;

static bool mock_setup_draw_ctx(TermWin *win) { return false; }
static void mock_draw_text(TermWin *win, int x, int y, wchar_t *text, int len,
                           unsigned long attrs, int lattrs, truecolour tc) {}
static void mock_draw_cursor(TermWin *win, int x, int y, wchar_t *text,
                             int len, unsigned long attrs, int lattrs,
                             truecolour tc) {}
static void mock_set_raw_mouse_mode(TermWin *win, bool enable) {}
static void mock_set_raw_mouse_mode_pointer(TermWin *win, bool enable) {}
static void mock_palette_set(TermWin *win, unsigned start, unsigned ncolours,
                             const rgb *colours) {}
static void mock_palette_get_overrides(TermWin *tw, Terminal *term) {}
static void mock_set_title(TermWin *win, const char *title, int codepage);
static void mock_set_icon_title(TermWin *win, const char *title, int cp) {}
static void mock_set_scrollbar(TermWin *win, int total, int start, int page) {}
static void mock_unthrottle(TermWin *win, size_t bufsize) {}

static void mock_clip_write(TermWin *win, int clipboard, wchar_t *text,
                            int *attrs, truecolour *colours, int len,
                            bool must_deselect)
{
    Mock *mk = container_of(win, Mock, tw);
    sfree(mk->clipboard_text);
    mk->clipboard_text = snewn(len + 1, wchar_t);
    if (len)
        memcpy(mk->clipboard_text, text, len * sizeof(wchar_t));
    mk->clipboard_text[len] = 0;
    mk->clipboard_len = len;
    /* The Windows clipboard representation includes the terminating NUL. */
    if (len && mk->clipboard_text[len - 1] == 0)
        mk->clipboard_len--;
    mk->clipboard_writes++;
}

static void mock_send(Backend *be, const char *buf, size_t len)
{
    Mock *mk = container_of(be, Mock, backend);
    put_data(mk->to_backend, buf, len);
}
static bool mock_sendok(Backend *be) { return true; }
static bool mock_ldisc_option_state(Backend *be, int option) { return false; }
static void mock_provide_ldisc(Backend *be, Ldisc *ldisc) {}

static const SeatVtable mock_seat_vt = {
    .echoedit_update = nullseat_echoedit_update,
};
static const BackendVtable mock_backend_vt = {
    .send = mock_send,
    .sendok = mock_sendok,
    .ldisc_option_state = mock_ldisc_option_state,
    .provide_ldisc = mock_provide_ldisc,
    .id = "mock",
};

static const TermWinVtable mock_termwin_vt = {
    .setup_draw_ctx = mock_setup_draw_ctx,
    .draw_text = mock_draw_text,
    .draw_cursor = mock_draw_cursor,
    .set_title = mock_set_title,
    .set_icon_title = mock_set_icon_title,
    .set_raw_mouse_mode = mock_set_raw_mouse_mode,
    .set_raw_mouse_mode_pointer = mock_set_raw_mouse_mode_pointer,
    .palette_set = mock_palette_set,
    .palette_get_overrides = mock_palette_get_overrides,
    .set_scrollbar = mock_set_scrollbar,
    .clip_write = mock_clip_write,
    .unthrottle = mock_unthrottle,
};

static Mock *mock_new(void)
{
    Mock *mk = snew(Mock);
    memset(mk, 0, sizeof(*mk));

    mk->conf = conf_new();
    do_defaults(NULL, mk->conf);
    /* NemoTerm must allow Shift selection even if this legacy option is off. */
    conf_set_bool(mk->conf, CONF_mouse_override, false);

    init_ucs_generic(mk->conf, mk->ucsdata);
    mk->ucsdata->line_codepage = CP_ISO8859_1;

    mk->context = strbuf_new();
    mk->title = strbuf_new();
    mk->to_backend = strbuf_new();

    mk->tw.vt = &mock_termwin_vt;
    mk->seat.vt = &mock_seat_vt;
    mk->backend.vt = &mock_backend_vt;

    return mk;
}

static void mock_free(Mock *mk)
{
    ldisc_free(mk->ldisc);
    strbuf_free(mk->context);
    conf_free(mk->conf);
    term_free(mk->term);
    strbuf_free(mk->title);
    strbuf_free(mk->to_backend);
    sfree(mk->clipboard_text);
    sfree(mk);
}

static void mock_set_title(TermWin *win, const char *title, int codepage)
{
    Mock *mk = container_of(win, Mock, tw);
    strbuf_clear(mk->title);
    put_dataz(mk->title, title);
}

static void reset(Mock *mk)
{
    term_pwron(mk->term, true);
    term_size(mk->term, 24, 80, 0);
    term_set_trust_status(mk->term, false);
    strbuf_clear(mk->context);
    strbuf_clear(mk->title);
    strbuf_clear(mk->to_backend);
    mk->clipboard_writes = 0;
}

static void test_context(Mock *mk, const char *fmt, ...)
{
    strbuf_clear(mk->context);
    va_list ap;
    va_start(ap, fmt);
    put_fmtv(mk->context, fmt, ap);
    va_end(ap);
}

static void report_fail(Mock *mk, const char *file, int line,
                        const char *fmt, ...)
{
    printf("%s:%d", file, line);
    if (mk->context->len)
        printf(" (%s)", mk->context->s);
    printf(": ");
    va_list ap;
    va_start(ap, fmt);
    vprintf(fmt, ap);
    va_end(ap);
    printf("\n");
    mk->any_test_failed = true;
}

static inline void check_iequal(Mock *mk, const char *file, int line,
                                long long lhs, long long rhs)
{
    if (lhs != rhs)
        report_fail(mk, file, line, "%lld != %lld / %#llx != %#llx",
                    lhs, rhs, lhs, rhs);
}

static inline void check_sequal(Mock *mk, const char *file, int line,
                                const char *lhs, const char *rhs)
{
    if (strcmp(lhs, rhs) != 0)
        report_fail(mk, file, line, "'%s' != '%s'", lhs, rhs);
}

#define IEQUAL(lhs, rhs) check_iequal(mk, __FILE__, __LINE__, lhs, rhs)
#define SEQUAL(lhs, rhs) check_sequal(mk, __FILE__, __LINE__, lhs, rhs)

static inline void term_datapl(Terminal *term, ptrlen pl)
{
    term_data(term, pl.ptr, pl.len);
}

/* Model arbitrary ConPTY read boundaries, including inside UTF-8 and CSI. */
static void term_data_fragmented(Terminal *term, const char *data)
{
    while (*data)
        term_data(term, data++, 1);
}

static void check_clipboard(Mock *mk, const wchar_t *expected)
{
    IEQUAL(mk->clipboard_writes, 1);
    IEQUAL(mk->clipboard_len, wcslen(expected));
    if (!mk->clipboard_text || wcscmp(mk->clipboard_text, expected))
        report_fail(mk, __FILE__, __LINE__, "clipboard text differs");
}

static struct termchar get_termchar(Terminal *term, int x, int y)
{
    termline *tl = term_get_line(term, y);
    termchar tc;
    if (0 <= x && x < tl->cols)
        tc = tl->chars[x];
    else
        tc = term->erase_char;
    term_release_line(tl);
    return tc;
}

static unsigned short get_lineattr(Terminal *term, int y)
{
    termline *tl = term_get_line(term, y);
    unsigned short lattr = tl->lattr;
    term_release_line(tl);
    return lattr;
}

static void test_hello_world(Mock *mk)
{
    /* A trivial test just to kick off this test framework */
    mk->ucsdata->line_codepage = CP_ISO8859_1;

    reset(mk);
    term_datapl(mk->term, PTRLEN_LITERAL("hello, world"));
    IEQUAL(mk->term->curs.x, 12);
    IEQUAL(mk->term->curs.y, 0);
    IEQUAL(get_termchar(mk->term, 0, 0).chr, CSET_ASCII | 'h');
    IEQUAL(get_termchar(mk->term, 1, 0).chr, CSET_ASCII | 'e');
    IEQUAL(get_termchar(mk->term, 2, 0).chr, CSET_ASCII | 'l');
    IEQUAL(get_termchar(mk->term, 3, 0).chr, CSET_ASCII | 'l');
    IEQUAL(get_termchar(mk->term, 4, 0).chr, CSET_ASCII | 'o');
    IEQUAL(get_termchar(mk->term, 5, 0).chr, CSET_ASCII | ',');
    IEQUAL(get_termchar(mk->term, 6, 0).chr, CSET_ASCII | ' ');
    IEQUAL(get_termchar(mk->term, 7, 0).chr, CSET_ASCII | 'w');
    IEQUAL(get_termchar(mk->term, 8, 0).chr, CSET_ASCII | 'o');
    IEQUAL(get_termchar(mk->term, 9, 0).chr, CSET_ASCII | 'r');
    IEQUAL(get_termchar(mk->term, 10, 0).chr, CSET_ASCII | 'l');
    IEQUAL(get_termchar(mk->term, 11, 0).chr, CSET_ASCII | 'd');
}

static void test_wrap(Mock *mk)
{
    /* Test behaviour when printing characters wrap to the next line */
    mk->ucsdata->line_codepage = CP_UTF8;

    /* Print 'abc' without enough space for the c, in wrapping mode */
    reset(mk);
    mk->term->curs.x = 78;
    mk->term->curs.y = 0;
    mk->term->wrap = true;
    /* The 'a' prints without anything unusual happening */
    term_datapl(mk->term, PTRLEN_LITERAL("a"));
    IEQUAL(mk->term->curs.x, 79);
    IEQUAL(mk->term->curs.y, 0);
    IEQUAL(mk->term->wrapnext, 0);
    IEQUAL(get_termchar(mk->term, 78, 0).chr, CSET_ASCII | 'a');
    /* The 'b' prints, leaving the cursor where it is with wrapnext set */
    term_datapl(mk->term, PTRLEN_LITERAL("b"));
    IEQUAL(mk->term->curs.x, 79);
    IEQUAL(mk->term->curs.y, 0);
    IEQUAL(mk->term->wrapnext, 1);
    IEQUAL(get_lineattr(mk->term, 0), 0);
    IEQUAL(get_termchar(mk->term, 79, 0).chr, CSET_ASCII | 'b');
    /* And now the 'c' causes a deferred wrap and goes to the next line */
    term_datapl(mk->term, PTRLEN_LITERAL("c"));
    IEQUAL(mk->term->curs.x, 1);
    IEQUAL(mk->term->curs.y, 1);
    IEQUAL(mk->term->wrapnext, 0);
    IEQUAL(get_lineattr(mk->term, 0), LATTR_WRAPPED);
    IEQUAL(get_termchar(mk->term, 79, 0).chr, CSET_ASCII | 'b');
    IEQUAL(get_termchar(mk->term, 0, 1).chr, CSET_ASCII | 'c');
    /* If we backspace once, the cursor moves back on to the c */
    term_datapl(mk->term, PTRLEN_LITERAL("\b"));
    IEQUAL(mk->term->curs.x, 0);
    IEQUAL(mk->term->curs.y, 1);
    IEQUAL(mk->term->wrapnext, 0);
    /* Now backspace again, and the cursor returns to the b */
    term_datapl(mk->term, PTRLEN_LITERAL("\b"));
    IEQUAL(mk->term->curs.x, 79);
    IEQUAL(mk->term->curs.y, 0);
    IEQUAL(mk->term->wrapnext, 0);

    /* Now try it with a double-width character in place of ab */
    mk->term->curs.x = 78;
    mk->term->curs.y = 0;
    mk->term->wrap = true;
    /* The DW character goes directly to the wrapnext state */
    term_datapl(mk->term, PTRLEN_LITERAL("\xEA\xB0\x80"));
    IEQUAL(mk->term->curs.x, 79);
    IEQUAL(mk->term->curs.y, 0);
    IEQUAL(mk->term->wrapnext, 1);
    IEQUAL(get_termchar(mk->term, 78, 0).chr, 0xAC00);
    IEQUAL(get_termchar(mk->term, 79, 0).chr, UCSWIDE);
    /* And the 'c' causes a deferred wrap as before */
    term_datapl(mk->term, PTRLEN_LITERAL("c"));
    IEQUAL(mk->term->curs.x, 1);
    IEQUAL(mk->term->curs.y, 1);
    IEQUAL(mk->term->wrapnext, 0);
    IEQUAL(get_lineattr(mk->term, 0), LATTR_WRAPPED);
    IEQUAL(get_termchar(mk->term, 78, 0).chr, 0xAC00);
    IEQUAL(get_termchar(mk->term, 79, 0).chr, UCSWIDE);
    IEQUAL(get_termchar(mk->term, 0, 1).chr, CSET_ASCII | 'c');
    /* If we backspace once, the cursor moves back on to the c */
    term_datapl(mk->term, PTRLEN_LITERAL("\b"));
    IEQUAL(mk->term->curs.x, 0);
    IEQUAL(mk->term->curs.y, 1);
    IEQUAL(mk->term->wrapnext, 0);
    /* Now backspace again, and the cursor goes to the RHS of the DW char */
    term_datapl(mk->term, PTRLEN_LITERAL("\b"));
    IEQUAL(mk->term->curs.x, 79);
    IEQUAL(mk->term->curs.y, 0);
    IEQUAL(mk->term->wrapnext, 0);

    /* Now put the DW character in place of bc */
    reset(mk);
    mk->term->curs.x = 78;
    mk->term->curs.y = 0;
    mk->term->wrap = true;
    /* The 'a' prints as before */
    term_datapl(mk->term, PTRLEN_LITERAL("a"));
    IEQUAL(mk->term->curs.x, 79);
    IEQUAL(mk->term->curs.y, 0);
    IEQUAL(mk->term->wrapnext, 0);
    IEQUAL(get_termchar(mk->term, 78, 0).chr, CSET_ASCII | 'a');
    /* The DW character wraps, setting LATTR_WRAPPED2 */
    term_datapl(mk->term, PTRLEN_LITERAL("\xEA\xB0\x80"));
    IEQUAL(mk->term->curs.x, 2);
    IEQUAL(mk->term->curs.y, 1);
    IEQUAL(mk->term->wrapnext, 0);
    IEQUAL(get_lineattr(mk->term, 0), LATTR_WRAPPED | LATTR_WRAPPED2);
    IEQUAL(get_termchar(mk->term, 78, 0).chr, CSET_ASCII | 'a');
    IEQUAL(get_termchar(mk->term, 79, 0).chr, CSET_ASCII | ' ');
    IEQUAL(get_termchar(mk->term, 0, 1).chr, 0xAC00);
    IEQUAL(get_termchar(mk->term, 1, 1).chr, UCSWIDE);
    /* If we backspace once, cursor moves to the RHS of the DW char */
    term_datapl(mk->term, PTRLEN_LITERAL("\b"));
    IEQUAL(mk->term->curs.x, 1);
    IEQUAL(mk->term->curs.y, 1);
    IEQUAL(mk->term->wrapnext, 0);
    /* Backspace again, and cursor moves from RHS to LHS of that char */
    term_datapl(mk->term, PTRLEN_LITERAL("\b"));
    IEQUAL(mk->term->curs.x, 0);
    IEQUAL(mk->term->curs.y, 1);
    IEQUAL(mk->term->wrapnext, 0);
    /* Now backspace again, and the cursor skips the empty column so
     * that it can return to the previous logical character, to wit, the a */
    term_datapl(mk->term, PTRLEN_LITERAL("\b"));
    IEQUAL(mk->term->curs.x, 78);
    IEQUAL(mk->term->curs.y, 0);
    IEQUAL(mk->term->wrapnext, 0);

    /* Print 'ab' up to the rightmost column, and then backspace */
    reset(mk);
    mk->term->curs.x = 78;
    mk->term->curs.y = 0;
    mk->term->wrap = true;
    /* As before, the 'ab' put us in the rightmost column with wrapnext set */
    term_datapl(mk->term, PTRLEN_LITERAL("ab"));
    IEQUAL(mk->term->curs.x, 79);
    IEQUAL(mk->term->curs.y, 0);
    IEQUAL(mk->term->wrapnext, 1);
    IEQUAL(get_lineattr(mk->term, 0), 0);
    IEQUAL(get_termchar(mk->term, 78, 0).chr, CSET_ASCII | 'a');
    IEQUAL(get_termchar(mk->term, 79, 0).chr, CSET_ASCII | 'b');
    /* Backspacing just clears the wrapnext flag, so we're logically
     * back on the b again */
    term_datapl(mk->term, PTRLEN_LITERAL("\b"));
    IEQUAL(mk->term->curs.x, 79);
    IEQUAL(mk->term->curs.y, 0);
    IEQUAL(mk->term->wrapnext, 0);

    /* For completeness, the easy case: just print 'a' then backspace */
    reset(mk);
    mk->term->curs.x = 78;
    mk->term->curs.y = 0;
    mk->term->wrap = true;
    /* 'a' printed in column n-1 takes us to column n */
    term_datapl(mk->term, PTRLEN_LITERAL("a"));
    IEQUAL(mk->term->curs.x, 79);
    IEQUAL(mk->term->curs.y, 0);
    IEQUAL(mk->term->wrapnext, 0);
    IEQUAL(get_lineattr(mk->term, 0), 0);
    IEQUAL(get_termchar(mk->term, 78, 0).chr, CSET_ASCII | 'a');
    /* Backspacing moves us back a space on to the a */
    term_datapl(mk->term, PTRLEN_LITERAL("\b"));
    IEQUAL(mk->term->curs.x, 78);
    IEQUAL(mk->term->curs.y, 0);
    IEQUAL(mk->term->wrapnext, 0);

    /*
     * Now test the special cases that arise when the terminal is only
     * one column wide!
     */

    reset(mk);
    term_size(mk->term, 24, 1, 0);
    mk->term->curs.x = 0;
    mk->term->curs.y = 0;
    mk->term->wrap = true;
    /* Printing a single-width character takes us into wrapnext immediately */
    term_datapl(mk->term, PTRLEN_LITERAL("a"));
    IEQUAL(mk->term->curs.x, 0);
    IEQUAL(mk->term->curs.y, 0);
    IEQUAL(mk->term->wrapnext, 1);
    IEQUAL(get_lineattr(mk->term, 0), 0);
    IEQUAL(get_termchar(mk->term, 0, 0).chr, CSET_ASCII | 'a');
    /* Printing a second one wraps, and takes us _back_ to wrapnext */
    term_datapl(mk->term, PTRLEN_LITERAL("b"));
    IEQUAL(mk->term->curs.x, 0);
    IEQUAL(mk->term->curs.y, 1);
    IEQUAL(mk->term->wrapnext, 1);
    IEQUAL(get_lineattr(mk->term, 0), LATTR_WRAPPED);
    IEQUAL(get_termchar(mk->term, 0, 0).chr, CSET_ASCII | 'a');
    IEQUAL(get_termchar(mk->term, 0, 1).chr, CSET_ASCII | 'b');
    /* Backspacing once clears the wrapnext flag, putting us on the b */
    term_datapl(mk->term, PTRLEN_LITERAL("\b"));
    IEQUAL(mk->term->curs.x, 0);
    IEQUAL(mk->term->curs.y, 1);
    IEQUAL(mk->term->wrapnext, 0);
    /* Backspacing again returns to the previous line, putting us on the a */
    term_datapl(mk->term, PTRLEN_LITERAL("\b"));
    IEQUAL(mk->term->curs.x, 0);
    IEQUAL(mk->term->curs.y, 0);
    IEQUAL(mk->term->wrapnext, 0);

    /* And now try with a double-width character */
    reset(mk);
    term_size(mk->term, 24, 1, 0);
    mk->term->curs.x = 0;
    mk->term->curs.y = 0;
    mk->term->wrap = true;
    /* DW character won't fit at all, so it transforms into U+FFFD
     * REPLACEMENT CHARACTER and then behaves like a SW char */
    term_datapl(mk->term, PTRLEN_LITERAL("\xEA\xB0\x80"));
    IEQUAL(mk->term->curs.x, 0);
    IEQUAL(mk->term->curs.y, 0);
    IEQUAL(mk->term->wrapnext, 1);
    IEQUAL(get_lineattr(mk->term, 0), 0);
    IEQUAL(get_termchar(mk->term, 0, 0).chr, 0xFFFD);
}

static void test_nonwrap(Mock *mk)
{
    /* Test behaviour when printing characters hit end of line without wrap.
     * The wrapnext flag is never set in this mode. */
    mk->ucsdata->line_codepage = CP_UTF8;

    /* Print 'abc' without enough space for the c */
    reset(mk);
    mk->term->curs.x = 78;
    mk->term->curs.y = 0;
    mk->term->wrap = false;
    /* The 'a' prints without anything unusual happening */
    term_datapl(mk->term, PTRLEN_LITERAL("a"));
    IEQUAL(mk->term->curs.x, 79);
    IEQUAL(mk->term->curs.y, 0);
    IEQUAL(mk->term->wrapnext, 0);
    IEQUAL(get_termchar(mk->term, 78, 0).chr, CSET_ASCII | 'a');
    /* The 'b' prints, leaving the cursor where it is */
    term_datapl(mk->term, PTRLEN_LITERAL("b"));
    IEQUAL(mk->term->curs.x, 79);
    IEQUAL(mk->term->curs.y, 0);
    IEQUAL(mk->term->wrapnext, 0);
    IEQUAL(get_lineattr(mk->term, 0), 0);
    IEQUAL(get_termchar(mk->term, 79, 0).chr, CSET_ASCII | 'b');
    /* The 'c' overwrites the b */
    term_datapl(mk->term, PTRLEN_LITERAL("c"));
    IEQUAL(mk->term->curs.x, 79);
    IEQUAL(mk->term->curs.y, 0);
    IEQUAL(mk->term->wrapnext, 0);
    IEQUAL(get_lineattr(mk->term, 0), 0);
    IEQUAL(get_termchar(mk->term, 78, 0).chr, CSET_ASCII | 'a');
    IEQUAL(get_termchar(mk->term, 79, 0).chr, CSET_ASCII | 'c');
    /* Since wrapnext was never set, backspacing returns us to the a */
    term_datapl(mk->term, PTRLEN_LITERAL("\b"));
    IEQUAL(mk->term->curs.x, 78);
    IEQUAL(mk->term->curs.y, 0);
    IEQUAL(mk->term->wrapnext, 0);

    /* Now try it with a double-width character in place of ab */
    mk->term->curs.x = 78;
    mk->term->curs.y = 0;
    mk->term->wrap = false;
    /* The DW character occupies the rightmost two columns */
    term_datapl(mk->term, PTRLEN_LITERAL("\xEA\xB0\x80"));
    IEQUAL(mk->term->curs.x, 79);
    IEQUAL(mk->term->curs.y, 0);
    IEQUAL(mk->term->wrapnext, 0);
    IEQUAL(get_termchar(mk->term, 78, 0).chr, 0xAC00);
    IEQUAL(get_termchar(mk->term, 79, 0).chr, UCSWIDE);
    /* The 'c' must overprint the RHS of the DW char, clearing the LHS */
    term_datapl(mk->term, PTRLEN_LITERAL("c"));
    IEQUAL(mk->term->curs.x, 79);
    IEQUAL(mk->term->curs.y, 0);
    IEQUAL(mk->term->wrapnext, 0);
    IEQUAL(get_lineattr(mk->term, 0), 0);
    IEQUAL(get_termchar(mk->term, 78, 0).chr, CSET_ASCII | ' ');
    IEQUAL(get_termchar(mk->term, 79, 0).chr, CSET_ASCII | 'c');

    /* Now put the DW char in place of the bc */
    reset(mk);
    mk->term->curs.x = 78;
    mk->term->curs.y = 0;
    mk->term->wrap = false;
    /* The 'a' prints as before */
    term_datapl(mk->term, PTRLEN_LITERAL("a"));
    IEQUAL(mk->term->curs.x, 79);
    IEQUAL(mk->term->curs.y, 0);
    IEQUAL(mk->term->wrapnext, 0);
    IEQUAL(get_termchar(mk->term, 78, 0).chr, CSET_ASCII | 'a');
    /* The DW char won't fit, so turns into U+FFFD REPLACEMENT CHARACTER */
    term_datapl(mk->term, PTRLEN_LITERAL("\xEA\xB0\x80"));
    IEQUAL(mk->term->curs.x, 79);
    IEQUAL(mk->term->curs.y, 0);
    IEQUAL(mk->term->wrapnext, 0);
    IEQUAL(get_lineattr(mk->term, 0), 0);
    IEQUAL(get_termchar(mk->term, 78, 0).chr, CSET_ASCII | 'a');
    IEQUAL(get_termchar(mk->term, 79, 0).chr, 0xFFFD);

    /* Just for completeness, try both of those together */
    reset(mk);
    mk->term->curs.x = 78;
    mk->term->curs.y = 0;
    mk->term->wrap = false;
    /* First DW character occupies the rightmost columns */
    term_datapl(mk->term, PTRLEN_LITERAL("\xEA\xB0\x80"));
    IEQUAL(mk->term->curs.x, 79);
    IEQUAL(mk->term->curs.y, 0);
    IEQUAL(mk->term->wrapnext, 0);
    IEQUAL(get_termchar(mk->term, 78, 0).chr, 0xAC00);
    IEQUAL(get_termchar(mk->term, 79, 0).chr, UCSWIDE);
    /* Second DW char becomes U+FFFD, overwriting RHS of the first one */
    term_datapl(mk->term, PTRLEN_LITERAL("\xEA\xB0\x81"));
    IEQUAL(mk->term->curs.x, 79);
    IEQUAL(mk->term->curs.y, 0);
    IEQUAL(mk->term->wrapnext, 0);
    IEQUAL(get_lineattr(mk->term, 0), 0);
    IEQUAL(get_termchar(mk->term, 78, 0).chr, CSET_ASCII | ' ');
    IEQUAL(get_termchar(mk->term, 79, 0).chr, 0xFFFD);
}

static void test_wintitle(Mock *mk)
{
    reset(mk);
    term_datapl(mk->term, PTRLEN_LITERAL("\033]0;foo\033\\"));
    term_update(mk->term);
    SEQUAL(mk->title->s, "foo");
    term_datapl(mk->term, PTRLEN_LITERAL("\033]0;bar\007"));
    term_update(mk->term);
    SEQUAL(mk->title->s, "bar");

    /* Regression test for a bug in which a DCS string was
     * accidentally treated as a title-setting OSC 0. We expect that
     * this is not a window-title setting sequence, and leaves the
     * title unchanged. */
    term_datapl(mk->term, PTRLEN_LITERAL("\033Pzz\033\\"));
    term_update(mk->term);
    SEQUAL(mk->title->s, "bar");

    /* A title and its ST terminator may span separate ConPTY reads. */
    term_data_fragmented(mk->term, "\033]2;agent \xe4\xb8\xad\033");
    term_data_fragmented(mk->term, "\\");
    term_update(mk->term);
    SEQUAL(mk->title->s, "agent \xe4\xb8\xad");
}

static void test_shift_selection(Mock *mk)
{
    const int modes[] = {1000, 1002, 1003};
    const int clipboard = CLIP_LOCAL + 1;
    mk->ucsdata->line_codepage = CP_UTF8;

    for (size_t mode = 0; mode < lenof(modes); mode++) {
        for (int sgr = 0; sgr < 2; sgr++) {
            for (int alternate = 0; alternate < 2; alternate++) {
                reset(mk);
                test_context(mk, "mouse %d, SGR %d, alternate screen %d",
                             modes[mode], sgr, alternate);
                term_data_fragmented(mk->term, "MAIN");
                if (alternate)
                    term_data_fragmented(mk->term, "\033[?1049h");
                term_data_fragmented(mk->term, "\033[H\033[2JOLD\r");
                /* Overwrite old output: copy must reflect current cells,
                 * including the wide character and combining acute mark. */
                term_data_fragmented(mk->term,
                                     "A\xe4\xb8\xad" "e\xcc\x81Z");
                IEQUAL(get_termchar(mk->term, 1, 0).chr, 0x4e2d);
                IEQUAL(get_termchar(mk->term, 2, 0).chr, UCSWIDE);
                char *enable = dupprintf("\033[?%dh\033[?1006%c",
                                         modes[mode], sgr ? 'h' : 'l');
                term_data_fragmented(mk->term, enable);
                sfree(enable);

                /* Unmodified mouse input belongs to the application. */
                term_mouse(mk->term, MBT_LEFT, MBT_SELECT,
                           MA_CLICK, 0, 0, false, false, false);
                term_mouse(mk->term, MBT_LEFT, MBT_SELECT,
                           MA_DRAG, 4, 0, false, false, false);
                term_mouse(mk->term, MBT_LEFT, MBT_SELECT,
                           MA_RELEASE, 4, 0, false, false, false);
                IEQUAL(mk->term->selstate, NO_SELECTION);
                IEQUAL(mk->clipboard_writes, 0);
                if (sgr) {
                    SEQUAL(mk->to_backend->s, mode == 0 ?
                           "\033[<0;1;1M\033[<0;5;1m" :
                           "\033[<0;1;1M\033[<32;5;1M\033[<0;5;1m");
                } else {
                    SEQUAL(mk->to_backend->s, mode == 0 ?
                           "\033[M !!\033[M#%!" :
                           "\033[M !!\033[M@%!\033[M#%!");
                }

                strbuf_clear(mk->to_backend);
                term_mouse(mk->term, MBT_NOTHING, MBT_NOTHING,
                           MA_MOVE, 5, 0, false, false, false);
                if (modes[mode] == 1003)
                    SEQUAL(mk->to_backend->s, sgr ?
                           "\033[<35;6;1M" : "\033[MC&!");
                else
                    IEQUAL(mk->to_backend->len, 0);
                strbuf_clear(mk->to_backend);
                term_mouse(mk->term, MBT_NOTHING, MBT_NOTHING,
                           MA_MOVE, 6, 0, true, false, false);
                IEQUAL(mk->to_backend->len, 0);

                /* Release Shift before releasing the button: a selection
                 * gesture must still finish locally, without a stray report. */
                term_mouse(mk->term, MBT_LEFT, MBT_SELECT,
                           MA_CLICK, 0, 0, true, false, false);
                term_mouse(mk->term, MBT_LEFT, MBT_SELECT,
                           MA_DRAG, 4, 0, true, false, false);
                term_mouse(mk->term, MBT_LEFT, MBT_SELECT,
                           MA_RELEASE, 4, 0, false, false, false);
                IEQUAL(mk->term->selstate, SELECTED);
                IEQUAL(mk->to_backend->len, 0);
                IEQUAL(mk->clipboard_writes, 0);
                term_request_copy(mk->term, &clipboard, 1);
                check_clipboard(mk, L"A\x4e2d" L"e\x0301Z");

                if (alternate)
                    term_data_fragmented(mk->term, "\033[?1049l");
            }
        }
    }
}

static void test_colour_and_alternate_screen(Mock *mk)
{
    reset(mk);
    term_data_fragmented(mk->term,
        "\033[38;2;17;34;51;48;2;68;85;102mT\033[0mD"
        "\033[38;5;196;48;5;22mI");
    termchar tc = get_termchar(mk->term, 0, 0);
    IEQUAL(tc.truecolour.fg.enabled, true);
    IEQUAL(tc.truecolour.fg.r, 17);
    IEQUAL(tc.truecolour.fg.g, 34);
    IEQUAL(tc.truecolour.fg.b, 51);
    IEQUAL(tc.truecolour.bg.enabled, true);
    IEQUAL(tc.truecolour.bg.r, 68);
    IEQUAL(tc.truecolour.bg.g, 85);
    IEQUAL(tc.truecolour.bg.b, 102);
    tc = get_termchar(mk->term, 1, 0);
    IEQUAL(tc.truecolour.fg.enabled, false);
    IEQUAL(tc.truecolour.bg.enabled, false);
    IEQUAL(tc.attr & (ATTR_FGMASK | ATTR_BGMASK), ATTR_DEFFG | ATTR_DEFBG);
    tc = get_termchar(mk->term, 2, 0);
    IEQUAL((tc.attr & ATTR_FGMASK) >> ATTR_FGSHIFT, 196);
    IEQUAL((tc.attr & ATTR_BGMASK) >> ATTR_BGSHIFT, 22);

    /* Alternate screen output must not overwrite the main screen, and
     * leaving 1049 restores the saved cursor as well as its text. */
    term_data_fragmented(mk->term, "\033[?1049h\033[H\033[0mALT");
    IEQUAL(get_termchar(mk->term, 0, 0).chr, CSET_ASCII | 'A');
    term_data_fragmented(mk->term, "\033[?1049l");
    IEQUAL(get_termchar(mk->term, 0, 0).chr, CSET_ASCII | 'T');
    IEQUAL(get_termchar(mk->term, 1, 0).chr, CSET_ASCII | 'D');
    IEQUAL(get_termchar(mk->term, 2, 0).chr, CSET_ASCII | 'I');
    IEQUAL(mk->term->curs.x, 3);
    IEQUAL(mk->term->curs.y, 0);
    tc = get_termchar(mk->term, 0, 0);
    IEQUAL(tc.truecolour.fg.r, 17);
    IEQUAL(tc.truecolour.bg.b, 102);
}

static void test_bracketed_paste(Mock *mk)
{
    static const wchar_t text[] = L"agent \x4e2d";
    mk->ucsdata->line_codepage = CP_UTF8;
    reset(mk);
    term_data_fragmented(mk->term, "\033[?2004h");
    term_do_paste(mk->term, text, lenof(text) - 1);
    SEQUAL(mk->to_backend->s,
           "\033[200~agent \xe4\xb8\xad\033[201~");

    strbuf_clear(mk->to_backend);
    term_data_fragmented(mk->term, "\033[?2004l");
    term_do_paste(mk->term, text, lenof(text) - 1);
    SEQUAL(mk->to_backend->s, "agent \xe4\xb8\xad");

    /* An empty paste must neither send data nor open a bracketed paste. */
    strbuf_clear(mk->to_backend);
    term_data_fragmented(mk->term, "\033[?2004h");
    term_do_paste(mk->term, L"", 0);
    IEQUAL(mk->to_backend->len, 0);
}

int main(void)
{
    Mock *mk = mock_new();
    mk->term = term_init(mk->conf, mk->ucsdata, &mk->tw);
    mk->ldisc = ldisc_create(mk->conf, mk->term, &mk->backend, &mk->seat);

    test_hello_world(mk);
    test_wrap(mk);
    test_nonwrap(mk);
    test_wintitle(mk);
    test_shift_selection(mk);
    test_colour_and_alternate_screen(mk);
    test_bracketed_paste(mk);

    bool failed = mk->any_test_failed;
    mock_free(mk);

    if (failed) {
        printf("Test suite FAILED!\n");
        return 1;
    } else {
        printf("Test suite passed\n");
        return 0;
    }
}
