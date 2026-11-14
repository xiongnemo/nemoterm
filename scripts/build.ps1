param([switch]$Tests, [string]$Destination = '')
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
if (!$Destination) { $Destination = Join-Path $root 'dist' }
$Destination = [IO.Path]::GetFullPath($Destination)
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
if ($Tests) { $targets += @('test_terminal', 'test_conf', 'test_sixel', 'test_iterm', 'test_kitty_transport', 'test_raster', 'test_sixel_terminal', 'test_resize', 'test_reflow', 'test_mouse', 'test_colour', 'test_osc_colour', 'test_modes', 'test_sync', 'test_snapshot', 'test_sgr', 'test_queries', 'test_titles', 'test_tcap', 'test_highlight', 'test_hyperlink', 'test_keyboard', 'test_osc52', 'test_mok', 'test_win32_input', 'test_state_control', 'test_selective_erase', 'test_rectangle', 'test_margins', 'test_cwd', 'test_shell_marks', 'test_shell', 'test_font_cmap', 'test_font_fallback', 'test_tabs_layout') }
if ($Tests) { $targets += @('test_grapheme', 'test_grapheme_terminal', 'test_cluster_renderer', 'test_gl_lifetime', 'test_iso2022_charset') }
& $cmake --build "$root/build" --target @targets --parallel 8
if ($LASTEXITCODE) { throw 'Build failed' }
New-Item -ItemType Directory -Force $Destination | Out-Null
Copy-Item "$root/build/nemoterm.exe" (Join-Path $Destination 'nemoterm.exe')
Copy-Item "$root/vendor/putty-0.85/LICENCE" (Join-Path $Destination 'LICENCE-PuTTY.txt')
Copy-Item "$root/LICENSE" (Join-Path $Destination 'LICENSE-Nemoterm.txt')
Copy-Item "$root/vendor/nerd-fonts/LICENSE" (Join-Path $Destination 'LICENSE-Nerd-Symbols.txt')
Copy-Item "$root/vendor/nerd-fonts/README.md" (Join-Path $Destination 'NOTICE-Nerd-Symbols.md')
Copy-Item "$root/vendor/nerd-fonts/NOTICE.txt" (Join-Path $Destination 'LICENSE-Nerd-Components.txt')
Copy-Item "$root/tools/unicode/18.0.0/LICENSE.txt" (Join-Path $Destination 'LICENSE-Unicode.txt')
Copy-Item "$root/tools/x11/xorg-server-21.1.16/LICENSE.txt" (Join-Path $Destination 'LICENSE-X11-Colours.txt')
& "$PSScriptRoot/fetch-conpty.ps1" -Architecture x64 -Destination $Destination
Get-Item (Join-Path $Destination 'nemoterm.exe') | Select-Object FullName,Length
