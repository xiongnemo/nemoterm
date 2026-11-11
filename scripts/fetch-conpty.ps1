param(
    [ValidateSet('x64', 'x86', 'arm64')][string]$Architecture = 'x64',
    [string]$Destination = (Join-Path (Split-Path $PSScriptRoot -Parent) 'dist')
)
$ErrorActionPreference = 'Stop'
$version = '1.25.260930003'
$archiveSha256 = '02B07B349AF66D801159BDF9E440D4A1CE78BB951F37FC8609731665AFDAE7EE'
$url = "https://api.nuget.org/v3-flatcontainer/microsoft.windows.console.conpty/$version/microsoft.windows.console.conpty.$version.nupkg"
$root = Split-Path $PSScriptRoot -Parent
$cacheDirectory = Join-Path $root 'tools/conpty'
$archive = Join-Path $cacheDirectory "microsoft.windows.console.conpty.$version.nupkg"
$Destination = [IO.Path]::GetFullPath($Destination)
New-Item -ItemType Directory -Force -Path $cacheDirectory, $Destination | Out-Null
if (!(Test-Path -LiteralPath $archive)) {
    Invoke-WebRequest -Uri $url -OutFile $archive
}
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $archiveSha256) {
    throw "ConPTY package SHA256 mismatch: $archive. No runtime files were deployed."
}

# Extract only the selected native pair from the verified package. No package
# scripts run, and nothing is installed into Windows or the user's settings.
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [IO.Compression.ZipFile]::OpenRead($archive)
try {
    $dllEntry = $zip.GetEntry("runtimes/win-$Architecture/native/conpty.dll")
    $hostEntry = $zip.GetEntry("build/native/runtimes/$Architecture/OpenConsole.exe")
    if (!$dllEntry -or !$hostEntry) { throw 'Expected ConPTY package files are missing' }
    [IO.Compression.ZipFileExtensions]::ExtractToFile($dllEntry, (Join-Path $Destination 'conpty.dll'), $true)
    [IO.Compression.ZipFileExtensions]::ExtractToFile($hostEntry, (Join-Path $Destination 'OpenConsole.exe'), $true)
} finally {
    $zip.Dispose()
}

# The NuGet nuspec declares MIT but does not include a license text file.
# Preserve Microsoft's full license from its official source repository:
$licenseSource = 'https://github.com/microsoft/terminal/blob/5f7dc283013152f89bfb76950515c33f45157ad7/LICENSE'
$licenseText = @'
Copyright (c) Microsoft Corporation. All rights reserved.

MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'@
$licenseText | Set-Content -LiteralPath (Join-Path $Destination 'LICENCE-Microsoft-ConPTY.txt') -Encoding utf8
$files = @('conpty.dll', 'OpenConsole.exe') | ForEach-Object {
    $file = Join-Path $Destination $_
    [ordered]@{ Name = $_; SHA256 = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash }
}
[ordered]@{
    Package = 'Microsoft.Windows.Console.ConPTY'
    Version = $version
    Architecture = $Architecture
    Source = $url
    PackageSHA256 = $archiveSha256
    LicenseSource = $licenseSource
    Files = @($files)
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $Destination 'CONPTY-RUNTIME.json') -Encoding utf8
Get-Item -LiteralPath (Join-Path $Destination 'conpty.dll'), (Join-Path $Destination 'OpenConsole.exe') | Select-Object FullName, Length
