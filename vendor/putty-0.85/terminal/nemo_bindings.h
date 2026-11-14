/* SPDX-License-Identifier: MIT */
#ifndef NEMO_BINDINGS_H
#define NEMO_BINDINGS_H

enum { NEMO_BIND_SHIFT = 1, NEMO_BIND_CTRL = 2, NEMO_BIND_ALT = 4 };
#define NEMO_BIND_KEY(key, mods) ((key) | ((mods) << 8))

/* The low byte is a Windows virtual key; zero disables the action. No
 * allocation or layout translation is needed to dispatch a local shortcut. */
static inline bool nemo_binding_matches(int binding, unsigned key, unsigned mods)
{
    return key && key <= 255 && mods <= 7 && (binding & 255) &&
        binding == (int)NEMO_BIND_KEY(key, mods);
}

static inline bool nemo_rectangle_binding(int configured, bool shift, bool ctrl, bool alt)
{
    unsigned pressed = (shift ? NEMO_BIND_SHIFT : 0) |
        (ctrl ? NEMO_BIND_CTRL : 0) | (alt ? NEMO_BIND_ALT : 0);
    /* Shift alone is reserved for forcing local selection. Extra Shift is
     * accepted so a mouse binding also works in application mouse modes. */
    return configured > 0 && configured <= 7 &&
        (configured & (NEMO_BIND_CTRL | NEMO_BIND_ALT)) &&
        (pressed & (unsigned)configured) == (unsigned)configured;
}

static inline bool nemo_zoom_wheel_binding(int configured, unsigned pressed,
                                         bool application_mouse)
{
    return configured > 0 && configured <= 7 && pressed <= 7 &&
        (configured & (NEMO_BIND_CTRL | NEMO_BIND_ALT)) &&
        (pressed == (unsigned)configured ||
         pressed == ((unsigned)configured | NEMO_BIND_SHIFT)) &&
        (!application_mouse || (pressed & NEMO_BIND_SHIFT));
}
#endif
