"""Prepare a pinned OpenConsole source overlay. Never modifies the submodule.

Build outputs stay under build/. Changes below deliberately fail if their
upstream anchors change; upgrading the submodule requires reviewing them.
"""
import argparse
import io
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import zipfile
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
REVISION = "f6de9e0618015def1c9dda5b82f9d3abf03eb799"
UPSTREAM = ROOT / "vendor/microsoft-terminal"
DEST = ROOT / "build/openconsole-single"


def replace(path, before, after):
    value = path.read_text(encoding="utf-8-sig")
    assert value.count(before) == 1, f"Upstream anchor changed: {path}: {before}"
    path.write_text(value.replace(before, after), encoding="utf-8")


def patch_visual_writer():
    # The two endpoints travel in the single PE. GetProcessHandle identifies
    # the writer of this call even when it was launched under another shell.
    def sub(path, before, after):
        replace(DEST / 'src' / path, before, after)

    sub('server/ConsoleShimPolicy.h', '    bool IsCmdExe()',
        '    bool SuppliesVisualCells() const noexcept { return _visualCells; }\n    bool IsCmdExe()')
    sub('server/ConsoleShimPolicy.h', '    bool _isCmd', '    bool _visualCells{ false };\n    bool _isCmd')
    sub('server/ConsoleShimPolicy.cpp', '#include "ConsoleShimPolicy.h"', '''#include "ConsoleShimPolicy.h"
#include <winver.h>
#pragma comment(lib, "version.lib")

// Limit this compatibility rule to the native client build whose wire and
// glyph order were measured. Unknown versions retain the normal policy.
static bool measuredVisualWriter(const std::filesystem::path& path)
{
    DWORD unused{};
    const auto size = GetFileVersionInfoSizeW(path.c_str(), &unused);
    if (!size || size > 1024 * 1024) return false;
    std::vector<BYTE> data(size);
    void* block{};
    UINT bytes{};
    if (!GetFileVersionInfoW(path.c_str(), 0, size, data.data()) ||
        !VerQueryValueW(data.data(), L"\\\\", &block, &bytes) || bytes < sizeof(VS_FIXEDFILEINFO)) return false;
    const auto& info = *static_cast<const VS_FIXEDFILEINFO*>(block);
    return info.dwSignature == VS_FFI_SIGNATURE && info.dwFileVersionMS == MAKELONG(1, 2) &&
           info.dwFileVersionLS == MAKELONG(0, 322);
}''')
    sub('server/ConsoleShimPolicy.cpp', '        _isCmd =',
        '        _visualCells = til::equals_insensitive_ascii(clientName, L"claude.exe") && measuredVisualWriter(processName);\n        _isCmd =')
    sub('host/_stream.cpp', '#include "writeData.hpp"', '''#include "writeData.hpp"
#include "../server/ApiMessage.h"
#include "../server/ProcessHandle.h"

static bool visualWriter(CONSOLE_API_MSG* message)
{
    const auto process = message ? message->GetProcessHandle() : nullptr;
    return process && process->GetShimPolicy().SuppliesVisualCells();
}''')
    for name, sig in [('WriteCharsVT', 'const std::wstring_view& str'), ('DoWriteConsole', 'std::wstring_view str')]:
        prefix = f'{name}(SCREEN_INFORMATION& screenInfo, {sig}'
        sub('host/_stream.h', prefix + ');', prefix + ', bool visual = false);')
        sub('host/_stream.cpp', prefix + ')', prefix + ', bool visual)')
    sub('host/_stream.cpp', 'WriteCharsVT(screenInfo, str);', 'WriteCharsVT(screenInfo, str, visual);')
    for obj, arg in [('screenInfo', 'wstr'), ('context', 'buffer')]:
        sub('host/_stream.cpp', f'DoWriteConsole({obj}, {arg});', f'DoWriteConsole({obj}, {arg}, visualWriter(pWaitReplyMessage));')
    for arg in ['screenInfo, std::move(wstr)', 'context, std::wstring{ buffer }']:
        sub('host/_stream.cpp', f'new WriteData({arg}, gci.OutputCP)', f'new WriteData({arg}, gci.OutputCP, visualWriter(pWaitReplyMessage))')
    sub('host/writeData.hpp', 'const UINT uiOutputCodepage);', 'const UINT uiOutputCodepage, bool visual = false);')
    sub('host/writeData.hpp', '    bool _fLeadByteCaptured;', '    bool _visual;\n    bool _fLeadByteCaptured;')
    sub('host/writeData.cpp', 'const UINT uiOutputCodepage) :', 'const UINT uiOutputCodepage, bool visual) :')
    sub('host/writeData.cpp', '    _fLeadByteCaptured(false),', '    _visual(visual),\n    _fLeadByteCaptured(false),')
    sub('host/writeData.cpp', 'DoWriteConsole(_siContext, _pwchContext)', 'DoWriteConsole(_siContext, _pwchContext, _visual)')
    # Use the parser's printable spans, never raw WriteFile boundaries: an
    # application may split a DCS, SGR or title across multiple calls.
    for path, sig in [('terminal/parser/stateMachine.hpp', 'void ProcessString'), ('terminal/parser/stateMachine.cpp', 'void StateMachine::ProcessString')]:
        default = ' = false' if path.endswith('.hpp') else ''
        sub(path, sig + '(const std::wstring_view string)', sig + f'(const std::wstring_view string, bool visual{default})')
    sub('terminal/parser/stateMachine.hpp', '        Count,\n    };\n\n    struct Injection',
        '        VisualCellsBegin, VisualCellsEnd,\n        Count,\n    };\n\n    struct Injection')
    sub('terminal/parser/stateMachine.cpp', '                _ActionPrintString(_CurrentRun());', '''                if (visual) _injections.emplace_back(InjectionType::VisualCellsBegin, _runOffset);
                _ActionPrintString(_CurrentRun());
                if (visual) InjectSequence(InjectionType::VisualCellsEnd);''')
    sub('host/_stream.cpp', 'stateMachine.ProcessString(str);', 'stateMachine.ProcessString(str, visual && !!writer);')
    sub('host/_stream.cpp', '            case InjectionType::RIS:', r'''            case InjectionType::VisualCellsBegin:
                sequence = "\x1b]777;nemoterm:visual=1\x07";
                break;
            case InjectionType::VisualCellsEnd:
                sequence = "\x1b]777;nemoterm:visual=0\x07";
                break;
            case InjectionType::RIS:''')


