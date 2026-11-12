$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
& "$PSScriptRoot/build.ps1" -Tests
foreach ($name in @('test_conf', 'test_terminal', 'test_sixel', 'test_sixel_terminal', 'test_resize', 'test_reflow', 'test_mouse', 'test_colour', 'test_osc_colour', 'test_modes', 'test_sync', 'test_snapshot', 'test_sgr', 'test_queries', 'test_tcap', 'test_highlight', 'test_hyperlink', 'test_keyboard', 'test_osc52', 'test_mok', 'test_win32_input', 'test_state_control')) {
    & "$root/build/$name.exe"
    if ($LASTEXITCODE) { throw "${name} failed: $LASTEXITCODE" }
}
