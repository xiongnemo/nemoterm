#ifndef NEMO_SHELL_H
#define NEMO_SHELL_H
#include "putty.h"

enum { NEMO_PWSH, NEMO_POWERSHELL, NEMO_BUSYBOX, NEMO_GIT_BASH,
       NEMO_WSL_BASH, NEMO_CMD, NEMO_SHELL_COUNT };
typedef struct NemoShellLocations {
    const wchar_t *system, *path, *scoop, *profile, *program_files,
        *program_files_x86, *local_app_data, *program_data, *git_install,
        *wsl_distribution;
} NemoShellLocations;
typedef struct NemoShellList {
    wchar_t *paths[NEMO_SHELL_COUNT];
    wchar_t *wsl_distribution;
} NemoShellList;
extern const char *const nemo_shell_ids[NEMO_SHELL_COUNT];
extern const char *const nemo_shell_names[NEMO_SHELL_COUNT];
void nemo_shell_detect_at(NemoShellList *, const NemoShellLocations *);
void nemo_shell_detect(NemoShellList *);
void nemo_shell_free(NemoShellList *);
int nemo_shell_index(const char *);
wchar_t *nemo_shell_command(const NemoShellList *, int);
wchar_t *nemo_shell_command_at(const NemoShellList *, int, const wchar_t *directory);
wchar_t *nemo_shell_git_environment(const wchar_t *);
wchar_t *nemo_shell_powershell_environment(void);
char *nemo_shell_json(const NemoShellList *);
#endif
