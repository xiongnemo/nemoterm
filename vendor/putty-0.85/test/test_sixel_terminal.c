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

/* Older grid fixtures start with 16-pixel cells. Query the current destination
 * of the first raster pixel in that original cell row. */
static int image_row(Terminal *term, NemoTermImage *image, unsigned original_row)
{
    unsigned y = original_row * 16;
    if (image->lines[y].anchor == INT_MIN) return INT_MIN;
    return image->lines[y].anchor + y / term->cell_height;
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
    term_data_fragmented(mk->term, "\033Pq!32~");
    IEQUAL(mk->term->sixel_pending != NULL, true);
    term_size(mk->term, 25, 80, 0);
    IEQUAL(mk->term->sixel_pending == NULL, true);
    term_data_fragmented(mk->term, "-!32~\033\\\033[2;2H");
    IEQUAL(image_count(mk->term), 4);
    IEQUAL(mk->term->termstate, TOPLEVEL);
    IEQUAL(mk->term->curs.x, 1);
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
    IEQUAL(image_count(mk->term), 2); /* visible half and inactive alt remain */
    IEQUAL(image_row(mk->term, mk->term->images, 0), INT_MIN);
    IEQUAL(image_row(mk->term, mk->term->images, 1), 0);
    term_data_fragmented(mk->term, "\033[?1049h");
    IEQUAL(image_count(mk->term), 1); /* 1049 clears only the alt screen */
    image_feed(mk);
    term_data_fragmented(mk->term, "\033c");
    IEQUAL(image_count(mk->term), 0);
    IEQUAL(mk->term->image_bytes, 0);
    image_feed(mk);
    term_size(mk->term, 30, 100, 100);
    IEQUAL(image_count(mk->term), 1);
    term_set_cell_size(mk->term, 9, 17);
    IEQUAL(image_count(mk->term), 1);
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
    IEQUAL(image_count(mk->term), 3);
    if (!mk->term->images || !mk->term->images->next) return;
    IEQUAL(mk->term->images->y, 1);
    IEQUAL(image_row(mk->term, mk->term->images->next, 0), 3);
    IEQUAL(image_row(mk->term, mk->term->images->next, 1), 5);
    IEQUAL(mk->term->images->next->next->y, 7);
    /* Further upward scrolls take the first image into history. Existing
     * history must continue moving, while the image below the margin stays. */
    term_data_fragmented(mk->term, "\n\n\n");
    IEQUAL(mk->term->images->y, -2);
    IEQUAL(image_row(mk->term, mk->term->images->next, 0), 0);
    IEQUAL(image_row(mk->term, mk->term->images->next, 1), 5);
    IEQUAL(count234(mk->term->scrollback), 4);
    term_data_fragmented(mk->term, "\033[3J");
    IEQUAL(image_count(mk->term), 2);
    IEQUAL(mk->term->images->y, 0);
    IEQUAL(mk->term->images->next->y, 7);
    /* Reverse scrolling never pulls bitmap pixels out of history. */
    term_data_fragmented(mk->term, "\033[1;1H\033M");
    IEQUAL(image_row(mk->term, mk->term->images, 0), 1);
    IEQUAL(image_row(mk->term, mk->term->images, 1), 5);
    IEQUAL(mk->term->images->next->y, 7);
}

static void solid_image(Mock *mk, int width, int height)
{
    char *header = dupprintf("\033P0;1q\"1;1;%d;%d#1;2;100;0;0",
                             width, height);
    term_data_fragmented(mk->term, header); sfree(header);
    for (int y = 0; y < height; y += 6) {
        char *band = dupprintf("!%d%c-", width,
                               63 + ((1 << min(6, height-y))-1));
        term_data_fragmented(mk->term, band); sfree(band);
    }
    term_data_fragmented(mk->term, "\033\\");
}

