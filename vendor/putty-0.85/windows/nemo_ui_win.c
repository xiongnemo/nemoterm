#include "putty.h"
#include "nemo_ui.h"

static const wchar_t preference_root[] = L"Software\\Nemo\\Nemoterm";

int nemo_ui_read_preference(void)
{
    wchar_t value[16];
    DWORD bytes = sizeof(value), type = 0;
    HKEY key;
    if (RegOpenKeyExW(HKEY_CURRENT_USER, preference_root, 0, KEY_QUERY_VALUE, &key) != ERROR_SUCCESS)
        return NEMO_UI_SYSTEM;
    LSTATUS status = RegQueryValueExW(key, L"UILanguage", NULL, &type, (BYTE *)value, &bytes);
    RegCloseKey(key);
    if (status != ERROR_SUCCESS || type != REG_SZ || bytes < sizeof(wchar_t) ||
        bytes > sizeof(value) || bytes % sizeof(wchar_t) || value[bytes/sizeof(wchar_t)-1])
        return NEMO_UI_SYSTEM;
    if (!wcscmp(value, L"en")) return NEMO_UI_EN;
    if (!wcscmp(value, L"zh-CN")) return NEMO_UI_ZH_CN;
    return NEMO_UI_SYSTEM;
}

unsigned long nemo_ui_save_preference(int preference)
{
    HKEY key;
    if (preference < NEMO_UI_SYSTEM || preference > NEMO_UI_ZH_CN) return ERROR_INVALID_PARAMETER;
    LSTATUS status = RegCreateKeyExW(HKEY_CURRENT_USER, preference_root, 0, NULL, 0,
                                    KEY_SET_VALUE, NULL, &key, NULL);
    if (status != ERROR_SUCCESS) return (unsigned long)status;
    const wchar_t *value = preference == NEMO_UI_ZH_CN ? L"zh-CN" : preference == NEMO_UI_EN ? L"en" : L"system";
    status = RegSetValueExW(key, L"UILanguage", 0, REG_SZ, (const BYTE *)value,
                           (DWORD)((wcslen(value)+1)*sizeof(wchar_t)));
    RegCloseKey(key);
    return (unsigned long)status;
}

void nemo_ui_init(int preference)
{
    if (preference != NEMO_UI_SYSTEM) { nemo_ui_set_language(preference); return; }
    ULONG count = 0, size = 0;
    nemo_ui_set_language(NEMO_UI_EN);
    if (!GetUserPreferredUILanguages(MUI_LANGUAGE_NAME, &count, NULL, &size) || !size) return;
    wchar_t *names = snewn(size, wchar_t);
    if (GetUserPreferredUILanguages(MUI_LANGUAGE_NAME, &count, names, &size)) {
        for (wchar_t *p = names; *p; p += wcslen(p)+1) {
            char *tag = dup_wc_to_mb(CP_UTF8, p, "");
            int selected = nemo_ui_match_language(tag);
            sfree(tag);
            if (selected != NEMO_UI_SYSTEM) { nemo_ui_set_language(selected); break; }
        }
    }
    sfree(names);
}

void nemo_ui_set_window_text(HWND window, const char *text)
{
    wchar_t *wide = dup_mb_to_wc(CP_UTF8, text ? text : "");
    SetWindowTextW(window, wide);
    sfree(wide);
}
void nemo_ui_set_item_text(HWND window, int id, const char *text)
{
    nemo_ui_set_window_text(GetDlgItem(window, id), text);
}
BOOL nemo_ui_append_menu(HMENU menu, UINT flags, UINT_PTR id, const char *text)
{
    wchar_t *wide = text ? dup_mb_to_wc(CP_UTF8, text) : NULL;
    BOOL result = AppendMenuW(menu, flags, id, wide);
    sfree(wide); return result;
}
BOOL nemo_ui_insert_menu(HMENU menu, UINT position, UINT flags, UINT_PTR id, const char *text)
{
    wchar_t *wide = text ? dup_mb_to_wc(CP_UTF8, text) : NULL;
    BOOL result = InsertMenuW(menu, position, flags, id, wide);
    sfree(wide); return result;
}
BOOL nemo_ui_modify_menu(HMENU menu, UINT position, UINT flags, UINT_PTR id, const char *text)
{
    wchar_t *wide = text ? dup_mb_to_wc(CP_UTF8, text) : NULL;
    BOOL result = ModifyMenuW(menu, position, flags, id, wide);
    sfree(wide); return result;
}
