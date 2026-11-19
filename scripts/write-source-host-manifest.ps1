# Metadata only: run in the same hosted VS developer shell that built the image.
[CmdletBinding()]
param([Parameter(Mandatory)][string]$Directory)
$ErrorActionPreference = 'Stop'
function Get-ToolRecord([string]$Name) {
    $path = (Get-Command $Name -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
    $file = Get-Item -LiteralPath $path
    [ordered]@{ Name=$file.Name; FileVersion=$file.VersionInfo.FileVersion; SHA256=(Get-FileHash -LiteralPath $file.FullName).Hash.ToLowerInvariant() }
}
$image = Get-Item -LiteralPath (Join-Path $Directory 'nemoterm.exe')
[ordered]@{
    SourceCommit = (git rev-parse HEAD).Trim()
    MicrosoftTerminalCommit = (git -C vendor/microsoft-terminal rev-parse HEAD).Trim()
    OverlaySHA256 = (Get-FileHash scripts/prepare-single-exe.py).Hash.ToLowerInvariant()
    EntrySHA256 = (Get-FileHash native/single_exe/entry.cpp).Hash.ToLowerInvariant()
    Executable = [ordered]@{ SHA256=(Get-FileHash -LiteralPath $image.FullName).Hash.ToLowerInvariant(); Bytes=$image.Length }
    BuildEnvironment = [ordered]@{
        ImageOS=$env:ImageOS; ImageVersion=$env:ImageVersion; VCToolsVersion=$env:VCToolsVersion; WindowsSDKVersion=$env:WindowsSDKVersion
        Tools=@(Get-ToolRecord 'cl.exe'; Get-ToolRecord 'link.exe'; Get-ToolRecord 'msbuild.exe')
    }
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Directory 'SOURCE-HOST.json') -Encoding utf8
