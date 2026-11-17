#ifndef NEMOTERM_UI_H
#define NEMOTERM_UI_H

/* UI strings are UTF-8; user data and terminal/protocol strings are not translated. */
enum { NEMO_UI_SYSTEM, NEMO_UI_EN, NEMO_UI_ZH_CN };
int nemo_ui_parse_language(const char *tag);
const char *nemo_ui_language_tag(int language);
int nemo_ui_match_language(const char *tag);
void nemo_ui_set_language(int language);
int nemo_ui_language(void);
const char *nemo_ui_text(const char *id);
char *nemo_ui_format(const char *id, const char *key1, const char *value1,
                     const char *key2, const char *value2);
const char *nemo_ui_category(const char *path, const char *fallback);

#ifdef _WIN32
/* Include putty.h (Windows types) before this header in Win32 front ends. */
int nemo_ui_read_preference(void);
unsigned long nemo_ui_save_preference(int language);
void nemo_ui_init(int preference);
void nemo_ui_set_window_text(HWND window, const char *utf8);
void nemo_ui_set_item_text(HWND window, int id, const char *utf8);
BOOL nemo_ui_append_menu(HMENU menu, UINT flags, UINT_PTR id, const char *utf8);
BOOL nemo_ui_insert_menu(HMENU menu, UINT position, UINT flags, UINT_PTR id, const char *utf8);
BOOL nemo_ui_modify_menu(HMENU menu, UINT position, UINT flags, UINT_PTR id, const char *utf8);
#endif
#endif
