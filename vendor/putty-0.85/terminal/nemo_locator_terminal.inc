/* SPDX-License-Identifier: MIT
 * DEC Locator, compared with the independently captured XTerm(412) reference.
 * Shares the existing mouse-mode group. All storage is in Terminal or on stack.
 */
static bool nemo_locator_active(Terminal *term)
{
    return term->xterm_mouse == MOUSE_TRACK_LOCATOR && !term->no_mouse_rep;
}

static void nemo_locator_off(Terminal *term)
{
    term->xterm_mouse = 0;
    term->mouse_buttons = 0;
    term_update_raw_mouse_mode(term);
}

static unsigned nemo_locator_buttons(unsigned buttons)
{
    return (buttons & 10u) | ((buttons & 1u) << 2) | ((buttons & 4u) >> 2);
}

static void nemo_locator_reply(Terminal *term, int event, unsigned buttons,
                               int row, int col)
{
    char reply[80];
    int length = event ? sprintf(reply, "\033[%d;%u;%d;%d&w", event, buttons, row, col) :
                        sprintf(reply, "\033[0&w");
    if (term->ldisc) nemo_protocol_send(term, reply, length);
    if (term->locator.once) nemo_locator_off(term);
}

static bool nemo_locator_snapshot(Terminal *term, TermPointerState *p, bool event)
{
    return term->win->vt->get_pointer &&
        term->win->vt->get_pointer(term->win, p, event) &&
        term->cell_width > 0 && term->cell_height > 0 &&
        term->rows > 0 && term->cols > 0;
}

static bool nemo_locator_coords(Terminal *term, const TermPointerState *p,
                                int *row, int *col)
{
    int64_t r, c, max_r, max_c;
    if (term->locator.pixels) {
        r = (int64_t)p->y + 1; c = (int64_t)p->x + 1;
        max_r = (int64_t)p->text_y + (int64_t)term->rows * term->cell_height;
        max_c = (int64_t)p->text_x + (int64_t)term->cols * term->cell_width;
    } else {
        /* C truncation at the leading padding edge agrees with XTerm. */
        r = ((int64_t)p->y - p->text_y) / term->cell_height + 1;
        c = ((int64_t)p->x - p->text_x) / term->cell_width + 1;
        max_r = term->rows; max_c = term->cols;
    }
    bool inside = r >= 1 && c >= 1 && r <= max_r && c <= max_c;
    *row = (int)max(1, min(r, min(max_r, INT_MAX)));
    *col = (int)max(1, min(c, min(max_c, INT_MAX)));
    return inside;
}

static void nemo_locator_enable(Terminal *term)
{
    nemo_highlight_cancel(term, false);
    term->mouse_buttons = 0;
    term->raw_mouse_reported_code = -1;
    if (term->esc_args[0] < 1 || term->esc_args[0] > 2) {
        nemo_locator_off(term);
    } else {
        term->xterm_mouse = MOUSE_TRACK_LOCATOR;
        term->locator.once = term->esc_args[0] == 2;
        term->locator.pixels = term->esc_nargs > 1 && term->esc_args[1] == 1;
        term->locator.filter = false;
        term_update_raw_mouse_mode(term);
    }
}

static void nemo_locator_select(Terminal *term)
{
    for (int i = 0; i < term->esc_nargs; i++) {
        switch (term->esc_args[i]) {
          case 0: term->locator.events = 0; term->locator.filter = false; break;
          case 1: term->locator.events |= 1; break;
          case 2: term->locator.events &= ~1u; break;
          case 3: term->locator.events |= 2; break;
          case 4: term->locator.events &= ~2u; break;
        }
    }
}

static void nemo_locator_request(Terminal *term)
{
    if (term->locator.filter) {
        term->locator.filter = false;
        term->locator.events = 0;
        nemo_locator_off(term);
    }
    TermPointerState p;
    int row = 0, col = 0;
    if (!nemo_locator_active(term) || !nemo_locator_snapshot(term, &p, false) ||
        !nemo_locator_coords(term, &p, &row, &col)) {
        nemo_locator_reply(term, 0, 0, 0, 0);
        return;
    }
    nemo_locator_reply(term, 1, nemo_locator_buttons(p.buttons), row, col);
}

