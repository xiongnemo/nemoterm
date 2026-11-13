param([string]$Destination = '')
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
& python "$PSScriptRoot/generate-grapheme-tables.py" --check
if ($LASTEXITCODE) { throw 'Unicode input or generated table verification failed' }
& "$PSScriptRoot/build.ps1" -Tests -Destination $Destination
foreach ($name in @('test_conf', 'test_terminal', 'test_sixel', 'test_sixel_terminal', 'test_resize', 'test_reflow', 'test_mouse', 'test_colour', 'test_osc_colour', 'test_modes', 'test_sync', 'test_snapshot', 'test_sgr', 'test_queries', 'test_titles', 'test_tcap', 'test_highlight', 'test_hyperlink', 'test_keyboard', 'test_osc52', 'test_mok', 'test_win32_input', 'test_state_control', 'test_selective_erase', 'test_rectangle', 'test_margins', 'test_cwd', 'test_shell_marks', 'test_shell', 'test_font_cmap', 'test_font_fallback')) {
    & "$root/build/$name.exe"
    if ($LASTEXITCODE) { throw "${name} failed: $LASTEXITCODE" }
}
& "$root/build/test_grapheme.exe" "$root/tools/unicode/18.0.0/GraphemeBreakTest.txt"
if ($LASTEXITCODE) { throw 'Unicode grapheme conformance tests failed' }
& "$root/build/test_grapheme_terminal.exe"
if ($LASTEXITCODE) { throw 'Terminal grapheme cell tests failed' }
& "$root/build/test_cluster_renderer.exe"
if ($LASTEXITCODE) { throw 'Native cluster renderer tests failed' }
& "$root/build/test_gl_lifetime.exe"
if ($LASTEXITCODE) { throw 'OpenGL context lifetime tests failed' }
