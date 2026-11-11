/* SPDX-License-Identifier: MIT
 * Exercise the real terminal parser, image lifecycle and shared budget using
 * the existing terminal test frontend, without changing its test entrypoint.
 */
#define main upstream_terminal_test_main
#include "test_terminal.c"
#undef main

static size_t image_count(Terminal *term)
{
    size_t count = 0;
    for (NemoTermImage *image = term->images; image; image = image->next) count++;
    return count;
}

static void image_feed(Mock *mk)
{
    term_data_fragmented(mk->term,
        "\033P0;1q\"1;1;32;32#1;2;100;0;0!32~\033\\");
}

static void test_sixel_framing(Mock *mk)
{
    test_context(mk, "Sixel byte framing and cancellation");
    reset(mk);
    term_data_fragmented(mk->term, "\033[?80h");
    image_feed(mk);
    IEQUAL(image_count(mk->term), 1);
    if (!mk->term->images) return;
    NemoSixelStats st = nemo_sixel_stats(mk->term->images->bitmap);
    IEQUAL(st.width, 32); IEQUAL(st.height, 32);
    IEQUAL(mk->term->images->pixel_width, 32);
    IEQUAL(mk->term->curs.y, 0);
    term_data_fragmented(mk->term, "\033Pq@\234");
    term_data_fragmented(mk->term, "\033Pq@\302\234");
    IEQUAL(image_count(mk->term), 3);
    term_data_fragmented(mk->term, "\033Pq@\030");
    term_data_fragmented(mk->term, "\033Pq@\032");
    term_data_fragmented(mk->term, "\033Pq@\033[H");
    IEQUAL(image_count(mk->term), 3);
    IEQUAL(mk->term->termstate, TOPLEVEL);
    term_data_fragmented(mk->term, "\033Pq!9999999999999999~\033\\");
    IEQUAL(image_count(mk->term), 3);
    /* Unknown DCS stays ignored and does not leak its payload as text. */
    term_data_fragmented(mk->term, "\033P$qmalformed\033\\");
    IEQUAL(mk->term->curs.x, 0);
    IEQUAL(mk->term->termstate, TOPLEVEL);
    /* A payload larger than the legacy 2048-byte OSC buffer still streams. */
    term_data_fragmented(mk->term, "\033Pq");
    for (unsigned i = 0; i < 3000; i++)
        term_data_fragmented(mk->term, "@$");
    term_data_fragmented(mk->term, "\033\\");
    IEQUAL(image_count(mk->term), 4);
}

static void test_sixel_erase(Mock *mk)
{
    reset(mk);
    test_context(mk, "Sixel cell erasure and text overwrite");
    term_data_fragmented(mk->term, "\033[?80h");
    image_feed(mk);
    uint32_t row[32];
    if (!mk->term->images) { IEQUAL(image_count(mk->term), 1); return; }
    IEQUAL(term_image_read_row(mk->term->images, 0, 0, row, 32), 32);
    IEQUAL(row[0], UINT32_C(0xffff0000));
    term_data_fragmented(mk->term, "X");
    IEQUAL(image_count(mk->term), 1);
    term_image_read_row(mk->term->images, 0, 0, row, 32);
    IEQUAL(row[0], 0); IEQUAL(row[7], 0);
    IEQUAL(row[8], UINT32_C(0xffff0000));
    term_data_fragmented(mk->term, "\033[X");
    term_image_read_row(mk->term->images, 0, 0, row, 32);
    IEQUAL(row[8], 0); IEQUAL(row[15], 0);
    IEQUAL(row[16], UINT32_C(0xffff0000));
    term_data_fragmented(mk->term, "\033[2K");
    term_image_read_row(mk->term->images, 0, 0, row, 32);
    IEQUAL(row[31], 0);
    term_data_fragmented(mk->term, "\033[2J");
    IEQUAL(image_count(mk->term), 0);
    IEQUAL(mk->term->image_bytes, 0);
}

