param(
    [string]$Destination = 'build/shutdown-observer',
    [string]$Python = $(if ($env:NEMOTERM_SHUTDOWN_PYTHON) { $env:NEMOTERM_SHUTDOWN_PYTHON } else { 'python' })
)
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$outputPath = [IO.Path]::GetFullPath($Destination, $repo)
New-Item -ItemType Directory -Force $outputPath | Out-Null
$vswhere = "${env:ProgramFiles(x86)}/Microsoft Visual Studio/Installer/vswhere.exe"
$vs = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if ($LASTEXITCODE -or -not $vs) { throw 'MSVC fixture compiler unavailable' }
Import-Module "$vs/Common7/Tools/Microsoft.VisualStudio.DevShell.dll"
Enter-VsDevShell -VsInstallPath $vs -SkipAutomaticLocation -DevCmdArguments '-arch=x64 -host_arch=x64'
$image = Join-Path $outputPath 'shutdown-probe-fixture.exe'
$object = Join-Path $outputPath 'shutdown-probe-fixture.obj'
& cl /nologo /std:c11 /utf-8 /W4 /WX /O2 /D_CRT_SECURE_NO_WARNINGS "/Fe:$image" "/Fo:$object" "$repo/tests/shutdown_probe_fixture.c" ole32.lib user32.lib 2>&1 | Tee-Object (Join-Path $outputPath 'build.log')
if ($LASTEXITCODE) { throw 'Shutdown observer control compilation failed' }
& $Python "$repo/tests/shutdown_probe_controls.py" --executable $image 2>&1 | Tee-Object (Join-Path $outputPath 'test.log')
$testExit = $LASTEXITCODE
Copy-Item "$repo/research/shutdown-probe-controls-observed.json" $outputPath -ErrorAction SilentlyContinue
if ($testExit) { throw 'Shutdown observer sensitivity controls failed' }
