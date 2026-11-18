/* SPDX-License-Identifier: MIT
 * OSC 50 with one scalable face per terminal. XTerm's scalable renderer
 * shares one face across its built-in menu entries; it does not load X11
 * bitmap aliases into a Windows font mapper. */
static void nemo_font_operation(Terminal *term, bool bel)
{
    if (term->osc_overflow) return;
    const TermWinVtable *vt = term->win->vt;
    const char *p = term->osc_string;
    bool query = *p == '?', indexed = false;
    if (query ? (!term->ldisc || !vt->get_font_face ||
                 !conf_get_bool(term->conf, CONF_nemo_allow_get_font)) :
                (!vt->set_font_face || !conf_get_bool(term->conf, CONF_nemo_allow_set_font)))
        return;
    int slot = 0;
    if (query || *p == '#') {
        bool relative = false, negative = false;
        p++;
        if (*p == '+' || *p == '-') { relative = true; negative = *p++ == '-'; }
        indexed = *p != '\0';
        unsigned number = relative ? 1 : 0;
        if (*p >= '0' && *p <= '9') {
            number = 0;
            do { if (number <= 7) number = number*10 + (*p-'0'); p++; }
            while (*p >= '0' && *p <= '9');
        }
        if (relative) {
            /* The default scalable menu entry lies between small and large.
             * Use the built-in menu order, never index outside the table. */
            static const int scale[] = {1,2,3,0,4,5,6};
            slot = number > 3 ? -1 : scale[negative ? 3-number : 3+number];
        } else slot = number <= 6 ? (int)number : -1;
    }
    if (query) {
        char face[128], reply[160];
        int n;
        const char *end = bel ? "\007" : "\033\\";
        if (slot < 0 || !vt->get_font_face(term->win, face, sizeof(face)))
            n = snprintf(reply, sizeof(reply), "\033]50%s", end);
        else if (indexed)
            n = snprintf(reply, sizeof(reply), "\033]50;#%d %s%s", slot, face, end);
        else n = snprintf(reply, sizeof(reply), "\033]50;%s%s", face, end);
        if (n > 0 && (size_t)n < sizeof(reply)) nemo_protocol_send(term, reply, n);
    } else if (slot >= 0) {
        while (*p == ' ' || *p == '\t') p++;
        size_t len = strlen(p);
        while (len && (p[len-1]==' ' || p[len-1]=='\t')) len--;
        char face[128];
        if (len && len < sizeof(face)) {
            memcpy(face,p,len); face[len]=0;
            vt->set_font_face(term->win, face);
        }
    }
}