def patch_dec_colour_table():
    parser = DEST / 'src/terminal/parser'
    shutil.copyfile(ROOT / 'vendor/putty-0.85/terminal/nemo_dec_colour.h', parser / 'nemo_dec_colour.h')
    shutil.copyfile(ROOT / 'native/single_exe/dec_colour_table.inc', parser / 'nemo_dec_colour_table.inc')
    hpp, cpp = parser / 'stateMachine.hpp', parser / 'stateMachine.cpp'
    replace(hpp, '#include <memory>', '#include <memory>\n#include "nemo_dec_colour.h"')
    anchor = '        IStateMachineEngine::StringHandler _dcsStringHandler;'
    replace(hpp, anchor, anchor + """
        std::unique_ptr<NemoPendingColourTable> _nemoColourTable;
        bool _nemoColourEsc = false;
        void _NemoDecColourCharacter(wchar_t wch);""")
    anchor = 'void StateMachine::_ActionDcsDispatch(const wchar_t wch)'
    replace(cpp, anchor, '#include "nemo_dec_colour_table.inc"\n\n' + anchor)
    anchor = '        _dcsStringHandler = _engine->ActionDcsDispatch(_identifier.Finalize(wch), { _parameters.data(), _parameters.size() });'
    replace(cpp, anchor, """        const auto id = _identifier.Finalize(wch);
        if (!_isEngineForInput && id == VTID("$p") && _parameters.size() == 1 && _parameters.front().value_or(0) == 2)
        {
            _nemoColourTable = std::make_unique<NemoPendingColourTable>();
            _nemoColourEsc = false;
            _dcsStringHandler = [this](const wchar_t ch) {
                if (_nemoColourTable && ch >= L' ') nemo_dec_colour_byte(_nemoColourTable.get(), ch);
                return true;
            };
        }
        else
        {
            _dcsStringHandler = _engine->ActionDcsDispatch(id, { _parameters.data(), _parameters.size() });
        }""")
    anchor = 'void StateMachine::ProcessCharacter(const wchar_t wch)\n{'
    replace(cpp, anchor, anchor + '\n    if (_nemoColourTable) _NemoDecColourCharacter(wch);')


def patch_linux_palette():
    # Keep Windows buffer reads in step with the unchanged byte stream sent
    # to Nemoterm. The input parser continues to parse OSC replies normally.
    parser = DEST / 'src/terminal/parser'
    cpp, hpp = parser / 'stateMachine.cpp', parser / 'stateMachine.hpp'
    shutil.copyfile(ROOT / 'native/single_exe/linux_palette.inc', parser / 'nemo_linux_palette.inc')
    replace(hpp, '            OscParam,', '            OscParam,\n            NemoOscPalette,')
    anchor = '        void _EventOscParam(const wchar_t wch);'
    replace(hpp, anchor, anchor + '\n        void _EventNemoOscPalette(const wchar_t wch);')
    replace(hpp, '        VTInt _oscParameter;', '        VTInt _oscParameter;\n        bool _nemoOscStart{};')
    anchor = '    _state = VTStates::OscParam;'
    replace(cpp, anchor, anchor + '\n    _nemoOscStart = !_isEngineForInput;')
    anchor = 'void StateMachine::_EventOscParam(const wchar_t wch)\n{'
    replace(cpp, anchor, '#include "nemo_linux_palette.inc"\n\n' + anchor + """
    if (std::exchange(_nemoOscStart, false))
    {
        if (wch == L'P')
        {
            _state = VTStates::NemoOscPalette;
            return;
        }
        if (wch == L'R')
        {
            // PuTTY resets the indexed table and all session colour overrides.
            // Reset the corresponding indexed and dynamic resources the host has.
            for (const VTInt reset : { 104, 110, 111, 112, 117 })
            {
                _oscParameter = reset;
                _ActionOscDispatch();
            }
            _EnterGround();
            return;
        }
    }""")
    anchor = '        case VTStates::OscParam:\n            return _EventOscParam(wch);'
    replace(cpp, anchor, anchor + '\n        case VTStates::NemoOscPalette:\n            return _EventNemoOscPalette(wch);')


def patch_column_edits():
    src = DEST / 'src'
    adapter = src / 'terminal/adapter/adaptDispatch.cpp'
    anchor = 'void AdaptDispatch::_ScrollRectHorizontally(const Page& page, const til::rect& scrollRect, const VTInt delta)'
    shutil.copyfile(ROOT / 'native/single_exe/column_edits.inc', adapter.parent / 'nemo_column_edits.inc')
    replace(adapter, anchor, '#include "nemo_column_edits.inc"\n\n' + anchor)
    anchor = '    const auto absoluteDelta = std::min(std::abs(delta), scrollRect.width());'
    replace(adapter, anchor, anchor + '''
    if (_api.IsConPTY())
    {
        nemoSplitScrollGlyphs(textBuffer, scrollRect, delta > 0 ? scrollRect.right - absoluteDelta : scrollRect.left + absoluteDelta);
    }''')
    anchor = '        void DeleteColumn(const VTInt distance) override;'
    replace(src / 'terminal/adapter/adaptDispatch.hpp', anchor, '        void NemoScrollColumns(VTInt count, bool right) override;\n' + anchor)
    anchor = '    virtual void UnknownSequence() noexcept = 0;'
    replace(src / 'terminal/adapter/ITermDispatch.hpp', anchor, anchor + '\n    virtual void NemoScrollColumns(VTInt, bool) { UnknownSequence(); }')
    anchor = '    case CsiActionCodes::ICH_InsertCharacter:'
    replace(src / 'terminal/parser/OutputStateMachineEngine.cpp', anchor, '''    case VTID(" @"):
    case VTID(" A"):
        _dispatch->NemoScrollColumns(parameters.at(0), id == VTID(" A"));
        break;
''' + anchor)


