param([Parameter(Mandatory)][int]$ProcessId,
      [string]$Output = 'research/nemoterm-memory.json',
      [string]$Scenario = 'visible frontend; no trimming',
      [ValidateSet('gdi','opengl','directx')][string]$ActualRenderer = 'gdi')
$ErrorActionPreference = 'Stop'
# This helper samples counters only. The caller must supply the observed
# renderer, including any fallback, rather than the requested setting.
$privateLimit = switch ($ActualRenderer) { 'gdi' {20000000}; 'directx' {25000000}; 'opengl' {$null} }
$p = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId"
if (!$p -or $p.Name -ne 'nemoterm.exe') { throw 'Expected live nemoterm.exe PID' }
$samples = @()
for ($i = 0; $i -lt 5; $i++) {
    $m = Get-CimInstance Win32_PerfFormattedData_PerfProc_Process -Filter "IDProcess=$ProcessId"
    if (!$m) { throw 'Process memory counters missing' }
    $samples += [pscustomobject]@{
        time = (Get-Date).ToString('o'); pid = $ProcessId
        private_working_set_bytes = [long]$m.WorkingSetPrivate
        total_working_set_bytes = [long]$m.WorkingSet
        private_committed_bytes = [long]$m.PrivateBytes
    }
    if ($i -lt 4) { Start-Sleep -Milliseconds 600 }
}
$children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$ProcessId" | ForEach-Object {
    $child = $_
    $m = Get-CimInstance Win32_PerfFormattedData_PerfProc_Process -Filter "IDProcess=$($child.ProcessId)"
    [pscustomobject]@{pid=$child.ProcessId;name=$child.Name;path=$child.ExecutablePath;private_working_set_bytes=$m.WorkingSetPrivate;total_working_set_bytes=$m.WorkingSet}
})
[pscustomobject]@{
    executable=$p.ExecutablePath;sha256=(Get-FileHash -LiteralPath $p.ExecutablePath).Hash
    scenario=$Scenario;samples=$samples;actual_renderer=$ActualRenderer
    renderer_source='caller-supplied, not detected by this counter-only helper'
    direct_children=$children
    limit_private_bytes=$privateLimit;target_total_bytes=50000000
    private_limit_inclusive=($ActualRenderer -eq 'directx')
    private_limit_pass=$(if ($null -eq $privateLimit) {$null}
        elseif ($ActualRenderer -eq 'directx') {(@($samples | Where-Object private_working_set_bytes -gt $privateLimit).Count -eq 0)}
        else {(@($samples | Where-Object private_working_set_bytes -ge $privateLimit).Count -eq 0)})
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $Output -Encoding utf8
Get-Content -LiteralPath $Output
