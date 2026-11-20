/* DECCTR: a 256-entry palette can be saved and replayed without keeping a
 * second palette in an idle terminal. RGB and HLS use decimal percentages. */
static void palette_rebuild(Terminal *term);

static void nemo_report_colour_table(Terminal *term)
{
    if (!term->ldisc || term->esc_nargs != 2 || term->esc_args[0] != 2)
        return;
    unsigned model = term->esc_args[1];
    if (model != 1 && model != 2) return;
    strbuf *reply = strbuf_new();
    put_dataz(reply, "\033P2$s");
    for (unsigned i = 0; i < 256; i++) {
        rgb c = term->palette[i];
        unsigned x, y, z;
        if (model == 2) {
            x = (c.r * 100 + 128) / 255;
            y = (c.g * 100 + 128) / 255;
            z = (c.b * 100 + 128) / 255;
        } else {
            int hi = max(c.r, max(c.g, c.b)), lo = min(c.r, min(c.g, c.b));
            int sum = hi + lo, d = hi - lo;
            x = z = 0;
            y = (sum * 50 + 127) / 255;
            if (d) {
                /* DEC has blue at 0 degrees, red at 120 and green at 240. */
                int h = hi == c.r ? 2*d+c.g-c.b :
                        hi == c.g ? 4*d+c.b-c.r : 6*d+c.r-c.g;
                x = ((h*60 + d/2) / d) % 360;
                int denom = min(sum, 510-sum);
                z = (d*100 + denom/2) / denom;
            }
        }
        put_fmt(reply, "%s%u;%u;%u;%u;%u", i ? "/" : "", i, model, x, y, z);
    }
    put_dataz(reply, "\033\\");
    nemo_protocol_send(term, reply->s, reply->len);
    strbuf_free(reply);
}

struct NemoPendingColourTable {
    optionalrgb entries[256];
    unsigned fields[5], field;
    bool invalid, digit;
};

static void nemo_dec_colour_entry(struct NemoPendingColourTable *p)
{
    unsigned *v = p->fields;
    if (!p->invalid && p->digit && p->field == 4 && v[0] < 256 &&
        (v[1] == 1 || v[1] == 2)) {
        unsigned r, g, b;
        if (v[1] == 1) {
            uint32_t pixel = nemo_sixel_hls(v[2], v[3], v[4]);
            r = (pixel >> 16) & 255; g = (pixel >> 8) & 255; b = pixel & 255;
        } else {
            r = (min(v[2],100u)*255+50)/100;
            g = (min(v[3],100u)*255+50)/100;
            b = (min(v[4],100u)*255+50)/100;
        }
        p->entries[v[0]] = (optionalrgb){true, r, g, b};
    }
    memset(p->fields, 0, sizeof(p->fields));
    p->field = 0; p->invalid = p->digit = false;
}

static void nemo_dec_colour_byte(struct NemoPendingColourTable *p, unsigned c)
{
    if (c == '/') {
        nemo_dec_colour_entry(p);
    } else if (p->invalid) {
        return;
    } else if (c >= '0' && c <= '9') {
        unsigned *v = &p->fields[p->field], digit = c-'0';
        if (*v > (UINT_MAX-digit)/10) p->invalid = true;
        else *v = *v*10 + digit;
        p->digit = true;
    } else if (c == ';' && p->field < 4 && p->digit) {
        p->field++; p->digit = false;
    } else {
        p->invalid = true;
    }
}

static void nemo_dec_colour_finish(Terminal *term)
{
    struct NemoPendingColourTable *p = term->dcs_colour_table;
    if (!p || term->dcs_query_invalid) return;
    nemo_dec_colour_entry(p);
    for (unsigned i = 0; i < 256; i++) {
        optionalrgb c = p->entries[i];
        if (c.enabled) {
            term->subpalettes[SUBPAL_SESSION].present[i] = true;
            term->subpalettes[SUBPAL_SESSION].values[i] = (rgb){c.r, c.g, c.b};
        }
    }
    palette_rebuild(term);
}
