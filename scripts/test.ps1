$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
& "$PSScriptRoot/build.ps1" -Tests
foreach ($name in @('test_conf', 'test_terminal', 'test_sixel', 'test_sixel_terminal', 'test_resize', 'test_mouse', 'test_colour', 'test_osc_colour')) {
    & "$root/build/$name.exe"
    if ($LASTEXITCODE) { throw "${name} failed: $LASTEXITCODE" }
}
