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
        if (ctrl && term->funky_type != FUNKY_XTERM_216) return -1;
        len = format_small_keypad_key(value, term, key.code, shift, ctrl, alt, &consumed_alt);
        break;
      case 'N':
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
    if (!len) return -1;
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
        value[0] = term->bksp_is_delete ? '\177' : '\010';
        return 1;
    }
    if (!strcmp(name, "kB") || !strcmp(name, "kcbt")) {
        memcpy(value, "\033[Z", 3);
        return 3;
    }
    if (!strcmp(name, "&8") || !strcmp(name, "kund")) return -1;

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
