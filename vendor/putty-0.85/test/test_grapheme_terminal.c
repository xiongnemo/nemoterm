/* SPDX-License-Identifier: MIT */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main

static void setup_cluster(Mock *mk, const char *name, int rows, int cols)
{
    reset(mk); test_context(mk, "%s", name);
    mk->ucsdata->line_codepage = CP_UTF8;
    term_size(mk->term, rows, cols, 100);
    term_data_fragmented(mk->term, "\033[2J\033[H\033%G");
    term_data_fragmented(mk->term, "\033[?2027h");
}

static void output_scalars(Terminal *term, const uint32_t *cp, size_t n)
{
    strbuf *text = strbuf_new();
    for (size_t i=0;i<n;i++) put_utf8_char(text, cp[i]);
    term_data_fragmented(term, text->s);
    strbuf_free(text);
}

static void cluster_contents(Mock *mk, int x, int y, const uint32_t *cp, size_t n)
{
    termline *line = term_get_line(mk->term, y);
    termchar *ch = &line->chars[x];
    for (size_t i=0;i<n;i++) {
        unsigned long actual=ch->chr;
        if ((actual&CSET_MASK)==CSET_ASCII) actual &= 0xff;
        IEQUAL(actual, cp[i]);
        if (i+1<n) {
            IEQUAL(ch->cc_next!=0, true);
            if (!ch->cc_next) break;
            ch += ch->cc_next;
        }
    }
    IEQUAL(ch->cc_next, 0);
    term_release_line(line);
}

static void test_shapes(Mock *mk)
{
    const struct { const char *name; uint32_t text[9]; unsigned count,cells; } cases[]={
        {"accent",{'e',0x301},2,1}, {"skin tone",{0x1f44d,0x1f3fd},2,2},
        {"profession",{0x1f469,0x200d,0x1f4bb},3,2},
        {"family",{0x1f468,0x200d,0x1f469,0x200d,0x1f467,0x200d,0x1f466},7,2},
        {"flag",{0x1f1e6,0x1f1fa},2,2}, {"keycap",{'1',0xfe0f,0x20e3},3,2},
        {"emoji heart",{0x2764,0xfe0f},2,2}, {"text heart",{0x2764,0xfe0e},2,1},
        {"jamo",{0x1100,0x1161,0x11a8},3,2},
        {"indic",{0x915,0x94d,0x937},3,1}, {"prepend",{0x600,'A'},2,1},
        {"orphan mark",{0x301},1,1}, {"orphan selector",{0xfe0f},1,1}
    };
    for (size_t i=0;i<lenof(cases);i++) {
        setup_cluster(mk,cases[i].name,8,20);
        output_scalars(mk->term,cases[i].text,cases[i].count);
        IEQUAL(mk->term->curs.x,cases[i].cells);IEQUAL(mk->term->curs.y,0);
        cluster_contents(mk,0,0,cases[i].text,cases[i].count);
        if (cases[i].cells==2) IEQUAL(get_termchar(mk->term,1,0).chr,UCSWIDE);
        term_data_fragmented(mk->term,"X");
        IEQUAL(get_termchar(mk->term,cases[i].cells,0).chr,CSET_ASCII|'X');
    }
    setup_cluster(mk,"flags pair without unbounded parity counter",8,20);
    uint32_t flags[]={0x1f1e6,0x1f1fa,0x1f1e7,0x1f1f7,0x1f1e8};
    output_scalars(mk->term,flags,lenof(flags));IEQUAL(mk->term->curs.x,6);
    cluster_contents(mk,0,0,flags,2);cluster_contents(mk,2,0,flags+2,2);
    cluster_contents(mk,4,0,flags+4,1);
}

