// Keep the console API's screen buffer in sync with the visible terminal.
void AdaptDispatch::NemoScrollColumns(const VTInt count, const bool right)
{
    if (!_api.IsConPTY())
    {
        UnknownSequence();
        return;
    }
    const auto page = _pages.ActivePage();
    const auto pos = page.Cursor().GetPosition();
    const auto [left, last] = _GetHorizontalMargins(page.Width());
    const auto [top, bottom] = _GetVerticalMargins(page, true);
    if (pos.x >= left && pos.x <= last && pos.y >= top && pos.y <= bottom)
    {
        _ScrollRectHorizontally(page, { left, top, last + 1, bottom + 1 }, right ? count : -count);
    }
}

// WriteLine restores both halves even when given a lone lead or trailer. That
// is appropriate for Read/WriteConsoleOutput backups, but a clipped glyph
// must not recreate its missing half across a scrolling margin. Split it in
// the original row, before any source cells or new neighbours have moved.
static void nemoSplitScrollGlyphs(TextBuffer& buffer, const til::rect& area, const til::CoordType cut)
{
    for (auto y = area.top; y < area.bottom; ++y)
    {
        const auto& row = buffer.GetRowByOffset(y);
        for (const auto x : { area.left, cut, area.right })
        {
            if (x > 0 && x < row.size() && row.DbcsAttrAt(x) == DbcsAttribute::Trailing)
            {
                buffer.GetMutableRowByOffset(y).ClearCell(x);
            }
        }
    }
}
