param([switch]$Collect)
$ErrorActionPreference = 'Stop'
if ($env:CI -ne 'true') { throw 'This script is only for disposable CI runners.' }
$root = Split-Path $PSScriptRoot -Parent
$directory = Join-Path $root 'build/native-crashes'
New-Item -ItemType Directory -Path $directory -Force | Out-Null
if ($Collect) {
    $events = @(Get-WinEvent -FilterHashtable @{
        LogName='Application'; Id=1000,1001; StartTime=(Get-Date).AddHours(-1)
    } -ErrorAction SilentlyContinue | Where-Object {
        $_.Message -match '(?i)\bnemoterm\.exe\b'
    } | Select-Object TimeCreated,Id,Message)
    ConvertTo-Json -InputObject $events -Depth 4 |
        Set-Content -LiteralPath (Join-Path $directory 'application-errors.json') -Encoding utf8
} else {
    # Application-scoped minidumps on a disposable runner. No debugger is
    # injected, and the ordinary executable contains no crash-test machinery.
    $key = 'HKLM:\SOFTWARE\Microsoft\Windows\Windows Error Reporting\LocalDumps\nemoterm.exe'
    New-Item -Path $key -Force | Out-Null
    New-ItemProperty -Path $key -Name DumpFolder -PropertyType ExpandString -Value $directory -Force | Out-Null
    New-ItemProperty -Path $key -Name DumpType -PropertyType DWord -Value 1 -Force | Out-Null
    New-ItemProperty -Path $key -Name DumpCount -PropertyType DWord -Value 5 -Force | Out-Null
}