def patch_column_resize_owner():
    src = DEST / 'src'
    def sub(file, before, after):
        replace(src / file, before, after)

    # Only the frontend can approve geometry. The Windows console still has
    # to apply the corresponding erase/cursor operations, in stream order,
    # before it processes later text in the same WriteConsole call.
    adapter = 'terminal/adapter/adaptDispatch.cpp'
    adapt_h = 'terminal/adapter/adaptDispatch.hpp'
    shutil.copyfile(ROOT / 'native/single_exe/column_modes.inc', src / 'terminal/adapter/nemo_column_modes.inc')
    anchor = 'void AdaptDispatch::_SetColumnMode(const bool enable)\n{'
    sub(adapter, anchor, '#include "nemo_column_modes.inc"\n\n' + anchor + '\n    if (_api.IsConPTY()) { _NemoApplyWidth(enable, false); return; }')
    sub(adapt_h, '            AllowDECCOLM,',
        '            AllowDECCOLM,\n            NemoColumnPermissionSet,\n            NemoColumnWidthSet,\n            NemoKeepOnColumnChange,')
    anchor = '        void _SetColumnMode(const bool enable);'
    sub(adapt_h, anchor, anchor + '\n        bool _NemoColumnPermission() const;\n        void _NemoApplyWidth(bool wide, bool restore);\n        til::enumset<Mode> _nemoSavedColumns;')
    anchor = '        void UnknownSequence() noexcept override;'
    sub(adapt_h, anchor, anchor + '\n        void NemoSaveRestoreModes(VTParameters parameters, bool save) override;')
    anchor = '    virtual void UnknownSequence() noexcept = 0;'
    sub('terminal/adapter/ITermDispatch.hpp', anchor, anchor + '\n    virtual void NemoSaveRestoreModes(VTParameters, bool) { UnknownSequence(); }')
    anchor = '    case CsiActionCodes::DECSET_PrivateModeSet:'
    sub('terminal/parser/OutputStateMachineEngine.cpp', anchor,
        '    case VTID("?s"):\n    case VTID("?r"):\n        _dispatch->NemoSaveRestoreModes(parameters, id == VTID("?s"));\n        break;\n' + anchor)
    sub('terminal/adapter/DispatchTypes.hpp','        XTERM_EnableDECCOLMSupport = DECPrivateMode(40),',
        '        XTERM_EnableDECCOLMSupport = DECPrivateMode(40),\n        NemoKeepOnColumnChange = DECPrivateMode(95),')
    sub(adapter,'        _modes.set(Mode::AllowDECCOLM, enable);','''        _modes.set(Mode::AllowDECCOLM, enable);
        _modes.set(Mode::NemoColumnPermissionSet);
        break;
    case DispatchTypes::ModeParams::NemoKeepOnColumnChange:
        if (_api.IsConPTY()) _modes.set(Mode::NemoKeepOnColumnChange, enable);''')
    sub(adapter,'    _modes = { Mode::PageCursorCoupling };', '''    const bool columnWasSet = _api.IsConPTY() && _modes.test(Mode::NemoColumnPermissionSet);
    const bool columnsAllowed = _modes.test(Mode::AllowDECCOLM);
    _modes = { Mode::PageCursorCoupling };
    if (columnWasSet)
    {
        _modes.set(Mode::NemoColumnPermissionSet);
        _modes.set(Mode::AllowDECCOLM, columnsAllowed);
    }''')
    sub('terminal/adapter/ITerminalApi.hpp','            AutoWrap,','            NemoColumnDenied,\n            NemoColumnStartEnabled,\n            NemoColumnStartWide,\n            AutoWrap,')
    sub('host/outputStream.cpp','bool ConhostInternalGetSet::GetSystemMode(const Mode mode) const\n{\n    switch (mode)\n    {',
        '''bool ConhostInternalGetSet::GetSystemMode(const Mode mode) const
{
    switch (mode)
    {
    case Mode::NemoColumnDenied:
        return ServiceLocator::LocateGlobals().getConsoleInformation().NemoColumnDenied();
    case Mode::NemoColumnStartEnabled:
        return ServiceLocator::LocateGlobals().getConsoleInformation().NemoColumnStart() != 2;
    case Mode::NemoColumnStartWide:
        return ServiceLocator::LocateGlobals().getConsoleInformation().NemoColumnStart() == 1;''')
    sub('host/server.h','    bool GetBracketedPasteMode() const noexcept;', '''    void InitializeNemoColumnPolicy(HANDLE event, int start) noexcept
    {
        _nemoColumnDenied.reset(event);
        _nemoColumnStart = start;
    }
    bool NemoColumnDenied() const noexcept
    {
        return _nemoColumnDenied && WaitForSingleObject(_nemoColumnDenied.get(), 0) != WAIT_TIMEOUT;
    }
    int NemoColumnStart() const noexcept { return _nemoColumnStart; }
    bool GetBracketedPasteMode() const noexcept;''')
    sub('host/server.h','    bool _bracketedPasteMode = false;', '    wil::unique_handle _nemoColumnDenied;\n    int _nemoColumnStart = 2;\n    bool _bracketedPasteMode = false;')
    sub('host/ConsoleArguments.hpp','    HANDLE GetSignalHandle() const;', '''    HANDLE GetSignalHandle() const;
    HANDLE GetNemoColumnEvent() const { return ULongToHandle(_nemoColumnEvent); }
    int GetNemoColumnStart() const { return _nemoColumnStart; }''')
    sub('host/ConsoleArguments.hpp','    DWORD _signalHandle = 0;', '    DWORD _signalHandle = 0;\n    DWORD _nemoColumnEvent = 0;\n    int _nemoColumnStart = 2;')
    sub('host/ConsoleArguments.cpp', '        else if (arg == SIGNAL_HANDLE_ARG)', '''        else if (arg == L"--nemoColumnOn" || arg == L"--nemoColumnOff" || arg == L"--nemoColumnDefault")
        {
            _nemoColumnStart = arg == L"--nemoColumnOn" ? 1 : arg == L"--nemoColumnOff" ? 2 : 0;
            std::wstring handle;
            hr = s_GetArgumentValue(args, i, &handle);
            if (SUCCEEDED(hr)) hr = s_ParseHandleArg(handle, _nemoColumnEvent);
        }
        else if (arg == SIGNAL_HANDLE_ARG)''')
    sub('host/VtIo.cpp', '        if (pArgs->GetAmbiguousIsWide())', '''        if (const auto event = pArgs->GetNemoColumnEvent())
        {
            ServiceLocator::LocateGlobals().getConsoleInformation().InitializeNemoColumnPolicy(event, pArgs->GetNemoColumnStart());
        }
        if (pArgs->GetAmbiguousIsWide())''')

    # Explicitly pass the optional owner handle through creation. Only the
    # same-image API adds it to the existing restricted inheritance list;
    # the host duplicate can observe but cannot change the parent's policy.
    cpp = 'winconpty/winconpty.cpp'
    sub('winconpty/winconpty.h','_Inout_ PseudoConsole* pPty);','_Inout_ PseudoConsole* pPty, HANDLE columnEvent = nullptr, int columnStart = 2);')
    sub(cpp,'_Inout_ PseudoConsole* pPty)\n{','_Inout_ PseudoConsole* pPty, HANDLE columnEvent, int columnStart)\n{')
    sub(cpp,'    const auto inheritCursor =', '''    wil::unique_handle columnRead;
    wil::unique_process_heap_string columnArg;
    if (columnEvent)
    {
        RETURN_IF_WIN32_BOOL_FALSE(DuplicateHandle(GetCurrentProcess(), columnEvent, GetCurrentProcess(),
                                                    columnRead.addressof(), SYNCHRONIZE, TRUE, 0));
        RETURN_IF_FAILED(wil::str_printf_nothrow(columnArg, L"--nemoColumn%s 0x%tx ",
            columnStart == 1 ? L"On" : columnStart == 2 ? L"Off" : L"Default", std::bit_cast<uintptr_t>(columnRead.get())));
    }
    const auto inheritCursor =''')
    sub(cpp,'--headless %s%s%s--width','--headless %s%s%s%s--width')
    sub(cpp,'        inheritCursor,\n        ambiguousIsWide,','        columnArg ? columnArg.get() : L"",\n        inheritCursor,\n        ambiguousIsWide,')
    sub(cpp,'    const size_t INHERITED_HANDLES_COUNT = 4;\n    HANDLE inheritedHandles[INHERITED_HANDLES_COUNT];',
        '    const size_t inheritedCount = columnRead ? 5 : 4;\n    HANDLE inheritedHandles[5];\n    inheritedHandles[4] = columnRead.get();')
    sub(cpp,'(INHERITED_HANDLES_COUNT * sizeof(HANDLE))','(inheritedCount * sizeof(HANDLE))')
    old='extern "C" HRESULT WINAPI ConptyCreatePseudoConsoleAsUser(_In_ HANDLE hToken,'
    sub(cpp,old,'static HRESULT _CreateForUser(HANDLE columnEvent, int columnStart, _In_ HANDLE hToken,')
    sub(cpp,'duplicatedOutput.get(), dwFlags, pPty));','duplicatedOutput.get(), dwFlags, pPty, columnEvent, columnStart));')
    marker='// Function Description:\n// Resizes the given conpty to the specified size, in characters.'
    sub(cpp,marker,'''extern "C" HRESULT WINAPI ConptyCreatePseudoConsoleAsUser(_In_ HANDLE token, _In_ COORD size, _In_ HANDLE in, _In_ HANDLE out, _In_ DWORD flags, _Out_ HPCON* pc)
{
    return _CreateForUser(nullptr, 2, token, size, in, out, flags, pc);
}

extern "C" HRESULT WINAPI NemoCreatePseudoConsole(COORD size, HANDLE in, HANDLE out, HANDLE columnEvent, int columnStart, HPCON* pc)
{
    return _CreateForUser(columnEvent, columnStart, INVALID_HANDLE_VALUE, size, in, out, 0, pc);
}

'''+marker)