static void test_sixel_grid_resize(Mock *mk)
{
    reset(mk);
    test_context(mk, "Sixel grid resize tracks text rows without bitmap copies");
    term_set_cell_size(mk->term, 8, 16);
    term_size(mk->term, 8, 10, 20);
    solid_image(mk, 32, 64);
    NemoTermImage *image = mk->term->images;
    if (!image) { IEQUAL(image_count(mk->term), 1); return; }
    NemoSixel *bitmap = image->bitmap;
    size_t bytes = mk->term->image_bytes;
    term_data_fragmented(mk->term, "\033[8;1H");
    for (unsigned repeat = 0; repeat < 100; repeat++) {
        term_size(mk->term, 6, 2, 20);
        IEQUAL(image_row(mk->term, image, 0), -2);
        IEQUAL(image_row(mk->term, image, 3), 1);
        IEQUAL(image->bitmap == bitmap, true);
        term_size(mk->term, 8, 10, 20);
        IEQUAL(image_row(mk->term, image, 0), 0);
        IEQUAL(image_row(mk->term, image, 3), 3);
        IEQUAL(mk->term->image_bytes, bytes);
    }
    uint32_t pixels[32];
    IEQUAL(term_image_read_row(image, 63, 0, pixels, 32), 32);
    IEQUAL(pixels[31], UINT32_C(0xffff0000));
    /* Deleting bottom rows while the cursor is above them must not restore
     * stale pixels when blank rows are subsequently added. */
    term_data_fragmented(mk->term, "\033[H");
    term_size(mk->term, 2, 10, 20);
    IEQUAL(image_row(mk->term, image, 0), 0);
    IEQUAL(image_row(mk->term, image, 1), 1);
    IEQUAL(image_row(mk->term, image, 2), INT_MIN);
    IEQUAL(image_row(mk->term, image, 3), INT_MIN);
    term_size(mk->term, 8, 10, 20);
    term_image_read_row(image, 32, 0, pixels, 32);
    IEQUAL(pixels[0], 0);
    /* A whole-row erase also discards the horizontally clipped tail. */
    term_size(mk->term, 8, 2, 20);
    term_data_fragmented(mk->term, "\033[2J");
    IEQUAL(image_count(mk->term), 0);
    IEQUAL(mk->term->image_bytes, 0);

    reset(mk);
    term_size(mk->term, 8, 10, 20);
    solid_image(mk, 16, 64);
    term_data_fragmented(mk->term, "\033[?1049h\033[H");
    solid_image(mk, 16, 64);
    image = mk->term->images;
    IEQUAL(image_count(mk->term), 2);
    if (!image || !image->next) return;
    term_size(mk->term, 2, 10, 20);
    IEQUAL(image_row(mk->term, image, 0), -2); /* main cursor was at row 3 */
    IEQUAL(image_row(mk->term, image, 3), 1);
    IEQUAL(image_row(mk->term, image->next, 0), 0);
    IEQUAL(image_row(mk->term, image->next, 2), INT_MIN);
    term_size(mk->term, 8, 10, 20);
    IEQUAL(image_row(mk->term, image, 0), 0);
    IEQUAL(image_row(mk->term, image->next, 2), INT_MIN);
    term_data_fragmented(mk->term, "\033[?1049l\033[8;1H\n\n");
    term_size(mk->term, 8, 10, 1);
    IEQUAL(image_row(mk->term, image, 0), INT_MIN);
    IEQUAL(image_row(mk->term, image, 1), -1);
    term_clrsb(mk->term);
    IEQUAL(image_row(mk->term, image, 1), INT_MIN);
    IEQUAL(image_row(mk->term, image, 2), 0);
    IEQUAL(image_row(mk->term, image->next, 0), 0);
}

