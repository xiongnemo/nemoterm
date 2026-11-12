/* SPDX-License-Identifier: MIT */
#include "putty.h"
#include "terminal.h"
#include "win-gui-seat.h"
#include "nemo_key_input.h"

typedef struct HeldKey {
    uint32_t key, shifted, base;
    bool active, protocol, down;
    bool win32;
    NemoWin32Key raw;
} HeldKey;

typedef struct NemoKeyInput {
    HeldKey held[768];
    unsigned known_mods, down_mods;
    unsigned win32_epoch;
} NemoKeyInput;

static unsigned flags(WinGuiSeat *wgs)
{
    return nemo_keyboard_flags(&wgs->term->keyboard[wgs->term->alt_which != 0]);
}

static bool enhanced(WinGuiSeat *wgs)
{
    return (flags(wgs) & (NEMO_KEY_DISAMBIGUATE | NEMO_KEY_EVENTS | NEMO_KEY_ALL)) != 0;
}

bool nemo_win32_input_active(WinGuiSeat *wgs)
{
    /* ConPTY requests 9001 on startup. Application keyboard negotiations must
     * still take precedence over that underlying transport request. */
    return wgs->term->win32_input && conf_get_bool(wgs->term->conf, CONF_nemo_win32_input) &&
        !flags(wgs) && wgs->term->modify_keys.level <= 0;
}

static void refresh_win32_epoch(WinGuiSeat *wgs)
{
    NemoKeyInput *ui = wgs->key_input;
    if (ui->win32_epoch == wgs->term->win32_input_epoch) return;
    for (size_t i = 0; i < lenof(ui->held); i++)
        if (ui->held[i].win32) memset(&ui->held[i], 0, sizeof(ui->held[i]));
    ui->win32_epoch = wgs->term->win32_input_epoch;
}

static unsigned specific_key(unsigned vk, LPARAM lp)
{
    bool extended = (HIWORD(lp) & KF_EXTENDED) != 0;
    if (vk == VK_CONTROL) return extended ? VK_RCONTROL : VK_LCONTROL;
    if (vk == VK_MENU) return extended ? VK_RMENU : VK_LMENU;
    if (vk == VK_SHIFT) return ((lp >> 16) & 255) == 0x36 ? VK_RSHIFT : VK_LSHIFT;
    return vk;
}

static unsigned key_index(unsigned vk, LPARAM lp)
{
    unsigned scan = (lp >> 16) & 255;
    /* A layout change can change the virtual key between press and release.
     * Keep physical positions stable; keys without scans have a separate bank. */
    return scan ? scan | ((HIWORD(lp) & KF_EXTENDED) ? 256 : 0) :
        512 + (specific_key(vk, lp) & 255);
}

void nemo_keyboard_prepare(WinGuiSeat *wgs, UINT message, WPARAM key, LPARAM lp, BYTE state[256])
{
    if (!wgs->term || key >= 256) return;
    bool kitty = enhanced(wgs);
    bool raw = nemo_win32_input_active(wgs);
    bool active = kitty || raw || wgs->term->modify_keys.level > 0;
    if (!wgs->key_input && !active) return;
    if (!wgs->key_input) {
        wgs->key_input = snew(NemoKeyInput);
        memset(wgs->key_input, 0, sizeof(*wgs->key_input));
    }
    NemoKeyInput *ui = wgs->key_input;
    refresh_win32_epoch(wgs);
    bool down = message == WM_KEYDOWN || message == WM_SYSKEYDOWN;
    unsigned vk = specific_key(key, lp);
    static const unsigned modifiers[] = {
        VK_LSHIFT, VK_RSHIFT, VK_LCONTROL, VK_RCONTROL, VK_LMENU, VK_RMENU, VK_LWIN, VK_RWIN
    };
    for (unsigned i = 0; i < lenof(modifiers); i++) {
        unsigned bit = 1u << i;
        if (vk == modifiers[i]) {
            ui->known_mods |= bit;
            if (down) ui->down_mods |= bit; else ui->down_mods &= ~bit;
        }
        if (active && (ui->known_mods & bit))
            state[modifiers[i]] = (state[modifiers[i]] & 1) | (ui->down_mods & bit ? 0x80 : 0);
    }
    if (active) {
        state[VK_SHIFT] = state[VK_LSHIFT] | state[VK_RSHIFT];
        state[VK_CONTROL] = state[VK_LCONTROL] | state[VK_RCONTROL];
        state[VK_MENU] = state[VK_LMENU] | state[VK_RMENU];
        if (kitty || raw) wgs->compose_state = 0; /* Native layout/IME replaces legacy compose. */
    }
    HeldKey *held = &ui->held[key_index(key, lp)];
    if (down && !(HIWORD(lp) & KF_REPEAT))
        *held = (HeldKey){.active=kitty || raw, .down=true};
}