static void test_late_width(Mock *mk)
{
    Terminal *t=mk->term;uint32_t heart[]={0x2764,0xfe0f};
    setup_cluster(mk,"late VS16 crosses right edge and preserves original cluster",4,6);
    term_data_fragmented(t,"ABCDE");output_scalars(t,heart,1);
    IEQUAL(t->wrapnext,true);output_scalars(t,heart+1,1);
    IEQUAL(t->curs.y,1);IEQUAL(t->curs.x,2);IEQUAL(t->wrapnext,false);
    cluster_contents(mk,0,1,heart,2);IEQUAL(get_termchar(t,1,1).chr,UCSWIDE);
    IEQUAL(get_lineattr(t,0)&(LATTR_WRAPPED|LATTR_WRAPPED2),LATTR_WRAPPED|LATTR_WRAPPED2);
    IEQUAL(get_termchar(t,5,0).chr,CSET_ASCII|' ');

    setup_cluster(mk,"late widening scrolls at bottom",2,4);
    term_data_fragmented(t,"1234abcd");output_scalars(t,heart,1);
    // Heart wrapped normally before writing; place another at the bottom edge.
    term_data_fragmented(t,"\033[2;4H");output_scalars(t,heart,1);output_scalars(t,heart+1,1);
    IEQUAL(t->curs.y,1);IEQUAL(t->curs.x,2);cluster_contents(mk,0,1,heart,2);
    IEQUAL(count234(t->scrollback)>0,true);

    setup_cluster(mk,"unwrappable growth becomes one bounded replacement",4,6);
    term_data_fragmented(t,"\033[?7l\033[1;6H");output_scalars(t,heart,2);
    IEQUAL(t->curs.x,5);IEQUAL(t->curs.y,0);IEQUAL(get_termchar(t,5,0).chr,0xfffd);
    IEQUAL(get_termchar(t,5,0).cc_next,0);
    setup_cluster(mk,"growth against neighbouring wide cell erases its remainder",4,10);
    term_data_fragmented(t,"\033[1;2H\xe4\xb8\xad\033[H");output_scalars(t,heart,2);
    cluster_contents(mk,0,0,heart,2);IEQUAL(get_termchar(t,1,0).chr,UCSWIDE);
    IEQUAL(get_termchar(t,2,0).chr,CSET_ASCII|' ');

    setup_cluster(mk,"insert growth shifts the next cell exactly once",4,10);
    term_data_fragmented(t,"XYZ\033[H\033[4h");output_scalars(t,heart,2);
    IEQUAL(get_termchar(t,2,0).chr,CSET_ASCII|'X');
    IEQUAL(get_termchar(t,3,0).chr,CSET_ASCII|'Y');
    IEQUAL(get_termchar(t,4,0).chr,CSET_ASCII|'Z');

    setup_cluster(mk,"late widening wraps inside horizontal margins",4,10);
    term_data_fragmented(t,"\033[?69h\033[3;7s\033[1;7H");output_scalars(t,heart,2);
    IEQUAL(t->curs.x,4);IEQUAL(t->curs.y,1);cluster_contents(mk,2,1,heart,2);
    IEQUAL(get_termchar(t,3,1).chr,UCSWIDE);
    IEQUAL(get_lineattr(t,0)&LATTR_WRAPPED,0);

    setup_cluster(mk,"single-column surface safely replaces double-cell cluster",4,1);
    output_scalars(t,heart,2);IEQUAL(get_termchar(t,0,0).chr,0xfffd);
    IEQUAL(t->curs.x,0);IEQUAL(t->curs.y,0);
}

static unsigned retained_clusters(Mock *mk, const uint32_t *cp, size_t n)
{
    unsigned count=0;
    for (int y=-count234(mk->term->scrollback);y<mk->term->rows;y++) {
        termline *line=term_get_line(mk->term,y);
        for (int x=0;x<line->cols;x++) if (line->chars[x].chr==cp[0]) {
            count++;
            cluster_contents(mk,x,y,cp,n);
            IEQUAL(x+1<line->cols,true);
            if (x+1<line->cols) IEQUAL(line->chars[x+1].chr,UCSWIDE);
        }
        term_release_line(line);
    }
    return count;
}

static void test_reflow_and_rectangle(Mock *mk)
{
    Terminal *t=mk->term;uint32_t tech[]={0x1f469,0x200d,0x1f4bb};
    setup_cluster(mk,"screen/history reflow keeps complete independent clusters",4,8);
    for (unsigned i=0;i<40;i++) {output_scalars(t,tech,3);term_data_fragmented(t,"\r\n");}
    IEQUAL(retained_clusters(mk,tech,3),40);
    for (unsigned i=0;i<8;i++) {
        term_size(t,6,3,100);IEQUAL(retained_clusters(mk,tech,3),40);
        term_size(t,4,8,100);IEQUAL(retained_clusters(mk,tech,3),40);
    }
    setup_cluster(mk,"rectangle copying preserves a whole cluster independently",4,10);
    output_scalars(t,tech,3);
    term_data_fragmented(t,"\033[1;1;1;2;1;2;3;1$v\033[HXX");
    cluster_contents(mk,2,1,tech,3);IEQUAL(get_termchar(t,3,1).chr,UCSWIDE);
    IEQUAL(get_termchar(t,0,0).chr,CSET_ASCII|'X');
    IEQUAL(get_termchar(t,0,0).cc_next,0);
}

