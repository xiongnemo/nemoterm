/* Installed local shells. Detection reads paths/registry; it launches nothing. */
#include "nemo_shell.h"
#include <wchar.h>

const char *const nemo_shell_ids[NEMO_SHELL_COUNT] = {
    "pwsh", "powershell", "busybox-ash", "git-bash", "wsl-bash", "cmd"
};
const char *const nemo_shell_names[NEMO_SHELL_COUNT] = {
    "PowerShell (pwsh)", "Windows PowerShell", "BusyBox ash", "Git Bash", "WSL Bash", "Command Prompt"
};

static bool absolute(const wchar_t *p)
{
    return p && ((p[0] && p[1] == L':' && (p[2] == L'\\' || p[2] == L'/')) ||
                 (p[0] == L'\\' && p[1] == L'\\'));
}
static bool exists(const wchar_t *p)
{
    DWORD a = GetFileAttributesW(p);
    return a != INVALID_FILE_ATTRIBUTES && !(a & FILE_ATTRIBUTE_DIRECTORY);
}
static void candidate(wchar_t **out, const wchar_t *base, const wchar_t *suffix)
{
    if (*out || !absolute(base)) return;
    wchar_t *p = dupwcscat(base, L"\\", suffix);
    if (exists(p)) *out = p; else sfree(p);
}
static void on_path(wchar_t **out, const wchar_t *path, const wchar_t *name)
{
    while (!*out && path && *path) {
        const wchar_t *end = wcschr(path, L';');
        size_t n = end ? (size_t)(end - path) : wcslen(path);
        const wchar_t *start = path;
        if (n >= 2 && start[0] == L'"' && start[n-1] == L'"') { start++; n -= 2; }
        wchar_t *part = snewn(n + 1, wchar_t);
        memcpy(part, start, n * sizeof(wchar_t)); part[n] = 0;
        candidate(out, part, name);
        sfree(part);
        path = end ? end + 1 : NULL;
    }
}
static void git_candidate(wchar_t **out, const wchar_t *base)
{
    if (*out || !absolute(base)) return;
    wchar_t *git = dupwcscat(base, L"\\cmd\\git.exe");
    if (exists(git)) candidate(out, base, L"bin\\bash.exe");
    sfree(git);
}

void nemo_shell_detect_at(NemoShellList *list, const NemoShellLocations *loc)
{
    memset(list, 0, sizeof(*list));
    wchar_t *scoop = loc->scoop && *loc->scoop ? dupwcs(loc->scoop) :
        dupwcscat(loc->profile ? loc->profile : L"", L"\\scoop");
    candidate(&list->paths[NEMO_PWSH], scoop, L"apps\\pwsh\\current\\pwsh.exe");
    candidate(&list->paths[NEMO_BUSYBOX], scoop, L"apps\\busybox\\current\\busybox.exe");
    on_path(&list->paths[NEMO_PWSH], loc->path, L"pwsh.exe");
    on_path(&list->paths[NEMO_BUSYBOX], loc->path, L"busybox.exe");
    candidate(&list->paths[NEMO_PWSH], loc->program_files, L"PowerShell\\7\\pwsh.exe");
    candidate(&list->paths[NEMO_PWSH], loc->local_app_data, L"Microsoft\\WindowsApps\\pwsh.exe");
    candidate(&list->paths[NEMO_POWERSHELL], loc->system, L"WindowsPowerShell\\v1.0\\powershell.exe");
    candidate(&list->paths[NEMO_CMD], loc->system, L"cmd.exe");
    git_candidate(&list->paths[NEMO_GIT_BASH], loc->git_install);
    wchar_t *git = dupwcscat(scoop, L"\\apps\\git\\current");
    git_candidate(&list->paths[NEMO_GIT_BASH], git); sfree(git);
    const wchar_t *roots[] = {loc->program_files, loc->program_files_x86, loc->local_app_data};
    for (size_t i = 0; i < lenof(roots); i++) if (roots[i]) {
        git = dupwcscat(roots[i], i == 2 ? L"\\Programs\\Git" : L"\\Git");
        git_candidate(&list->paths[NEMO_GIT_BASH], git); sfree(git);
    }
    /* Git's bin/cmd directory may be on PATH. Never classify bare bash.exe
     * (notably System32's WSL launcher) as Git Bash. */
    wchar_t *path_git = NULL;
    on_path(&path_git, loc->path, L"git.exe");
    if (path_git) {
        wchar_t *slash = wcsrchr(path_git, L'\\');
        if (slash) { *slash = 0; slash = wcsrchr(path_git, L'\\'); }
        if (slash) { *slash = 0; git_candidate(&list->paths[NEMO_GIT_BASH], path_git); }
        sfree(path_git);
    }
    if (loc->wsl_distribution && *loc->wsl_distribution) {
        candidate(&list->paths[NEMO_WSL_BASH], loc->system, L"wsl.exe");
        if (list->paths[NEMO_WSL_BASH]) list->wsl_distribution = dupwcs(loc->wsl_distribution);
    }
    sfree(scoop);
}

