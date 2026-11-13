param(
    [Parameter(Mandatory=$true)][string]$SourceDirectory,
    [Parameter(Mandatory=$true)][string]$Destination,
    [Parameter(Mandatory=$true)][string]$ExpectedCommit
)
$ErrorActionPreference = 'Stop'
$SourceDirectory = (Resolve-Path -LiteralPath $SourceDirectory).Path
$Destination = (Resolve-Path -LiteralPath $Destination).Path
$metadata = Get-Content -LiteralPath (Join-Path $SourceDirectory 'SOURCE-HOST.json') -Raw | ConvertFrom-Json
if ($metadata.SourceCommit -cne $ExpectedCommit) { throw 'Console host and frontend source commits differ' }
$image = Join-Path $SourceDirectory 'nemoterm.exe'
$sha = (Get-FileHash -LiteralPath $image -Algorithm SHA256).Hash.ToLowerInvariant()
if ($sha -cne $metadata.Executable.SHA256 -or
    (Get-Item -LiteralPath $image).Length -ne $metadata.Executable.Bytes) {
    throw 'Source-built console host does not match its build manifest'
}
$runtimePath = Join-Path $Destination 'CONPTY-RUNTIME.json'
$runtime = Get-Content -LiteralPath $runtimePath -Raw | ConvertFrom-Json
$hostRecord = @($runtime.Files | Where-Object Name -eq 'OpenConsole.exe')
if ($hostRecord.Count -ne 1) { throw 'Expected one pinned console host in the runtime manifest' }
$dllRecord = @($runtime.Files | Where-Object Name -eq 'conpty.dll')
if ($dllRecord.Count -ne 1 -or
    (Get-FileHash -LiteralPath (Join-Path $Destination 'conpty.dll') -Algorithm SHA256).Hash -ne $dllRecord[0].SHA256) {
    throw 'ConPTY library does not match the pinned package manifest'
}
$originalHostSHA256 = $hostRecord[0].SHA256
# The combined image dispatches --headless to OpenConsole. Its GUI entry point
# is unused here; the normal distribution remains one combined nemoterm.exe.
$target = Join-Path $Destination 'OpenConsole.exe'
Copy-Item -LiteralPath $image -Destination $target
if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $sha) {
    throw 'Copied console host hash mismatch'
}
$hostRecord[0].SHA256 = $sha
$runtime | Add-Member -NotePropertyName SourceHost -NotePropertyValue ([ordered]@{
    Build = $metadata
    OriginalPackageHostSHA256 = $originalHostSHA256
    Mode = 'Source-built combined image invoked only as the headless console host'
}) -Force
$runtime | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $runtimePath -Encoding utf8
Copy-Item -LiteralPath (Join-Path $SourceDirectory 'SOURCE-HOST.json') -Destination $Destination
Write-Host "Installed source host $ExpectedCommit ($sha)"