static void test_sixel_split_scroll(Mock *mk)
{
    reset(mk);
    test_context(mk, "Sixel split scroll, erase, deletion and raster aspect");
    term_size(mk->term, 8, 10, 20);
    term_data_fragmented(mk->term, "\033[2;1H");
    solid_image(mk, 32, 64);
    NemoTermImage *image = mk->term->images;
    if (!image) { IEQUAL(image_count(mk->term), 1); return; }
    size_t bytes = mk->term->image_bytes;
    term_data_fragmented(mk->term, "\033[3;4r\033[S");
    IEQUAL(image_row(mk->term, image, 0), 1);
    IEQUAL(image_row(mk->term, image, 1), INT_MIN);
    IEQUAL(image_row(mk->term, image, 2), 2);
    IEQUAL(image_row(mk->term, image, 3), 4);
    uint32_t pixels[32];
    term_image_read_row(image, 16, 0, pixels, 32); IEQUAL(pixels[0], 0);
    for (unsigned repeat = 0; repeat < 100; repeat++) {
        term_data_fragmented(mk->term, "\033[T");
        IEQUAL(image_row(mk->term, image, 2), 3);
        term_data_fragmented(mk->term, "\033[S");
        IEQUAL(image_row(mk->term, image, 2), 2);
        IEQUAL(mk->term->image_bytes, bytes);
    }
    term_data_fragmented(mk->term, "\033[3;2HX");
    term_image_read_row(image, 32, 0, pixels, 32);
    IEQUAL(pixels[7], UINT32_C(0xffff0000)); IEQUAL(pixels[8], 0);
    IEQUAL(pixels[15], 0); IEQUAL(pixels[16], UINT32_C(0xffff0000));
    term_data_fragmented(mk->term, "\033[99T");
    IEQUAL(image_row(mk->term, image, 2), INT_MIN);
    IEQUAL(image_row(mk->term, image, 0), 1); IEQUAL(image_row(mk->term, image, 3), 4);
    term_data_fragmented(mk->term, "\033[r\033[2J");
    IEQUAL(mk->term->image_bytes, 0);

    /* One source pixel spans output rows 6..8. Erasing cell row zero must
     * leave rows 7 and 8 intact even though they share that source pixel. */
    term_set_cell_size(mk->term, 8, 7);
    term_data_fragmented(mk->term,
        "\033[?80h\033[H\033P0;1q\"3;2;8;6#1;2;100;0;0!3~"
        "#2;2;0;100;0!5~\033\\");
    image = mk->term->images;
    if (!image) { IEQUAL(image_count(mk->term), 1); return; }
    IEQUAL(image->pixel_width, 16); IEQUAL(image->pixel_height, 18);
    term_data_fragmented(mk->term, "\033[X");
    term_image_read_row(image, 6, 0, pixels, 16);
    IEQUAL(pixels[7], 0); IEQUAL(pixels[8], UINT32_C(0xff00ff00));
    term_image_read_row(image, 7, 0, pixels, 16);
    IEQUAL(pixels[0], UINT32_C(0xffff0000));
    IEQUAL(term_image_read_row(image, 7, 3, pixels, 5), 5);
    IEQUAL(pixels[0], UINT32_C(0xffff0000)); IEQUAL(pixels[2], UINT32_C(0xffff0000));
    IEQUAL(pixels[3], UINT32_C(0xff00ff00)); IEQUAL(pixels[4], UINT32_C(0xff00ff00));
    IEQUAL(term_image_read_row(image, 18, 0, pixels, 16), 0);
    IEQUAL(term_image_read_row(image, 7, 16, pixels, 16), 0);
    term_set_cell_size(mk->term, 8, 16);
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
            image->pixel_height*sizeof(NemoImageRow) +
            image->band_count*sizeof(unsigned char *) +
            nemo_sixel_stats(image->bitmap).allocated_bytes;
    IEQUAL(accounted, mk->term->image_bytes);
}