def patch_cursor_sync():
    # ConPTY's internal CPR must not consume an application's outstanding CPR.
    # This same-image host uses a tagged Nemoterm query with viewport-absolute
    # coordinates; ordinary and DEC cursor reports remain application input.
    replace(DEST / "src/host/VtIo.cpp",
            '    _io->_back.append("\\x1b[6n");\n    _io->_pVtInputThread->CaptureNextCursorPositionReport();',
            '''    const auto request = _io->_pVtInputThread->CaptureNextCursorPositionReport();
    fmt::format_to(std::back_inserter(_io->_back), FMT_COMPILE("\\x1b[?9001;{}n"), request);''')
    replace(DEST / "src/host/VtInputThread.hpp",
            "void CaptureNextCursorPositionReport() const noexcept;",
            "unsigned CaptureNextCursorPositionReport() const noexcept;")
    replace(DEST / "src/host/VtInputThread.cpp",
            "void VtInputThread::CaptureNextCursorPositionReport() const noexcept",
            "unsigned VtInputThread::CaptureNextCursorPositionReport() const noexcept")
    replace(DEST / "src/host/VtInputThread.cpp",
            "    engine.CaptureNextCursorPositionReport();",
            "    return engine.CaptureNextCursorPositionReport();")
    replace(DEST / "src/terminal/parser/InputStateMachineEngine.hpp",
            "void CaptureNextCursorPositionReport() noexcept;",
            "unsigned CaptureNextCursorPositionReport() noexcept;")
    replace(DEST / "src/terminal/parser/InputStateMachineEngine.hpp",
            "        std::atomic<bool> _captureNextCursorPositionReport{ false };",
            "        std::atomic<unsigned> _nemoCursorSequence{ 0 };\n"
            "        std::atomic<unsigned> _nemoCursorRequest{ 0 };")
    path = DEST / "src/terminal/parser/InputStateMachineEngine.cpp"
    replace(path,
            "void InputStateMachineEngine::CaptureNextCursorPositionReport() noexcept\n{\n"
            "    _captureNextCursorPositionReport.store(true, std::memory_order_relaxed);\n}",
            '''unsigned InputStateMachineEngine::CaptureNextCursorPositionReport() noexcept
{
    const auto request = _nemoCursorSequence.fetch_add(1, std::memory_order_relaxed) % 65535 + 1;
    _nemoCursorRequest.store(request, std::memory_order_relaxed);
    return request;
}''')
    replace(path,
            "    _captureNextCursorPositionReport.store(false, std::memory_order_relaxed);",
            "    _nemoCursorRequest.store(0, std::memory_order_relaxed);")
    replace(path, "    // case CsiActionCodes::DSR_DeviceStatusReportResponse:",
            '''    case VTID("?R"):
        if (parameters.size() == 4 && parameters.at(0).value_or(0) == 9001)
        {
            auto request = static_cast<unsigned>(parameters.at(1).value_or(0));
            if (request && parameters.at(2).value_or(0) && parameters.at(3).value_or(0) &&
                _nemoCursorRequest.compare_exchange_strong(request, 0, std::memory_order_relaxed))
            {
                _pDispatch->MoveCursor(parameters.at(2), parameters.at(3));
            }
            // Late internal replies also stay out of the application's input.
            return true;
        }
        return false;
    // case CsiActionCodes::DSR_DeviceStatusReportResponse:''')
    replace(path,
            '''        // The F3 case is special - it shares a code with the DeviceStatusResponse.
        // If we're looking for that response, then do that, and break out.
        // Else, fall though to the _GetCursorKeysModifierState handler.
        if (_captureNextCursorPositionReport.exchange(false, std::memory_order_relaxed))
        {
            _pDispatch->MoveCursor(parameters.at(0), parameters.at(1));
            return true;
        }''',
            "        // Internal cursor synchronization uses tagged ?R replies above.")