static unsigned modifiers(const BYTE state[256])
{
    return (state[VK_SHIFT] & 0x80 ? NEMO_KEY_SHIFT : 0) |
        (state[VK_MENU] & 0x80 ? NEMO_KEY_ALT : 0) |
        (state[VK_CONTROL] & 0x80 ? NEMO_KEY_CTRL : 0) |
        ((state[VK_LWIN] | state[VK_RWIN]) & 0x80 ? NEMO_KEY_SUPER : 0) |
        (state[VK_CAPITAL] & 1 ? NEMO_KEY_CAPS : 0) |
        (state[VK_NUMLOCK] & 1 ? NEMO_KEY_NUM : 0);
}

static uint32_t logical_key(unsigned vk, LPARAM lp)
{
    bool ext = (HIWORD(lp) & KF_EXTENDED) != 0;
    if (vk >= VK_F1 && vk <= VK_F24) return NK_F1 + vk-VK_F1;
    if (vk >= VK_NUMPAD0 && vk <= VK_NUMPAD9) return NK_KP_0 + vk-VK_NUMPAD0;
    switch (specific_key(vk, lp)) {
      case VK_ESCAPE: return 27;
      case VK_RETURN: return ext ? NK_KP_ENTER : 13;
      case VK_TAB: return 9;
      case VK_BACK: return 127;
      case VK_INSERT: return ext ? NK_INSERT : NK_KP_INSERT;
      case VK_DELETE: return ext ? NK_DELETE : NK_KP_DELETE;
      case VK_LEFT: return ext ? NK_LEFT : NK_KP_LEFT;
      case VK_RIGHT: return ext ? NK_RIGHT : NK_KP_RIGHT;
      case VK_UP: return ext ? NK_UP : NK_KP_UP;
      case VK_DOWN: return ext ? NK_DOWN : NK_KP_DOWN;
      case VK_PRIOR: return ext ? NK_PAGE_UP : NK_KP_PAGE_UP;
      case VK_NEXT: return ext ? NK_PAGE_DOWN : NK_KP_PAGE_DOWN;
      case VK_HOME: return ext ? NK_HOME : NK_KP_HOME;
      case VK_END: return ext ? NK_END : NK_KP_END;
      case VK_CLEAR: return NK_KP_BEGIN;
      case VK_DECIMAL: return NK_KP_DECIMAL;
      case VK_DIVIDE: return NK_KP_DIVIDE;
      case VK_MULTIPLY: return NK_KP_MULTIPLY;
      case VK_SUBTRACT: return NK_KP_SUBTRACT;
      case VK_ADD: return NK_KP_ADD;
      case VK_SEPARATOR: return NK_KP_SEPARATOR;
      case VK_CAPITAL: return NK_CAPS_LOCK;
      case VK_SCROLL: return NK_SCROLL_LOCK;
      case VK_NUMLOCK: return NK_NUM_LOCK;
      case VK_SNAPSHOT: return NK_PRINT_SCREEN;
      case VK_PAUSE: return NK_PAUSE;
      case VK_APPS: return NK_MENU;
      case VK_MEDIA_PLAY_PAUSE: return NK_MEDIA_PLAY_PAUSE;
      case VK_MEDIA_STOP: return NK_MEDIA_STOP;
      case VK_MEDIA_NEXT_TRACK: return NK_MEDIA_NEXT;
      case VK_MEDIA_PREV_TRACK: return NK_MEDIA_PREVIOUS;
      case VK_VOLUME_DOWN: return NK_VOLUME_DOWN;
      case VK_VOLUME_UP: return NK_VOLUME_UP;
      case VK_VOLUME_MUTE: return NK_VOLUME_MUTE;
      case VK_LSHIFT: return NK_LEFT_SHIFT;
      case VK_RSHIFT: return NK_RIGHT_SHIFT;
      case VK_LCONTROL: return NK_LEFT_CONTROL;
      case VK_RCONTROL: return NK_RIGHT_CONTROL;
      case VK_LMENU: return NK_LEFT_ALT;
      case VK_RMENU: return NK_RIGHT_ALT;
      case VK_LWIN: return NK_LEFT_SUPER;
      case VK_RWIN: return NK_RIGHT_SUPER;
      default: return 0;
    }
}

