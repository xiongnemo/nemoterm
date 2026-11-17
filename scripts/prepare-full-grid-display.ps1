param([switch]$Restore)
$ErrorActionPreference='Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_ENVIRONMENT -ne 'github-hosted') {
    throw 'Display setup requires a disposable GitHub-hosted runner'
}
$root=Split-Path $PSScriptRoot -Parent
$directory=Join-Path $root 'build/interaction-dependencies'
$helper=Join-Path $directory 'dpi-display.exe'
$recordPath=Join-Path $directory 'full-grid-display.json'
function Read-Display([string[]]$Arguments=@()) {
    $raw=& $helper @Arguments | Out-String
    if ($LASTEXITCODE) { throw 'Display probe failed' }
    return $raw | ConvertFrom-Json
}
function Primary($State) {
    $monitors=@($State.monitors | Where-Object primary)
    if ($monitors.Count -ne 1) { throw 'Expected exactly one primary display' }
    return $monitors[0]
}
function Save-Record {
    $script:record | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath $recordPath -Encoding utf8
}
function Set-Scale([int]$Percent) {
    $attempt=Read-Display @('--set-percent', [string]$Percent)
    for ($poll=0; $poll -lt 30; $poll++) {
        $current=Read-Display
        if ((Primary $current).dpi -eq $Percent*96/100) { return $attempt }
        Start-Sleep -Milliseconds 100
    }
    throw "Display did not reach $Percent percent scaling"
}
if ($Restore) {
    if (-not (Test-Path -LiteralPath $recordPath)) { return }
    $script:record=Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json -AsHashtable
    try {
        $initial=Primary $record.initial
        $percent=[int]($initial.dpi*100/96)
        if ((Primary (Read-Display)).dpi -ne $initial.dpi) { $record.scale_restoration=Set-Scale $percent }
        $width=$initial.bounds[2]-$initial.bounds[0]
        $height=$initial.bounds[3]-$initial.bounds[1]
        $record.resolution_restoration=Read-Display @('--set-size', [string]$width, [string]$height)
        $record.final=Read-Display
        $final=Primary $record.final
        $record.restored=($final.bounds[2]-$final.bounds[0] -eq $width -and
            $final.bounds[3]-$final.bounds[1] -eq $height -and $final.dpi -eq $initial.dpi)
        if (-not $record.restored) { throw 'Display restoration did not match the initial mode' }
    } catch { $record.restoration_error=$_.Exception.Message; throw }
    finally { Save-Record }
    return
}
if (Test-Path -LiteralPath $recordPath) { throw 'Display record already exists; refusing to overwrite the original mode' }
$script:record=[ordered]@{initial=(Read-Display);ready=$false}
Save-Record
try {
    $monitor=Primary $record.initial
    $modes=@($monitor.display_modes | Where-Object { $_[0] -ge 1600 -and $_[1] -ge 1100 } |
        Sort-Object { $_[0]*$_[1] })
    if (-not $modes.Count) { throw 'No advertised display mode has room for the full Sarasa grid' }
    $mode=$modes[0]
    $record.resolution_preparation=Read-Display @('--set-size', [string]$mode[0], [string]$mode[1])
    if ($record.resolution_preparation.resize_result -ne 0) { throw 'Advertised display mode change failed' }
    if ((Primary (Read-Display)).dpi -ne 96) { $record.scale_preparation=Set-Scale 100 }
    $record.prepared=Read-Display
    $prepared=Primary $record.prepared
    if ($prepared.dpi -ne 96 -or $prepared.work[2]-$prepared.work[0] -lt 1600 -or
        $prepared.work[3]-$prepared.work[1] -lt 1000) { throw 'Actual display work area is too small' }
    $record.ready=$true
} catch { $record.preparation_error=$_.Exception.Message; throw }
finally { Save-Record }
