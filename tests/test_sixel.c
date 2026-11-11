/* SPDX-License-Identifier: MIT */
#include "nemo_sixel.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

#define WHITE UINT32_C(0xffffffff)
#define BLACK UINT32_C(0xff000000)
#define RED   UINT32_C(0xffff0000)
#define GREEN UINT32_C(0xff00ff00)
#define BLUE  UINT32_C(0xff0000ff)

static NemoSixel *fresh(bool transparent)
{
    NemoSixel *s = nemo_sixel_init(0, WHITE, BLACK, transparent);
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
    nemo_sixel_reset(s, WHITE, UINT32_C(0xff123456), false);
    feed(s, "\"1;1;2;3@");
    assert(pixel(s, 0, 0) == WHITE);
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
    nemo_sixel_reset(s, WHITE, BLACK, false);
    feed(s, "#1;2;100;0;0@#1;2;0;100;0@");
    assert(pixel(s, 0, 0) == RED && pixel(s, 1, 0) == GREEN);
    nemo_sixel_free(s);
}

static void extents_and_repeat(void)
{
    NemoSixel *s = fresh(false);
    NemoSixelStats st;
    feed(s, "\"2;1;3;2!40~-@-$!0@");
    st = nemo_sixel_stats(s);
    assert(st.width == 40 && st.height == 13);
    assert(st.aspect_vertical == 2 && st.aspect_horizontal == 1);
    assert(pixel(s, 39, 5) == WHITE);
    assert(pixel(s, 0, 6) == WHITE);
    assert(pixel(s, 0, 12) == WHITE);
    assert(pixel(s, 1, 6) == BLACK);
    nemo_sixel_reset(s, WHITE, BLACK, true);
    feed(s, "?@");
    st = nemo_sixel_stats(s);
    assert(st.width == 2 && st.height == 1); /* highest set bit, not six */
    assert(pixel(s, 0, 0) == 0 && pixel(s, 1, 0) == WHITE);
    nemo_sixel_reset(s, WHITE, BLACK, false);
    nemo_sixel_set_aspect(s, 10, 4);
    feed(s, "\"3;2;64;64");
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
        nemo_sixel_reset(s, WHITE, BLACK, true);
        assert(nemo_sixel_feed(s, payload, split));
        assert(nemo_sixel_feed(s, payload + split, len - split));
        assert(nemo_sixel_finish(s));
        assert(fingerprint(s) == expected);
    }
    nemo_sixel_reset(s, WHITE, BLACK, true);
    for (i = 0; i < len; i++) assert(nemo_sixel_feed(s, payload + i, 1));
    assert(nemo_sixel_finish(s) && fingerprint(s) == expected);
    assert(!nemo_sixel_feed(s, "~", 1)); /* finished object is immutable */
    nemo_sixel_free(s);
}

static void rejected_inputs(void)
{
    static const char *invalid[] = {
        "!4294967296~", "!99999999999999999999999999999999999999999999~",
        "!8193~", "!3#", "#256~", "#2;3;0;0;0~", "#2;2;100~",
        "#1;2;1;2;3;4~", "\"1;1;8193;1~", "\"1;1;8192;8192~",
        "\x18", "\x1a", "\x1b", "\x9c"
    };
    size_t i;
    NemoSixel *s = fresh(true);
    for (i = 0; i < sizeof(invalid) / sizeof(*invalid); i++) {
        NemoSixelStats st;
        nemo_sixel_reset(s, WHITE, BLACK, true);
        assert(!nemo_sixel_feed(s, invalid[i], strlen(invalid[i])));
        assert(!nemo_sixel_finish(s));
        assert(!nemo_sixel_feed(s, "~", 1));
        st = nemo_sixel_stats(s);
        assert(st.status != NEMO_SIXEL_OK);
        assert(st.allocated_bytes <= st.budget_bytes);
    }
    nemo_sixel_reset(s, WHITE, BLACK, true);
    assert(nemo_sixel_feed(s, "!12", 3));
    assert(!nemo_sixel_finish(s));
    nemo_sixel_reset(s, WHITE, BLACK, true);
    assert(nemo_sixel_feed(s, "#1;2;4", 6));
    assert(!nemo_sixel_finish(s));
    nemo_sixel_free(s);
    assert(!nemo_sixel_init(1, WHITE, BLACK, true));
}

static void bounded_memory(void)
{
    NemoSixel *s = nemo_sixel_init(8192, WHITE, BLACK, true);
    NemoSixelStats st;
    assert(s);
    assert(nemo_sixel_feed(s, "@", 1));
    st = nemo_sixel_stats(s);
    assert(st.allocated_bytes <= 8192);
    /* A second tile exceeds the budget despite tiny logical geometry. */
    assert(!nemo_sixel_feed(s, "!32@", 4));
    st = nemo_sixel_stats(s);
    assert(st.status == NEMO_SIXEL_LIMIT && st.allocated_bytes <= 8192);
    nemo_sixel_reset(s, WHITE, BLACK, true);
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
    assert(pixel(s, 511, 511) == WHITE);
    /* Start inside a tile and cross the next boundary. */
    assert(nemo_sixel_read_row(s, 511, 31, row, 40) == 40);
    for (i = 0; i < 40; i++) assert(row[i] == WHITE);
    assert(nemo_sixel_read_row(s, 511, 510, row, 40) == 2);
    assert(nemo_sixel_read_row(s, 512, 0, row, 40) == 0);
    assert(nemo_sixel_read_row(s, 0, 512, row, 40) == 0);
    nemo_sixel_free(s);
}

static void deterministic_fuzz(void)
{
    NemoSixel *s = nemo_sixel_init(16384, WHITE, BLACK, true);
    uint32_t rng = 0xc0ffee;
    unsigned trial, i;
    assert(s);
    for (trial = 0; trial < 20000; trial++) {
        NemoSixelStats st;
        nemo_sixel_reset(s, WHITE, BLACK, (trial & 1) != 0);
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

int main(void)
{
    basic_pixels();
    color_and_overlay();
    extents_and_repeat();
    arbitrary_chunk_boundaries();
    rejected_inputs();
    bounded_memory();
    dense_image_and_partial_rows();
    deterministic_fuzz();
    puts("Sixel decoder: pixel/color/stream/bounds/budget + 20000 fuzz cases passed");
    return 0;
}
