#define main upstream_terminal_test_main
#include "../../test/test_terminal.c"
#undef main
#include "nemo_shell.h"
#include <psapi.h>

static SIZE_T private_commit(void)
{
    typedef BOOL (WINAPI *MemoryInfo)(HANDLE,PPROCESS_MEMORY_COUNTERS,DWORD);
    MemoryInfo get_info=(MemoryInfo)GetProcAddress(GetModuleHandleW(L"kernel32.dll"),
                                                 "K32GetProcessMemoryInfo");
    assert(get_info);
    PROCESS_MEMORY_COUNTERS_EX info={0};info.cb=sizeof(info);
    assert(get_info(GetCurrentProcess(),(PPROCESS_MEMORY_COUNTERS)&info,sizeof(info)));
    return info.PrivateUsage;
}

static void long_conversion(void)
{
    wchar_t text[4097];
    for (size_t i=0;i<4096;i++) text[i]=0x4e2d;
    text[4096]=0;
    char *encoded=dup_wc_to_mb(CP_UTF8,text,NULL);
    assert(strlen(encoded)==4096*3);
    wchar_t *decoded=dup_mb_to_wc(CP_UTF8,encoded);
    assert(!wcscmp(text,decoded));
    sfree(encoded);sfree(decoded);
}

static wchar_t *created[64];
static size_t ncreated;
static void fake_file(const wchar_t *root, const wchar_t *suffix)
{
    wchar_t *path = dupwcscat(root, L"\\", suffix);
    for (wchar_t *p = path + wcslen(root) + 1; *p; p++) if (*p == L'\\') {
        *p = 0;
        if (CreateDirectoryW(path, NULL)) created[ncreated++] = dupwcs(path);
        *p = L'\\';
    }
    HANDLE h = CreateFileW(path, GENERIC_WRITE, 0, NULL, CREATE_NEW, 0, NULL);
    assert(h != INVALID_HANDLE_VALUE); CloseHandle(h);
    created[ncreated++] = path;
    assert(ncreated < lenof(created));
}
int main(void)
{
    /* A Windows font codepage distinct from UTF-8 must not cause init_ucs
     * to register a single-byte reverse map for a multibyte encoding. This
     * affects Unicode paths/titles converted after a terminal is created. */
    Conf *conversion_conf=conf_new();
    conf_set_str(conversion_conf,CONF_line_codepage,"UTF-8");
    conf_set_int(conversion_conf,CONF_vtmode,VT_XWINDOWS);
    struct unicode_data conversion_ucs={0};conversion_ucs.font_codepage=1252;
    init_ucs(conversion_conf,&conversion_ucs);
    const wchar_t conversion_wide[]={0x41,0xe9,0x4e2d,0xd83d,0xde00,0};
    const char conversion_utf8[]="A\xc3\xa9\xe4\xb8\xad\xf0\x9f\x98\x80";
    char *converted=dup_wc_to_mb(CP_UTF8,conversion_wide,NULL);
    if (strcmp(converted,conversion_utf8)) {
        fputs("UTF-8 conversion lost characters after non-UTF-8 font initialization\n",stderr);
        return 1;
    }
    wchar_t *roundtrip=dup_mb_to_wc(CP_UTF8,converted);
    assert(!wcscmp(roundtrip,conversion_wide));
    sfree(roundtrip);sfree(converted);conf_free(conversion_conf);

    /* Exercise both heap-backed conversion directions after warming their
     * allocator size classes. Leaking the temporary buffers grows > 20 MiB;
     * allow 8 MiB for allocator retention without trimming the process. */
    for (int i=0;i<16;i++) long_conversion();
    SIZE_T conversion_before=private_commit();
    for (int i=0;i<1000;i++) long_conversion();
    SIZE_T conversion_after=private_commit();
    printf("1000 long UTF-8 round trips: private commit %llu -> %llu bytes\n",
           (unsigned long long)conversion_before,(unsigned long long)conversion_after);
    if (conversion_after>conversion_before+8*1024*1024) {
        fputs("Character conversion retains temporary buffers\n",stderr);
        return 1;
    }

    wchar_t temp[MAX_PATH], base[MAX_PATH];
    assert(GetTempPathW(lenof(temp), temp));
    assert(GetTempFileNameW(temp, L"nsh", 0, base));
    assert(DeleteFileW(base)); assert(CreateDirectoryW(base, NULL));
    wchar_t *root = dupwcscat(base, L"\\shell space \x4e2d");
    assert(CreateDirectoryW(root, NULL));
    fake_file(root, L"cmd.exe");
    fake_file(root, L"WindowsPowerShell\\v1.0\\powershell.exe");
    fake_file(root, L"bash.exe");
    fake_file(root, L"wsl.exe");
    NemoShellLocations loc = {0};
    loc.system = root; loc.path = root;
    NemoShellList list;
    nemo_shell_detect_at(&list, &loc);
    assert(list.paths[NEMO_POWERSHELL] && list.paths[NEMO_CMD]);
    assert(!list.paths[NEMO_PWSH] && !list.paths[NEMO_GIT_BASH] && !list.paths[NEMO_WSL_BASH]);
    nemo_shell_free(&list);

    fake_file(root, L"apps\\pwsh\\current\\pwsh.exe");
    fake_file(root, L"apps\\busybox\\current\\busybox.exe");
    fake_file(root, L"apps\\git\\current\\cmd\\git.exe");
    fake_file(root, L"apps\\git\\current\\bin\\bash.exe");
    fake_file(root, L"apps\\git\\current\\mingw64\\bin\\git.exe");
    loc.scoop = root; loc.path = L""; loc.wsl_distribution = L"Debian Space";
    nemo_shell_detect_at(&list, &loc);
    for (int i = 0; i < NEMO_SHELL_COUNT; i++) {
        assert(list.paths[i]);
        wchar_t *command = nemo_shell_command(&list, i);
        assert(command && command[0] == L'"');
        if (i == NEMO_BUSYBOX) assert(wcsstr(command, L"\" ash -i"));
        if (i == NEMO_WSL_BASH) assert(wcsstr(command, L"--distribution \"Debian Space\" --exec bash --login -i"));
        sfree(command);
    }
    assert(!nemo_shell_command(&list, -1));
    assert(!nemo_shell_command(&list, NEMO_SHELL_COUNT));
    const wchar_t *directories[]={ L"/tmp/space \x4e2d;$(echo nope)",
        L"C:\\Unicode \x4e2d\\", L"/tmp/quote\"slash\\end" };
    for (size_t i=0;i<lenof(directories);i++) {
        wchar_t *command=nemo_shell_command_at(&list,NEMO_WSL_BASH,directories[i]);
        int argc;wchar_t **argv=CommandLineToArgvW(command,&argc);
        assert(argv && argc==9);
        assert(!wcscmp(argv[3],L"--cd") && !wcscmp(argv[4],directories[i]));
        assert(!wcscmp(argv[5],L"--exec") && !wcscmp(argv[8],L"-i"));
        LocalFree(argv);sfree(command);
        if (directories[i][0]==L'/') {
            command=nemo_shell_command_at(&list,NEMO_GIT_BASH,directories[i]);
            argv=CommandLineToArgvW(command,&argc);
            assert(argv && argc==5);
            assert(!wcscmp(argv[1],L"-c"));
            assert(!wcscmp(argv[2],L"cd -- \"$1\" && exec /usr/bin/bash --login -i"));
            assert(!wcscmp(argv[4],directories[i]));
            LocalFree(argv);sfree(command);
        }
    }
    char *json = nemo_shell_json(&list);
    assert(strstr(json, "busybox-ash") && strstr(json, "\xe4\xb8\xad"));
    sfree(json);
    SetEnvironmentVariableW(L"MSYSTEM", L"UCRT64");
    SetEnvironmentVariableW(L"CHERE_INVOKING", L"0");
    wchar_t *env = nemo_shell_git_environment(list.paths[NEMO_GIT_BASH]);
    int systems = 0, chere = 0;
    for (const wchar_t *p = env; *p; p += wcslen(p) + 1) {
        if (!_wcsnicmp(p, L"MSYSTEM=", 8)) { systems++; assert(!wcscmp(p, L"MSYSTEM=MINGW64")); }
        if (!_wcsnicmp(p, L"CHERE_INVOKING=", 15)) { chere++; assert(!wcscmp(p, L"CHERE_INVOKING=1")); }
    }
    assert(systems == 1 && chere == 1);
    wchar_t actual[32]; GetEnvironmentVariableW(L"MSYSTEM", actual, lenof(actual));
    assert(!wcscmp(actual, L"UCRT64"));
    sfree(env); nemo_shell_free(&list);

    /* Filtering is child-local and exact: mixed casing, a similar variable,
     * Unicode values and every unrelated/hidden environment entry survive. */
    for (int present = 0; present < 2; present++) {
        assert(SetEnvironmentVariableW(L"pSmOdUlEpAtH", present ? L"Core;custom \x4e2d" : NULL));
        assert(SetEnvironmentVariableW(L"PSModulePathExtra", L"keep \x4e2d"));
        wchar_t *before = GetEnvironmentStringsW();
        env = nemo_shell_powershell_environment();
        assert(before && env);
        const wchar_t *next = env;
        size_t original_chars = 1;
        for (const wchar_t *p = before; *p; p += wcslen(p) + 1) {
            original_chars += wcslen(p) + 1;
            if (!_wcsnicmp(p, L"PSModulePath=", 13)) continue;
            assert(!wcscmp(p, next)); next += wcslen(next) + 1;
        }
        assert(!*next);
        wchar_t *after = GetEnvironmentStringsW();
        assert(after && !memcmp(before, after, original_chars * sizeof(wchar_t)));
        FreeEnvironmentStringsW(before); FreeEnvironmentStringsW(after); sfree(env);
    }
    while (ncreated) {
        wchar_t *p = created[--ncreated];
        if (GetFileAttributesW(p) & FILE_ATTRIBUTE_DIRECTORY) assert(RemoveDirectoryW(p));
        else assert(DeleteFileW(p));
        sfree(p);
    }
    assert(RemoveDirectoryW(root)); sfree(root); assert(RemoveDirectoryW(base));
    puts("Shell detection, Unicode command quoting and child environment suite passed");
    return 0;
}
