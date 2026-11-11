param([Parameter(Mandatory)][int]$ProcessId, [string]$Output = 'research/nemoterm-memory.json')
$ErrorActionPreference = 'Stop'
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
    scenario='visible 80x24 Sarasa text/colour fixture; no trimming';samples=$samples
    direct_children=$children
    limit_private_bytes=20000000;target_total_bytes=50000000
    private_limit_pass=(@($samples | Where-Object private_working_set_bytes -ge 20000000).Count -eq 0)
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $Output -Encoding utf8
Get-Content -LiteralPath $Output
