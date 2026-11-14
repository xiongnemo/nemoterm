/* SPDX-License-Identifier: MIT */
#include "nemo_sixel.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

#define BLACK UINT32_C(0xff000000)
#define RED   UINT32_C(0xffff0000)
#define GREEN UINT32_C(0xff00ff00)
#define BLUE  UINT32_C(0xff0000ff)
#define DEFAULT_FG UINT32_C(0xff33cc33) /* register 3 in the VT340 palette */

static NemoSixel *fresh(bool transparent)
{
    NemoSixel *s = nemo_sixel_init(0, transparent);
    assert(s);
    return s;
}

static void feed(NemoSixel *s, const char *payload)
{
    assert(nemo_sixel_feed(s, payload, strlen(payload)));
    assert(nemo_sixel_finish(s));
}

static uint32_t pixel(NemoSixel *s, unsigned x, unsigned y)
{
    uint32_t out = 0xdeadbeef;
    assert(nemo_sixel_read_row(s, y, x, &out, 1) == 1);
    return out;
}

static uint64_t fingerprint(NemoSixel *s)
{
    NemoSixelStats st = nemo_sixel_stats(s);
    uint64_t hash = UINT64_C(1469598103934665603);
    unsigned x, y;
    uint32_t row[512];
    assert(st.width <= 512);
    for (y = 0; y < st.height; y++) {
        assert(nemo_sixel_read_row(s, y, 0, row, 512) == st.width);
        for (x = 0; x < st.width; x++) {
            hash ^= row[x];
            hash *= UINT64_C(1099511628211);
        }
    }
    return hash ^ ((uint64_t)st.width << 32) ^ st.height;
}

static void basic_pixels(void)
{
    NemoSixel *s = fresh(true);
    NemoSixelStats st;
    feed(s, "\"1;1;2;6#2;2;100;0;0@A");
    st = nemo_sixel_stats(s);
    assert(st.width == 2 && st.height == 6);
    assert(pixel(s, 0, 0) == RED);
    assert(pixel(s, 0, 1) == 0);
    assert(pixel(s, 1, 0) == 0);
    assert(pixel(s, 1, 1) == RED);
    assert(pixel(s, 1, 5) == 0);
    assert(st.allocated_bytes < 12000);
    nemo_sixel_reset(s, false);
    uint32_t palette[256];
    nemo_sixel_get_palette(s, palette);
    palette[0] = UINT32_C(0xff123456);
    nemo_sixel_set_palette(s, palette);
    feed(s, "\"1;1;2;3@");
    assert(pixel(s, 0, 0) == DEFAULT_FG);
    assert(pixel(s, 0, 1) == UINT32_C(0xff123456));
    assert(pixel(s, 1, 0) == UINT32_C(0xff123456));
    nemo_sixel_free(s);
}

static void color_and_overlay(void)
{
    NemoSixel *s = fresh(true);
    feed(s, "#1;1;120;50;100@#2;1;240;50;100@#3;1;0;50;100@"
            "$#3A");
    assert(pixel(s, 0, 0) == RED);
    assert(pixel(s, 1, 0) == GREEN);
    assert(pixel(s, 2, 0) == BLUE);
    assert(pixel(s, 0, 1) == BLUE);
    /* Repeated color planes do not clear previously painted zero bits. */
    assert(pixel(s, 1, 1) == 0);
    nemo_sixel_reset(s, false);
    feed(s, "#1;2;100;0;0@#1;2;0;100;0@");
    /* Register redefinition recolors the earlier pixels in the same DCS. */
    assert(pixel(s, 0, 0) == GREEN && pixel(s, 1, 0) == GREEN);
    nemo_sixel_free(s);
}

