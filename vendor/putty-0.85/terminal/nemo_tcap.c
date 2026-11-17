/* SPDX-License-Identifier: MIT */
#include "putty.h"
#include "terminal.h"
#include "nemo_tcap.h"

/* XTGETTCAP uses a bounded whitelist of identity, colour, rendition and keys,
 * not an arbitrary terminfo database. Key values use the same encoders as the
 * Win32 input path. Local shortcuts and
 * keyboard layout translation precede those encoders and remain independent.
 * Protocol reference: xterm ctlseqs, DCS + q (Patch 411). */
typedef struct CapKey {
    const char *short_name, *long_name;
    char kind;
    int code;
    unsigned modifiers; /* Shift=1, Alt=2, Ctrl=4 */
} CapKey;

static const CapKey keys[] = {
    {"ku", "kcuu1", 'A', 'A', 0}, {"kd", "kcud1", 'A', 'B', 0},
    {"kr", "kcuf1", 'A', 'C', 0}, {"kl", "kcub1", 'A', 'D', 0},
    {"kC", "kclr", 'A', 'G', 0},
    {"kR", "kri", 'A', 'A', 1}, {"kF", "kind", 'A', 'B', 1},
    {"%i", "kRIT", 'A', 'C', 1}, {"#4", "kLFT", 'A', 'D', 1},
    {"kh", "khome", 'E', SKK_HOME, 0}, {"@7", "kend", 'E', SKK_END, 0},
    {"kI", "kich1", 'E', SKK_INSERT, 0}, {"kD", "kdch1", 'E', SKK_DELETE, 0},
    {"kP", "kpp", 'E', SKK_PGUP, 0}, {"kN", "knp", 'E', SKK_PGDN, 0},
    {"#2", "kHOM", 'E', SKK_HOME, 1}, {"*7", "kEND", 'E', SKK_END, 1},
    {"%e", "kPRV", 'E', SKK_PGUP, 1}, {"%c", "kNXT", 'E', SKK_PGDN, 1},
    {"@0", "kfnd", 'E', SKK_FIND, 0}, {"*6", "kslt", 'E', SKK_SELECT, 0},
    {"%1", "khlp", 'E', SKK_HELP, 0}, {"*0", "kFND", 'E', SKK_FIND, 1},
    {"#6", "kSLT", 'E', SKK_SELECT, 1}, {"#1", "kHLP", 'E', SKK_HELP, 1},
    {"@8", "kent", 'N', '\r', 0},
    {"K1", "ka1", 'N', '7', 0}, {"K3", "ka3", 'N', '9', 0},
    {"K4", "kc1", 'N', '1', 0}, {"K5", "kc3", 'N', '3', 0},
};

static const CapKey extended[] = {
    {NULL, "kUP", 'A', 'A', 0}, {NULL, "kDN", 'A', 'B', 0},
    {NULL, "kRIT", 'A', 'C', 0}, {NULL, "kLFT", 'A', 'D', 0},
    {NULL, "kHOM", 'E', SKK_HOME, 0}, {NULL, "kEND", 'E', SKK_END, 0},
    {NULL, "kIC", 'E', SKK_INSERT, 0}, {NULL, "kDC", 'E', SKK_DELETE, 0},
    {NULL, "kPRV", 'E', SKK_PGUP, 0}, {NULL, "kNXT", 'E', SKK_PGDN, 0},
    {NULL, "kpADD", 'N', '+', 0}, {NULL, "kpSUB", 'N', '-', 0},
    {NULL, "kpMUL", 'N', '*', 0}, {NULL, "kpDIV", 'N', '/', 0},
    {NULL, "kpDOT", 'N', '.', 0}, {NULL, "kpCMA", 'N', ',', 0},
    {NULL, "kpZRO", 'N', '0', 0},
};

void nemo_tcap_configure(Terminal *term, const char *name)
{
    int profile = nemo_tcap_db_find(name, strlen(name));
    term->tcap_profile = profile < 0 ? 0 : (unsigned)profile;
}