static void test_sixel_font_resize(Mock *mk)
{
    reset(mk);
    test_context(mk, "Sixel fixed raster, font resize, pixel erasure and scrolling");
    term_set_cell_size(mk->term, 8, 16);
    term_size(mk->term, 12, 40, 20);
    term_data_fragmented(mk->term, "\033[3;4H");
    solid_image(mk, 24, 48);
    NemoTermImage *image = mk->term->images;
    if (!image) { IEQUAL(image_count(mk->term), 1); return; }
    NemoSixel *bitmap = image->bitmap;
    uint32_t pixels[24];
    size_t initial = mk->term->image_bytes;
    IEQUAL(image->erased_bytes, 0);
    term_data_fragmented(mk->term, "\033[3;5H\033[X");
    IEQUAL(image->erased_bytes, 32*3);
    size_t with_hole = mk->term->image_bytes;
    IEQUAL(with_hole, initial+32*3);
    for (unsigned repeat = 0; repeat < 100; repeat++) {
        term_set_cell_size(mk->term, 16, 24);
        IEQUAL(image_count(mk->term), 1);
        IEQUAL(image->bitmap == bitmap, true);
        IEQUAL(image->pixel_width, 24); IEQUAL(image->pixel_height, 48);
        IEQUAL(term_image_pixel_y(image, 0, 24), 48);
        IEQUAL(term_image_pixel_y(image, 47, 24), 95);
        term_image_read_row(image, 15, 0, pixels, 24);
        IEQUAL(pixels[7], UINT32_C(0xffff0000)); IEQUAL(pixels[8], 0);
        IEQUAL(pixels[15], 0); IEQUAL(pixels[16], UINT32_C(0xffff0000));
        term_set_cell_size(mk->term, 9, 17);
        IEQUAL(term_image_pixel_y(image, 0, 17), 34);
        IEQUAL(term_image_pixel_y(image, 47, 17), 81);
        IEQUAL(mk->term->image_bytes, with_hole);
    }
    /* New cells cut through the original eight-pixel/sixteen-pixel grid. */
    term_data_fragmented(mk->term, "\033[4;5H\033[X");
    IEQUAL(image->erased_bytes, 48*3);
    term_image_read_row(image, 16, 0, pixels, 24);
    IEQUAL(pixels[9], UINT32_C(0xffff0000));
    term_image_read_row(image, 17, 0, pixels, 24);
    IEQUAL(pixels[8], UINT32_C(0xffff0000)); IEQUAL(pixels[9], 0);
    IEQUAL(pixels[17], 0); IEQUAL(pixels[18], UINT32_C(0xffff0000));
    term_image_read_row(image, 33, 0, pixels, 24); IEQUAL(pixels[9], 0);
    term_image_read_row(image, 34, 0, pixels, 24);
    IEQUAL(pixels[9], UINT32_C(0xffff0000));
    /* Scroll only the pixels in the new margins. No old-grid rounding. */
    term_data_fragmented(mk->term, "\033[4;5r\033[S");
    IEQUAL(term_image_pixel_y(image, 16, 17), 50);
    IEQUAL(term_image_pixel_y(image, 17, 17), INT64_MIN);
    IEQUAL(term_image_pixel_y(image, 33, 17), INT64_MIN);
    IEQUAL(term_image_pixel_y(image, 34, 17), 51);
    IEQUAL(term_image_pixel_y(image, 47, 17), 64);
    IEQUAL(image->erased_bytes, 32*3); /* freed the second mask band */
    for (unsigned repeat = 0; repeat < 100; repeat++) {
        term_set_cell_size(mk->term, 16, 24);
        IEQUAL(term_image_pixel_y(image, 0, 24), 48);
        IEQUAL(term_image_pixel_y(image, 34, 24), 58);
        term_set_cell_size(mk->term, 9, 17);
        IEQUAL(term_image_pixel_y(image, 34, 17), 51);
        IEQUAL(mk->term->image_bytes, with_hole);
    }
    term_data_fragmented(mk->term, "\033Pq!24~");
    term_set_cell_size(mk->term, 8, 16);
    IEQUAL(mk->term->sixel_pending == NULL, true);
    term_data_fragmented(mk->term, "\033\\\033[r\033[2J");
    IEQUAL(image_count(mk->term), 0); IEQUAL(mk->term->image_bytes, 0);

    reset(mk); term_size(mk->term, 12, 40, 20);
    solid_image(mk, 24, 48);
    image = mk->term->images;
    if (!image) { IEQUAL(image_count(mk->term), 1); return; }
    term_set_cell_size(mk->term, 9, 17);
    term_data_fragmented(mk->term, "\033[12;1H\n");
    term_set_cell_size(mk->term, 9, 24);
    term_clrsb(mk->term);
    IEQUAL(term_image_pixel_y(image, 23, 24), INT64_MIN);
    IEQUAL(term_image_pixel_y(image, 24, 24), 0);
    term_set_cell_size(mk->term, 9, 17);
    IEQUAL(term_image_pixel_y(image, 24, 17), 7);
    IEQUAL(term_image_pixel_y(image, 23, 17), INT64_MIN);
    term_set_cell_size(mk->term, 8, 16);
}