static wchar_t *environment(const wchar_t *name)
{
    DWORD n = GetEnvironmentVariableW(name, NULL, 0);
    if (!n) return NULL;
    wchar_t *p = snewn(n, wchar_t);
    DWORD got = GetEnvironmentVariableW(name, p, n);
    if (!got || got >= n) { sfree(p); return NULL; }
    return p;
}
static wchar_t *registry(HKEY hive, const wchar_t *path, const wchar_t *name)
{
    HKEY key;
    if (RegOpenKeyExW(hive, path, 0, KEY_READ, &key) != ERROR_SUCCESS) return NULL;
    DWORD bytes = 0, type;
    wchar_t *p = NULL;
    if (RegQueryValueExW(key, name, NULL, &type, NULL, &bytes) == ERROR_SUCCESS &&
        type == REG_SZ && bytes && bytes <= 65536) {
        p = snewn(bytes / sizeof(wchar_t) + 1, wchar_t);
        if (RegQueryValueExW(key, name, NULL, &type, (BYTE *)p, &bytes) != ERROR_SUCCESS) {
            sfree(p); p = NULL;
        } else p[bytes / sizeof(wchar_t)] = 0;
    }
    RegCloseKey(key);
    return p;
}
void nemo_shell_detect(NemoShellList *list)
{
    wchar_t system[MAX_PATH + 1];
    UINT n = GetSystemDirectoryW(system, lenof(system));
    if (!n || n >= lenof(system)) system[0] = 0;
    wchar_t *path = environment(L"PATH"), *scoop = environment(L"SCOOP"),
        *profile = environment(L"USERPROFILE"), *pf = environment(L"ProgramFiles"),
        *pfx86 = environment(L"ProgramFiles(x86)"), *local = environment(L"LOCALAPPDATA"),
        *data = environment(L"ProgramData");
    wchar_t *git = registry(HKEY_CURRENT_USER, L"SOFTWARE\\GitForWindows", L"InstallPath");
    if (!git) git = registry(HKEY_LOCAL_MACHINE, L"SOFTWARE\\GitForWindows", L"InstallPath");
    const wchar_t *lxss = L"Software\\Microsoft\\Windows\\CurrentVersion\\Lxss";
    wchar_t *id = registry(HKEY_CURRENT_USER, lxss, L"DefaultDistribution"), *distro = NULL;
    if (id) {
        wchar_t *key = dupwcscat(lxss, L"\\", id);
        distro = registry(HKEY_CURRENT_USER, key, L"DistributionName");
        sfree(key); sfree(id);
    }
    NemoShellLocations loc = {system,path,scoop,profile,pf,pfx86,local,data,git,distro};
    nemo_shell_detect_at(list, &loc);
    sfree(path); sfree(scoop); sfree(profile); sfree(pf); sfree(pfx86);
    sfree(local); sfree(data); sfree(git); sfree(distro);
}
void nemo_shell_free(NemoShellList *list)
{
    for (int i = 0; i < NEMO_SHELL_COUNT; i++) sfree(list->paths[i]);
    sfree(list->wsl_distribution);
    memset(list, 0, sizeof(*list));
}
int nemo_shell_index(const char *id)
{
    for (int i = 0; i < NEMO_SHELL_COUNT; i++) if (!strcmp(id, nemo_shell_ids[i])) return i;
    return -1;
}
/* Quote a single Windows argv element, including trailing slash/quote cases. */
static wchar_t *quote(const wchar_t *text)
{
    wchar_t *out = snewn(wcslen(text) * 2 + 3, wchar_t), *p = out;
    *p++ = L'"';
    while (*text) {
        size_t slashes = 0;
        while (*text == L'\\') { slashes++; text++; }
        size_t count = (*text == L'"' || !*text) ? slashes * 2 : slashes;
        while (count--) *p++ = L'\\';
        if (*text == L'"') *p++ = L'\\';
        if (*text) *p++ = *text++;
    }
    *p++ = L'"'; *p = 0; return out;
}
wchar_t *nemo_shell_command(const NemoShellList *list, int which)
{ return nemo_shell_command_at(list, which, NULL); }
wchar_t *nemo_shell_command_at(const NemoShellList *list, int which, const wchar_t *directory)
{
    if (which < 0 || which >= NEMO_SHELL_COUNT || !list->paths[which]) return NULL;
    wchar_t *exe = quote(list->paths[which]), *out;
    const wchar_t *args[] = {L" -NoLogo",L" -NoLogo",L" ash -i",L" --login -i",L"",L""};
    if (which == NEMO_WSL_BASH) {
        /* Old inbox WSL treats unnecessary quotes around a simple distro
         * name literally. Preserve the conventional unquoted argv spelling. */
        wchar_t *distro = wcspbrk(list->wsl_distribution, L" \t\n\v\"") ?
            quote(list->wsl_distribution) : dupwcs(list->wsl_distribution);
        wchar_t *dir = directory && *directory ? quote(directory) : NULL;
        out = dupwcscat(exe, L" --distribution ", distro,
                       dir ? L" --cd " : L"", dir ? dir : L"", L" --exec bash --login -i");
        sfree(dir);
        sfree(distro);
    } else if (which == NEMO_GIT_BASH && directory && directory[0] == L'/') {
        /* MSYS owns its mount table (/tmp is often Windows TEMP). Pass the
         * path as one positional argument to fixed shell code, never as code.
         * CHERE_INVOKING keeps the login profile in the selected directory. */
        wchar_t *code=quote(L"cd -- \"$1\" && exec /usr/bin/bash --login -i");
        wchar_t *dir=quote(directory);
        out=dupwcscat(exe,L" -c ",code,L" nemoterm ",dir);
        sfree(code);sfree(dir);
    } else out = dupwcscat(exe, args[which]);
    sfree(exe); return out;
}