static bool nemo_locator_outside(Terminal *term, int row, int col)
{
    int *b = term->locator.bounds;
    return !b[0] || row < b[0] || row > b[2] || col < b[1] || col > b[3];
}

static void nemo_locator_filter(Terminal *term)
{
    if (!nemo_locator_active(term)) return;
    int *b = term->locator.bounds;
    bool explicit = false;
    for (int i = 0; i < 4; i++) {
        b[i] = i < term->esc_nargs ? (int)min(term->esc_args[i], (unsigned)INT_MAX) : 0;
        explicit |= b[i] != 0;
    }
    TermPointerState p;
    int row, col;
    if (!nemo_locator_snapshot(term, &p, false) ||
        !nemo_locator_coords(term, &p, &row, &col)) {
        if (explicit) nemo_locator_reply(term, 0, 0, 0, 0);
        else term->locator.filter = true;
        return;
    }
    /* The reference clamps explicit cell bounds to max_row/max_col (zero-based)
     * but substitutes omitted bounds with the one-based current position. */
    int max_row = term->locator.pixels ?
        (int)min((int64_t)p.text_y + (int64_t)term->rows * term->cell_height, INT_MAX) : term->rows-1;
    int max_col = term->locator.pixels ?
        (int)min((int64_t)p.text_x + (int64_t)term->cols * term->cell_width, INT_MAX) : term->cols-1;
    for (int i = 0; i < 4; i++)
        b[i] = !b[i] ? (i & 1 ? col : row) : min(b[i], i & 1 ? max_col : max_row);
    if (b[0] > b[2]) { int tmp = b[0]; b[0] = b[2]; b[2] = tmp; }
    if (b[1] > b[3]) { int tmp = b[1]; b[1] = b[3]; b[3] = tmp; }
    if (nemo_locator_outside(term, row, col))
        nemo_locator_reply(term, 10, nemo_locator_buttons(p.buttons), row, col);
    else term->locator.filter = true;
}

static void nemo_locator_mouse(Terminal *term, Mouse_Button button, Mouse_Action action,
                               int px, int py, bool cancelling)
{
    if (!nemo_locator_active(term) || px < 0 || py < 0 ||
        (int64_t)px >= (int64_t)term->cols * term->cell_width ||
        (int64_t)py >= (int64_t)term->rows * term->cell_height) return;
    TermPointerState p;
    if (!nemo_locator_snapshot(term, &p, true)) return;
    p.x = (int)min((int64_t)px + p.text_x, INT_MAX);
    p.y = (int)min((int64_t)py + p.text_y, INT_MAX);
    if (cancelling) p.buttons = term->mouse_buttons;
    int row, col;
    bool inside = nemo_locator_coords(term, &p, &row, &col);
    if (action == MA_MOVE || action == MA_DRAG) {
        if (term->locator.filter && (!inside || nemo_locator_outside(term, row, col))) {
            term->locator.filter = false;
            nemo_locator_reply(term, inside ? 10 : 0, nemo_locator_buttons(p.buttons), row, col);
        }
        return;
    }
    bool press = action == MA_CLICK;
    if ((!press && action != MA_RELEASE) || !(term->locator.events & (press ? 1u : 2u))) return;
    int index;
    switch (button) {
      case MBT_LEFT: index = 0; break;
      case MBT_MIDDLE: index = 1; break;
      case MBT_RIGHT: index = 2; break;
      case MBT_X1: index = 3; break;
      case MBT_X2: index = 4; break;
      default: return; /* Wheel routing remains the frontend's policy. */
    }
    unsigned bit = 1u << index;
    p.buttons = press ? p.buttons | bit : p.buttons & ~bit;
    term->mouse_buttons = press ? term->mouse_buttons | bit : term->mouse_buttons & ~bit;
    term->mouse_last_px = px; term->mouse_last_py = py;
    unsigned mask = nemo_locator_buttons(p.buttons);
    /* XTerm's fifth-button extension is outside DEC's four-button mask. */
    if (index == 4) mask |= 16;
    nemo_locator_reply(term, inside ? 2 + 2*index + !press : 0, mask, row, col);
    if (inside && term->locator.filter) {
        term->locator.filter = false;
        term->locator.events = 0;
        nemo_locator_off(term);
    }
}
