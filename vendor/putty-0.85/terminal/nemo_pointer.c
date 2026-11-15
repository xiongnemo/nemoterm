/* SPDX-License-Identifier: MIT */
#include "nemo_pointer.h"
#include <string.h>

static const char *const names[] = {
    "0",
#define NEMO_POINTER_NAME(id, name) name,
    NEMO_POINTER_SHAPES(NEMO_POINTER_NAME)
#undef NEMO_POINTER_NAME
};

NemoPointerShape nemo_pointer_current(const NemoPointerState *state, bool alternate)
{
    if (!state || !state->count[alternate]) return NEMO_POINTER_NONE;
    return (NemoPointerShape)state->stack[alternate][state->count[alternate]-1];
}

const char *nemo_pointer_name(NemoPointerShape shape)
{
    return (unsigned)shape < NEMO_POINTER_SHAPE_COUNT ? names[shape] : "0";
}

NemoPointerShape nemo_pointer_lookup(const char *name, size_t length)
{
    if (!name || !length || length > 32) return NEMO_POINTER_NONE;
    for (unsigned i = 1; i < NEMO_POINTER_SHAPE_COUNT; i++)
        if (strlen(names[i]) == length && !memcmp(name, names[i], length))
            return (NemoPointerShape)i;
    return NEMO_POINTER_NONE;
}

static bool equal_name(const char *name, size_t length, const char *literal)
{
    return strlen(literal) == length && !memcmp(name, literal, length);
}

static NemoPointerShape setter_shape(const char *name, size_t length)
{
    static const struct { const char *name; NemoPointerShape shape; } aliases[] = {
        {"arrow", NEMO_POINTER_DEFAULT}, {"left_ptr", NEMO_POINTER_DEFAULT},
        {"xterm", NEMO_POINTER_TEXT}, {"ibeam", NEMO_POINTER_TEXT},
        {"beam", NEMO_POINTER_TEXT}, {"hand", NEMO_POINTER_POINTER},
        {"hand2", NEMO_POINTER_POINTER}, {"pointing_hand", NEMO_POINTER_POINTER},
        {"hand1", NEMO_POINTER_GRAB}, {"openhand", NEMO_POINTER_GRAB},
        {"closedhand", NEMO_POINTER_GRABBING}, {"dnd-none", NEMO_POINTER_GRABBING},
        {"question_arrow", NEMO_POINTER_HELP}, {"whats_this", NEMO_POINTER_HELP},
        {"clock", NEMO_POINTER_WAIT}, {"watch", NEMO_POINTER_WAIT},
        {"half-busy", NEMO_POINTER_PROGRESS}, {"left_ptr_watch", NEMO_POINTER_PROGRESS},
        {"tcross", NEMO_POINTER_CROSSHAIR}, {"plus", NEMO_POINTER_CELL},
        {"cross", NEMO_POINTER_CELL}, {"fleur", NEMO_POINTER_MOVE},
        {"pointer-move", NEMO_POINTER_MOVE}, {"right_side", NEMO_POINTER_E_RESIZE},
        {"top_right_corner", NEMO_POINTER_NE_RESIZE},
        {"top_left_corner", NEMO_POINTER_NW_RESIZE}, {"top_side", NEMO_POINTER_N_RESIZE},
        {"bottom_right_corner", NEMO_POINTER_SE_RESIZE},
        {"bottom_left_corner", NEMO_POINTER_SW_RESIZE}, {"bottom_side", NEMO_POINTER_S_RESIZE},
        {"left_side", NEMO_POINTER_W_RESIZE}, {"sb_h_double_arrow", NEMO_POINTER_EW_RESIZE},
        {"sb_v_double_arrow", NEMO_POINTER_NS_RESIZE}, {"size_bdiag", NEMO_POINTER_NESW_RESIZE},
        {"size_fdiag", NEMO_POINTER_NWSE_RESIZE}, {"dnd-link", NEMO_POINTER_ALIAS},
        {"dnd-copy", NEMO_POINTER_COPY}, {"forbidden", NEMO_POINTER_NOT_ALLOWED},
        {"crossed_circle", NEMO_POINTER_NOT_ALLOWED}, {"dnd-no-drop", NEMO_POINTER_NO_DROP}
    };
    NemoPointerShape shape = nemo_pointer_lookup(name, length);
    if (shape) return shape;
    for (size_t i = 0; i < sizeof(aliases)/sizeof(*aliases); i++)
        if (equal_name(name, length, aliases[i].name)) return aliases[i].shape;
    return NEMO_POINTER_NONE;
}

