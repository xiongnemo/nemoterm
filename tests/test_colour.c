/* SPDX-License-Identifier: MIT */
#include "nemo_colour.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "x11_colour_cases.h"

#define CHECK(condition) do { \
    if (!(condition)) { \
        fprintf(stderr, "%s:%d: %s\n", __FILE__, __LINE__, #condition); \
        exit(1); \
    } \
} while (0)

static void expect_slice(const char *text, size_t len,
                         unsigned r, unsigned g, unsigned b)
{
    NemoColour colour = { 19, 23, 29 };
    CHECK(nemo_colour_parse(text, len, &colour));
    CHECK(colour.r == r && colour.g == g && colour.b == b);
}

static void reject_slice(const char *text, size_t len)
{
    NemoColour colour = { 19, 23, 29 };
    CHECK(!nemo_colour_parse(text, len, &colour));
    CHECK(colour.r == 19 && colour.g == 23 && colour.b == 29);
}

static void examples(void)
{
    static const struct {
        const char *text;
        unsigned r, g, b;
    } cases[] = {
        { "rgb:0/0/0", 0, 0, 0 },
        { "rgb:f/f/f", 255, 255, 255 },
        { "rgb:ff/ff/ff", 255, 255, 255 },
        { "rgb:fff/fff/fff", 255, 255, 255 },
        { "rgb:ffff/ffff/ffff", 255, 255, 255 },
        { "RGB:a/B/c", 170, 187, 204 },
        { "RgB:Ff/AbCd/012", 255, 171, 1 },
        { "rgb:f/80/0000", 255, 128, 0 },
        { "rgb:800/8000/80", 128, 128, 128 },
        { "rgb:7ff/7fff/7f", 127, 127, 127 },
        { "rgb:123/4567/89", 18, 69, 137 },
        { "rgb:0001/0100/00ff", 0, 1, 0 },
        { "rgb:1/11/1111", 17, 17, 17 },
        { "#000", 0, 0, 0 },
        { "#fff", 240, 240, 240 },
        { "#3a7", 48, 160, 112 },
        { "#3000a0007000", 48, 160, 112 },
        { "#ffffff", 255, 255, 255 },
        { "#fffffffff", 255, 255, 255 },
        { "#ffffffffffff", 255, 255, 255 },
        { "#123456", 18, 52, 86 },
        { "#123456789", 18, 69, 120 },
        { "#123456789aBc", 18, 86, 154 },
        { "black", 0, 0, 0 },
        { "WHITE", 255, 255, 255 },
        { "red", 255, 0, 0 },
        { "green", 0, 255, 0 },
        { "blue", 0, 0, 255 },
        { "yellow", 255, 255, 0 },
        { "MaGeNtA", 255, 0, 255 },
        { "cyan", 0, 255, 255 },
        { "gray", 190, 190, 190 },
        { "grey", 190, 190, 190 },
        { "WebGray", 128, 128, 128 },
        { "WebGreen", 0, 128, 0 },
        { "RED1", 255, 0, 0 },
        { "gray50", 127, 127, 127 },
        { "LightGoldenrodYellow", 250, 250, 210 },
        { "light goldenrod yellow", 250, 250, 210 },
    };
    size_t i;
    for (i = 0; i < sizeof(cases) / sizeof(cases[0]); i++)
        expect_slice(cases[i].text, strlen(cases[i].text),
                     cases[i].r, cases[i].g, cases[i].b);
}

static void invalid(void)
{
    static const char *const cases[] = {
        "", "?", "#", "#1", "#12", "#1234", "#12345", "#1234567",
        "#12345678", "#1234567890", "#12345678901", "#1234567890123",
        "#ggg", "#12x456", "#12345678901z", "#123456;",
        "rgb:", "rgb:1", "rgb:1/2", "rgb:/1/2", "rgb:1//2",
        "rgb:1/2/", "rgb:1/2/3/", "rgb:1/2/3/4", "rgb:1/2/3junk",
        "rgb:1/2/gg", "rgb:00000/0/0", "rgb:0/00000/0", "rgb:0/0/00000",
        "rgb:-1/0/0", "rgb:+1/0/0", "rgb:0x1/0/0", "rgb:1.0/0/0",
        "rgb:1/2/3;", "rgb:1/2/3\n", "rgb: 1/2/3", " rgb:1/2/3",
        "rgbi:0.5/0/1", "rgbi:0/0/0", "rgbi:nan/inf/-1",
        "CIEXYZ:0/0/0", "transparent", "not-a-colour", "red ", " red",
        "reddish", "r", "red\n", "gray101", "grey-1", "RED5", "\xff",
        "gray 50", "light  blue", "light\tblue", "LightGoldenrodYellow ",
        " light goldenrod yellow", "light goldenrod yellow!",
    };
    const char embedded_nul[] = { 'r', 'e', 'd', '\0', 'x' };
    const char hex_nul[] = { '#', 'f', 'f', '\0' };
    size_t i;
    NemoColour colour;
    for (i = 0; i < sizeof(cases) / sizeof(cases[0]); i++)
        reject_slice(cases[i], strlen(cases[i]));
    reject_slice(embedded_nul, sizeof(embedded_nul));
    reject_slice(hex_nul, sizeof(hex_nul));
    reject_slice(NULL, 0);
    reject_slice(NULL, 1);
    reject_slice("", SIZE_MAX);
    CHECK(!nemo_colour_parse("red", 3, NULL));
    CHECK(!nemo_colour_parse(NULL, 0, &colour));
}