static uint32_t base_key(unsigned scan)
{
    /* Physical US PC-101 positions, independent of the active input locale. */
    static const char row1[] = "1234567890-=", row2[] = "qwertyuiop[]";
    static const char row3[] = "asdfghjkl;'", row4[] = "zxcvbnm,./";
    if (scan >= 2 && scan < 2+sizeof(row1)-1) return row1[scan-2];
    if (scan >= 0x10 && scan < 0x10+sizeof(row2)-1) return row2[scan-0x10];
    if (scan >= 0x1e && scan < 0x1e + sizeof(row3)-1) return row3[scan-0x1e];
    if (scan >= 0x2c && scan < 0x2c+sizeof(row4)-1) return row4[scan-0x2c];
    if (scan == 0x29) return '`';
    if (scan == 0x2b) return '\\';
    if (scan == 0x39) return ' ';
    return 0;
}

static size_t scalars(const wchar_t *text, size_t count, uint32_t *out)
{
    size_t n = 0;
    for (size_t i = 0; i < count; i++) {
        uint32_t ch = text[i];
        if (ch >= 0xd800 && ch <= 0xdbff && i+1 < count &&
            text[i+1] >= 0xdc00 && text[i+1] <= 0xdfff)
            ch = 0x10000 + ((ch-0xd800)<<10) + text[++i]-0xdc00;
        if (ch >= 32 && !(ch >= 127 && ch <= 159) && !(ch >= 0xd800 && ch <= 0xdfff)) out[n++] = ch;
    }
    return n;
}

static uint32_t layout_key(unsigned vk, unsigned scan, HKL layout, bool shift)
{
    BYTE plain[256] = {0};
    wchar_t text[16]; uint32_t chars[16];
    if (shift) plain[VK_SHIFT] = plain[VK_LSHIFT] = 0x80;
    int n = ToUnicodeEx(vk, scan, plain, text, lenof(text), 4, layout);
    if (n < 0) n = -n;
    return n && scalars(text, min(n, (int)lenof(text)), chars) ? chars[0] : 0;
}

static void send_event(WinGuiSeat *wgs, unsigned mode, const NemoKeyEvent *event, HeldKey *held)
{
    char encoded[NEMO_KEY_ENCODED_MAX];
    int n = nemo_keyboard_encode(mode, event, encoded, sizeof(encoded));
    if (n > 0) term_keyinput(wgs->term, -1, encoded, n);
    if (held) {
        NemoKeyEvent release = *event;
        release.type = 3;
        held->protocol = nemo_keyboard_encode(mode, &release, encoded, sizeof(encoded)) > 0;
    }
}

static uint32_t modified_character(unsigned vk, unsigned scan, const BYTE source[256],
                                   HKL layout, unsigned ignore, bool altgr)
{
    BYTE state[256]; memcpy(state, source, sizeof(state));
    if (!altgr) {
        state[VK_CONTROL] = state[VK_LCONTROL] = state[VK_RCONTROL] = 0;
        state[VK_MENU] = state[VK_LMENU] = state[VK_RMENU] = 0;
    }
    if (ignore & 1) state[VK_SHIFT] = state[VK_LSHIFT] = state[VK_RSHIFT] = 0;
    if (ignore & 2) state[VK_CAPITAL] = 0;
    if (ignore & 16) state[VK_NUMLOCK] = 0;
    wchar_t wide[16]; uint32_t text[16];
    int n = ToUnicodeEx(vk, scan, state, wide, lenof(wide), 4, layout);
    if (n < 0) n = -n;
    return n && scalars(wide, min(n, (int)lenof(wide)), text) ? text[0] : 0;
}