static void test_controls_and_storage(Mock *mk)
{
    Terminal *t=mk->term;uint32_t tech[]={0x1f469,0x200d,0x1f4bb};
    setup_cluster(mk,"SGR and CPR preserve pending cluster but first style owns cell",4,10);
    output_scalars(t,tech,1);unsigned long attr=get_termchar(t,0,0).attr;
    term_data_fragmented(t,"\033[31m\033[6n\033[?2026$p");
    output_scalars(t,tech+1,2);IEQUAL(t->curs.x,2);
    cluster_contents(mk,0,0,tech,3);IEQUAL(get_termchar(t,0,0).attr,attr);
    setup_cluster(mk,"explicit same-position move breaks attachment",4,10);
    output_scalars(t,tech,1);term_data_fragmented(t,"\033[1;3H");
    output_scalars(t,tech+1,2);IEQUAL(t->curs.x,5);

    setup_cluster(mk,"erasing a wide cluster's second half erases all members",4,10);
    output_scalars(t,tech,3);term_data_fragmented(t,"\033[1;2H\033[X");
    IEQUAL(get_termchar(t,0,0).chr,CSET_ASCII|' ');IEQUAL(get_termchar(t,0,0).cc_next,0);
    IEQUAL(get_termchar(t,1,0).chr,CSET_ASCII|' ');

    setup_cluster(mk,"cluster copied as original Unicode",4,10);
    output_scalars(t,tech,3);
    term_mouse(t,MBT_LEFT,MBT_SELECT,MA_CLICK,0,0,true,false,false);
    term_mouse(t,MBT_LEFT,MBT_SELECT,MA_DRAG,1,0,true,false,false);
    term_mouse(t,MBT_LEFT,MBT_SELECT,MA_RELEASE,1,0,true,false,false);
    int clip=CLIP_LOCAL+1;mk->clipboard_writes=0;term_request_copy(t,&clip,1);
#ifdef PLATFORM_IS_UTF16
    check_clipboard(mk,L"\xd83d\xdc69\x200d\xd83d\xdcbb");
#else
    check_clipboard(mk,L"\U0001f469\u200d\U0001f4bb");
#endif
    setup_cluster(mk,"alternate screen does not inherit cluster attachment",4,10);
    output_scalars(t,tech,1);term_data_fragmented(t,"\033[?1049h\033[H");
    output_scalars(t,tech+1,2);IEQUAL(t->curs.x,3);
    term_data_fragmented(t,"\033[?1049l");cluster_contents(mk,0,0,tech,1);
    term_data_fragmented(t,"\033c");IEQUAL(t->grapheme_mode,false);

    setup_cluster(mk,"long cluster replacement retains constant columns and storage",4,10);
    uint32_t mark=0x301;term_data_fragmented(t,"a");
    for (unsigned i=0;i<10000;i++) output_scalars(t,&mark,1);
    IEQUAL(t->curs.x,1);IEQUAL(get_termchar(t,0,0).chr,0xfffd);
    IEQUAL(get_termchar(t,0,0).cc_next,0);
    term_data_fragmented(t,"Z");IEQUAL(t->curs.x,2);
}

static void test_repeat(Mock *mk)
{
    Terminal *t=mk->term;
    const uint32_t tech[]={0x1f469,0x200d,0x1f4bb};
    const uint32_t skin[]={0x1f44d,0x1f3fd};
    setup_cluster(mk,"REP repeats whole cluster including after a cursor move",4,20);
    output_scalars(t,tech,3);term_data_fragmented(t,"\033[2b");
    IEQUAL(t->curs.x,6);
    for (int x=0;x<6;x+=2) cluster_contents(mk,x,0,tech,3);
    term_data_fragmented(t,"\033[2;1H\033[b");
    IEQUAL(t->curs.x,2);cluster_contents(mk,0,1,tech,3);

    setup_cluster(mk,"REP retains the cluster after its source is erased",4,20);
    output_scalars(t,skin,2);term_data_fragmented(t,"\033[H\033[2K\033[2b");
    IEQUAL(t->curs.x,4);
    cluster_contents(mk,0,0,skin,2);cluster_contents(mk,2,0,skin,2);

    setup_cluster(mk,"REP forces boundaries between regional indicator clusters",4,20);
    uint32_t ri=0x1f1e6;output_scalars(t,&ri,1);term_data_fragmented(t,"\033[3b");
    IEQUAL(t->curs.x,8);
    for (int x=0;x<8;x+=2) cluster_contents(mk,x,0,&ri,1);

    setup_cluster(mk,"REP obeys the same combining-member bound as cells",4,20);
    uint32_t long_cluster[CC_LIMIT+1];long_cluster[0]='e';
    for (unsigned i=1;i<lenof(long_cluster);i++) long_cluster[i]=0x301;
    output_scalars(t,long_cluster,lenof(long_cluster));
    term_data_fragmented(t,"\033[b");
    cluster_contents(mk,1,0,long_cluster,lenof(long_cluster));
    output_scalars(t,long_cluster+1,1);
    IEQUAL(get_termchar(t,1,0).chr,0xfffd);
    term_data_fragmented(t,"\033[2b");
    IEQUAL(t->curs.x,4);uint32_t replacement=0xfffd;
    cluster_contents(mk,2,0,&replacement,1);cluster_contents(mk,3,0,&replacement,1);

    setup_cluster(mk,"disabled mode retains legacy scalar REP",4,20);
    term_set_grapheme_clustering(t,false);output_scalars(t,tech,3);
    term_data_fragmented(t,"\033[b");IEQUAL(t->curs.x,6);
    IEQUAL(get_termchar(t,4,0).chr,tech[2]);
}