static const char *database_key(Terminal *term, char kind, int code, unsigned mods)
{
    const char *value;
    char name[16];
    if (kind == 'F') {
        /* XTerm's physical table ends at F35. Higher query entries use
         * synthetic codes and continue through its ordinary key formatter. */
        if (mods || code < 1 || code > 35) return NULL;
        sprintf(name, "kf%d", code);
        return nemo_tcap_db_value(term->tcap_profile, name);
    }
    if (kind == 'S') {
        if (mods) return NULL;
        const char *cap = code == 8 ? "kbs" : code == 9 ? "kcbt" :
            code == 12 ? "kclr" : code == 26 ? "kund" : NULL;
        return cap ? nemo_tcap_db_value(term->tcap_profile, cap) : NULL;
    }
    if (kind == 'N' && !mods && code >= '1' && code <= '9') {
        sprintf(name, "kp%c", code);
        return nemo_tcap_db_value(term->tcap_profile, name);
    }
    for (size_t i = 0; i < lenof(keys); i++) {
        const CapKey *key = &keys[i];
        /* ka1/ka3/kc1/kc3 name navigation positions, not numeric keys. */
        if (key->kind == 'N' && key->code != '\r') continue;
        if (key->kind == kind && key->code == code && key->modifiers == mods &&
            (value = nemo_tcap_db_value(term->tcap_profile, key->long_name)) != NULL)
            return value;
    }
    if (mods >= 1 && mods <= 7) {
        for (size_t i = 0; i < lenof(extended); i++) {
            const CapKey *key = &extended[i];
            if (key->kind != kind || key->code != code) continue;
            if (mods == 1) strcpy(name, key->long_name);
            else sprintf(name, "%s%u", key->long_name, mods+1);
            if ((value = nemo_tcap_db_value(term->tcap_profile, name)) != NULL)
                return value;
        }
    }
    return NULL;
}

static bool extended_resource(Terminal *term, unsigned resource)
{
    unsigned index = resource <= 3 ? resource-1 : 4; /* resource 7 */
    return term->special_modify_keys[index].level == 4;
}

static int copy_database_key(Terminal *term, char kind, int code,
                             unsigned modifiers, char output[64])
{
    const char *value = database_key(term, kind, code, modifiers);
    if (!value) return -1;
    size_t length = strlen(value);
    if (length >= 64) return -1;
    memcpy(output, value, length);
    return (int)length;
}

int nemo_tcap_key(Terminal *term, char kind, int code, unsigned modifiers,
                  char output[64])
{
    if (term->funky_type != FUNKY_TCAP || term->vt52_mode) return -1;
    unsigned resource = kind == 'F' || (kind == 'E' && code == SKK_HELP) ? 2 :
        kind == 'N' ? 3 : kind == 'S' ? 7 : 1;
    /* XTerm handles explicit extended encoding before keyboardIsTermcap.
     * The raw database only precedes the ordinary key formatter. */
    if (extended_resource(term, resource)) return -1;
    return copy_database_key(term, kind, code, modifiers, output);
}

int nemo_tcap_special_key(Terminal *term, unsigned resource, unsigned point,
                          unsigned modifiers, char output[64])
{
    if (term->funky_type != FUNKY_TCAP || term->vt52_mode) return -1;
    if ((resource != 2 && resource != 3 && resource != 7) ||
        extended_resource(term, resource)) return -1;
    char kind = 0;
    int code = 0;
    if (resource == 7) {
        kind = 'S';
        if (point == 8) code = 8;
        else if (point == 0xe120) code = 9; /* ISO Left Tab, not ordinary Tab */
    } else if (resource == 2 && point == 0xe26a) {
        kind = 'E'; code = SKK_HELP;
    } else if (resource == 3) {
        /* XTerm converts keypad navigation to dedicated navigation before
         * the database lookup. Num Lock digits retain their numeric identity. */
        if (point >= 0xe295 && point <= 0xe29d) {
            switch (point) {
              case 0xe295: kind = 'E'; code = SKK_HOME; break;
              case 0xe296: kind = 'A'; code = 'D'; break;
              case 0xe297: kind = 'A'; code = 'A'; break;
              case 0xe298: kind = 'A'; code = 'C'; break;
              case 0xe299: kind = 'A'; code = 'B'; break;
              case 0xe29a: kind = 'E'; code = SKK_PGUP; break;
              case 0xe29b: kind = 'E'; code = SKK_PGDN; break;
              case 0xe29c: kind = 'E'; code = SKK_END; break;
              default: break;
            }
        } else if (point >= 0xe2b0 && point <= 0xe2b9) {
            kind = 'N'; code = '0' + point-0xe2b0;
        } else {
            kind = 'N';
            switch (point) {
              case 0xe28d: code = '\r'; break;
              case 0xe2aa: code = '*'; break;
              case 0xe2ab: code = '+'; break;
              case 0xe2ac: code = ','; break;
              case 0xe2ad: code = '-'; break;
              case 0xe2ae: code = '.'; break;
              case 0xe2af: code = '/'; break;
              default: break;
            }
        }
    }
    /* Preserve the original resource when testing extended mode. Keypad Home
     * is resource 3 even though its database lookup uses dedicated Home. */
    return kind && code ? copy_database_key(term, kind, code, modifiers & 15, output) : -1;
}

