param(
    [Parameter(Mandatory=$true)][string]$Run,
    [Parameter(Mandatory=$true)][string]$Commit,
    [Parameter(Mandatory=$true)][string]$Destination
)
$ErrorActionPreference='Stop'
if ($Run -notmatch '^\d+$' -or $Commit -notmatch '^[0-9a-f]{40}$') { throw 'Invalid product identity' }
$record=gh run view $Run --repo $env:GITHUB_REPOSITORY --json headSha,jobs | ConvertFrom-Json
if ($LASTEXITCODE -or $record.headSha -ne $Commit) { throw 'Source run identity mismatch' }
$source=@($record.jobs | Where-Object { $_.name -eq 'Source-built console host for compiler comparison' -and $_.conclusion -eq 'success' })
if ($source.Count -ne 1) { throw 'Expected a successful source-host build job' }
git diff --quiet $Commit HEAD -- vendor native locales scripts/build.ps1 scripts/build-single-exe.ps1 scripts/prepare-single-exe.py scripts/generate-ui-catalog.py
if ($LASTEXITCODE) { throw 'Production differs; select a fresh source-host artifact' }
gh run download $Run --repo $env:GITHUB_REPOSITORY --name "source-console-host-x64-$Commit" --dir $Destination
if ($LASTEXITCODE) { throw 'Product download failed' }
$manifest=Get-Content (Join-Path $Destination 'SOURCE-HOST.json') -Raw | ConvertFrom-Json
$exe=Get-Item (Join-Path $Destination 'nemoterm.exe')
if ($manifest.SourceCommit -ne $Commit -or $manifest.Executable.SHA256 -ne (Get-FileHash -LiteralPath $exe.FullName).Hash.ToLowerInvariant() -or $manifest.Executable.Bytes -ne $exe.Length) { throw 'Executable identity mismatch' }
Write-Host "Verified product $Commit : $($manifest.Executable.SHA256)"
