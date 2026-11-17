/* SPDX-License-Identifier: MIT */
#include <string.h>
#include "nemo_tcap_db.h"
#include "../../terminfo/nemo_tcap_database.inc"

#define COUNT(a) (sizeof(a) / sizeof(*(a)))
#define STRING(offset) ((const char *)nemo_tcap_db_bytes + (offset))

int nemo_tcap_db_find(const char *name, size_t length)
{
    if (!name || !length) return -1;
    size_t low = 0, high = COUNT(nemo_tcap_db_names);
    while (low < high) {
        size_t mid = low + (high-low)/2;
        const char *candidate = STRING(nemo_tcap_db_names[mid].name);
        size_t n = strlen(candidate), common = n < length ? n : length;
        int order = memcmp(name, candidate, common);
        if (!order) order = length < n ? -1 : length > n ? 1 : 0;
        if (!order) return (int)nemo_tcap_db_names[mid].profile;
        if (order < 0) high = mid; else low = mid+1;
    }
    return -1;
}

const char *nemo_tcap_db_value(unsigned profile, const char *capability)
{
    if (profile >= COUNT(nemo_tcap_db_profiles) || !capability) return NULL;
    size_t low = 0, high = COUNT(nemo_tcap_db_cap_names), cap;
    while (low < high) {
        size_t mid = low + (high-low)/2;
        int order = strcmp(capability, STRING(nemo_tcap_db_cap_names[mid]));
        if (!order) { low = mid; break; }
        if (order < 0) high = mid; else low = mid+1;
    }
    if (low == COUNT(nemo_tcap_db_cap_names) ||
        strcmp(capability, STRING(nemo_tcap_db_cap_names[low]))) return NULL;
    cap = low;
    const NemoTcapDbProfile *p = &nemo_tcap_db_profiles[profile];
    low = p->first; high = low+p->count;
    while (low < high) {
        size_t mid = low + (high-low)/2;
        const NemoTcapDbValue *v = &nemo_tcap_db_values[mid];
        if (cap == v->cap) return STRING(v->value);
        if (cap < v->cap) high = mid; else low = mid+1;
    }
    return NULL;
}