static bool modified_key_input(WinGuiSeat *wgs, unsigned vk, LPARAM lp,
                               const BYTE state[256], HKL layout, HeldKey *held)
{
    if (wgs->term->modify_keys.level <= 0 || wgs->compose_state) return false;
    uint32_t logical = logical_key(vk, lp);
    /* Cursor/function/keypad/modifier keys keep their existing translators. */
    if (logical >= NK_INSERT) return false;
    unsigned scan = (lp >> 16) & 255;
    wchar_t wide[16]; uint32_t text[16];
    /* Preview without consuming a pending Windows dead key. If the encoder
     * declines the event, the legacy path performs the only stateful lookup. */
    int n = ToUnicodeEx(vk, scan, state, wide, lenof(wide), 4, layout);
    if (n < 0) return false;
    size_t count = n > 0 ? scalars(wide, min(n, (int)lenof(wide)), text) : 0;
    bool altgr = count && (state[VK_RMENU] & 0x80);
    NemoModifiedKey event = {.key=logical, .modifiers=modifiers(state),
        .type=(HIWORD(lp) & KF_REPEAT) ? 2 : 1};
    if (altgr) event.modifiers &= ~(NEMO_KEY_CTRL | NEMO_KEY_ALT);
    switch (logical) {
      case 9: event.kind = NMK_TAB; break;
      case 13: event.kind = NMK_ENTER; break;
      case 27: event.kind = NMK_ESCAPE; break;
      case 127:
        event.kind = NMK_BACKSPACE;
        event.key = conf_get_bool(wgs->conf, CONF_bksp_is_delete) ? 127 : 8;
        if (event.modifiers & NEMO_KEY_CTRL) event.key ^= 127 ^ 8;
        break;
      default:
        event.key = modified_character(vk, scan, state, layout, 0, altgr);
        if (!event.key) return false;
        event.factored_key = modified_character(vk, scan, state, layout,
                                                wgs->term->modify_keys.ignore, altgr);
        break;
    }
    char output[16*NEMO_MOK_ENCODED_MAX];
    size_t used = 0;
    bool multiple = !logical && count > 1 && wgs->term->modify_keys.level == 3 &&
        !(event.modifiers & (NEMO_KEY_CTRL | NEMO_KEY_ALT | NEMO_KEY_SUPER));
    for (size_t i = 0; i < (multiple ? count : 1); i++) {
        if (multiple) event.key = event.factored_key = text[i];
        int length = nemo_mok_encode(&wgs->term->modify_keys, &event, output+used, sizeof(output)-used);
        if (length < 0) return false;
        if (!length) return true;
        used += length;
    }
    ToUnicodeEx(vk, scan, state, wide, lenof(wide), 0, layout);
    held->active = held->down = true;
    held->protocol = false; /* modifyOtherKeys never emits key releases */
    for (unsigned i = 0, repeat = max(1, LOWORD(lp)); i < repeat; i++)
        term_keyinput(wgs->term, -1, output, used);
    return true;
}

static void win32_send(WinGuiSeat *wgs, const NemoWin32Key *key)
{
    char output[NEMO_WIN32_ENCODED_MAX];
    int n = nemo_win32_encode(key, output, sizeof(output));
    if (n > 0) term_keyinput(wgs->term, -1, output, n);
}

