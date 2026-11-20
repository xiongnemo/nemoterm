// Methods of the bundled OpenConsole adapter. Each console has its own mode
// slots; the terminal frontend is the sole owner of actual window geometry.
bool AdaptDispatch::_NemoColumnPermission() const
{
    return _modes.test(Mode::NemoColumnPermissionSet) ? _modes.test(Mode::AllowDECCOLM) :
        _api.GetSystemMode(ITerminalApi::Mode::NemoColumnStartEnabled);
}

void AdaptDispatch::_NemoApplyWidth(const bool wide, const bool restore)
{
    if (_api.GetSystemMode(ITerminalApi::Mode::NemoColumnDenied) || !_NemoColumnPermission())
    {
        return;
    }
    _modes.set(Mode::NemoColumnWidthSet);
    _modes.set(Mode::Column, wide);
    if (!restore)
    {
        _DoSetTopBottomScrollingMargins(0, 0);
        _DoSetLeftRightScrollingMargins(0, 0);
    }
    if (!_modes.test(Mode::NemoKeepOnColumnChange))
    {
        EraseInDisplay(DispatchTypes::EraseType::All);
    }
    else if (!restore)
    {
        const auto page = _pages.ActivePage();
        page.Buffer().ResetLineRenditionRange(page.Top(), page.Bottom());
    }
    CursorPosition(1, 1);
}

void AdaptDispatch::NemoSaveRestoreModes(const VTParameters parameters, const bool save)
{
    if (!_api.IsConPTY())
    {
        UnknownSequence();
        return;
    }
    const bool denied = _api.GetSystemMode(ITerminalApi::Mode::NemoColumnDenied);
    bool other = false;
    parameters.for_each([&](const auto value) {
        const DispatchTypes::ModeParams mode = DispatchTypes::DECPrivateMode(value);
        switch (mode)
        {
        case DispatchTypes::DECCOLM_SetNumberOfColumns:
            if (denied || !_NemoColumnPermission()) break;
            if (save)
            {
                const bool wide = _modes.test(Mode::NemoColumnWidthSet) ? _modes.test(Mode::Column) :
                    _api.GetSystemMode(ITerminalApi::Mode::NemoColumnStartWide);
                _nemoSavedColumns.set(Mode::Column, wide);
            }
            else _NemoApplyWidth(_nemoSavedColumns.test(Mode::Column), true);
            break;
        case DispatchTypes::XTERM_EnableDECCOLMSupport:
            if (denied) break;
            if (save) _nemoSavedColumns.set(Mode::AllowDECCOLM, _NemoColumnPermission());
            else _ModeParamsHelper(DispatchTypes::XTERM_EnableDECCOLMSupport, _nemoSavedColumns.test(Mode::AllowDECCOLM));
            break;
        case DispatchTypes::NemoKeepOnColumnChange:
            // XTerm 412 saves the NOCLEAR_COLM mask even if it had been off.
            if (save) _nemoSavedColumns.set(Mode::NemoKeepOnColumnChange);
            else _ModeParamsHelper(DispatchTypes::NemoKeepOnColumnChange, _nemoSavedColumns.test(Mode::NemoKeepOnColumnChange));
            break;
        default:
            other = true;
        }
    });
    // Preserve upstream cursor reconciliation for unrelated modes.
    if (other) UnknownSequence();
}
