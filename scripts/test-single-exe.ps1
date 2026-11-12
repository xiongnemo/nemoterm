param(
    [Parameter(Mandatory=$true)][string]$Executable,
    [string]$Destination = ''
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$Executable = (Resolve-Path -LiteralPath $Executable).Path
if (!$Destination) { $Destination = Join-Path $root 'build/single-exe-check' }
$Destination = [IO.Path]::GetFullPath($Destination)
if (Test-Path -LiteralPath $Destination) { throw 'Choose a fresh validation directory to preserve previous evidence.' }
New-Item -ItemType Directory -Path $Destination | Out-Null
New-Item -ItemType Directory -Path "$Destination/dist", "$Destination/research", "$Destination/build", "$Destination/logs" | Out-Null
Copy-Item -LiteralPath "$root/tests" -Destination "$Destination/tests" -Recurse
Copy-Item -LiteralPath $Executable -Destination "$Destination/dist/nemoterm.exe"
$previousExe = $env:NEMOTERM_TEST_EXE
$env:NEMOTERM_TEST_EXE = "$Destination/dist/nemoterm.exe"
$checks = [Collections.Generic.List[string]]::new()
try {
    $tests = @('single_exe', 'mouse', 'sync', 'sgr', 'font_resize', 'font_fallback', 'query',
        'highlight', 'sixel', 'sixel_font', 'hyperlink', 'reflow', 'keyboard',
        'osc52', 'mok', 'win32_input', 'state_control', 'selective_erase', 'rectangle', 'margins',
        'input_method', 'unicode_input', 'shell', 'delegated_console')
    foreach ($name in $tests) {
        & python "$Destination/tests/${name}_window_smoke.py" 2>&1 | Tee-Object "$Destination/logs/$name.log"
        if ($LASTEXITCODE) { throw "Single-executable native test failed: $name" }
        $checks.Add($name)
        if ($name -eq 'font_fallback') {
            Copy-Item "$Destination/research/font-fallback-observed.json" "$Destination/research/font-fallback-default-observed.json"
            Copy-Item "$Destination/research/font-fallback.png" "$Destination/research/font-fallback-default.png"
            & python "$Destination/tests/font_fallback_window_smoke.py" --font Courier 2>&1 | Tee-Object "$Destination/logs/font-fallback-courier.log"
            if ($LASTEXITCODE) { throw 'Single-executable bitmap-primary font fallback test failed' }
            $checks.Add('font-fallback-courier')
        }
        if ($name -eq 'keyboard' -or $name -eq 'mok') {
            Copy-Item "$Destination/research/$name-window-observed.json" "$Destination/research/$name-default-observed.json"
            Copy-Item "$Destination/research/$name-window.png" "$Destination/research/$name-default.png"
            $variantArgs = @('--font', 'Courier New')
            if ($name -eq 'mok') { $variantArgs += @('--initial-level', '3', '--initial-format', '1') }
            & python "$Destination/tests/${name}_window_smoke.py" @variantArgs 2>&1 | Tee-Object "$Destination/logs/$name-courier.log"
            if ($LASTEXITCODE) { throw "Single-executable alternate-font test failed: $name" }
            $checks.Add("$name-courier")
        }
    }
    & powershell.exe -NoProfile -File "$Destination/tests/settings_window_smoke.ps1" 2>&1 | Tee-Object "$Destination/logs/settings.log"
    if ($LASTEXITCODE) { throw 'Single-executable settings test failed' }
    $checks.Add('settings')
    $files = @(Get-ChildItem -LiteralPath "$Destination/dist" -File)
    if ($files.Count -ne 1 -or $files[0].Name -ne 'nemoterm.exe') { throw 'Unexpected sidecar files in isolated executable directory' }
    $digest = Get-FileHash -LiteralPath "$Destination/dist/nemoterm.exe" -Algorithm SHA256
    [ordered]@{
        executable_sha256 = $digest.Hash.ToLowerInvariant()
        executable_bytes = $files[0].Length
        passed_checks = @($checks.ToArray())
        executable_directory_files = @($files.Name)
        recorded_utc = [DateTime]::UtcNow.ToString('o')
    } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath "$Destination/research/single-exe-validation.json" -Encoding utf8
    $digest
} finally {
    $env:NEMOTERM_TEST_EXE = $previousExe
}