static void palette_identity(void)
{
    NemoSixel *s = fresh(true);
    /* Equal RGB values do not merge the identities of two registers. */
    feed(s, "#1;2;100;0;0!8~#2;2;100;0;0!8~#1;2;0;100;0");
    for (unsigned y = 0; y < 6; y++)
        for (unsigned x = 0; x < 16; x++)
            assert(pixel(s, x, y) == (x < 8 ? GREEN : RED));
    nemo_sixel_reset(s, true);
    /* An overwritten pixel follows its new register, not its old one. */
    feed(s, "#1;2;100;0;0!16~$#2;2;0;0;100!8~#1;2;0;100;0");
    for (unsigned y = 0; y < 6; y++)
        for (unsigned x = 0; x < 16; x++)
            assert(pixel(s, x, y) == (x < 8 ? BLUE : GREEN));
    nemo_sixel_reset(s, false);
    /* Register zero is the fill identity, including unallocated tiles.
     * Default foreground pixels retain their independent register 3. */
    feed(s, "\"1;1;64;6@#0;2;100;0;0@#0;1;240;50;100");
    assert(pixel(s, 0, 0) == DEFAULT_FG);
    assert(pixel(s, 1, 0) == GREEN);
    assert(pixel(s, 1, 1) == GREEN && pixel(s, 63, 5) == GREEN);
    uint32_t palette[256];
    nemo_sixel_get_palette(s, palette);
    palette[0] = BLUE;
    size_t bytes = nemo_sixel_stats(s).allocated_bytes;
    nemo_sixel_set_palette(s, palette);
    assert(pixel(s, 1, 0) == BLUE && pixel(s, 0, 0) == DEFAULT_FG);
    assert(pixel(s, 63, 5) == BLUE);
    assert(nemo_sixel_stats(s).allocated_bytes == bytes);
    nemo_sixel_free(s);
}

static void palette_notification(void *ctx)
{
    unsigned *notifications = ctx;
    (*notifications)++;
}

static void shared_palette_lifetime(void)
{
    NemoSixel *first = fresh(true), *next = fresh(true), *private = fresh(true);
    uint32_t shared[256], copy[256];
    unsigned notifications = 0;
    nemo_sixel_get_palette(first, shared);
    assert(nemo_sixel_share_palette(first, shared, palette_notification, &notifications));
    assert(nemo_sixel_share_palette(next, shared, palette_notification, &notifications));
    feed(first, "#1;2;100;0;0~");
    feed(private, "#1;2;100;0;0~");
    assert(notifications == 1);
    assert(!nemo_sixel_share_palette(first, shared, NULL, NULL));
    const char *definition = "#1;2;0;100;0";
    for (size_t i = 0; i < strlen(definition); i++)
        assert(nemo_sixel_feed(next, definition+i, 1));
    assert(pixel(first, 0, 0) == RED && notifications == 1);
    size_t retained_bytes = nemo_sixel_stats(first).allocated_bytes;
    assert(nemo_sixel_feed(next, "?", 1));
    /* A completed definition is live before image finish, and freeing the
     * pending decoder (DCS cancellation) does not roll it back. */
    assert(notifications == 2 && shared[1] == GREEN);
    nemo_sixel_free(next);
    assert(pixel(first, 0, 0) == GREEN && pixel(private, 0, 0) == RED);
    nemo_sixel_get_palette(first, copy);
    assert(copy[1] == GREEN);
    copy[1] = BLUE;
    nemo_sixel_set_palette(first, copy);
    assert(notifications == 3 && shared[1] == BLUE);
    assert(pixel(first, 0, 0) == BLUE);
    assert(nemo_sixel_stats(first).allocated_bytes == retained_bytes);
    nemo_sixel_set_palette(first, copy);
    assert(notifications == 3); /* unchanged definitions need no redraw */
    nemo_sixel_reset(first, true);
    feed(first, "#1;2;100;0;0~");
    assert(pixel(first, 0, 0) == RED && shared[1] == BLUE);
    assert(notifications == 3); /* reset detached the borrowed palette */
    nemo_sixel_free(first);
    nemo_sixel_free(private);
}