/* Literal sequences from ncurses' ecma+ renditions. Keep
 * termcap aliases only where include/Caps defines them; extended names are
 * case sensitive (Smol/Rmol, unlike the lower-case standard names).
 * https://github.com/ThomasDickey/ncurses-snapshots/blob/master/misc/terminfo.src
 * https://github.com/ThomasDickey/ncurses-snapshots/blob/master/include/Caps */
static const struct { const char *name, *alias, *value; } renditions[] = {
    {"smul", "us", "\033[4m"},  {"rmul", "ue", "\033[24m"},
    {"sitm", "ZH", "\033[3m"},  {"ritm", "ZR", "\033[23m"},
    {"smxx", NULL, "\033[9m"},  {"rmxx", NULL, "\033[29m"},
    {"Smol", NULL, "\033[53m"}, {"Rmol", NULL, "\033[55m"},
    /* Terminfo programs, expanded by the client. Smulx takes style 0..5;
     * Setulc takes one packed 0xRRGGBB value, as in tmux's usstyle feature.
     * The empty colour-space field is accepted by our SGR 58 parser. */
    {"Smulx", NULL, "\033[4:%p1%dm"},
    {"Setulc", NULL, "\033[58:2::%p1%{65536}%/%d:%p1%{256}%/%{255}%&%d:%p1%{255}%&%dm"},
};

static int key_value(Terminal *term, CapKey key, char value[64])
{
    if (term->funky_type == FUNKY_TCAP && key.long_name) {
        if (key.modifiers == 1) {
            const char *shifted = nemo_tcap_db_value(term->tcap_profile, key.long_name);
            const char *plain = database_key(term, key.kind, key.code, 0);
            if (!shifted || (plain && !strcmp(plain, shifted))) return -1;
        }
        /* Query injection has no character payload. A missing Delete key
         * falls back to the real key's DEL byte, but that byte is absent in
         * the synthetic query, so XTerm reports a present empty value. */
        if (key.kind == 'E' && key.code == SKK_DELETE &&
            !extended_resource(term, 1) &&
            (!term->modify_keys.level || !key.modifiers) &&
            !database_key(term, key.kind, key.code, key.modifiers)) return 0;
        if (key.kind == 'N' && key.code >= '1' && key.code <= '9') {
            if (!strcmp(key.long_name, "ka1")) key.kind = 'E', key.code = SKK_HOME;
            if (!strcmp(key.long_name, "kc1")) key.kind = 'E', key.code = SKK_END;
            if (!strcmp(key.long_name, "ka3")) key.kind = 'E', key.code = SKK_PGUP;
            if (!strcmp(key.long_name, "kc3")) key.kind = 'E', key.code = SKK_PGDN;
        }
    }
    bool shift = key.modifiers & 1, alt = key.modifiers & 2;
    bool ctrl = key.modifiers & 4, consumed_alt = false;
    int len;
    switch (key.kind) {
      case 'A':
        len = format_arrow_key(value, term, key.code, shift, ctrl, alt, &consumed_alt);
        break;
      case 'F':
        len = format_function_key(value, term, key.code, shift, ctrl, alt, &consumed_alt);
        break;
      case 'E':
        if (ctrl && term->funky_type != FUNKY_XTERM_216 &&
            term->funky_type != FUNKY_XTERM_LEGACY && term->funky_type != FUNKY_TCAP &&
            !term->special_modify_keys_set) return -1;
        len = format_small_keypad_key(value, term, key.code, shift, ctrl, alt, &consumed_alt);
        break;
      case 'N':
        len = nemo_tcap_key(term, 'N', key.code, key.modifiers, value);
        if (len >= 0) { consumed_alt = alt; break; }
        if (term->special_modify_keys_set || term->funky_type == FUNKY_XTERM_LEGACY ||
            term->funky_type == FUNKY_TCAP) {
            unsigned point = 0xe280 + (unsigned char)key.code;
            len = term_format_xterm_extended_key(term, 3, point, key.modifiers, value, 64);
            if (len < 0) len = term_format_xterm_legacy_key(term, 3, point, key.modifiers, false, value, 64);
            if (len >= 0) { consumed_alt = alt; break; }
        }
        if (alt) return -1; /* Win32 uses Alt+numpad for local character entry. */
        len = format_numeric_keypad_key(value, term, key.code, shift, ctrl);
        if (!len) {
            value[len++] = key.code;
            if (key.code == '\r' && term->cr_lf_return && !shift && !ctrl)
                value[len++] = '\n';
        }
        break;
      default: return -1;
    }
    if (!len && term->funky_type != FUNKY_TCAP) return -1;
    if (alt && !consumed_alt) {
        memmove(value+1, value, len);
        value[0] = '\033';
        len++;
    }
    return len;
}

