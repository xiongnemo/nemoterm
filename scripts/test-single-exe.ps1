param(
    [Parameter(Mandatory=$true)][string]$Executable,
    [string]$Destination = '',
    [string]$CodexExecutable = ''
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$Executable = (Resolve-Path -LiteralPath $Executable).Path
if ($CodexExecutable) { $CodexExecutable = (Resolve-Path -LiteralPath $CodexExecutable).Path }
if (!$Destination) { $Destination = Join-Path $root 'build/single-exe-check' }
$Destination = [IO.Path]::GetFullPath($Destination)
if (Test-Path -LiteralPath $Destination) { throw 'Choose a fresh validation directory to preserve previous evidence.' }
New-Item -ItemType Directory -Path $Destination | Out-Null
New-Item -ItemType Directory -Path "$Destination/dist", "$Destination/research", "$Destination/build", "$Destination/logs" | Out-Null
Copy-Item -LiteralPath "$root/tests" -Destination "$Destination/tests" -Recurse
New-Item -ItemType Directory -Path "$Destination/tools" | Out-Null
Copy-Item -LiteralPath "$root/tools/nemoterm_debug.py" -Destination "$Destination/tools/nemoterm_debug.py"
Copy-Item -LiteralPath $Executable -Destination "$Destination/dist/nemoterm.exe"
$previousExe = $env:NEMOTERM_TEST_EXE
$env:NEMOTERM_TEST_EXE = "$Destination/dist/nemoterm.exe"
$checks = [Collections.Generic.List[string]]::new()
try {
    foreach ($renderer in @('gdi', 'directx')) {
        & python "$Destination/tests/automation_window_smoke.py" --renderer $renderer 2>&1 | Tee-Object "$Destination/logs/automation-$renderer.log"
        if ($LASTEXITCODE) { throw "Local automation integration test failed: $renderer" }
        $checks.Add("automation-$renderer")
        & python "$Destination/tests/drop_window_smoke.py" --renderer $renderer 2>&1 | Tee-Object "$Destination/logs/drop-$renderer.log"
        if ($LASTEXITCODE) { throw "File drop and clipboard integration test failed: $renderer" }
        $checks.Add("drop-$renderer")
    }
    $tests = @('single_exe', 'shutdown', 'startup_size', 'renderer', 'grapheme', 'rtl', 'bindings', 'input_method', 'unicode_input', 'console_unicode', 'mouse', 'selection', 'sync', 'sgr', 'font_resize', 'font_fallback', 'query',
        'highlight', 'sixel', 'sixel_font', 'sixel_palette', 'hyperlink', 'reflow', 'keyboard',
        'osc52', 'mok', 'win32_input', 'state_control', 'tabulation', 'double_size', 'alignment', 'graphics_query', 'dec_status', 'checksum', 'sgr_stack', 'palette_stack', 'reset_palette', 'selection_colour', 'attribute_colour', 'presentation_state', 'horizontal', 'reverse_wrap', 'relative_cursor', 'selective_erase', 'guarded_area', 'rectangle', 'margins', 'cwd',
        'shell_marks', 'shell', 'powershell_environment', 'delegated_console', 'caret_startup', 'session', 'session_restart', 'titles', 'geometry', 'window_resize', 'gpu_lifecycle')
    $tests += 'c1_controls', 'startup_visibility'
    foreach ($name in $tests) {
        Write-Host "Starting isolated native test: $name"
        $nativeArgs = @()
        if ($name -eq 'input_method' -and $env:CI -eq 'true') { $nativeArgs += @('--font', 'Consolas') }
        & python "$Destination/tests/${name}_window_smoke.py" @nativeArgs 2>&1 | Tee-Object "$Destination/logs/$name.log"
        if ($LASTEXITCODE) { throw "Single-executable native test failed: $name" }
        $checks.Add($name)
        if ($name -eq 'c1_controls') {
            & python "$Destination/tests/c1_controls_window_smoke.py" --input-cp 65001 2>&1 | Tee-Object "$Destination/logs/c1-controls-utf8.log"
            if ($LASTEXITCODE) { throw 'Single-executable UTF-8 C1 transport test failed' }
            $checks.Add('c1-controls-utf8')
        }
        if ($name -eq 'grapheme') {
            & python "$Destination/tests/grapheme_window_smoke.py" --font-resize 2>&1 | Tee-Object "$Destination/logs/grapheme-font.log"
            if ($LASTEXITCODE) { throw 'Single-executable grapheme font resize test failed' }
            $checks.Add('grapheme-font')
        }
        if ($name -eq 'rtl') {
            Copy-Item "$Destination/research/rtl-window-observed.json" "$Destination/research/rtl-default-observed.json"
            & python "$Destination/tests/rtl_window_smoke.py" --font Courier 2>&1 | Tee-Object "$Destination/logs/rtl-courier.log"
            if ($LASTEXITCODE) { throw 'Single-executable bitmap-primary RTL test failed' }
            $checks.Add('rtl-courier')
        }
        if ($name -eq 'session') {
            foreach ($renderer in @('opengl', 'directx')) {
                & python "$Destination/tests/session_window_smoke.py" --renderer $renderer 2>&1 | Tee-Object "$Destination/logs/session-$renderer.log"
                if ($LASTEXITCODE) { throw "Single-executable session lifetime test failed: $renderer" }
                $checks.Add("session-$renderer")
            }
        }
        if ($name -eq 'selection') {
            Copy-Item "$Destination/research/selection-observed.json" "$Destination/research/selection-gdi-observed.json"
            & python "$Destination/tests/selection_window_smoke.py" --renderer 2 2>&1 | Tee-Object "$Destination/logs/selection-directx.log"
            if ($LASTEXITCODE) { throw 'Single-executable DirectX selection test failed' }
            Copy-Item "$Destination/research/selection-observed.json" "$Destination/research/selection-directx-observed.json"
            $checks.Add('selection-directx')
        }
        if ($name -in @('palette_stack', 'reset_palette', 'selection_colour', 'attribute_colour', 'alignment', 'relative_cursor', 'sixel_palette')) {
            foreach ($renderer in @('opengl', 'directx')) {
                & python "$Destination/tests/${name}_window_smoke.py" --renderer $renderer 2>&1 | Tee-Object "$Destination/logs/$name-$renderer.log"
                if ($LASTEXITCODE) { throw "Single-executable renderer test failed: $name $renderer" }
                $checks.Add("$name-$renderer")
            }
            if ($name -eq 'selection_colour') {
                & python "$Destination/tests/selection_colour_window_smoke.py" --renderer gdi --configured 2>&1 | Tee-Object "$Destination/logs/selection-colour-gdi-configured.log"
                if ($LASTEXITCODE) { throw 'Single-executable configured selection colour test failed' }
                $checks.Add('selection-colour-gdi-configured')
            }
            if ($name -eq 'attribute_colour') {
                & python "$Destination/tests/attribute_colour_window_smoke.py" --renderer gdi --configured 2>&1 | Tee-Object "$Destination/logs/attribute-colour-gdi-configured.log"
                if ($LASTEXITCODE) { throw 'Single-executable configured attribute colour test failed' }
                $checks.Add('attribute-colour-gdi-configured')
            }
        }
        if ($name -eq 'titles') {
            & python "$Destination/tests/titles_window_smoke.py" --modes 2>&1 | Tee-Object "$Destination/logs/title-modes.log"
            if ($LASTEXITCODE) { throw 'Single-executable title encoding test failed' }
            $checks.Add('title-modes')
        }
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
    foreach ($case in @(@('gdi','top'), @('gdi','bottom'), @('directx','left'), @('opengl','right'))) {
        $name = "tabs-$($case[0])-$($case[1])"
        & python "$Destination/tests/tabs_window_smoke.py" --renderer $case[0] --side $case[1] 2>&1 | Tee-Object "$Destination/logs/$name.log"
        if ($LASTEXITCODE) { throw "Single-executable tab host test failed: $name" }
        $checks.Add($name)
    }
    & python "$Destination/tests/tabs_regression_suite.py" 2>&1 | Tee-Object "$Destination/logs/tabs-regressions.log"
    if ($LASTEXITCODE) { throw 'Single-executable tab regression suite failed' }
    $checks.Add('tabs-regressions')
    & powershell.exe -NoProfile -File "$Destination/tests/settings_window_smoke.ps1" 2>&1 | Tee-Object "$Destination/logs/settings.log"
    if ($LASTEXITCODE) { throw 'Single-executable settings test failed' }
    $checks.Add('settings')
    & powershell.exe -NoProfile -File "$Destination/tests/settings_window_smoke.ps1" -TabHost 2>&1 | Tee-Object "$Destination/logs/tabs-settings.log"
    if ($LASTEXITCODE) { throw 'Single-executable tab settings test failed' }
    $checks.Add('tabs-settings')
    if ($CodexExecutable) {
        $imageArgs = @('--client', 'codex', '--client-exe', $CodexExecutable,
            '--terminal', "$Destination/dist/nemoterm.exe")
        if ($env:CI -eq 'true') { $imageArgs += @('--font', 'Consolas') }
        & python "$Destination/tests/agent_clipboard_smoke.py" @imageArgs 2>&1 | Tee-Object "$Destination/logs/codex-image-paste.log"
        if ($LASTEXITCODE) { throw 'Real Codex image clipboard test failed' }
        $checks.Add('codex-image-paste')
        foreach ($mode in @('default', 'inline', 'tabs-default', 'tabs-inline')) {
            $nativeArgs = @('--codex', $CodexExecutable)
            if ($mode.EndsWith('inline')) { $nativeArgs += '--inline' }
            if ($mode.StartsWith('tabs-')) { $nativeArgs += '--tabs' }
            if ($env:CI -eq 'true') { $nativeArgs += @('--font', 'Consolas') }
            & python "$Destination/tests/codex_window_smoke.py" @nativeArgs 2>&1 | Tee-Object "$Destination/logs/codex-$mode.log"
            if ($LASTEXITCODE) { throw "Single-executable Codex test failed: $mode" }
            $checks.Add("codex-$mode")
        }
    }
    # Independent functional checks run before the still-mandatory memory gate.
    # No success manifest or distributable is produced when either workload fails.
    foreach ($case in @(@('gdi','top'), @('directx','left'))) {
        $name = "workload-tabs-$($case[0])-$($case[1])"
        & python "$Destination/tests/tabs_window_smoke.py" --renderer $case[0] --side $case[1] --workload-memory 2>&1 | Tee-Object "$Destination/logs/$name.log"
        if ($LASTEXITCODE) { throw "Single-executable tab workload and memory test failed: $name" }
        $checks.Add($name)
    }
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
