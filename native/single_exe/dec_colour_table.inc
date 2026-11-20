// Identical palette row parsing in the console's Win32 shadow and the frontend.
// Original VT continues to the frontend unmodified; OSC dispatch below only
// updates the local console when an entire restore has terminated.
void StateMachine::_NemoDecColourCharacter(const wchar_t wch)
{
    if (!_nemoColourTable) return;
    if (_nemoColourEsc)
    {
        auto pending = std::move(_nemoColourTable);
        _nemoColourEsc = false;
        if (wch != L'\\') return;
        nemo_dec_colour_entry(pending.get());
        for (size_t i = 0; i < std::size(pending->entries); ++i)
        {
            const auto& colour = pending->entries[i];
            if (!colour.enabled) continue;
            wchar_t spec[16];
            const auto length = swprintf_s(spec, L"%u;#%02x%02x%02x", static_cast<unsigned>(i),
                                           static_cast<unsigned>(colour.r), static_cast<unsigned>(colour.g),
                                           static_cast<unsigned>(colour.b));
            if (length > 0)
            {
                _engine->ActionOscDispatch(4, std::wstring_view{spec, static_cast<size_t>(length)});
            }
        }
    }
    else if (wch == AsciiChars::ESC)
    {
        _nemoColourEsc = true;
    }
    else if (wch == AsciiChars::CAN || wch == AsciiChars::SUB)
    {
        _nemoColourTable.reset();
    }
}
