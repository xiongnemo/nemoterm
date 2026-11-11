param([string]$OutputDirectory = $PSScriptRoot)
$ErrorActionPreference = 'Stop'
$snapshotTime = Get-Date -Format o
$processes = @(Get-CimInstance Win32_Process | Where-Object Name -eq 'pterm.exe')
$ids = @($processes.ProcessId)
$counters = @(Get-CimInstance Win32_PerfFormattedData_PerfProc_Process | Where-Object IDProcess -in $ids)
$rows = foreach ($process in $processes) {
    $counter = $counters | Where-Object IDProcess -eq $process.ProcessId | Select-Object -First 1
    [pscustomobject]@{
        ProcessId = $process.ProcessId
        ParentProcessId = $process.ParentProcessId
        ExecutablePath = $process.ExecutablePath
        WorkingSetBytes = $counter.WorkingSet
        PrivateWorkingSetBytes = $counter.WorkingSetPrivate
        PrivateCommitBytes = $counter.PrivateBytes
        ThreadCount = $counter.ThreadCount
    }
}
$result = [pscustomobject]@{
    ObservedAt = $snapshotTime
    Method = 'Read-only Win32_Process and Win32_PerfFormattedData_PerfProc_Process; no trimming, launch, input or window mutation'
    Scope = 'Existing pterm processes only; excludes ConPTY conhost and child applications'
    Processes = @($rows)
}
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$result | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $OutputDirectory 'pterm-memory-latest.json') -Encoding utf8
$rows | Format-Table
