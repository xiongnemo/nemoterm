# CI fixture: start the actual client from an attached PowerShell process.
# ProcessStartInfo.ArgumentList preserves empty --tools and --setting-sources.
param([Parameter(Mandatory)][string]$FixtureRoot)
$ErrorActionPreference = 'Stop'
$arguments = @(Get-Content -LiteralPath (Join-Path $FixtureRoot 'shell-argv.json') -Raw | ConvertFrom-Json)
$info = [Diagnostics.ProcessStartInfo]::new()
$info.UseShellExecute = $false
$info.FileName = $arguments[0]
foreach ($item in $arguments[1..($arguments.Count-1)]) { $info.ArgumentList.Add([string]$item) }
[Console]::WriteLine('NEMO_SHELL_BEFORE:דהו')
$client = [Diagnostics.Process]::Start($info)
try {
    $pair = @{ parent = $PID; parent_image = (Get-Process -Id $PID).ProcessName; child = $client.Id; child_image = $client.ProcessName }
    $pair | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $FixtureRoot 'shell-processes.json')
    $client.WaitForExit()
    [Console]::WriteLine('NEMO_SHELL_AFTER:דהו')
    exit $client.ExitCode
} finally { $client.Dispose() }