def patch_vt_backspace_input():
    # A VT-aware child reads the bytes already chosen by the frontend. Turning
    # them back into VK_BACK would apply DECBKM a second time. A native console
    # reader still needs the original key-record and cooked editing behaviour.
    anchor = 'bool InputStateMachineEngine::ActionExecute(const wchar_t wch)\n{\n'
    replace(DEST / 'src/terminal/parser/InputStateMachineEngine.cpp', anchor, anchor + r'''    if ((wch == L'\b' || wch == L'\x7f') && _pDispatch->IsVtInputEnabled())
    {
        _pDispatch->WriteStringRaw(std::wstring_view{ &wch, 1 });
        return true;
    }
''')


def patch_input_dcs_fragments():
    # Input DCS replies are deliberately buffered until ST by the input engine.
    # Discarding a prefix cached by an earlier ProcessString call loses bytes
    # when the pipe splits a header before its final character. Output-engine
    # DCS handling remains streaming and must still discard that cache.
    replace(DEST / "src/terminal/parser/stateMachine.cpp",
            "void StateMachine::_EnterDcsIgnore() noexcept\n{\n"
            "    _state = VTStates::DcsIgnore;\n    _cachedSequence.reset();",
            "void StateMachine::_EnterDcsIgnore() noexcept\n{\n"
            "    _state = VTStates::DcsIgnore;\n"
            "    if (!_isEngineForInput)\n    {\n        _cachedSequence.reset();\n    }")


def patch_cursor_sync_fragments():
    # A tagged cursor reply can cross pipe reads before the first actual key.
    # While that transaction is pending, a trailing ESC/ESC[ is a stream
    # prefix, not the parser's legacy heuristic for an isolated Alt key.
    replace(DEST / "src/terminal/parser/InputStateMachineEngine.cpp",
            "    return _encounteredWin32InputModeSequence;",
            "    return _encounteredWin32InputModeSequence ||\n"
            "        _nemoCursorRequest.load(std::memory_order_relaxed) != 0;")


def patch_initial_window_visibility():
    # CreateWindow sends WM_SIZE(SIZE_RESTORED) before it returns, even for
    # the hidden pseudo-window. That is initialization, not a client request
    # to restore the hosting terminal. Keep later explicit visibility changes.
    replace(DEST / "src/interactivity/base/InteractivityFactory.cpp",
            "    if (_suppressVisibilityChange.load(std::memory_order_relaxed))",
            "    if (!_pseudoConsoleWindowHwnd ||\n"
            "        _suppressVisibilityChange.load(std::memory_order_relaxed))")


