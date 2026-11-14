/* SPDX-License-Identifier: MIT
 * Included by the shared graphics lifecycle suite. Native tests independently
 * exercise real image codecs; this mock isolates transport/terminal ownership. */
static bool inline_mock_decode(TermWin *win, const void *data, size_t length,
                               NemoRaster *out, NemoRasterAdmission admit, void *ctx)
{
    (void)win;
    if (length != 3 || (memcmp(data, "abc", 3) && memcmp(data, "big", 3))) return false;
    unsigned width = 8, height = 32;
    if (!memcmp(data, "big", 3)) width = height = 512;
    size_t bytes = width * height * 4;
    if (!admit(ctx, width, height, bytes)) return false;
    *out = (NemoRaster){.width=width, .height=height, .bytes=bytes,
        .pixels=malloc(bytes), .partial_alpha=true};
    if (!out->pixels) return false;
    for (unsigned y = 0; y < height; y++)
        for (unsigned x = 0; x < width; x++)
            out->pixels[y*width+x] = 0x80000000 | (y << 8) | x;
    return true;
}

static void test_inline_images(Mock *mk)
{
    TermWinVtable vt = mock_termwin_vt;
    vt.decode_image = inline_mock_decode;
    mk->tw.vt = &vt;
    reset(mk);
    term_set_cell_size(mk->term, 8, 16);
    test_context(mk, "iTerm streamed image ownership and placement");
    term_data_fragmented(mk->term,
        "\033[2;3H\033]1337;File=inline=1:YWJj\033\\");
    IEQUAL(image_count(mk->term), 1);
    if (mk->term->images) {
        NemoTermImage *image = mk->term->images;
        IEQUAL(image->pixel_width, 8); IEQUAL(image->pixel_height, 32);
        IEQUAL(image->x, 2); IEQUAL(image->y, 1);
        IEQUAL(mk->term->curs.y, 2);
        uint32_t row[8];
        IEQUAL(term_image_read_row(image, 7, 0, row, 8), 8);
        for (unsigned x = 0; x < 8; x++) IEQUAL(row[x], 0x80000700 | x);
        IEQUAL(mk->term->image_bytes, image->memory_bytes + image->source->memory_bytes);
    }
    IEQUAL(mk->term->iterm_pending == NULL, true);
    term_data_fragmented(mk->term, "\033]1337;FileEnd\007");
    IEQUAL(image_count(mk->term), 1);
    term_data_fragmented(mk->term, "\033[2J");
    IEQUAL(image_count(mk->term), 0); IEQUAL(mk->term->image_bytes, 0);

    test_context(mk, "iTerm multipart interleaving and recovery");
    term_data_fragmented(mk->term,
        "\033]1337;MultipartFile=inline=1;width=16px;height=16px;preserveAspectRatio=0\007"
        "\033]1337;FilePart=Y\007\033]2;interleaved title\007"
        "\033P0;1q#1;2;100;0;0~\033\\"
        "\033]1337;FilePart=WJ\007\033]1337;FilePart=j\007"
        "\033]1337;FileEnd\007");
    IEQUAL(image_count(mk->term), 2);
    if (mk->term->images && mk->term->images->next) {
        NemoTermImage *image = mk->term->images->next;
        IEQUAL(image->pixel_width, 16); IEQUAL(image->pixel_height, 16);
        uint32_t row[16];
        IEQUAL(term_image_read_row(image, 7, 0, row, 16), 16);
        for (unsigned x = 0; x < 16; x++) IEQUAL(row[x], 0x80000e00 | (x/2));
    }
    IEQUAL(mk->term->iterm_pending == NULL, true);
    const char *abort[] = {"\030", "\032", "\r", "\n", "\033[H"};
    for (unsigned i = 0; i < lenof(abort); i++) {
        reset(mk);
        term_data_fragmented(mk->term, "\033]1337;File=inline=1:YWJj");
        term_data_fragmented(mk->term, abort[i]);
        IEQUAL(mk->term->iterm_pending == NULL, true);
        IEQUAL(image_count(mk->term), 0);
        term_data_fragmented(mk->term, "\033]1337;File=inline=1:YWJj\007");
        IEQUAL(image_count(mk->term), 1);
    }
    reset(mk);
    term_data_fragmented(mk->term, "\033]1337;MultipartFile=inline=1\007"
        "\033]1337;FilePart=YWJj\007");
    IEQUAL(mk->term->iterm_pending != NULL, true);
    term_size(mk->term, 25, 81, 100);
    IEQUAL(mk->term->iterm_pending == NULL, true);
    term_data_fragmented(mk->term, "\033]1337;FileEnd\007");
    IEQUAL(image_count(mk->term), 0);
    test_context(mk, "iTerm sources share the Sixel retention budget");
    reset(mk);
    for (unsigned i = 0; i < 5; i++) {
        term_data_fragmented(mk->term,
            "\033[H\033]1337;File=inline=1;width=1;height=1;preserveAspectRatio=0:Ymln\007");
        IEQUAL(mk->term->image_bytes <= NEMO_SIXEL_DEFAULT_BUDGET, true);
    }
    IEQUAL(image_count(mk->term), 3);
    term_data_fragmented(mk->term, "\033]1337;MultipartFile=inline=1\007\033]1337;FilePart=");
    for (unsigned i = 0; i < 1000; i++)
        term_data_fragmented(mk->term, "YWJjYWJjYWJjYWJjYWJjYWJjYWJjYWJj");
    IEQUAL(mk->term->image_bytes + nemo_iterm_memory(mk->term->iterm_pending)
           <= NEMO_SIXEL_DEFAULT_BUDGET, true);
    term_data_fragmented(mk->term, "\007\033P0;1q!100~");
    IEQUAL(mk->term->image_bytes + nemo_iterm_memory(mk->term->iterm_pending) +
           nemo_sixel_stats(mk->term->sixel_pending).allocated_bytes
           <= NEMO_SIXEL_DEFAULT_BUDGET, true);
    term_data_fragmented(mk->term, "\033\\\033c");
    IEQUAL(mk->term->image_bytes, 0);
    IEQUAL(mk->term->iterm_pending == NULL, true);
    /* The entire image OSC must be ignored by frontends without a decoder. */
    mk->tw.vt = &mock_termwin_vt;
    reset(mk);
    term_data_fragmented(mk->term, "\033]1337;File=inline=1:YWJj\007");
    IEQUAL(mk->term->curs.x, 0); IEQUAL(image_count(mk->term), 0);
    IEQUAL(mk->term->iterm_pending == NULL, true);
}
