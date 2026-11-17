/* SPDX-License-Identifier: MIT
 * Decode the compiled export, independently of its Python serializer.
 * Run only on a GitHub-hosted runner, never on the development computer. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "nemo_tcap_database.inc"
#include "nemo_tcap_db.h"

#define COUNT(a) (sizeof(a) / sizeof(*(a)))
#define CHECK(c) do { if (!(c)) { \
    fprintf(stderr, "Invalid exported table at line %d: %s\n", __LINE__, #c); \
    exit(2); } } while (0)

static const char *string_at(uint32_t offset)
{
    CHECK(offset < sizeof(nemo_tcap_db_bytes));
    CHECK(memchr(nemo_tcap_db_bytes + offset, 0,
                 sizeof(nemo_tcap_db_bytes) - offset));
    return (const char *)nemo_tcap_db_bytes + offset;
}

static void hex(const char *s)
{
    for (; *s; s++) printf("%02x", (unsigned char)*s);
}

int main(void)
{
    const char *runner = getenv("RUNNER_ENVIRONMENT");
    CHECK(runner && !strcmp(runner, "github-hosted"));
    CHECK(nemo_tcap_db_find(NULL, 0) == -1);
    CHECK(nemo_tcap_db_find("no-such-nemoterm-database", 25) == -1);
    CHECK(nemo_tcap_db_value((unsigned)-1, "kf1") == NULL);
    CHECK(nemo_tcap_db_value(0, NULL) == NULL);
    CHECK(nemo_tcap_db_value(0, "no-such-nemoterm-capability") == NULL);
    for (size_t i = 0; i < COUNT(nemo_tcap_db_cap_names); i++) {
        const char *cap = string_at(nemo_tcap_db_cap_names[i]);
        if (i) CHECK(strcmp(string_at(nemo_tcap_db_cap_names[i-1]), cap) < 0);
        fputs("C\t", stdout); hex(cap); putchar('\n');
    }
    for (size_t i = 0; i < COUNT(nemo_tcap_db_names); i++) {
        const NemoTcapDbName *entry = &nemo_tcap_db_names[i];
        const char *name = string_at(entry->name);
        CHECK(entry->profile < COUNT(nemo_tcap_db_profiles));
        CHECK(nemo_tcap_db_find(name, strlen(name)) == (int)entry->profile);
        if (i) CHECK(strcmp(string_at(nemo_tcap_db_names[i-1].name), name) < 0);
        if (!strcmp(name, "xterm-256color")) CHECK(entry->profile == 0);
        const NemoTcapDbProfile *profile = &nemo_tcap_db_profiles[entry->profile];
        CHECK(profile->first <= COUNT(nemo_tcap_db_values));
        CHECK(profile->count <= COUNT(nemo_tcap_db_values) - profile->first);
        fputs("N\t", stdout); hex(name); putchar('\n');
        unsigned char present[COUNT(nemo_tcap_db_cap_names)] = {0};
        for (size_t j = 0; j < profile->count; j++) {
            const NemoTcapDbValue *value = &nemo_tcap_db_values[profile->first+j];
            CHECK(value->cap < COUNT(nemo_tcap_db_cap_names));
            present[value->cap] = 1;
            const char *runtime = nemo_tcap_db_value(entry->profile,
                string_at(nemo_tcap_db_cap_names[value->cap]));
            CHECK(runtime && !strcmp(runtime, string_at(value->value)));
            if (j) CHECK(nemo_tcap_db_values[profile->first+j-1].cap < value->cap);
            fputs("V\t", stdout); hex(name); putchar('\t');
            hex(string_at(nemo_tcap_db_cap_names[value->cap])); putchar('\t');
            hex(string_at(value->value)); putchar('\n');
        }
        for (size_t j = 0; j < COUNT(nemo_tcap_db_cap_names); j++)
            if (!present[j]) CHECK(nemo_tcap_db_value(entry->profile,
                string_at(nemo_tcap_db_cap_names[j])) == NULL);
    }
    CHECK(!ferror(stdout));
    return 0;
}
