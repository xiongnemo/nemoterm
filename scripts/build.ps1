param([switch]$Tests)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$cmake = Join-Path $root 'tools/python/cmake/data/bin/cmake.exe'
$ninja = Join-Path $root 'tools/python/bin/ninja.exe'
if (!(Test-Path $cmake) -or !(Test-Path $ninja)) {
    python -m pip install --target "$root/tools/python" cmake==4.4.4 ninja==1.13.2
    if ($LASTEXITCODE) { throw 'Build tool installation failed' }
}
$cc = (Get-Command gcc.exe -ErrorAction Stop).Source
& $cmake -S "$root/vendor/putty-0.85" -B "$root/build" -G Ninja "-DCMAKE_MAKE_PROGRAM=$ninja" "-DCMAKE_C_COMPILER=$cc" -DCMAKE_BUILD_TYPE=MinSizeRel '-DCMAKE_C_FLAGS_MINSIZEREL=-Os -ffunction-sections -fdata-sections' '-DCMAKE_EXE_LINKER_FLAGS=-Wl,--gc-sections -static-libgcc' -DPUTTY_GSSAPI=OFF
if ($LASTEXITCODE) { throw 'Configure failed' }
$targets = @('pterm')
if ($Tests) { $targets += @('test_terminal', 'test_conf', 'test_sixel', 'test_sixel_terminal', 'test_resize', 'test_mouse', 'test_colour', 'test_osc_colour', 'test_modes', 'test_sync', 'test_snapshot', 'test_sgr', 'test_queries', 'test_tcap', 'test_highlight', 'test_hyperlink') }
& $cmake --build "$root/build" --target @targets --parallel 8
if ($LASTEXITCODE) { throw 'Build failed' }
New-Item -ItemType Directory -Force "$root/dist" | Out-Null
Copy-Item "$root/build/nemoterm.exe" "$root/dist/nemoterm.exe"
Copy-Item "$root/vendor/putty-0.85/LICENCE" "$root/dist/LICENCE-PuTTY.txt"
Copy-Item "$root/LICENSE" "$root/dist/LICENSE-Nemoterm.txt"
& "$PSScriptRoot/fetch-conpty.ps1" -Architecture x64 -Destination "$root/dist"
Get-Item "$root/dist/nemoterm.exe" | Select-Object FullName,Length
