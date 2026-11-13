/* SPDX-License-Identifier: MIT
 * Prepared SPA/EPA regression checks. Not run during the runtime-test pause. */
#include "../../../tests/guarded_area_cases.h"

static void test_guarded_area(Mock *mk)
{
    Terminal *t = mk->term;
    bool old_checksum = conf_get_bool(mk->conf, CONF_nemo_allow_checksum);
    conf_set_bool(mk->conf, CONF_nemo_allow_checksum, true);
    term_reconfig(t, mk->conf);
    mk->ucsdata->line_codepage = CP_UTF8;
    for (size_t i = 0; i < lenof(guarded_area_cases); i++) {
        reset(mk);
        test_context(mk, "authored guarded area: %s", guarded_area_cases[i].name);
        erase_reply(mk, guarded_area_cases[i].sequence, guarded_area_cases[i].reply);
        IEQUAL(mk->clipboard_writes, 0);
    }

    erase_setup(mk, "ISO guards retain whole wide glyphs and combining chains");
    term_data_fragmented(t, "\033V\xe4\xb8\xad" "e\xcc\x81\033Wz"
                         "\033[1;2H\033[4X");
    IEQUAL(get_termchar(t, 0, 0).chr, 0x4e2d);
    IEQUAL(get_termchar(t, 1, 0).chr, UCSWIDE);
    IEQUAL(get_termchar(t, 2, 0).chr, CSET_ASCII|'e');
    IEQUAL(get_termchar(t, 2, 0).cc_next != 0, true);
    IEQUAL(get_termchar(t, 3, 0).chr, CSET_ASCII|' ');
    IEQUAL(t->curs.x, 1);

    erase_setup(mk, "protected selection, hyperlinks and Sixel survive ordinary erasure");
    term_data_fragmented(t, "\033V\033]8;;https://example.org/guarded\033\\ A "
                         "\033]8;;\033\\\033W B \033[H\033[?80h"
                         "\033P0;1q\"1;1;48;16#1;2;100;0;0!48~\033\\");
    uint32_t link = get_termchar(t, 0, 0).hyperlink;
    t->selstate = SELECTED;
    t->selstart = (pos){0, 0}; t->selend = (pos){0, 3};
    term_data_fragmented(t, "\033[H\033[6X");
    erase_row_text(mk, 0, " A    ");
    IEQUAL(t->selstate, SELECTED);
    IEQUAL(link != 0, true);
    IEQUAL(get_termchar(t, 0, 0).hyperlink, link);
    uint32_t pixels[48];
    IEQUAL(t->images != NULL, true);
    if (t->images) {
        IEQUAL(term_image_read_row(t->images, 0, 0, pixels, 48), 48);
        for (int x = 0; x < 48; x++)
            IEQUAL(pixels[x], x < 24 ? UINT32_C(0xffff0000) : 0);
    }
    term_data_fragmented(t, "\033[1;1;1;6${");
    erase_row_text(mk, 0, "      ");
    IEQUAL(t->selstate, NO_SELECTION);
    IEQUAL(get_termchar(t, 0, 0).hyperlink, 0);
    if (t->images) {
        term_image_read_row(t->images, 0, 0, pixels, 48);
        for (int x = 0; x < 48; x++) IEQUAL(pixels[x], 0);
    }

    erase_setup(mk, "ISO family follows soft reset and is shared between screens");
    term_data_fragmented(t, "\033VABC\033W\033[?47h\033[0\"q\033[?47l\033[2K");
    erase_row_text(mk, 0, "   ");
    IEQUAL(t->protection_mode, NEMO_PROTECT_DEC);
    term_data_fragmented(t, "\033V\033[?47h\033[!p\033[?47l");
    IEQUAL(t->protection_mode, NEMO_PROTECT_NONE);

    erase_setup(mk, "guarded text survives compressed history and reflow");
    for (int i = 0; i < 20; i++)
        term_data_fragmented(t, "\033VPROTECT\033Wtail\r\n");
    term_size(t, 8, 6, 100);
    int protected_count = 0;
    for (int row = -count234(t->scrollback); row < t->rows; row++) {
        termline *line = term_get_line(t, row);
        for (int col = 0; col < line->cols; col++)
            if (line->chars[col].truecolour.decoration & CELL_PROTECTED)
                protected_count++;
        term_release_line(line);
    }
    IEQUAL(protected_count, 140);
    IEQUAL(t->protection_mode, NEMO_PROTECT_ISO);

    erase_setup(mk, "legacy raw C1 aliases use the configured control-byte table");
    mk->ucsdata->line_codepage = CP_ISO8859_1;
    unsigned char old_spa = mk->ucsdata->unitab_ctrl[0x96];
    unsigned char old_epa = mk->ucsdata->unitab_ctrl[0x97];
    mk->ucsdata->unitab_ctrl[0x96] = 0x96;
    mk->ucsdata->unitab_ctrl[0x97] = 0x97;
    term_data_fragmented(t, "\226ABC\227DEF\033[2K");
    erase_row_text(mk, 0, "ABC   ");
    IEQUAL(t->protection_mode, NEMO_PROTECT_ISO);
    mk->ucsdata->unitab_ctrl[0x96] = old_spa;
    mk->ucsdata->unitab_ctrl[0x97] = old_epa;

    erase_setup(mk, "UTF-8 C1 text and wrong intermediates do not start guarded areas");
    term_data_fragmented(t, "\302\226A\033#V\033 V\033[V");
    IEQUAL(t->protection_mode, NEMO_PROTECT_NONE);
    IEQUAL(get_termchar(t, 0, 0).truecolour.decoration & CELL_PROTECTED, 0);
    IEQUAL(get_termchar(t, 1, 0).truecolour.decoration & CELL_PROTECTED, 0);
    conf_set_bool(mk->conf, CONF_nemo_allow_checksum, old_checksum);
    term_reconfig(t, mk->conf);
    reset(mk);
}