bool nemo_pointer_change(NemoPointerState *state, bool alternate, char operation,
                         NemoPointerShape shape)
{
    if (!state || (operation != '=' && operation != '>' && operation != '<') ||
        (operation != '<' && (unsigned)shape >= NEMO_POINTER_SHAPE_COUNT))
        return false;
    uint8_t *count = &state->count[alternate];
    uint8_t *stack = state->stack[alternate];
    if (operation == '<') {
        if (*count) stack[--*count] = 0;
    } else {
        if (operation == '>') {
            if (*count == NEMO_POINTER_STACK_MAX) {
                memmove(stack, stack+1, NEMO_POINTER_STACK_MAX-1);
                --*count;
            }
            ++*count;
        } else if (!*count) {
            *count = 1;
        }
        stack[*count-1] = (uint8_t)shape;
    }
    return true;
}

NemoPointerResult nemo_pointer_command(NemoPointerState *state, bool alternate,
    const char *payload, size_t length, char *reply, size_t capacity, size_t *used)
{
    if (!used) return NEMO_POINTER_IGNORED;
    *used = 0;
    if (!payload || length > NEMO_POINTER_OSC_MAX || memchr(payload, 0, length))
        return NEMO_POINTER_IGNORED;
    char operation = '=';
    if (length && (payload[0] == '=' || payload[0] == '>' ||
                   payload[0] == '<' || payload[0] == '?')) {
        operation = *payload++;
        --length;
    }
    if (operation == '<') {
        if (state) nemo_pointer_change(state, alternate, '<', NEMO_POINTER_NONE);
        return NEMO_POINTER_APPLIED;
    }
    if (operation != '?' && !state) return NEMO_POINTER_IGNORED;
    size_t start = 0, output = 0;
    bool applied = false, first = true;
    do {
        size_t end = start;
        while (end < length && payload[end] != ',') ++end;
        const char *name = payload + start;
        size_t size = end - start;
        if (operation == '?') {
            const char *answer = "0";
            if (nemo_pointer_lookup(name, size) || equal_name(name, size, "arrow") ||
                equal_name(name, size, "beam") || equal_name(name, size, "hand"))
                answer = "1";
            else if (equal_name(name, size, "__current__"))
                answer = nemo_pointer_name(nemo_pointer_current(state, alternate));
            else if (equal_name(name, size, "__default__"))
                answer = "text";
            else if (equal_name(name, size, "__grabbed__"))
                answer = "default";
            size_t count = strlen(answer);
            size_t separator = first ? 0 : 1;
            if (!reply || capacity - output < count + separator)
                return NEMO_POINTER_IGNORED;
            if (separator) reply[output++] = ',';
            memcpy(reply + output, answer, count);
            output += count;
        } else {
            NemoPointerShape shape = setter_shape(name, size);
            if (shape || (!size && operation == '=')) {
                nemo_pointer_change(state, alternate, operation, shape);
                applied = true;
            }
        }
        first = false;
        if (end == length) break;
        start = end + 1;
    } while (true);
    if (operation == '?') {
        *used = output;
        return NEMO_POINTER_QUERY;
    }
    return applied ? NEMO_POINTER_APPLIED : NEMO_POINTER_IGNORED;
}