static void test_sixel_mask_budget(Mock *mk)
{
    reset(mk);
    test_context(mk, "Sixel lazy erase masks share budget and evict safely");
    term_set_cell_size(mk->term, 1, 1);
    term_data_fragmented(mk->term, "\033[?80h");
    for (unsigned i = 0; i < 1600; i++) image_feed(mk);
    size_t before = image_count(mk->term);
    /* Each image needs one 128-byte mask band for these ECHs. At a
     * nearly full budget, admission may remove the oldest images first. */
    for (unsigned y = 1; y <= 16; y++) {
        char *erase = dupprintf("\033[%u;2H\033[X", y);
        term_data_fragmented(mk->term, erase); sfree(erase);
    }
    IEQUAL(image_count(mk->term) > 1, true);
    IEQUAL(image_count(mk->term) < before, true);
    size_t accounted = 0;
    for (NemoTermImage *image = mk->term->images; image; image = image->next) {
        uint32_t pixels[32];
        term_image_read_row(image, 0, 0, pixels, 32);
        IEQUAL(pixels[0], UINT32_C(0xffff0000)); IEQUAL(pixels[1], 0);
        IEQUAL(pixels[2], UINT32_C(0xffff0000));
        IEQUAL(image->erased_bytes, 128);
        accounted += sizeof(*image) + 32*sizeof(NemoImageRow) +
            sizeof(unsigned char *) + 128 +
            nemo_sixel_stats(image->bitmap).allocated_bytes;
    }
    IEQUAL(accounted, mk->term->image_bytes);
    IEQUAL(accounted <= NEMO_SIXEL_DEFAULT_BUDGET, true);
    term_data_fragmented(mk->term, "\033[H\033[2J");
    /* Images extend below this small grid; RIS also releases unseen rows. */
    term_data_fragmented(mk->term, "\033c");
    IEQUAL(mk->term->image_bytes, 0);
    term_set_cell_size(mk->term, 8, 16);
}

static uint32_t image_random(uint32_t *state)
{
    *state = *state * UINT32_C(1664525) + UINT32_C(1013904223);
    return *state;
}