static void test_sixel_screen_lifecycle(Mock *mk)
{
    reset(mk);
    test_context(mk, "Sixel alternate screen, scrollback and reset");
    term_size(mk->term, 24, 80, 100);
    image_feed(mk);
    IEQUAL(image_count(mk->term), 1);
    term_data_fragmented(mk->term, "\033[?1049h");
    image_feed(mk);
    IEQUAL(image_count(mk->term), 2);
    if (!mk->term->images || !mk->term->images->next) return;
    IEQUAL(mk->term->images->screen, 0);
    IEQUAL(mk->term->images->next->screen, 1);
    term_data_fragmented(mk->term, "\033[?1049l\033[24;1H\n");
    IEQUAL(mk->term->images->y, -1);
    term_data_fragmented(mk->term, "\033[3J");
    IEQUAL(image_count(mk->term), 1); /* only inactive alt image remains */
    term_data_fragmented(mk->term, "\033[?1049h");
    IEQUAL(image_count(mk->term), 0); /* 1049 clears the alt screen */
    image_feed(mk);
    term_data_fragmented(mk->term, "\033c");
    IEQUAL(image_count(mk->term), 0);
    IEQUAL(mk->term->image_bytes, 0);
    image_feed(mk);
    term_size(mk->term, 30, 100, 100);
    IEQUAL(image_count(mk->term), 0);
    image_feed(mk);
    term_set_cell_size(mk->term, 9, 17);
    IEQUAL(image_count(mk->term), 0);
    term_set_cell_size(mk->term, 8, 16);
}

static void test_sixel_top_partial_scroll(Mock *mk)
{
    reset(mk);
    test_context(mk, "Sixel top partial-scroll lower boundary and history");
    term_size(mk->term, 24, 80, 100);
    /* Each image occupies two cell rows: one inside, one crossing the
     * lower scrolling margin, and one wholly below the margin. */
    term_data_fragmented(mk->term, "\033[3;1H"); image_feed(mk);
    term_data_fragmented(mk->term, "\033[5;1H"); image_feed(mk);
    term_data_fragmented(mk->term, "\033[8;1H"); image_feed(mk);
    IEQUAL(image_count(mk->term), 3);
    term_data_fragmented(mk->term, "\033[1;5r\033[5;1H\n");
    IEQUAL(image_count(mk->term), 2);
    if (!mk->term->images || !mk->term->images->next) return;
    IEQUAL(mk->term->images->y, 1);
    IEQUAL(mk->term->images->next->y, 7);
    /* Further upward scrolls take the first image into history. Existing
     * history must continue moving, while the image below the margin stays. */
    term_data_fragmented(mk->term, "\n\n\n");
    IEQUAL(mk->term->images->y, -2);
    IEQUAL(mk->term->images->next->y, 7);
    IEQUAL(count234(mk->term->scrollback), 4);
    term_data_fragmented(mk->term, "\033[3J");
    IEQUAL(image_count(mk->term), 1);
    IEQUAL(mk->term->images->y, 7);
    /* Reverse scrolling never pulls bitmap pixels out of history. */
    term_data_fragmented(mk->term, "\033[1;1H\033M");
    IEQUAL(mk->term->images->y, 7);
}

static void test_sixel_budget(Mock *mk)
{
    reset(mk);
    test_context(mk, "Sixel multi-image shared budget and eviction");
    term_data_fragmented(mk->term, "\033[?80h");
    for (unsigned i = 0; i < 800; i++) {
        image_feed(mk);
        IEQUAL(mk->term->image_bytes <= NEMO_SIXEL_DEFAULT_BUDGET, true);
    }
    IEQUAL(image_count(mk->term) > 1, true);
    IEQUAL(image_count(mk->term) < 800, true);
    term_data_fragmented(mk->term, "\033Pq\"1;1;512;512");
    for (unsigned i = 0; i < 85; i++) {
        term_data_fragmented(mk->term, "!512~-");
        size_t inflight = nemo_sixel_stats(mk->term->sixel_pending).allocated_bytes;
        IEQUAL(inflight + mk->term->image_bytes <= NEMO_SIXEL_DEFAULT_BUDGET, true);
    }
    term_data_fragmented(mk->term, "!512B\033\\");
    IEQUAL(mk->term->image_bytes <= NEMO_SIXEL_DEFAULT_BUDGET, true);
    size_t accounted = 0;
    for (NemoTermImage *image = mk->term->images; image; image = image->next)
        accounted += sizeof(*image) + image->erased_bytes +
            nemo_sixel_stats(image->bitmap).allocated_bytes;
    IEQUAL(accounted, mk->term->image_bytes);
}

int main(void)
{
    Mock *mk = mock_new();
    mk->term = term_init(mk->conf, mk->ucsdata, &mk->tw);
    mk->ldisc = ldisc_create(mk->conf, mk->term, &mk->backend, &mk->seat);
    test_sixel_framing(mk);
    test_sixel_erase(mk);
    test_sixel_screen_lifecycle(mk);
    test_sixel_top_partial_scroll(mk);
    test_sixel_budget(mk);
    bool failed = mk->any_test_failed;
    mock_free(mk);
    puts(failed ? "Sixel terminal suite FAILED" : "Sixel terminal suite passed");
    return failed ? 1 : 0;
}