def patch_quoted_paste_input():
    # The frontend still emits XTerm's byte stream. Opt only this console
    # into the decoder after an application actually requests DECSET 2005.
    # A queued paste snapshots its mode and may arrive after DECRST or RIS:
    # keep recognizing the otherwise invalid encoding for this connection.
    src = DEST / 'src'
    shutil.copyfile(ROOT / 'native/single_exe/quoted_utf8.hpp', src / 'host/nemo_quoted_utf8.hpp')
    replace(src / 'terminal/adapter/DispatchTypes.hpp', '        XTERM_BracketedPasteMode = DECPrivateMode(2004),',
            '        XTERM_QuotePaste = DECPrivateMode(2005),\n        XTERM_BracketedPasteMode = DECPrivateMode(2004),')
    replace(src / 'terminal/adapter/ITerminalApi.hpp', '            BracketedPaste\n',
            '            BracketedPaste,\n            NemoQuotedPasteSeen\n')
    replace(src / 'terminal/adapter/adaptDispatch.cpp',
            '    case DispatchTypes::ModeParams::XTERM_BracketedPasteMode:\n        _api.SetSystemMode',
            '    case DispatchTypes::ModeParams::XTERM_QuotePaste:\n'
            '        if (enable) _api.SetSystemMode(ITerminalApi::Mode::NemoQuotedPasteSeen, true);\n'
            '        break;\n    case DispatchTypes::ModeParams::XTERM_BracketedPasteMode:\n        _api.SetSystemMode')
    replace(src / 'host/server.h', '    bool GetBracketedPasteMode() const noexcept;',
            '    bool HasSeenQuotedPaste() const noexcept { return _nemoQuoteSeen.load(std::memory_order_relaxed); }\n'
            '    void EnableQuotedPasteDecoder() noexcept { _nemoQuoteSeen.store(true, std::memory_order_relaxed); }\n'
            '    bool GetBracketedPasteMode() const noexcept;')
    replace(src / 'host/server.h', '    bool _bracketedPasteMode = false;',
            '    std::atomic<bool> _nemoQuoteSeen{false};\n    bool _bracketedPasteMode = false;')
    replace(src / 'host/outputStream.cpp', '    case Mode::BracketedPaste:\n        ServiceLocator',
            '    case Mode::NemoQuotedPasteSeen:\n'
            '        if (enabled) ServiceLocator::LocateGlobals().getConsoleInformation().EnableQuotedPasteDecoder();\n'
            '        break;\n    case Mode::BracketedPaste:\n        ServiceLocator')
    file = src / 'host/VtInputThread.cpp'
    replace(file, '#include "VtInputThread.hpp"', '#include "VtInputThread.hpp"\n#include "nemo_quoted_utf8.hpp"')
    replace(file, '    char buffer[4096];', '    nemo::QuotedUtf8Input quoted;\n    char* const buffer = quoted.input();')
    text = file.read_text(encoding='utf-8'); assert text.count('sizeof(buffer)') == 2
    file.write_text(text.replace('sizeof(buffer)', 'static_cast<DWORD>(nemo::QuotedUtf8Input::capacity)'), encoding='utf-8')
    replace(file, '        FAILED_LOG(til::u8u16({ &buffer[0], gsl::narrow_cast<size_t>(read) }, wstr, u8State));\n    }',
            '        const auto bytes = quoted.consume(read, ServiceLocator::LocateGlobals().getConsoleInformation().HasSeenQuotedPaste());\n'
            '        FAILED_LOG(til::u8u16(bytes, wstr, u8State));\n    }\n'
            '    if (const auto remaining = quoted.finish(); !remaining.empty())\n    {\n'
            '        try {\n'
            '            THROW_IF_FAILED(til::u8u16(remaining, wstr, u8State));\n'
            '            LockConsole();\n            const auto unlock = wil::scope_exit([&] { UnlockConsole(); });\n'
            '            _pInputStateMachine->ProcessString(wstr);\n        } CATCH_LOG();\n    }')