static void check_image_accounting(Mock *mk)
{
    size_t total = 0;
    for (NemoTermImage *image = mk->term->images; image; image = image->next) {
        size_t masks = 0, stride = ((size_t)image->pixel_width+7)/8;
        int live = 0;
        for (unsigned band = 0; band < image->band_count; band++)
            if (image->mask_bands[band])
                masks += stride*min(32, image->pixel_height-(int)band*32);
        for (int y = 0; y < image->pixel_height; y++) {
            NemoImageRow *row = &image->lines[y];
            if (row->anchor == INT_MIN) {
                IEQUAL(row->erased == NULL, true);
                continue;
            }
            live++;
            unsigned char *band = image->mask_bands[y/32];
            IEQUAL(row->erased == (band ? band+(y%32)*stride : NULL), true);
            unsigned erased = 0;
            if (row->erased)
                for (int x = 0; x < image->pixel_width; x++)
                    erased += !!(row->erased[x/8] & (1u << (x%8)));
            IEQUAL(erased, row->erased_pixels);
            IEQUAL(erased < (unsigned)image->pixel_width, true);
        }
        IEQUAL(live, image->live_rows);
        IEQUAL(live > 0, true);
        IEQUAL(masks, image->erased_bytes);
        size_t bytes = sizeof(*image) + image->pixel_height*sizeof(NemoImageRow) +
            image->band_count*sizeof(unsigned char *) + masks +
            nemo_sixel_stats(image->bitmap).allocated_bytes;
        IEQUAL(bytes, image->memory_bytes);
        total += bytes;
    }
    IEQUAL(total, mk->term->image_bytes);
    IEQUAL(total <= NEMO_SIXEL_DEFAULT_BUDGET, true);
}

static void test_sixel_mixed_lifecycle(Mock *mk)
{
    reset(mk);
    term_set_cell_size(mk->term, 8, 16);
    uint32_t state = UINT32_C(0x51e1f047);
    for (unsigned step = 0; step < 2000; step++) {
        test_context(mk, "Sixel mixed lifecycle stress step %u", step);
        unsigned choice = image_random(&state) >> 16;
        int a = (image_random(&state) >> 16) % 60 + 1;
        int b = (image_random(&state) >> 16) % 60 + 1;
        char *seq = NULL;
        switch (choice % 12) {
          case 0: case 1: case 2: case 3:
            seq = dupprintf("\033[%d;%dH", a%mk->term->rows+1, b%mk->term->cols+1);
            term_data_fragmented(mk->term, seq);
            solid_image(mk, a, b);
            break;
          case 4:
            term_set_cell_size(mk->term, a%19+1, b%27+1); break;
          case 5:
            term_data_fragmented(mk->term, "\033[r\033[2S"); break;
          case 6:
            seq = dupprintf("\033[2;%dr\033[3T", max(2, mk->term->rows-1));
            term_data_fragmented(mk->term, seq); break;
          case 7:
            seq = dupprintf("\033[%d;%dH\033[%dX", a%mk->term->rows+1,
                             b%mk->term->cols+1, a);
            term_data_fragmented(mk->term, seq); break;
          case 8:
            term_size(mk->term, a%30+1, b, choice%41); break;
          case 9:
            term_clrsb(mk->term); break;
          case 10:
            term_data_fragmented(mk->term, "\033[2K"); break;
          case 11:
            if (step%64 == 0) term_data_fragmented(mk->term, "\033c");
            else term_set_cell_size(mk->term, a%19+1, b%27+1);
            break;
        }
        sfree(seq);
        check_image_accounting(mk);
    }
    term_data_fragmented(mk->term, "\033c");
    IEQUAL(mk->term->image_bytes, 0);
    term_set_cell_size(mk->term, 8, 16);
}

int main(void)
{
    setvbuf(stdout, NULL, _IONBF, 0);
    Mock *mk = mock_new();
    mk->term = term_init(mk->conf, mk->ucsdata, &mk->tw);
    mk->ldisc = ldisc_create(mk->conf, mk->term, &mk->backend, &mk->seat);
    test_sixel_framing(mk);
    test_sixel_erase(mk);
    test_sixel_screen_lifecycle(mk);
    test_sixel_top_partial_scroll(mk);
    test_sixel_grid_resize(mk);
    test_sixel_split_scroll(mk);
    test_sixel_font_resize(mk);
    test_sixel_budget(mk);
    test_sixel_mask_budget(mk);
    test_sixel_mixed_lifecycle(mk);
    bool failed = mk->any_test_failed;
    mock_free(mk);
    puts(failed ? "Sixel terminal suite FAILED" : "Sixel terminal suite passed");
    return failed ? 1 : 0;
}