/* -2: unknown name; -1: known but unavailable; otherwise value byte count. */
static int capability(Terminal *term, const char *name, char value[64])
{
    if (!strcmp(name, "TN") || !strcmp(name, "name")) {
        strcpy(value, NEMO_TERM_NAME);
        return strlen(value);
    }
    if (!strcmp(name, "Co") || !strcmp(name, "colors"))
        return sprintf(value, "%u", !term->ansi_colour ? 2 : term->xterm_256_colour ? 256 : 16);
    if (!strcmp(name, "RGB"))
        return sprintf(value, "%d", term->true_colour ? 8 : -1);
    for (size_t i = 0; i < lenof(renditions); i++) {
        if (!strcmp(name, renditions[i].name) ||
            (renditions[i].alias && !strcmp(name, renditions[i].alias))) {
            if (!strcmp(name, "Setulc") && (!term->true_colour || !term->ansi_colour))
                return -1; /* known, but disabled by the local colour policy */
            size_t len = strlen(renditions[i].value);
            if (len >= 64) return -1;
            memcpy(value, renditions[i].value, len+1);
            return len;
        }
    }
    if (!strcmp(name, "kb") || !strcmp(name, "kbs")) {
        int length = nemo_tcap_key(term, 'S', 8, 0, value);
        if (length >= 0) return length;
        value[0] = term->bksp_is_delete ? '\177' : '\010';
        return 1;
    }
    if (!strcmp(name, "kB") || !strcmp(name, "kcbt")) {
        int length = nemo_tcap_key(term, 'S', 9, 0, value);
        if (length >= 0) return length;
        memcpy(value, "\033[Z", 3);
        return 3;
    }
    if (!strcmp(name, "&8") || !strcmp(name, "kund")) {
        int length = nemo_tcap_key(term, 'S', 26, 0, value);
        return length < 0 && term->funky_type == FUNKY_TCAP ? 0 : length;
    }
    if (term->funky_type == FUNKY_TCAP &&
        (!strcmp(name, "kC") || !strcmp(name, "kclr"))) {
        int length = nemo_tcap_key(term, 'S', 12, 0, value);
        return length < 0 ? 0 : length;
    }

    size_t n = strlen(name);
    int function = 0;
    if (n >= 3 && n <= 4 && name[0] == 'k' && name[1] == 'f' &&
        name[2] >= '1' && name[2] <= '9') {
        function = name[2]-'0';
        if (n == 4) {
            if (name[3] < '0' || name[3] > '9') return -2;
            function = 10*function + name[3]-'0';
        }
        if (function > 63) return -2;
    } else if (n == 2 && name[0] == 'k') {
        if (name[1] >= '1' && name[1] <= '9') function = name[1]-'0';
        else if (name[1] == ';') function = 10;
    } else if (n == 2 && name[0] == 'F') {
        if (name[1] >= '1' && name[1] <= '9') function = 10 + name[1]-'0';
        else if (name[1] >= 'A' && name[1] <= 'Z') function = 20 + name[1]-'A';
        else if (name[1] >= 'a' && name[1] <= 'r') function = 46 + name[1]-'a';
    }
    if (function) return key_value(term, (CapKey){NULL, NULL, 'F', function, 0}, value);
    if (n == 3 && name[0] == 'k' && name[1] == 'p' && name[2] >= '1' && name[2] <= '9')
        return key_value(term, (CapKey){NULL, NULL, 'N', name[2], 0}, value);

    for (size_t i = 0; i < lenof(keys); i++)
        if (!strcmp(name, keys[i].short_name) || !strcmp(name, keys[i].long_name))
            return key_value(term, keys[i], value);
    for (size_t i = 0; i < lenof(extended); i++) {
        size_t len = strlen(extended[i].long_name);
        if (strncmp(name, extended[i].long_name, len)) continue;
        unsigned parameter = 2; /* bare extended name denotes Shift */
        if (n != len) {
            if (n != len+1 || name[len] < '3' || name[len] > '8') continue;
            parameter = name[len]-'0';
        }
        CapKey key = extended[i];
        key.modifiers = parameter-1;
        return key_value(term, key, value);
    }
    return -2;
}

