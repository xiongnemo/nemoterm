param([string]$Destination = 'build/failure-dump')
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$outputPath = [IO.Path]::GetFullPath($Destination, $repo)
New-Item -ItemType Directory -Force $outputPath | Out-Null
$vswhere = "${env:ProgramFiles(x86)}/Microsoft Visual Studio/Installer/vswhere.exe"
$vs = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if ($LASTEXITCODE -or -not $vs) { throw 'MSVC fixture compiler unavailable' }
Import-Module "$vs/Common7/Tools/Microsoft.VisualStudio.DevShell.dll"
Enter-VsDevShell -VsInstallPath $vs -SkipAutomaticLocation -DevCmdArguments '-arch=x64 -host_arch=x64'
foreach ($item in @(@('helper','native_failure_dump'),@('control','native_exception_control'))) {
    $kind = $item[0]
    & cl /nologo /std:c11 /utf-8 /W4 /WX /O2 /MT /D_CRT_SECURE_NO_WARNINGS "/Fe:$outputPath/$kind.exe" "/Fo:$outputPath/$kind.obj" "$repo/tests/$($item[1]).c" dbghelp.lib 2>&1 | Tee-Object "$outputPath/build-$kind.log"
    if ($LASTEXITCODE) { throw "Failure dump $kind compilation failed" }
}
& python "$repo/tests/native_failure_dump_controls.py" --helper "$outputPath/helper.exe" --control "$outputPath/control.exe" --destination "$outputPath/controls" 2>&1 | Tee-Object "$outputPath/test.log"
if ($LASTEXITCODE) { throw 'Failure dump context, survival or ownership controls failed' }
