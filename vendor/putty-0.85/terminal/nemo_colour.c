/* SPDX-License-Identifier: MIT */
#include "nemo_colour.h"

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

static bool equal_ascii(const char *text, size_t len, const char *name)
{
    size_t i;
    for (i = 0; i < len; i++) {
        if (!name[i] || ascii_lower((unsigned char)text[i]) !=
                        (unsigned char)name[i])
            return false;
    }
    return name[len] == '\0';
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
    static const struct {
        const char *name;
        NemoColour colour;
    } names[] = {
        { "black",   {   0,   0,   0 } },
        { "white",   { 255, 255, 255 } },
        { "red",     { 255,   0,   0 } },
        { "green",   {   0, 255,   0 } },
        { "blue",    {   0,   0, 255 } },
        { "yellow",  { 255, 255,   0 } },
        { "magenta", { 255,   0, 255 } },
        { "cyan",    {   0, 255, 255 } },
    };
    uint8_t channels[3];
    size_t i;

    if (!text || !out || !len || len > 18)
        return false;
    if (len >= 4 && equal_ascii(text, 4, "rgb:")) {
        if (!parse_rgb(text, len, channels))
            return false;
    } else if (text[0] == '#') {
        if (!parse_sharp(text, len, channels))
            return false;
    } else {
        for (i = 0; i < sizeof(names) / sizeof(names[0]); i++) {
            if (equal_ascii(text, len, names[i].name)) {
                *out = names[i].colour;
                return true;
            }
        }
        return false;
    }
    out->r = channels[0];
    out->g = channels[1];
    out->b = channels[2];
    return true;
}