static uint32_t win32_modifiers(const BYTE state[256], LPARAM lp)
{
    return (state[VK_RMENU] & 0x80 ? RIGHT_ALT_PRESSED : 0) |
        (state[VK_LMENU] & 0x80 ? LEFT_ALT_PRESSED : 0) |
        (state[VK_RCONTROL] & 0x80 ? RIGHT_CTRL_PRESSED : 0) |
        (state[VK_LCONTROL] & 0x80 ? LEFT_CTRL_PRESSED : 0) |
        (state[VK_SHIFT] & 0x80 ? SHIFT_PRESSED : 0) |
        (state[VK_NUMLOCK] & 1 ? NUMLOCK_ON : 0) |
        (state[VK_SCROLL] & 1 ? SCROLLLOCK_ON : 0) |
        (state[VK_CAPITAL] & 1 ? CAPSLOCK_ON : 0) |
        (HIWORD(lp) & KF_EXTENDED ? ENHANCED_KEY : 0);
}

static void win32_key_input(WinGuiSeat *wgs, unsigned vk, LPARAM lp,
                            const BYTE state[256], HKL layout, HeldKey *held, bool down)
{
    unsigned scan = (lp >> 16) & 255;
    wchar_t wide[16];
    /* Key-up previews must not consume a pending dead key. The menu flag
     * prevents Alt+navigation from unexpectedly producing a text character. */
    int n = ToUnicodeEx(vk, scan, state, wide, lenof(wide), down ? 1 : 5, layout);
    /* A preview can combine the pending dead key with itself on release.
     * It is not a second text commit and must not produce multiple releases. */
    if (n < 0 || (!down && n != 1)) n = 0;
    n = min(n, (int)lenof(wide));
    NemoWin32Key key = {.vk=vk, .scan=scan, .down=down,
        .control=win32_modifiers(state, lp), .repeat=max(1, LOWORD(lp))};
    for (int i = 0; i < max(1, n); i++) {
        key.character = n ? (uint16_t)wide[i] : 0;
        win32_send(wgs, &key);
    }
    held->active = held->down = down;
    held->win32 = true;
    held->raw = key;
}

bool nemo_keyboard_input(WinGuiSeat *wgs, UINT message, WPARAM vk, LPARAM lp,
                         const BYTE state[256], HKL layout)
{
    if (!wgs->key_input || vk >= 256) return false;
    HeldKey *held = &wgs->key_input->held[key_index(vk, lp)];
    bool down = message == WM_KEYDOWN || message == WM_SYSKEYDOWN;
    bool active = enhanced(wgs);
    bool raw = nemo_win32_input_active(wgs);
    if (!down) {
        bool consume = held->active || active || raw;
        if (raw && held->win32 && held->down) {
            win32_key_input(wgs, vk, lp, state, layout, held, false);
        } else if (active && held->protocol) {
            NemoKeyEvent event = {.key=held->key, .shifted=held->shifted, .base=held->base,
                                 .modifiers=modifiers(state), .type=3};
            send_event(wgs, flags(wgs), &event, NULL);
        }
        memset(held, 0, sizeof(*held));
        return consume;
    }
    if (raw) {
        win32_key_input(wgs, vk, lp, state, layout, held, true);
        return true;
    }
    if (!active) return modified_key_input(wgs, vk, lp, state, layout, held);
    held->active = held->down = true;
    unsigned scan = (lp >> 16) & 255, mode = flags(wgs);
    uint32_t text[NEMO_KEY_TEXT_MAX], translated[16];
    wchar_t wide[16];
    int n = ToUnicodeEx(vk, scan, state, wide, lenof(wide), 0, layout);
    size_t count = n > 0 ? scalars(wide, min(n, (int)lenof(wide)), text) : 0;
    NemoKeyEvent event = {.key=logical_key(vk, lp), .modifiers=modifiers(state),
        .type=(HIWORD(lp) & KF_REPEAT) ? 2 : 1, .text=text, .text_len=count};
    if (!event.key) {
        unsigned mapped = MapVirtualKeyExW(vk, MAPVK_VK_TO_CHAR, layout);
        event.key = mapped & 0x80000000u ? mapped & 0x7fffffffu : layout_key(vk, scan, layout, false);
        event.shifted = n < 0 && (event.modifiers & NEMO_KEY_SHIFT) &&
            scalars(wide, min(-n, (int)lenof(wide)), translated) ? translated[0] :
            layout_key(vk, scan, layout, true);
        event.base = (HIWORD(lp) & KF_EXTENDED) ? 0 : base_key(scan);
        if (!event.key) event.key = event.base;
    }
    /* AltGr text consumes the layout's Ctrl+Alt combination. Plain Ctrl/Alt
     * shortcuts do not acquire an associated printable character by accident. */
    if (count && (state[VK_RMENU] & 0x80))
        event.modifiers &= ~(NEMO_KEY_CTRL | NEMO_KEY_ALT);
    else if (event.modifiers & (NEMO_KEY_CTRL | NEMO_KEY_ALT | NEMO_KEY_SUPER)) event.text_len = 0;
    if (n < 0 && !(mode & NEMO_KEY_ALL) && !(event.modifiers & ~193u)) return true;
    if (event.type == 2 && held->key) {
        event.key = held->key; event.shifted = held->shifted; event.base = held->base;
    }
    held->key = event.key; held->shifted = event.shifted; held->base = event.base;
    unsigned repeat = max(1, LOWORD(lp));
    for (unsigned i = 0; i < repeat; i++) {
        if (i) event.type = 2;
        send_event(wgs, mode, &event, held);
    }
    return true;
}