def patch_closed_console_connections():
    # A child created before close can finish its initial console connection
    # after ProcessCtrlEvents took the close-event client snapshot. Such a
    # client must not revive the closed PTY or hold its output pipe open.
    # Both the close transition and this admission check hold LockConsole.
    replace(DEST / "src/host/VtIo.hpp",
            "        void SendCloseEvent();",
            "        void SendCloseEvent();\n"
            "        // Caller must hold the console lock.\n"
            "        bool IsClosing() const noexcept { return _closeEventSent; }")
    replace(DEST / "src/server/IoDispatchers.cpp",
            "    CONSOLE_API_CONNECTINFO Cac;\n"
            "    Status = ConsoleInitializeConnectInfo(pReceiveMsg, &Cac);",
            """    // Closing is final even if a child retained an inherited console
    // reference before the terminal went away. Reject its late attachment
    // before allocating client state; normal launcher delegation is unchanged.
    if (gci.GetVtIo()->IsClosing())
    {
        Status = STATUS_PIPE_DISCONNECTED;
        return pReceiveMsg;
    }

    CONSOLE_API_CONNECTINFO Cac;
    Status = ConsoleInitializeConnectInfo(pReceiveMsg, &Cac);""")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--architecture", choices=("x64", "x86", "arm64"), default="x64",
                        help="Windows architecture the overlay is built for (default x64)")
    args = parser.parse_args()
    actual = subprocess.check_output(["git", "-C", str(UPSTREAM), "rev-parse", "HEAD"], text=True).strip()
    if actual != REVISION:
        raise SystemExit(f"Expected Microsoft Terminal {REVISION}, got {actual}")
    archive = subprocess.check_output(["git", "-C", str(UPSTREAM), "archive", "--format=zip", REVISION])
    DEST.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        for info in z.infolist():
            target = (DEST / info.filename).resolve()
            if not target.is_relative_to(DEST.resolve()):
                raise ValueError(f"Unsafe archive path: {info.filename}")
        z.extractall(DEST)

    # A single PE image supplies both the GUI and the console-server entrypoint.
    path = DEST / "src/winconpty/winconpty.cpp"
    value = path.read_text(encoding="utf-8-sig")
    start = value.index("static wil::unique_process_heap_string _InboxConsoleHostPath()")
    end = value.index("\nstatic ", value.index("static wchar_t* _ConsoleHostPath()") + 1)
    value = value[:start] + '''static wchar_t* _ConsoleHostPath()
{
    static auto path = wil::GetModuleFileNameW<wil::unique_process_heap_string>(nullptr);
    return path.get();
}
''' + value[end:]
    path.write_text(value, encoding="utf-8")
    replace(DEST / "src/host/exe/exemain.cpp", "int CALLBACK wWinMain(", "int CALLBACK NemoConsoleMain(")
    shutil.copyfile(ROOT / "native/single_exe/entry.cpp", DEST / "src/host/exe/nemo-entry.cpp")

    # ReadFile/ReadConsoleA raw input supplies Consume one UTF-16 unit at a
    # time. Preserve a high surrogate until its partner arrives, including
    # across pending reads and small destination buffers. Keep this overlay
    # separate from the pinned, unmodified upstream checkout.
    replace(DEST / "src/host/inputBuffer.hpp",
            "    std::string _cachedTextA;",
            "    wchar_t _nemoReadHighSurrogate = 0;\n    std::string _cachedTextA;")
    replace(DEST / "src/host/inputBuffer.cpp",
            "        const auto cp = ServiceLocator::LocateGlobals().getConsoleInformation().CP;",
            """        const auto cp = ServiceLocator::LocateGlobals().getConsoleInformation().CP;

        if (_nemoReadHighSurrogate)
        {
            const auto high = std::exchange(_nemoReadHighSurrogate, wchar_t{});
            wchar_t prefix[3]{ UNICODE_REPLACEMENT, 0, 0 };
            size_t length = 1;
            if (til::is_trailing_surrogate(source.front()))
            {
                prefix[0] = high;
                prefix[1] = source.front();
                source.remove_prefix(1);
                length = 2;
            }
            else if (cp == CP_UTF8 && til::is_leading_surrogate(source.front()) && source.size() == 1)
            {
                _nemoReadHighSurrogate = source.front();
                source.remove_prefix(1);
            }
            else
            {
                prefix[1] = source.front();
                source.remove_prefix(1);
                length = 2;
                if (til::is_leading_surrogate(prefix[1]) && !source.empty() && til::is_trailing_surrogate(source.front()))
                {
                    prefix[2] = source.front();
                    source.remove_prefix(1);
                    length = 3;
                }
            }
            // Consume at least the incoming unit even if the orphan's
            // replacement fills a one-byte destination. Raw reads pass one
            // unit and cannot retain an unconsumed lookahead character.
            char bytes[12];
            const auto written = WideCharToMultiByte(cp, 0, prefix, static_cast<int>(length), bytes, sizeof(bytes), nullptr, nullptr);
            THROW_LAST_ERROR_IF(written <= 0);
            std::string_view pending{ bytes, static_cast<size_t>(written) };
            til::bytes_transfer(target, pending);
            if (!pending.empty())
            {
                _cachedTextA = pending;
                _cachedTextReaderA = _cachedTextA;
            }
            if (source.empty() || target.empty())
            {
                return;
            }
        }
        if (cp == CP_UTF8 && source.size() == 1 && til::is_leading_surrogate(source.front()))
        {
            _nemoReadHighSurrogate = source.front();
            source = {};
            return;
        }""")
    # GetChar uses Read(Stream=true) internally. Do not switch to event mode
    # there: that discards the string decoder's state between UTF-16 units.
    replace(DEST / "src/host/inputBuffer.cpp", "    if (Peek)\n    {\n        PeekCached(Unicode, AmountToRead, OutEvents);\n    }\n    else\n    {\n        ConsumeCached(Unicode, AmountToRead, OutEvents);\n    }",
            "    if (!Stream)\n    {\n        if (Peek) PeekCached(Unicode, AmountToRead, OutEvents);\n        else ConsumeCached(Unicode, AmountToRead, OutEvents);\n    }")
    replace(DEST / "src/host/inputBuffer.cpp", "    Cache(Unicode, OutEvents, AmountToRead);",
            "    if (!Stream) Cache(Unicode, OutEvents, AmountToRead);")
    replace(DEST / "src/host/inputBuffer.cpp", "                ++read;",
            "                read += s.size(); // UTF-16 units, not scalar count.")
    replace(DEST / "src/host/inputBuffer.cpp",
            "void InputBuffer::_switchReadingModeSlowPath(ReadingMode mode)\n{",
            "void InputBuffer::_switchReadingModeSlowPath(ReadingMode mode)\n{\n    _nemoReadHighSurrogate = 0;")
    replace(DEST / "src/host/inputBuffer.cpp", "void InputBuffer::ReinitializeInputBuffer()\n{",
            "void InputBuffer::ReinitializeInputBuffer()\n{\n    _nemoReadHighSurrogate = 0;")
    replace(DEST / "src/host/inputBuffer.cpp", "void InputBuffer::Flush()\n{",
            "void InputBuffer::Flush()\n{\n    _nemoReadHighSurrogate = 0;")
    replace(DEST / "src/host/stream.cpp", "        noDataReadYet = false;",
            "        noDataReadYet = writer.size() == buffer.size(); // A high surrogate alone emitted no bytes.")

    # Text commits have no physical key to release. In particular, inserting
    # key-up records between UTF-16 surrogate units breaks Windows consumers
    # that decode the event stream (observed with Codex/crossterm). Match
    # Terminal::SendCharEvent's key-down-only text delivery for these units.
    # Cover both the scalar parser action and its plain-string fast path.
    replace(DEST / "src/terminal/parser/InputStateMachineEngine.cpp",
            "    input.push_back(rec);\n    rec.Event.KeyEvent.bKeyDown = FALSE;\n    input.push_back(rec);",
            """    input.push_back(rec);
    if (wch < 0xd800 || wch > 0xdfff)
    {
        rec.Event.KeyEvent.bKeyDown = FALSE;
        input.push_back(rec);
    }""")
    replace(DEST / "src/terminal/adapter/InteractDispatch.cpp",
            "                CharToKeyEvents(wch, codepage, keyEvents);",
            """                if (wch >= 0xd800 && wch <= 0xdfff)
                {
                    keyEvents.push_back(SynthesizeKeyEvent(true, 1, 0, 0, wch, 0));
                }
                else
                {
                    CharToKeyEvents(wch, codepage, keyEvents);
                }""")

    patch_visual_writer()
    patch_column_resize_owner()
    patch_column_edits()
    patch_linux_palette()
    patch_dec_colour_table()
    patch_cursor_sync()
    patch_vt_backspace_input()
    patch_input_dcs_fragments()
    patch_cursor_sync_fragments()
    patch_initial_window_visibility()
    patch_quoted_paste_input()
    patch_closed_console_connections()

    # No COM handoff registration or legacy conhost loading
    # is needed for a host reached only through our inherited ConDrv handle.
    features = DEST / "src/features.xml"
    value = features.read_text(encoding="utf-8")
    for feature in ("ReceiveIncomingHandoff",):
        value, count = re.subn(
            rf"(<name>Feature_{feature}</name>.*?<stage>)AlwaysEnabled(</stage>)",
            r"\g<1>AlwaysDisabled\2", value, flags=re.S)
        assert count == 1
    features.write_text(value, encoding="utf-8")

    # Conhost only needs fmt/GSL. Do not build Windows Terminal's XAML/WebView UI.
    replace(DEST / "src/common.build.pre.props",
            "<VcpkgAdditionalInstallOptions>--x-feature=terminal</VcpkgAdditionalInstallOptions>",
            "<VcpkgAdditionalInstallOptions></VcpkgAdditionalInstallOptions>")

    # Match the native frontend's manifest (including its DPI policy).
    shutil.copyfile(ROOT / "vendor/putty-0.85/windows/putty.mft",
                    DEST / "src/host/exe/openconsole.exe.manifest")
    project = DEST / "src/host/exe/Host.EXE.vcxproj"
    replace(project, "<TargetName>OpenConsole</TargetName>", "<TargetName>nemoterm</TargetName>")
    replace(project, '<ClCompile Include="exemain.cpp" />',
            '<ClCompile Include="exemain.cpp" />\n'
            '    <ClCompile Include="nemo-entry.cpp"><PrecompiledHeader>NotUsing</PrecompiledHeader></ClCompile>')

    # Use distinct frontend libraries, with one shared MSVC /MT runtime policy.
    libs = (ROOT / "build/frontend-single").resolve()
    names = ("nemoterm", "guiterminal", "guimisc", "eventloop", "settings", "network", "utils")
    deps = ";".join(escape(str(libs / (n + ".lib"))) for n in names)
    src = escape(str(ROOT / "vendor/putty-0.85/windows"))
    generated = escape(str(libs / "CMakeFiles"))
    # This artifact is reproducible on the pinned Linux toolchain. Reject a
    # mismatched source or guest image even on a Windows-only build.
    bundle = ROOT / 'native/wsl_pty/bundled'
    manifest = json.loads((bundle / 'manifest.json').read_text())
    elf = (bundle / 'relay-x86_64.elf').read_bytes()
    source = (bundle.parent / 'relay.c').read_text(encoding='utf-8').encode()
    notice = (bundle / 'musl-copyright.txt').read_text(encoding='utf-8').encode()
    for data, key in [(elf, 'relay_sha256'), (source, 'source_sha256'), (notice, 'musl_notice_sha256')]:
        if hashlib.sha256(data).hexdigest() != manifest[key]:
            raise ValueError('Bundled WSL relay identity mismatch: '+key)
    # The relay runs inside WSL, so it must match the distribution's machine,
    # which is the Windows host's: x86-64 under x64 and x86 builds. Windows on
    # Arm runs aarch64 distributions, and there is no aarch64 relay yet; without
    # resource 40003 the Linux PTY option is not offered (config.c) and WSL
    # uses ConPTY, as it does when that option is off.
    embed_relay = args.architecture in ("x64", "x86")
    if embed_relay:
        (DEST / 'src/host/exe/nemo-wsl-relay.elf').write_bytes(elf)
    notices = "\n\n".join(p.read_text(encoding="utf-8-sig") for p in (
        ROOT / "LICENSE", ROOT / "vendor/putty-0.85/LICENCE",
        UPSTREAM / "LICENSE", UPSTREAM / "NOTICE.md",
        ROOT / "vendor/nerd-fonts/LICENSE", ROOT / "vendor/nerd-fonts/NOTICE.txt",
        ROOT / "tools/unicode/18.0.0/LICENSE.txt",
        ROOT / "tools/x11/xorg-server-21.1.16/LICENSE.txt",
        ROOT / "vendor/terminfo/COPYING.ncurses", bundle / "musl-copyright.txt",
        ROOT / "vendor/putty-0.85/terminal/puff/puff.h"))
    (DEST / "src/host/exe/nemo-licenses.txt").write_text(notices, encoding="utf-8")
    (DEST / "src/host/exe/nemo-licenses.rc").write_text(
        '40000 RCDATA "nemo-licenses.txt"\n'
        + ('40003 RCDATA "nemo-wsl-relay.elf"\n' if embed_relay else ''), encoding="ascii")
    # One RC invocation allocates the individual ICON image IDs consistently;
    # separate .res files both start those implicit IDs at 1 and collide.
    host_rc = DEST / "src/host/exe/Host.EXE.rc"
    with host_rc.open("a", encoding="utf-8") as f:
        f.write('\n#include "' + (ROOT / "vendor/putty-0.85/windows/pterm.rc").as_posix() + '"\n')
        f.write('#include "nemo-licenses.rc"\n')
    replace(project, '<ResourceCompile Include="Host.EXE.rc" />', f'''<ResourceCompile Include="Host.EXE.rc">
      <AdditionalIncludeDirectories>{src};{src}\\..;{generated};%(AdditionalIncludeDirectories)</AdditionalIncludeDirectories>
      <PreprocessorDefinitions>HAVE_CMAKE_H;NO_MANIFESTS;%(PreprocessorDefinitions)</PreprocessorDefinitions>
    </ResourceCompile>''')
    additions = f'''
  <ItemGroup>
    <ProjectReference Include="..\\..\\winconpty\\lib\\winconptylib.vcxproj">
      <Project>{{58a03bb2-df5a-4b66-91a0-7ef3ba01269a}}</Project>
    </ProjectReference>
  </ItemGroup>
  <ItemDefinitionGroup>
    <Link>
      <AdditionalDependencies>{deps};comdlg32.lib;ws2_32.lib;windowscodecs.lib;uuid.lib;%(AdditionalDependencies)</AdditionalDependencies>
      <EntryPointSymbol>wWinMainCRTStartup</EntryPointSymbol>
    </Link>
  </ItemDefinitionGroup>
'''
    replace(project, "\n</Project>", additions + "\n</Project>")
    (DEST / "NEMOTERM-UPSTREAM.txt").write_text(REVISION + "\n", encoding="ascii")
    print(f"Prepared {DEST} from Microsoft Terminal {REVISION}")


if __name__ == "__main__":
    main()