static bool cluster_test_draw_context(TermWin *win) { return true; }
static int cluster_test_char_width(TermWin *win, int uc) { return 1; }
static void cluster_test_free_context(TermWin *win) {}
static void cluster_test_cursor_pos(TermWin *win, int x, int y) {}

static void test_bidi_cache(Mock *mk)
{
    setup_cluster(mk,"identity cluster rows and bidi mapping transitions",4,20);
    Terminal *t=mk->term;
    const TermWinVtable *original=mk->tw.vt;
    TermWinVtable drawing=*original;drawing.setup_draw_ctx=cluster_test_draw_context;
    drawing.char_width=cluster_test_char_width;drawing.free_draw_ctx=cluster_test_free_context;
    drawing.set_cursor_pos=cluster_test_cursor_pos;
    mk->tw.vt=&drawing;t->no_bidi=t->no_arabicshaping=false;
    static const uint32_t text[]={'e',0x301,0x1f469,0x200d,0x1f4bb};
    output_scalars(t,text,lenof(text));term_update(t);
    for (int y=0;y<t->bidi_cache_size;y++) {
        IEQUAL(t->pre_bidi_cache[y].chars==NULL,true);
        IEQUAL(t->post_bidi_cache[y].chars==NULL,true);
    }
    term_data_fragmented(t,"\033[2J\033[Habc ");
    static const uint32_t hebrew[]={0x5d0,0x5d1,0x5d2};
    output_scalars(t,hebrew,lenof(hebrew));term_update(t);
    IEQUAL(t->bidi_cache_size>0,true);
    IEQUAL(t->post_bidi_cache[0].chars!=NULL,true);
    if (t->post_bidi_cache[0].chars) {
        IEQUAL(t->post_bidi_cache[0].forward[4],6);
        IEQUAL(t->post_bidi_cache[0].backward[4],6);
        IEQUAL(t->disptext[0]->chars[4].chr,0x5d2);
    }
    term_data_fragmented(t,"\033[2J\033[H");output_scalars(t,text,lenof(text));term_update(t);
    IEQUAL(t->post_bidi_cache[0].chars==NULL,true);
    IEQUAL(t->post_bidi_cache[0].forward==NULL,true);
    IEQUAL(t->post_bidi_cache[0].backward==NULL,true);
    cluster_contents(mk,1,0,text+2,3);

    /* Unique dense RTL rows exceed the retained-cache budget. Repainting
     * evicted rows must retain visual glyphs and not grow cached copies. */
    setup_cluster(mk,"bounded bidi cache with distinct dense rows",48,160);
    t=mk->term;t->no_bidi=t->no_arabicshaping=false;
    for (int y=0;y<48;y++) {
        char prefix[40];sprintf(prefix,"\033[%d;1HL%02d ",y+1,y);
        term_data_fragmented(t,prefix);output_scalars(t,hebrew,lenof(hebrew));
        for (int x=0;x<60;x++) output_scalars(t,text,2);
    }
    for (int repeat=0;repeat<3;repeat++) {
        term_invalidate(t);term_update(t);
        IEQUAL(t->bidi_cache_bytes>0,true);
        IEQUAL(t->bidi_cache_bytes<=NEMO_BIDI_CACHE_BYTES,true);
        int retained=0;
        for (int y=0;y<48;y++) {
            IEQUAL(t->disptext[y]->chars[4].chr,0x5d2);
            retained+=t->post_bidi_cache[y].chars!=NULL;
        }
        IEQUAL(retained>0 && retained<48,true);
        IEQUAL(t->post_bidi_cache[0].chars==NULL,true);
        term_mouse_pixels(t,MBT_LEFT,MBT_SELECT,MA_CLICK,4,0,35,7,false,false,false);
        IEQUAL(t->selanchor.x,6);IEQUAL(t->selanchor.y,0);
        term_mouse_pixels(t,MBT_LEFT,MBT_SELECT,MA_RELEASE,4,0,35,7,false,false,false);
        term_data_fragmented(t,"\033[1;5H");term_update(t);
        IEQUAL((t->disptext[0]->chars[6].attr&(ATTR_ACTCURS|ATTR_PASCURS))!=0,true);
        IEQUAL((t->disptext[0]->chars[4].attr&(ATTR_ACTCURS|ATTR_PASCURS))==0,true);
    }
    /* One row larger than the cache budget must still render and map input.
     * Keeping it must evict every other row, including another oversized one. */
    term_size(t,2,2048,0);
    term_data_fragmented(t,"\033[2J\033[HL ");
    output_scalars(t,hebrew,lenof(hebrew));
    term_data_fragmented(t,"\033[2;1HL ");
    output_scalars(t,hebrew,lenof(hebrew));
    term_update(t);
    IEQUAL(t->bidi_cache_bytes>NEMO_BIDI_CACHE_BYTES,true);
    IEQUAL(t->post_bidi_cache[0].chars==NULL,true);
    IEQUAL(t->post_bidi_cache[1].chars!=NULL,true);
    IEQUAL(t->disptext[0]->chars[2].chr,0x5d2);
    IEQUAL(t->disptext[1]->chars[2].chr,0x5d2);
    term_mouse_pixels(t,MBT_LEFT,MBT_SELECT,MA_CLICK,2,0,19,7,false,false,false);
    IEQUAL(t->selanchor.x,4);IEQUAL(t->selanchor.y,0);
    IEQUAL(t->post_bidi_cache[0].chars!=NULL,true);
    IEQUAL(t->post_bidi_cache[1].chars==NULL,true);
    term_mouse_pixels(t,MBT_LEFT,MBT_SELECT,MA_RELEASE,2,0,19,7,false,false,false);
    conf_set_bool(mk->conf,CONF_no_bidi,true);
    term_reconfig(t,mk->conf);IEQUAL(t->bidi_cache_bytes,0);
    conf_set_bool(mk->conf,CONF_no_bidi,false);
    term_reconfig(t,mk->conf);term_size(t,12,80,0);term_update(t);
    IEQUAL(t->bidi_cache_bytes<=NEMO_BIDI_CACHE_BYTES,true);
    mk->tw.vt=original;
}

