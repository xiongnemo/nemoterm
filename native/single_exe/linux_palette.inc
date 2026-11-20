// PuTTY and the Linux console accept ESC ] P nrrggbb without a terminator.
// This state belongs to one output parser, including across WriteFile calls.
// The original bytes still go to the frontend; OSC 4 is used only to update
// the console application's own colour table, via its existing dispatcher.
void StateMachine::_EventNemoOscPalette(const wchar_t wch)
{
    const auto digit = [](wchar_t ch) -> int {
        if (ch >= L'0' && ch <= L'9') return ch - L'0';
        if (ch >= L'a' && ch <= L'l') return ch - L'a' + 10;
        if (ch >= L'A' && ch <= L'L') return ch - L'A' + 10;
        return -1;
    };
    const auto n = digit(wch);
    if (n < 0 || (!_oscString.empty() && n > 15))
    {
        _EnterGround(); // consume the invalid digit, never the subsequent text
        return;
    }
    _oscString.push_back(wch);
    if (_oscString.size() != 7) return;

    const auto index = digit(_oscString.front());
    size_t code = 4;
    std::array<wchar_t, 10> spec{}; // "15;#rrggbb"
    size_t used = 0;
    if (index < 16)
    {
        if (index >= 10) spec[used++] = L'1';
        spec[used++] = static_cast<wchar_t>(L'0' + index % 10);
        spec[used++] = L';';
    }
    else
    {
        // PuTTY's additional slots G, I and L have native counterparts.
        // Its bold defaults and separate cursor-text colour are frontend
        // roles only: consume all seven digits without changing ANSI slots.
        if (index == 16) code = 10;
        else if (index == 18) code = 11;
        else if (index == 21) code = 12;
        else { _EnterGround(); return; }
    }
    spec[used++] = L'#';
    for (size_t i = 1; i < 7; ++i) spec[used++] = _oscString[i];
    _trace.DispatchSequenceTrace(_SafeExecute([&]() {
        return _engine->ActionOscDispatch(code, std::wstring_view{spec.data(), used});
    }));
    _EnterGround();
}