static int hex_digit(char c)
{
    if (c >= '0' && c <= '9') return c-'0';
    if (c >= 'a' && c <= 'f') return c-'a'+10;
    if (c >= 'A' && c <= 'F') return c-'A'+10;
    return -1;
}

static bool decode_name(const char *data, size_t len, char name[32])
{
    if (!len || len % 2 || len >= 64) return false;
    for (size_t i = 0; i < len; i += 2) {
        int hi = hex_digit(data[i]), lo = hex_digit(data[i+1]);
        if (hi < 0 || lo < 0) return false;
        int c = hi*16+lo;
        if (c < ' ' || c > '~') return false;
        name[i/2] = c;
    }
    name[len/2] = '\0';
    return true;
}

bool nemo_tcap_set(Terminal *term, const char *encoded_name, bool invalid)
{
    if (invalid) return false;
    size_t length = 0;
    while (length < 64 && encoded_name[length]) length++;
    char name[32];
    if (!decode_name(encoded_name, length, name)) return false;
    for (const char *p = name; *p; p++)
        if (*p <= ' ' || strchr("\\|,:'\"", *p)) return false;
    int profile = nemo_tcap_db_find(name, length/2);
    if (profile < 0) return false;
    term->tcap_profile = (unsigned)profile;
    return true;
}

strbuf *nemo_tcap_reply(Terminal *term, const char *query, bool invalid)
{
    strbuf *reply = strbuf_new();
    put_dataz(reply, "\033P0+r");
    /* Cap both parser and direct callers. Setulc is the largest expansion:
     * 13 query bytes (including a separator) yield 134 response bytes.
     * A 2047-byte request stays below 22 KiB. Enforce that reply limit too,
     * so future capabilities cannot silently increase transient allocation. */
    if (!invalid && strlen(query) >= NEMO_DCS_QUERY_SIZE) invalid = true;
    if (!invalid) {
        const char *token = query;
        bool first = true;
        while (*token) {
            const char *end = strchr(token, ';');
            size_t len = end ? (size_t)(end-token) : strlen(token);
            char name[32], value[64];
            if (!decode_name(token, len, name)) { invalid = true; break; }
            int size = capability(term, name, value);
            if (first && size >= 0) reply->s[2] = '1';
            if (size == -2) break;
            if (reply->len + len + (size < 0 ? 0 : 1+2*size) + 3 > 22*1024) {
                invalid = true;
                break;
            }
            put_data(reply, token, len); /* preserve the request's hex case */
            if (size < 0) break;
            put_byte(reply, '=');
            for (int i = 0; i < size; i++) put_fmt(reply, "%02x", (unsigned char)value[i]);
            if (!end) break;
            put_byte(reply, ';');
            first = false;
            token = end+1;
        }
    }
    if (invalid) {
        strbuf_clear(reply);
        put_dataz(reply, "\033P0+r");
    }
    put_dataz(reply, "\033\\");
    return reply;
}
