param([string]$Destination = 'build/exception-observer')
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$outputPath = [IO.Path]::GetFullPath($Destination, $repo)
New-Item -ItemType Directory -Force $outputPath | Out-Null
$vswhere = "${env:ProgramFiles(x86)}/Microsoft Visual Studio/Installer/vswhere.exe"
$vs = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if ($LASTEXITCODE -or -not $vs) { throw 'MSVC fixture compiler unavailable' }
Import-Module "$vs/Common7/Tools/Microsoft.VisualStudio.DevShell.dll"
Enter-VsDevShell -VsInstallPath $vs -SkipAutomaticLocation -DevCmdArguments '-arch=x64 -host_arch=x64'
foreach ($kind in 'observer','control') {
    $image = Join-Path $outputPath "$kind.exe"
    $object = Join-Path $outputPath "$kind.obj"
    & cl /nologo /std:c11 /utf-8 /W4 /WX /O2 /MT /D_CRT_SECURE_NO_WARNINGS "/Fe:$image" "/Fo:$object" "$repo/tests/native_exception_$kind.c" dbghelp.lib 2>&1 | Tee-Object (Join-Path $outputPath "build-$kind.log")
    if ($LASTEXITCODE) { throw "Exception $kind compilation failed" }
}
& python "$repo/tests/native_exception_controls.py" --observer "$outputPath/observer.exe" --control "$outputPath/control.exe" --destination "$outputPath/controls" 2>&1 | Tee-Object (Join-Path $outputPath 'test.log')
if ($LASTEXITCODE) { throw 'Exception observer sensitivity or lifecycle controls failed' }