static void test_mode(Mock *mk)
{
    Terminal *t=mk->term;reset(mk);test_context(mk,"2027 query, save, restore and reset semantics");
    term_data_fragmented(t,"\033[?2027$p\033[?2027h\033[?2027$p\033[?2027s"
        "\033[?2027l\033[?2027$p\033[?2027r\033[?2027$p\033[!p\033[?2027$p");
    SEQUAL(mk->to_backend->s,"\033[?2027;2$y\033[?2027;1$y\033[?2027;2$y"
        "\033[?2027;1$y\033[?2027;2$y");
    strbuf_clear(mk->to_backend);
    /* Like the other XTSAVE slots, an explicit later restore can re-enable
     * saved state; RIS itself must first report the reset mode. */
    term_data_fragmented(t,"\033[?2027h\033[?2027s\033c\033[?2027$p"
        "\033[?2027r\033[?2027$p\033[?2027l");
    SEQUAL(mk->to_backend->s,"\033[?2027;2$y\033[?2027;1$y");
    strbuf_clear(mk->to_backend);
    const TermWinVtable *original=mk->tw.vt;
    TermWinVtable unsupported=*original;unsupported.grapheme_clusters=false;mk->tw.vt=&unsupported;
    term_data_fragmented(t,"\033[?2027h\033[?2027$p");
    SEQUAL(mk->to_backend->s,"\033[?2027;0$y");IEQUAL(t->grapheme_mode,false);
    mk->tw.vt=original;
}

int main(void)
{
    Mock *mk=mock_new();TermWinVtable supported=*mk->tw.vt;supported.grapheme_clusters=true;
    mk->tw.vt=&supported;mk->term=term_init(mk->conf,mk->ucsdata,&mk->tw);
    mk->ldisc=ldisc_create(mk->conf,mk->term,&mk->backend,&mk->seat);
    test_shapes(mk);test_late_width(mk);test_controls_and_storage(mk);
    test_reflow_and_rectangle(mk);test_repeat(mk);test_mode(mk);test_bidi_cache(mk);
    bool failed=mk->any_test_failed;mock_free(mk);
    puts(failed?"Grapheme terminal suite FAILED":"Grapheme terminal suite passed");
    return failed?1:0;
}
