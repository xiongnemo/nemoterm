param([string]$Destination = 'build/code-boundary-controls')
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$outputPath = [IO.Path]::GetFullPath($Destination, $repo)
New-Item -ItemType Directory -Force $outputPath | Out-Null
$vswhere = "${env:ProgramFiles(x86)}/Microsoft Visual Studio/Installer/vswhere.exe"
$vs = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if ($LASTEXITCODE -or -not $vs) { throw 'MSVC fixture compiler unavailable' }
Import-Module "$vs/Common7/Tools/Microsoft.VisualStudio.DevShell.dll"
Enter-VsDevShell -VsInstallPath $vs -SkipAutomaticLocation -DevCmdArguments '-arch=x64 -host_arch=x64'
& cl /nologo /std:c11 /utf-8 /W4 /WX /O2 /MT /D_CRT_SECURE_NO_WARNINGS "/Fe:$outputPath/control.exe" "/Fo:$outputPath/control.obj" "$repo/tests/native_exception_control.c" 2>&1 | Tee-Object "$outputPath/build.log"
if ($LASTEXITCODE) { throw 'Code-boundary control compilation failed' }
& python "$repo/tests/owned_code_boundary_controls.py" --control "$outputPath/control.exe" --destination "$outputPath/results" 2>&1 | Tee-Object "$outputPath/test.log"
if ($LASTEXITCODE) { throw 'Owned code-boundary controls failed' }