static void extents_and_repeat(void)
{
    NemoSixel *s = fresh(false);
    NemoSixelStats st;
    feed(s, "\"2;1;3;2!40~-@-$!0@");
    st = nemo_sixel_stats(s);
    assert(st.width == 40 && st.height == 13);
    assert(st.aspect_vertical == 2 && st.aspect_horizontal == 1);
    assert(pixel(s, 39, 5) == DEFAULT_FG);
    assert(pixel(s, 0, 6) == DEFAULT_FG);
    assert(pixel(s, 0, 12) == DEFAULT_FG);
    assert(pixel(s, 1, 6) == 0); /* outside the declared fill rectangle */
    nemo_sixel_reset(s, true);
    feed(s, "?@");
    st = nemo_sixel_stats(s);
    assert(st.width == 2 && st.height == 1); /* highest set bit, not six */
    assert(pixel(s, 0, 0) == 0 && pixel(s, 1, 0) == DEFAULT_FG);
    nemo_sixel_reset(s, false);
    nemo_sixel_set_aspect(s, 10, 4);
    feed(s, "\"3;2;64;64?");
    st = nemo_sixel_stats(s);
    assert(st.width == 64 && st.height == 64);
    assert(st.aspect_vertical == 3 && st.aspect_horizontal == 2);
    /* A background-only declared raster needs no tile allocation. */
    assert(st.allocated_bytes < 4096 && pixel(s, 63, 63) == BLACK);
    nemo_sixel_free(s);
}

static void arbitrary_chunk_boundaries(void)
{
    const char *payload = "\"2;2;100;73#42;2;50;25;75!40~$#3;1;240;50;100"
                          "!20A-!80~-?@-!90A#4;1;120;50;100";
    size_t len = strlen(payload), split, i;
    NemoSixel *s = fresh(true);
    uint64_t expected;
    feed(s, payload);
    expected = fingerprint(s);
    for (split = 0; split <= len; split++) {
        nemo_sixel_reset(s, true);
        assert(nemo_sixel_feed(s, payload, split));
        assert(nemo_sixel_feed(s, payload + split, len - split));
        assert(nemo_sixel_finish(s));
        assert(fingerprint(s) == expected);
    }
    nemo_sixel_reset(s, true);
    for (i = 0; i < len; i++) assert(nemo_sixel_feed(s, payload + i, 1));
    assert(nemo_sixel_finish(s) && fingerprint(s) == expected);
    assert(!nemo_sixel_feed(s, "~", 1)); /* finished pixels reject more input */
    nemo_sixel_free(s);
}

static void rejected_inputs(void)
{
    static const char *invalid[] = {
        "!4294967296~", "!99999999999999999999999999999999999999999999~",
        "!8193~", "!3#", "#2;3;0;0;0~", "#2;2;100~",
        "#1;2;1;2;3;4~", "\"1;1;8193;1~", "\"1;1;8192;8192~",
        "\x18", "\x1a", "\x1b", "\x9c"
    };
    size_t i;
    NemoSixel *s = fresh(true);
    for (i = 0; i < sizeof(invalid) / sizeof(*invalid); i++) {
        NemoSixelStats st;
        nemo_sixel_reset(s, true);
        assert(!nemo_sixel_feed(s, invalid[i], strlen(invalid[i])));
        assert(!nemo_sixel_finish(s));
        assert(!nemo_sixel_feed(s, "~", 1));
        st = nemo_sixel_stats(s);
        assert(st.status != NEMO_SIXEL_OK);
        assert(st.allocated_bytes <= st.budget_bytes);
    }
    nemo_sixel_reset(s, true);
    assert(nemo_sixel_feed(s, "!12", 3));
    assert(!nemo_sixel_finish(s));
    nemo_sixel_reset(s, true);
    assert(nemo_sixel_feed(s, "#1;2;4", 6));
    assert(!nemo_sixel_finish(s));
    nemo_sixel_free(s);
    assert(!nemo_sixel_init(1, true));
}

