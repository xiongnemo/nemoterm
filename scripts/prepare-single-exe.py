"""Prepare a pinned OpenConsole source overlay. Never modifies the submodule.

Build outputs stay under build/. Changes below deliberately fail if their
upstream anchors change; upgrading the submodule requires reviewing them.
"""
import io
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


def main():
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

    patch_cursor_sync()
    patch_input_dcs_fragments()
    patch_cursor_sync_fragments()

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
    notices = "\n\n".join(p.read_text(encoding="utf-8-sig") for p in (
        ROOT / "LICENSE", ROOT / "vendor/putty-0.85/LICENCE",
        UPSTREAM / "LICENSE", UPSTREAM / "NOTICE.md",
        ROOT / "vendor/nerd-fonts/LICENSE", ROOT / "vendor/nerd-fonts/NOTICE.txt",
        ROOT / "tools/unicode/18.0.0/LICENSE.txt"))
    (DEST / "src/host/exe/nemo-licenses.txt").write_text(notices, encoding="utf-8")
    (DEST / "src/host/exe/nemo-licenses.rc").write_text(
        '40000 RCDATA "nemo-licenses.txt"\n', encoding="ascii")
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
      <AdditionalDependencies>{deps};comdlg32.lib;ws2_32.lib;%(AdditionalDependencies)</AdditionalDependencies>
      <EntryPointSymbol>wWinMainCRTStartup</EntryPointSymbol>
    </Link>
  </ItemDefinitionGroup>
'''
    replace(project, "\n</Project>", additions + "\n</Project>")
    (DEST / "NEMOTERM-UPSTREAM.txt").write_text(REVISION + "\n", encoding="ascii")
    print(f"Prepared {DEST} from Microsoft Terminal {REVISION}")


if __name__ == "__main__":
    main()
