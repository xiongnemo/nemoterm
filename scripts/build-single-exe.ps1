param([string]$Destination = '')
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
if (!$Destination) { $Destination = Join-Path $root 'build/single-exe-dist' }
$Destination = [IO.Path]::GetFullPath($Destination)

# Run in a VS developer shell. CI supplies the pinned Windows runner toolchain.
Get-Command cl.exe, msbuild.exe, cmake.exe, ninja.exe, nuget.exe -ErrorAction Stop | Out-Null
& python "$PSScriptRoot/prepare-single-exe.py"
if ($LASTEXITCODE) { throw 'OpenConsole source preparation failed' }
$source = Join-Path $root 'build/openconsole-single'
$frontend = Join-Path $root 'build/frontend-single'
& cmake -S "$root/vendor/putty-0.85" -B $frontend -G Ninja -DCMAKE_C_COMPILER=cl -DCMAKE_CXX_COMPILER=cl -DCMAKE_BUILD_TYPE=MinSizeRel '-DCMAKE_C_FLAGS=/std:c11 /utf-8' '-DCMAKE_C_FLAGS_MINSIZEREL=/O1 /Ob1 /Gy /Gw' -DCMAKE_POLICY_DEFAULT_CMP0091=NEW -DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded -DCMAKE_ARCHIVE_OUTPUT_DIRECTORY="$frontend" -DPUTTY_GSSAPI=OFF -DNEMOTERM_SINGLE_EXE=ON
if ($LASTEXITCODE) { throw 'Frontend configure failed' }
& cmake --build $frontend --target pterm --parallel 4
if ($LASTEXITCODE) { throw 'Frontend build failed' }

# Restore only the WIL headers used by the native console host.
& nuget install Microsoft.Windows.ImplementationLibrary -Version 1.0.250325.1 -Source https://api.nuget.org/v3/index.json -OutputDirectory "$source/packages" -NonInteractive
if ($LASTEXITCODE) { throw 'WIL restore failed' }
& msbuild "$source/src/host/exe/Host.EXE.vcxproj" /m:2 /v:minimal /p:Configuration=Release /p:Platform=x64 "/p:SolutionDir=$source\" /p:WindowsTerminalBranding=Release /p:BuildInParallel=false /bl:"$root/build/single-exe.binlog"
if ($LASTEXITCODE) { throw 'Combined console host build failed' }
New-Item -ItemType Directory -Force $Destination | Out-Null
Copy-Item -LiteralPath "$source/bin/x64/Release/nemoterm.exe" -Destination (Join-Path $Destination 'nemoterm.exe')
Get-FileHash -LiteralPath (Join-Path $Destination 'nemoterm.exe') -Algorithm SHA256
