#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#endif
#include "nemo_ui.h"

int main(void)
{
    assert(nemo_ui_parse_language("system") == NEMO_UI_SYSTEM);
    assert(nemo_ui_parse_language("zh-CN") == NEMO_UI_ZH_CN);
    assert(nemo_ui_parse_language("fr") == -1);
    assert(nemo_ui_match_language("zh-Hans-SG") == NEMO_UI_ZH_CN);
    assert(nemo_ui_match_language("ZH-cn") == NEMO_UI_ZH_CN);
    assert(nemo_ui_match_language("zh-TW") == NEMO_UI_SYSTEM);
    assert(nemo_ui_match_language("zh-Hant-CN") == NEMO_UI_SYSTEM);
    assert(nemo_ui_match_language("en-AU") == NEMO_UI_EN);
    assert(nemo_ui_match_language("fr-FR") == NEMO_UI_SYSTEM);
    nemo_ui_set_language(NEMO_UI_EN);
    assert(!strcmp(nemo_ui_text("common.cancel"), "Cancel"));
    assert(!strcmp(nemo_ui_text("missing.id"), "missing.id"));
    const char *name = "profile %s {app} / \xe4\xb8\xad\xe6\x96\x87";
    char *text = nemo_ui_format("settings.title", "profile", name, "app", "Nemoterm");
    assert(!strcmp(text, "Nemoterm - Profile: profile %s {app} / \xe4\xb8\xad\xe6\x96\x87"));
    free(text);
    nemo_ui_set_language(NEMO_UI_ZH_CN);
    assert(!strcmp(nemo_ui_text("common.cancel"), "\xe5\x8f\x96\xe6\xb6\x88"));
    text = nemo_ui_format("settings.title", "app", "Nemoterm", "profile", name);
    assert(strstr(text, name));
    free(text);
    assert(!strcmp(nemo_ui_category("Window/Language", "Language"), nemo_ui_text("language.title")));
    assert(!strcmp(nemo_ui_category("Unknown", "user text"), "user text"));
    puts("UI language matching, lookup, named formatting and user-data preservation passed");
    return 0;
}