static int compare_env(const void *a, const void *b)
{ return _wcsicmp(*(const wchar_t *const *)a, *(const wchar_t *const *)b); }
wchar_t *nemo_shell_git_environment(const wchar_t *bash)
{
    wchar_t *root = dupwcs(bash), *slash = wcsrchr(root, L'\\');
    if (slash) { *slash = 0; slash = wcsrchr(root, L'\\'); if (slash) *slash = 0; }
    wchar_t *check = dupwcscat(root, L"\\mingw64\\bin\\git.exe");
    const wchar_t *msystem = exists(check) ? L"MSYSTEM=MINGW64" : L"MSYSTEM=MINGW32";
    sfree(check);
    check = dupwcscat(root, L"\\clangarm64\\bin\\git.exe");
    if (exists(check)) msystem = L"MSYSTEM=CLANGARM64";
    sfree(check); sfree(root);
    wchar_t *original = GetEnvironmentStringsW();
    size_t count = 0, chars = 2;
    for (wchar_t *p = original; p && *p; p += wcslen(p) + 1) count++;
    const wchar_t **items = snewn(count + 2, const wchar_t *);
    count = 0;
    for (wchar_t *p = original; p && *p; p += wcslen(p) + 1) {
        if (!_wcsnicmp(p, L"MSYSTEM=", 8) || !_wcsnicmp(p, L"CHERE_INVOKING=", 15)) continue;
        items[count++] = p;
    }
    items[count++] = msystem; items[count++] = L"CHERE_INVOKING=1";
    qsort(items, count, sizeof(*items), compare_env);
    for (size_t i = 0; i < count; i++) chars += wcslen(items[i]) + 1;
    wchar_t *block = snewn(chars, wchar_t), *p = block;
    for (size_t i = 0; i < count; i++) { size_t n = wcslen(items[i]) + 1; memcpy(p, items[i], n * sizeof(*p)); p += n; }
    *p = 0;
    if (original) FreeEnvironmentStringsW(original);
    sfree(items); return block;
}

static void json_string(strbuf *out, const char *s)
{
    put_byte(out, '"');
    for (; *s; s++) {
        unsigned char c = (unsigned char)*s;
        if (c == '"' || c == '\\') put_byte(out, '\\');
        if (c < 32) put_fmt(out, "\\u%04x", c); else put_byte(out, c);
    }
    put_byte(out, '"');
}
char *nemo_shell_json(const NemoShellList *list)
{
    strbuf *out = strbuf_new(); put_byte(out, '[');
    for (int i = 0; i < NEMO_SHELL_COUNT; i++) {
        if (i) put_byte(out, ',');
        put_fmt(out, "{\"id\":\"%s\",\"name\":\"%s\",\"available\":%s,\"path\":",
                    nemo_shell_ids[i], nemo_shell_names[i], list->paths[i] ? "true" : "false");
        char *path = dup_wc_to_mb(CP_UTF8, list->paths[i] ? list->paths[i] : L"", NULL);
        json_string(out, path); sfree(path);
        put_data(out, ",\"command\":", 11);
        wchar_t *wide_command = nemo_shell_command(list, i);
        char *command = dup_wc_to_mb(CP_UTF8, wide_command ? wide_command : L"", NULL);
        json_string(out, command); sfree(command); sfree(wide_command);
        put_byte(out, '}');
    }
    put_data(out, "]\n", 2); return strbuf_to_str(out);
}
