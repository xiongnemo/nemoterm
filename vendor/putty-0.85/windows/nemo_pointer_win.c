/* SPDX-License-Identifier: MIT */
#include "nemo_pointer_win.h"
#include "nemo_pointer_glyph.h"

enum { CURSOR_SIZES = (NEMO_POINTER_CURSOR_MAX-32)/8+1 };
static HCURSOR owned[CURSOR_SIZES][NEMO_POINTER_GLYPH_COUNT];

HCURSOR nemo_pointer_cursor(NemoPointerShape shape, unsigned requested_size)
{
    LPCTSTR stock = NULL;
    switch (shape) {
      case NEMO_POINTER_NONE: case NEMO_POINTER_DEFAULT: stock = IDC_ARROW; break;
      case NEMO_POINTER_TEXT: stock = IDC_IBEAM; break;
      case NEMO_POINTER_POINTER: stock = IDC_HAND; break;
      case NEMO_POINTER_HELP: stock = IDC_HELP; break;
      case NEMO_POINTER_WAIT: stock = IDC_WAIT; break;
      case NEMO_POINTER_PROGRESS: stock = IDC_APPSTARTING; break;
      case NEMO_POINTER_CROSSHAIR: stock = IDC_CROSS; break;
      case NEMO_POINTER_MOVE: stock = IDC_SIZEALL; break;
      case NEMO_POINTER_E_RESIZE: case NEMO_POINTER_W_RESIZE:
      case NEMO_POINTER_EW_RESIZE: stock = IDC_SIZEWE; break;
      case NEMO_POINTER_N_RESIZE: case NEMO_POINTER_S_RESIZE:
      case NEMO_POINTER_NS_RESIZE: stock = IDC_SIZENS; break;
      case NEMO_POINTER_NE_RESIZE: case NEMO_POINTER_SW_RESIZE:
      case NEMO_POINTER_NESW_RESIZE: stock = IDC_SIZENESW; break;
      case NEMO_POINTER_NW_RESIZE: case NEMO_POINTER_SE_RESIZE:
      case NEMO_POINTER_NWSE_RESIZE: stock = IDC_SIZENWSE; break;
      case NEMO_POINTER_NOT_ALLOWED: case NEMO_POINTER_NO_DROP: stock = IDC_NO; break;
      default: break;
    }
    if (stock) return LoadCursor(NULL, stock);
    int index = nemo_pointer_glyph_index(shape);
    if (index < 0) return LoadCursor(NULL, IDC_ARROW);
    unsigned size = requested_size < 32 ? 32 : requested_size;
    if (size > NEMO_POINTER_CURSOR_MAX) size = NEMO_POINTER_CURSOR_MAX;
    unsigned bucket = (size-32+7)/8;
    HCURSOR *slot = &owned[bucket][index];
    if (!*slot) {
        size = 32+bucket*8;
        uint8_t and_mask[NEMO_POINTER_CURSOR_MAX*NEMO_POINTER_CURSOR_MAX/8];
        uint8_t xor_mask[sizeof(and_mask)];
        unsigned hot_x, hot_y;
        if (nemo_pointer_glyph_masks(shape, size, and_mask, xor_mask,
                                    sizeof(and_mask), &hot_x, &hot_y))
            *slot = CreateCursor(GetModuleHandleW(NULL), (int)hot_x, (int)hot_y,
                                 (int)size, (int)size, and_mask, xor_mask);
    }
    return *slot ? *slot : LoadCursor(NULL, IDC_ARROW);
}

void nemo_pointer_cursors_free(void)
{
    for (unsigned size = 0; size < CURSOR_SIZES; size++)
        for (unsigned index = 0; index < NEMO_POINTER_GLYPH_COUNT; index++) {
            HCURSOR cursor = owned[size][index];
            if (!cursor) continue;
            if (GetCursor() == cursor) SetCursor(LoadCursor(NULL, IDC_ARROW));
            DestroyCursor(cursor);
            owned[size][index] = NULL;
        }
}
