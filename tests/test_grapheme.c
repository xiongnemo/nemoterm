/* SPDX-License-Identifier: MIT */
#include "nemo_grapheme.h"
#ifdef NDEBUG
#undef NDEBUG
#endif
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Read Unicode's actual test vectors; do not duplicate generated properties
 * in an implementation-shaped oracle. Test every possible input chunk split. */
static unsigned conformance(const char *path)
{
    FILE *f = fopen(path, "rb");
    if (!f) { perror(path); exit(1); }
    char line[8192];
    unsigned cases = 0, number = 0;
    while (fgets(line, sizeof(line), f)) {
        number++;
        char *comment = strchr(line, '#');
        if (comment) *comment = 0;
        uint32_t cp[256]; bool boundaries[257]; size_t count = 0;
        char *p = strtok(line, " \t\r\n");
        if (!p) continue;
        while (p) {
            if (count >= 256) { fprintf(stderr, "Overlong vector %u\n", number); exit(1); }
            if (!strcmp(p, "\xc3\xb7")) boundaries[count] = true;
            else if (!strcmp(p, "\xc3\x97")) boundaries[count] = false;
            else { fprintf(stderr, "Bad boundary marker on line %u\n", number); exit(1); }
            p = strtok(NULL, " \t\r\n");
            if (!p) break;
            char *end;
            unsigned long value = strtoul(p, &end, 16);
            if (*end || value > 0x10ffff) exit(1);
            cp[count++] = (uint32_t)value;
            p = strtok(NULL, " \t\r\n");
        }
        assert(count && boundaries[0] && boundaries[count]);
        for (size_t split = 0; split <= count; split++) {
            NemoGraphemeState state = {0};
            for (size_t chunk = 0; chunk < 2; chunk++) {
                size_t start = chunk ? split : 0, end = chunk ? count : split;
                for (size_t i = start; i < end; i++) {
                    bool got = nemo_grapheme_feed(&state, cp[i]);
                    if (got != boundaries[i]) {
                        fprintf(stderr, "UAX29 line %u scalar %zu U+%04lX: expected %s, got %s\n",
                            number, i, (unsigned long)cp[i], boundaries[i] ? "break" : "join",
                            got ? "break" : "join");
                        exit(1);
                    }
                }
            }
        }
        cases++;
    }
    assert(!ferror(f)); fclose(f);
    return cases;
}

int main(int argc, char **argv)
{
    if (argc != 2) { fprintf(stderr, "usage: test_grapheme GraphemeBreakTest.txt\n"); return 1; }
    unsigned cases = conformance(argv[1]);
    assert(cases > 500);
    NemoGraphemeState s = {0};
    assert(sizeof(s) <= 8);
    assert(nemo_grapheme_feed(&s, 0x1f469));
    for (unsigned i = 0; i < 1000000; i++) assert(!nemo_grapheme_feed(&s, 0x301));
    assert(!nemo_grapheme_feed(&s, 0x200d));
    assert(!nemo_grapheme_feed(&s, 0x1f4bb));
    nemo_grapheme_reset(&s);
    for (unsigned i = 0; i < 1000000; i++)
        assert(nemo_grapheme_feed(&s, 0x1f1e6) == !(i & 1));
    for (uint32_t invalid = 0xd800; invalid <= 0xdfff; invalid++) {
        assert(nemo_grapheme_feed(&s, invalid));
        assert(nemo_grapheme_feed(&s, 0x301));
    }
    assert(nemo_grapheme_feed(&s, 0x110000));
    assert(nemo_grapheme_feed(&s, 0xffffffff));
    assert(nemo_grapheme_feed(&s, 'a'));
    assert(!nemo_grapheme_feed(&s, 0x301));
    nemo_grapheme_reset(&s);
    assert(nemo_grapheme_feed(&s, 0x301));
    NemoGraphemeWidth width = {0};
    assert(nemo_grapheme_cell_width(&width, 0x2764, 1) == 1);
    assert(nemo_grapheme_cell_width(&width, 0xfe0f, 0) == 2);
    assert(nemo_grapheme_cell_width(&width, 0xfe0e, 0) == 2); /* no shrinking */
    width = (NemoGraphemeWidth){0};
    assert(nemo_grapheme_cell_width(&width, 'e', 1) == 1);
    assert(nemo_grapheme_cell_width(&width, 0xfe0f, 0) == 1); /* not emoji eligible */
    width = (NemoGraphemeWidth){0};
    assert(nemo_grapheme_cell_width(&width, 0x1f1e6, 1) == 2);
    assert(nemo_grapheme_cell_width(&width, 0x1f1fa, 1) == 2);
    width = (NemoGraphemeWidth){0};
    assert(nemo_grapheme_cell_width(&width, 0x4e2d, 1) == 2); /* pinned EAW */
    width = (NemoGraphemeWidth){0};
    assert(nemo_grapheme_cell_width(&width, 0x3b1, 2) == 2); /* caller's ambiguous policy */
    printf("UAX29 Unicode 18.0.0: %u official vectors, all chunk splits, bounded long streams and invalid scalars passed\n", cases);
    return 0;
}
