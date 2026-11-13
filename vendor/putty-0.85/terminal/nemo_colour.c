/* SPDX-License-Identifier: MIT */
#include "nemo_colour.h"
#include "nemo_x11_colour_data.h"

/* Xlib sections 6.1/6.2 describe device RGB, linear RGBi and the distinct
 * rgb:/# scaling rules:
 * https://www.x.org/releases/X11R7.6/doc/libX11/specs/libX11/libX11.html
 * Windows Terminal also restricts numeric XParseColor forms to rgb:/#:
 * https://github.com/microsoft/terminal/blob/5f7dc283013152f89bfb76950515c33f45157ad7/src/types/utils.cpp
 */

static unsigned char ascii_lower(unsigned char c)
{
    return c >= 'A' && c <= 'Z' ? (unsigned char)(c + ('a' - 'A')) : c;
}

static int compare_ascii(const char *text, size_t len, const char *name)
{
    size_t i;
    for (i = 0; i < len && name[i]; i++) {
        int diff = (int)ascii_lower((unsigned char)text[i]) -
                   (unsigned char)name[i];
        if (diff)
            return diff;
    }
    return i < len ? 1 : (name[i] ? -1 : 0);
}

static bool hex_value(const char *text, size_t len, uint32_t *value)
{
    uint32_t result = 0;
    size_t i;
    if (len < 1 || len > 4)
        return false;
    for (i = 0; i < len; i++) {
        unsigned char c = ascii_lower((unsigned char)text[i]);
        unsigned digit;
        if (c >= '0' && c <= '9')
            digit = c - '0';
        else if (c >= 'a' && c <= 'f')
            digit = c - 'a' + 10;
        else
            return false;
        result = (result << 4) | digit;
    }
    *value = result;
    return true;
}

static bool parse_rgb(const char *text, size_t len, uint8_t channels[3])
{
    size_t pos = 4;
    unsigned channel;
    for (channel = 0; channel < 3; channel++) {
        size_t start = pos, digits;
        uint32_t value, maximum;
        while (pos < len && text[pos] != '/')
            pos++;
        digits = pos - start;
        if (!hex_value(text + start, digits, &value))
            return false;
        maximum = (UINT32_C(1) << (4 * digits)) - 1;
        channels[channel] = (uint8_t)((value * UINT32_C(65535) / maximum) >> 8);
        if (channel < 2) {
            if (pos == len)
                return false;
            pos++;
        } else if (pos != len) {
            return false;
        }
    }
    return true;
}

static bool parse_sharp(const char *text, size_t len, uint8_t channels[3])
{
    size_t digits;
    unsigned channel;
    if (len != 4 && len != 7 && len != 10 && len != 13)
        return false;
    digits = (len - 1) / 3;
    for (channel = 0; channel < 3; channel++) {
        uint32_t value;
        if (!hex_value(text + 1 + channel * digits, digits, &value))
            return false;
        channels[channel] = (uint8_t)((value << (4 * (4 - digits))) >> 8);
    }
    return true;
}

bool nemo_colour_parse(const char *text, size_t len, NemoColour *out)
{
    uint8_t channels[3];

    if (!text || !out || !len || len > NEMO_X11_COLOUR_MAX_NAME)
        return false;
    if (len >= 4 && compare_ascii(text, 4, "rgb:") == 0) {
        if (!parse_rgb(text, len, channels))
            return false;
    } else if (text[0] == '#') {
        if (!parse_sharp(text, len, channels))
            return false;
    } else {
        size_t low = 0, high = sizeof(nemo_x11_colours) / sizeof(nemo_x11_colours[0]);
        while (low < high) {
            size_t mid = low + (high - low) / 2;
            int diff = compare_ascii(text, len,
                nemo_x11_colour_names + nemo_x11_colours[mid].offset);
            if (!diff) {
                out->r = nemo_x11_colours[mid].r;
                out->g = nemo_x11_colours[mid].g;
                out->b = nemo_x11_colours[mid].b;
                return true;
            }
            if (diff < 0)
                high = mid;
            else
                low = mid + 1;
        }
        return false;
    }
    out->r = channels[0];
    out->g = channels[1];
    out->b = channels[2];
    return true;
}
