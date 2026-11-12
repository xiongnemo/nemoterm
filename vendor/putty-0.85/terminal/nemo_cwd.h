/* SPDX-License-Identifier: MIT */
#ifndef NEMO_CWD_H
#define NEMO_CWD_H

#define NEMO_CWD_PATH_MAX 4096
#define NEMO_CWD_HOST_MAX 255
#define NEMO_CWD_OSC_MAX 16384

typedef struct NemoCwd {
    char *path, *host; /* validated UTF-8 path, ASCII host; allocated on demand */
} NemoCwd;
void nemo_cwd_clear(NemoCwd *);
bool nemo_cwd_update(NemoCwd *, unsigned osc, const char *, size_t);
bool nemo_cwd_local(const NemoCwd *, const char *hostname, const char *fqdn);
char *nemo_cwd_uri(const NemoCwd *); /* caller owns result, NULL if unknown */
char *nemo_cwd_native(const NemoCwd *, const char *, const char *, bool msys);
size_t nemo_cwd_memory(const NemoCwd *);
#endif