static void slices(void)
{
    const char no_terminator[] = { '#', '1', '2', '3' };
    const char command[] = "rgb:f/0/0;next-pair";
    size_t i;
    expect_slice(no_terminator, sizeof(no_terminator), 16, 32, 48);
    expect_slice(command, 9, 255, 0, 0);
    expect_slice("redjunk", 3, 255, 0, 0);
    for (i = 0; i < 9; i++)
        reject_slice(command, i);
}

static void named_colours(void)
{
    for (size_t i = 0; i < sizeof(x11_colour_cases)/sizeof(x11_colour_cases[0]); i++) {
        const char *name = x11_colour_cases[i].name;
        size_t len = strlen(name);
        /* Exact allocation without a NUL sentinel makes ASan check the
         * bounded-slice contract, including the binary-search edge names. */
        char *slice = malloc(len);
        char *invalid = malloc(len + 1);
        CHECK(slice && invalid);
        for (unsigned variant = 0; variant < 4; variant++) {
            for (size_t j = 0; j < len; j++) {
                unsigned char c = (unsigned char)name[j];
                if (variant && c >= 'A' && c <= 'Z') c += 'a' - 'A';
                if ((variant == 2 || (variant == 3 && j % 2)) &&
                    c >= 'a' && c <= 'z') c -= 'a' - 'A';
                slice[j] = (char)c;
            }
            expect_slice(slice, len, x11_colour_cases[i].r,
                         x11_colour_cases[i].g, x11_colour_cases[i].b);
        }
        memcpy(invalid, name, len);
        invalid[len] = '!';
        reject_slice(invalid, len + 1);
        invalid[len] = '\0';
        reject_slice(invalid, len + 1); /* terminator is not part of a name */
        for (size_t j = 0; j < len; j++) {
            memcpy(slice, name, len);
            slice[j] = '\0';
            reject_slice(slice, len);
        }
        free(invalid);
        free(slice);
    }
}

static void precision(void)
{
    unsigned value;
    char text[19];

    /* Exhaust all 16-bit inputs and both numeric spellings. The output
     * quantization is the high byte, including exact transition edges. */
    for (value = 0; value <= 65535; value++) {
        unsigned byte = value >> 8;
        CHECK(snprintf(text, sizeof(text), "rgb:%04x/%04x/%04x",
                       value, value, value) == 18);
        expect_slice(text, 18, byte, byte, byte);
        CHECK(snprintf(text, sizeof(text), "#%04x%04x%04x",
                       value, value, value) == 13);
        expect_slice(text, 13, byte, byte, byte);
    }
    for (value = 0; value <= 4095; value++) {
        unsigned byte = value >> 4;
        CHECK(snprintf(text, sizeof(text), "rgb:%03x/%03x/%03x",
                       value, value, value) == 15);
        expect_slice(text, 15, byte, byte, byte);
    }
    for (value = 0; value <= 255; value++) {
        CHECK(snprintf(text, sizeof(text), "rgb:%02x/%02x/%02x",
                       value, value, value) == 12);
        expect_slice(text, 12, value, value, value);
    }
    for (value = 0; value <= 15; value++) {
        CHECK(snprintf(text, sizeof(text), "rgb:%x/%x/%x",
                       value, value, value) == 9);
        expect_slice(text, 9, value * 17, value * 17, value * 17);
        CHECK(snprintf(text, sizeof(text), "#%x%x%x",
                       value, value, value) == 4);
        expect_slice(text, 4, value * 16, value * 16, value * 16);
    }
}

int main(void)
{
    examples();
    invalid();
    slices();
    named_colours();
    precision();
    puts("OSC colour parser tests passed");
    return 0;
}