static void bounded_memory(void)
{
    NemoSixel *s = nemo_sixel_init(8192, true);
    NemoSixelStats st;
    assert(s);
    assert(nemo_sixel_feed(s, "@", 1));
    st = nemo_sixel_stats(s);
    assert(st.allocated_bytes <= 8192);
    /* A second tile exceeds the budget despite tiny logical geometry. */
    assert(!nemo_sixel_feed(s, "!32@", 4));
    st = nemo_sixel_stats(s);
    assert(st.status == NEMO_SIXEL_LIMIT && st.allocated_bytes <= 8192);
    nemo_sixel_reset(s, true);
    assert(nemo_sixel_stats(s).allocated_bytes < 4096);
    nemo_sixel_free(s);
}

static void dense_image_and_partial_rows(void)
{
    NemoSixel *s = fresh(true);
    NemoSixelStats st;
    uint32_t row[40];
    unsigned i;
    assert(nemo_sixel_feed(s, "\"1;1;512;512", 12));
    for (i = 0; i < 85; i++)
        assert(nemo_sixel_feed(s, "!512~-", 6));
    assert(nemo_sixel_feed(s, "!512B", 5));
    assert(nemo_sixel_finish(s));
    st = nemo_sixel_stats(s);
    assert(st.width == 512 && st.height == 512);
    assert(st.allocated_bytes >= 512u * 512u * 4u);
    assert(st.allocated_bytes < 1100000u);
    assert(pixel(s, 511, 511) == DEFAULT_FG);
    /* Start inside a tile and cross the next boundary. */
    assert(nemo_sixel_read_row(s, 511, 31, row, 40) == 40);
    for (i = 0; i < 40; i++) assert(row[i] == DEFAULT_FG);
    assert(nemo_sixel_read_row(s, 511, 510, row, 40) == 2);
    assert(nemo_sixel_read_row(s, 512, 0, row, 40) == 0);
    assert(nemo_sixel_read_row(s, 0, 512, row, 40) == 0);
    nemo_sixel_free(s);
}

static void deterministic_fuzz(void)
{
    NemoSixel *s = nemo_sixel_init(16384, true);
    uint32_t rng = 0xc0ffee;
    unsigned trial, i;
    assert(s);
    for (trial = 0; trial < 20000; trial++) {
        NemoSixelStats st;
        nemo_sixel_reset(s, (trial & 1) != 0);
        for (i = 0; i < 100; i++) {
            unsigned char c;
            rng = rng * 1664525u + 1013904223u;
            c = (unsigned char)(rng >> 24);
            if (!nemo_sixel_feed(s, &c, 1)) break;
        }
        (void)nemo_sixel_finish(s);
        st = nemo_sixel_stats(s);
        assert(st.width <= NEMO_SIXEL_MAX_DIMENSION);
        assert(st.height <= NEMO_SIXEL_MAX_DIMENSION);
        assert(st.allocated_bytes <= st.budget_bytes);
        if (st.height) assert(st.width <= st.budget_bytes / 4 / st.height);
    }
    nemo_sixel_free(s);
}

static void register_counts(void)
{
    NemoSixel *s = fresh(true);
    assert(!nemo_sixel_set_register_count(s, 0));
    assert(!nemo_sixel_set_register_count(s, 1));
    assert(!nemo_sixel_set_register_count(s, 257));
    assert(nemo_sixel_set_register_count(s, 2));
    /* Register 2 aliases 0 at this limit, for both definition and selection. */
    const char *payload = "#2;2;100;0;0#0~#3;2;0;100;0#1~";
    assert(nemo_sixel_feed(s, payload, strlen(payload)));
    assert(nemo_sixel_finish(s));
    uint32_t pixels[2];
    assert(nemo_sixel_read_row(s, 0, 0, pixels, 2) == 2);
    assert(pixels[0] == UINT32_C(0xffff0000));
    assert(pixels[1] == UINT32_C(0xff00ff00));
    assert(!nemo_sixel_set_register_count(s, 16));
    nemo_sixel_reset(s, true);
    /* Reset restores 256 registers; out-of-range selectors wrap, not abort. */
    payload = "#256;2;100;0;0#0~#4294967295;2;0;100;0#255~";
    assert(nemo_sixel_feed(s, payload, strlen(payload)));
    assert(!nemo_sixel_set_register_count(s, 2));
    assert(nemo_sixel_finish(s));
    assert(nemo_sixel_read_row(s, 0, 0, pixels, 2) == 2);
    assert(pixels[0] == UINT32_C(0xffff0000));
    assert(pixels[1] == UINT32_C(0xff00ff00));
    nemo_sixel_free(s);
}

