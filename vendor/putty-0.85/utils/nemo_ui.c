#include <stdlib.h>
#include <string.h>
#include <ctype.h>
/* The core also builds independently for catalog/formatting tests. */
#define NEMO_UI_CORE
#include "nemo_ui_core.h"
#include "nemo_ui_catalog.h"

static int language = NEMO_UI_EN;

int nemo_ui_parse_language(const char *tag)
{
    if (!strcmp(tag, "system")) return NEMO_UI_SYSTEM;
    if (!strcmp(tag, "en")) return NEMO_UI_EN;
    if (!strcmp(tag, "zh-CN")) return NEMO_UI_ZH_CN;
    return -1;
}

const char *nemo_ui_language_tag(int value)
{
    return value == NEMO_UI_ZH_CN ? "zh-CN" : value == NEMO_UI_EN ? "en" : "system";
}

int nemo_ui_match_language(const char *tag)
{
    char lower[85];
    size_t i, n = strlen(tag);
    if (n >= sizeof(lower)) return NEMO_UI_SYSTEM;
    for (i = 0; i <= n; i++) lower[i] = (char)tolower((unsigned char)tag[i]);
    if (!strcmp(lower, "en") || !strncmp(lower, "en-", 3)) return NEMO_UI_EN;
    if (!strcmp(lower, "zh-cn") || !strcmp(lower, "zh-sg") ||
        !strcmp(lower, "zh-hans") || !strncmp(lower, "zh-hans-", 8))
        return NEMO_UI_ZH_CN;
    return NEMO_UI_SYSTEM;
}

void nemo_ui_set_language(int value) { language = value == NEMO_UI_ZH_CN ? value : NEMO_UI_EN; }
int nemo_ui_language(void) { return language; }

const char *nemo_ui_text(const char *id)
{
    size_t lo = 0, hi = sizeof(nemo_ui_catalog) / sizeof(nemo_ui_catalog[0]);
    while (lo < hi) {
        size_t mid = lo + (hi-lo)/2;
        int cmp = strcmp(id, nemo_ui_catalog[mid].id);
        if (cmp < 0) hi = mid;
        else if (cmp > 0) lo = mid+1;
        else return language == NEMO_UI_ZH_CN && *nemo_ui_catalog[mid].zh ?
            nemo_ui_catalog[mid].zh : nemo_ui_catalog[mid].en;
    }
    return id;
}

/* Values are copied once, never recursively expanded or used as printf formats. */
char *nemo_ui_format(const char *id, const char *key1, const char *value1,
                     const char *key2, const char *value2)
{
    const char *format = nemo_ui_text(id);
    char *result = NULL;
    size_t size = 0;
    for (int pass = 0; pass < 2; pass++) {
        const char *p = format;
        size_t pos = 0;
        while (*p) {
            const char *value = p;
            size_t count = 1, advance = 1;
            if (*p == '{') {
                const char *end = strchr(p+1, '}');
                if (end) {
                    size_t n = (size_t)(end-p-1);
                    if (key1 && strlen(key1) == n && !memcmp(p+1, key1, n)) value = value1;
                    else if (key2 && strlen(key2) == n && !memcmp(p+1, key2, n)) value = value2;
                    if (value != p) { count = strlen(value); advance = n+2; }
                }
            }
            if (pass) memcpy(result+pos, value, count);
            pos += count;
            p += advance;
        }
        if (!pass) {
            size = pos;
            result = malloc(size+1);
            if (!result) abort();
        }
    }
    result[size] = '\0';
    return result;
}

const char *nemo_ui_category(const char *path, const char *fallback)
{
    static const struct { const char *path, *id; } categories[] = {
        {"Profile", "category.profile"}, {"Profile/Logging", "category.logging"},
        {"Profile/Shell", "category.shell"}, {"Terminal", "category.terminal"},
        {"Terminal/Keyboard", "category.keyboard"}, {"Terminal/Keyboard/Extended", "category.extended"},
        {"Terminal/Bell", "category.bell"}, {"Terminal/Bell/Overload", "category.overload"},
        {"Terminal/Features", "category.features"}, {"Terminal/Screen queries", "category.screen_queries"},
        {"Terminal/Hyperlinks", "category.hyperlinks"}, {"Terminal/Clipboard", "category.clipboard"},
        {"Window", "category.window"}, {"Window/Language", "language.title"},
        {"Window/Rendering", "category.rendering"}, {"Window/Appearance", "category.appearance"},
        {"Window/Behaviour", "category.behaviour"}, {"Window/Translation", "category.encoding"},
        {"Window/Translation/Line drawing", "category.line_drawing"}, {"Window/Tabs", "category.tabs"},
        {"Window/Bindings", "category.bindings"}, {"Window/Bindings/Font", "category.font"},
        {"Window/Bindings/Commands", "category.commands"}, {"Window/Selection", "category.selection"},
        {"Window/Selection/Copy", "category.copy"}, {"Window/Colours", "category.colours"},
        {"Window/Colours/Attributes", "category.attributes"},
    };
    for (size_t i = 0; i < sizeof(categories)/sizeof(categories[0]); i++)
        if (!strcmp(path, categories[i].path)) return nemo_ui_text(categories[i].id);
    return fallback;
}