bool nemo_keyboard_text(WinGuiSeat *wgs, const wchar_t *text, size_t length)
{
    unsigned mode = flags(wgs);
    if (nemo_win32_input_active(wgs)) {
        /* IME/WM_CHAR text has no physical key identity. Preserve UTF-16 units
         * (including surrogate pairs) in the protocol's UnicodeChar field. */
        NemoWin32Key key = {.down=true, .repeat=1};
        for (size_t i = 0; i < length; i++) {
            key.character = (uint16_t)text[i];
            win32_send(wgs, &key);
        }
        return true;
    }
    if (!enhanced(wgs) && wgs->term->modify_keys.level == 3) {
        while (length) {
            size_t take = min(length, NEMO_KEY_TEXT_MAX);
            if (take < length && text[take-1] >= 0xd800 && text[take-1] <= 0xdbff) take--;
            uint32_t values[NEMO_KEY_TEXT_MAX];
            size_t count = scalars(text, take, values);
            for (size_t i = 0; i < count; i++) {
                NemoModifiedKey key = {.key=values[i], .type=1};
                char encoded[NEMO_MOK_ENCODED_MAX];
                int n = nemo_mok_encode(&wgs->term->modify_keys, &key, encoded, sizeof(encoded));
                if (n > 0) term_keyinput(wgs->term, -1, encoded, n);
            }
            text += take; length -= take;
        }
        return true;
    }
    if (!(mode & NEMO_KEY_ALL)) return false;
    while (length) {
        size_t take = min(length, NEMO_KEY_TEXT_MAX);
        if (take < length && text[take-1] >= 0xd800 && text[take-1] <= 0xdbff) take--;
        uint32_t values[NEMO_KEY_TEXT_MAX];
        NemoKeyEvent event = {.type=1, .text=values, .text_len=scalars(text, take, values)};
        if (event.text_len) send_event(wgs, mode, &event, NULL);
        text += take; length -= take;
    }
    return true;
}

void nemo_keyboard_focus_lost(WinGuiSeat *wgs)
{
    if (!wgs->key_input) return;
    refresh_win32_epoch(wgs);
    for (size_t i = 0; i < lenof(wgs->key_input->held); i++) {
        HeldKey *held = &wgs->key_input->held[i];
        if (held->win32 && held->down && nemo_win32_input_active(wgs)) {
            NemoWin32Key key = held->raw;
            key.down = false;
            key.repeat = 1;
            key.control &= ENHANCED_KEY | CAPSLOCK_ON | NUMLOCK_ON | SCROLLLOCK_ON;
            win32_send(wgs, &key);
        } else if (held->protocol && held->down) {
            NemoKeyEvent event = {.key=held->key, .shifted=held->shifted,
                                 .base=held->base, .type=3};
            send_event(wgs, flags(wgs), &event, NULL);
        }
    }
    memset(wgs->key_input, 0, sizeof(*wgs->key_input));
}

void nemo_keyboard_free(WinGuiSeat *wgs)
{
    sfree(wgs->key_input);
    wgs->key_input = NULL;
}