static void implicit_background(void)
{
    NemoSixel *s = fresh(false);
    feed(s, "\"1;1;8;6@");
    assert(pixel(s, 0, 0) == DEFAULT_FG && pixel(s, 1, 0) == BLACK);
    nemo_sixel_reset(s, false);
    feed(s, "\"1;1;8;6@#3;2;100;0;0?#0;2;0;0;100?");
    assert(pixel(s, 0, 0) == RED && pixel(s, 7, 5) == BLUE);
    nemo_sixel_reset(s, true);
    feed(s, "\"1;1;8;6@#0;2;0;0;100?");
    assert(pixel(s, 0, 0) == DEFAULT_FG && pixel(s, 7, 5) == 0);

    nemo_sixel_reset(s, false);
    feed(s, "@?A");
    assert(pixel(s, 0, 0) == DEFAULT_FG && pixel(s, 2, 1) == DEFAULT_FG);
    assert(pixel(s, 1, 0) == 0 && pixel(s, 2, 0) == 0);
    nemo_sixel_reset(s, false);
    feed(s, "\"1;1;2;2@?A#0;2;0;0;100?");
    assert(pixel(s, 1, 0) == BLUE && pixel(s, 0, 1) == BLUE);
    assert(pixel(s, 1, 1) == BLUE && pixel(s, 2, 0) == 0);
    assert(pixel(s, 2, 1) == DEFAULT_FG);

    nemo_sixel_reset(s, false);
    feed(s, "\"1;1;64;64");
    assert(pixel(s, 0, 0) == 0 && pixel(s, 63, 63) == 0);
    assert(!nemo_sixel_stats(s).has_sixels);
    nemo_sixel_reset(s, false);
    feed(s, "\"1;1;64;64?");
    assert(pixel(s, 0, 0) == BLACK && pixel(s, 63, 63) == BLACK);
    assert(nemo_sixel_stats(s).has_sixels);
    assert(nemo_sixel_stats(s).allocated_bytes < 4096);

    /* Fill spans both tile boundaries without allocating background tiles;
     * growth beyond the original rectangle must leave the new holes clear. */
    nemo_sixel_reset(s, false);
    feed(s, "\"1;1;33;33@?A!31?@-----#3~#0;2;0;0;100?");
    NemoSixelStats st = nemo_sixel_stats(s);
    assert(st.width == 35 && st.height == 36);
    uint32_t row[4];
    assert(nemo_sixel_read_row(s, 0, 31, row, 4) == 4);
    assert(row[0] == BLUE && row[1] == BLUE && row[2] == 0 && row[3] == DEFAULT_FG);
    assert(pixel(s, 32, 32) == BLUE && pixel(s, 33, 32) == 0);
    assert(pixel(s, 1, 33) == 0 && pixel(s, 0, 35) == DEFAULT_FG);
    assert(st.allocated_bytes < 16000);
    nemo_sixel_free(s);
}

int main(void)
{
    implicit_background();
    basic_pixels();
    color_and_overlay();
    palette_identity();
    shared_palette_lifetime();
    extents_and_repeat();
    arbitrary_chunk_boundaries();
    rejected_inputs();
    bounded_memory();
    dense_image_and_partial_rows();
    deterministic_fuzz();
    register_counts();
    puts("Sixel decoder: pixel/color/stream/bounds/budget + 20000 fuzz cases passed");
    return 0;
}
