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
        UPSTREAM / "LICENSE", UPSTREAM / "NOTICE.md"))
    (DEST / "src/host/exe/nemo-licenses.txt").write_text(notices, encoding="utf-8")
    (DEST / "src/host/exe/nemo-licenses.rc").write_text(
        '40000 RCDATA "nemo-licenses.txt"\n', encoding="ascii")
    additions = f'''
  <ItemGroup>
    <ResourceCompile Include="nemo-licenses.rc" />
    <ProjectReference Include="..\\..\\winconpty\\lib\\winconptylib.vcxproj">
      <Project>{{58a03bb2-df5a-4b66-91a0-7ef3ba01269a}}</Project>
    </ProjectReference>
    <ResourceCompile Include="{src}\\pterm.rc">
      <AdditionalIncludeDirectories>{src};{src}\\..;{generated};%(AdditionalIncludeDirectories)</AdditionalIncludeDirectories>
      <PreprocessorDefinitions>HAVE_CMAKE_H;NO_MANIFESTS;%(PreprocessorDefinitions)</PreprocessorDefinitions>
    </ResourceCompile>
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
