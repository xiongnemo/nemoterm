/* SPDX-License-Identifier: MIT */
#include "nemo_pointer.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned checks;
#define CHECK(x) do { ++checks; if (!(x)) { \
    fprintf(stderr, "%s:%d: %s\n", __FILE__, __LINE__, #x); exit(1); \
} } while (0)

typedef struct PointerReference {
    const char *name;
    bool reset;
    const char *input;
    size_t input_length;
    const char *reply;
    size_t reply_length;
    const char *shape;
} PointerReference;
#include "pointer_shape_reference.h"

static void reference_cases(void)
{
    NemoPointerState state = {0};
    for (size_t i = 0; i < sizeof(pointer_reference)/sizeof(*pointer_reference); i++) {
        const PointerReference *r = &pointer_reference[i];
        if (r->reset) memset(&state, 0, sizeof(state));
        char actual[16384];
        size_t position = 0, output = 0;
        /* This is an OSC frame splitter for the complete-payload component,
         * not a substitute for replay through Nemoterm's VT parser. */
        while (position < r->input_length) {
            CHECK(r->input_length-position >= 5);
            CHECK(!memcmp(r->input+position, "\033]22;", 5));
            position += 5;
            size_t end = position;
            while (end < r->input_length && r->input[end] != '\007' &&
                   !(r->input[end] == '\033' && end+1 < r->input_length && r->input[end+1] == '\\'))
                ++end;
            CHECK(end < r->input_length);
            char reply[NEMO_POINTER_REPLY_MAX];
            size_t used = 0;
            NemoPointerResult result = nemo_pointer_command(&state, false,
                r->input+position, end-position, reply, sizeof(reply), &used);
            if (result == NEMO_POINTER_QUERY) {
                CHECK(output + 7 + used <= sizeof(actual));
                memcpy(actual+output, "\033]22;", 5); output += 5;
                memcpy(actual+output, reply, used); output += used;
                memcpy(actual+output, "\033\\", 2); output += 2;
            }
            position = end + (r->input[end] == '\007' ? 1u : 2u);
        }
        if (output != r->reply_length || memcmp(actual, r->reply, output) ||
            strcmp(nemo_pointer_name(nemo_pointer_current(&state, false)), r->shape)) {
            fprintf(stderr, "Independent pointer reference mismatch: %s\n", r->name);
            exit(1);
        }
        checks += 3;
    }
}

static void bounds_and_isolation(void)
{
    _Static_assert(sizeof(NemoPointerState) == 34, "Pointer state grew");
    NemoPointerState state = {0};
    CHECK(nemo_pointer_current(NULL, false) == NEMO_POINTER_NONE);
    CHECK(nemo_pointer_change(&state, false, '>', NEMO_POINTER_WAIT));
    CHECK(nemo_pointer_change(&state, true, '>', NEMO_POINTER_TEXT));
    CHECK(nemo_pointer_current(&state, false) == NEMO_POINTER_WAIT);
    CHECK(nemo_pointer_current(&state, true) == NEMO_POINTER_TEXT);
    NemoPointerState before = state;
    char reply[NEMO_POINTER_REPLY_MAX];
    size_t used = 99;
    CHECK(nemo_pointer_command(&state, false, "?__current__", 12,
        reply, 1, &used) == NEMO_POINTER_IGNORED);
    CHECK(used == 0 && !memcmp(&state, &before, sizeof(state)));
    CHECK(nemo_pointer_command(&state, false, "?__current__", 12,
        reply, sizeof(reply), &used) == NEMO_POINTER_QUERY);
    CHECK(used == 4 && !memcmp(reply, "wait", 4));
    CHECK(!memcmp(&state, &before, sizeof(state)));
    CHECK(nemo_pointer_command(&state, false, "text\0wait", 9,
        reply, sizeof(reply), &used) == NEMO_POINTER_IGNORED);
    CHECK(!memcmp(&state, &before, sizeof(state)));
    char large[NEMO_POINTER_OSC_MAX+1];
    memset(large, ',', sizeof(large)); large[0] = '?';
    CHECK(nemo_pointer_command(&state, false, large, sizeof(large),
        reply, sizeof(reply), &used) == NEMO_POINTER_IGNORED);
    CHECK(!memcmp(&state, &before, sizeof(state)));
    CHECK(nemo_pointer_command(&state, false, large, sizeof(large)-1,
        reply, sizeof(reply), &used) == NEMO_POINTER_QUERY);
    CHECK(used == 4095 && !memcmp(&state, &before, sizeof(state)));
    CHECK(nemo_pointer_command(NULL, false, "?__current__", 12,
        reply, sizeof(reply), &used) == NEMO_POINTER_QUERY);
    CHECK(used == 1 && reply[0] == '0');
}

int main(void)
{
    reference_cases();
    bounds_and_isolation();
    printf("Pointer component: %u checks; %zu independent stages; %zu state bytes\n",
           checks, sizeof(pointer_reference)/sizeof(*pointer_reference), sizeof(NemoPointerState));
    return 0;
}
