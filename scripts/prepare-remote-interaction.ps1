param([switch]$Shells)
$ErrorActionPreference='Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_ENVIRONMENT -ne 'github-hosted') { throw 'Setup is restricted to disposable GitHub-hosted Windows runners' }
$root=Split-Path $PSScriptRoot -Parent
$destination=Join-Path $root 'build/interaction-dependencies'
New-Item -ItemType Directory -Force $destination | Out-Null
$fontArchive=Join-Path $destination 'SarasaTermSCNerd-v2.3.1.ttf.7z'
$fontUrl='https://github.com/laishulu/Sarasa-Term-SC-Nerd/releases/download/v2.3.1/SarasaTermSCNerd.ttf.7z'
$fontHash='44483b749ed826111c150e37f92209927709bb53ec5021129701cc7d97eda0a9'
Invoke-WebRequest $fontUrl -OutFile $fontArchive
if ((Get-FileHash -LiteralPath $fontArchive).Hash.ToLowerInvariant() -ne $fontHash) { throw 'Sarasa archive hash mismatch' }
& 7z x $fontArchive "-o$destination/fonts" -y | Out-Null
if ($LASTEXITCODE) { throw 'Font extraction failed' }
$font=@(Get-ChildItem "$destination/fonts" -Recurse -Filter '*Light.ttf' | Where-Object { $_.Name -notmatch 'ExtraLight' })
if ($font.Count -ne 1) { throw "Expected one Light font, found $($font.Count)" }
Add-Type @'
using System;
using System.Runtime.InteropServices;
using System.Text;
public static class FixtureFont {
 [DllImport("gdi32.dll",CharSet=CharSet.Unicode)] public static extern int AddFontResourceW(string path);
 [DllImport("gdi32.dll",CharSet=CharSet.Unicode)] public static extern IntPtr CreateFontW(int h,int w,int e,int o,int weight,uint italic,uint underline,uint strike,uint charset,uint op,uint cp,uint quality,uint pitch,string name);
 [DllImport("gdi32.dll")] public static extern IntPtr CreateCompatibleDC(IntPtr dc);
 [DllImport("gdi32.dll")] public static extern IntPtr SelectObject(IntPtr dc,IntPtr obj);
 [DllImport("gdi32.dll",CharSet=CharSet.Unicode)] public static extern int GetTextFaceW(IntPtr dc,int size,StringBuilder name);
 [DllImport("gdi32.dll")] public static extern bool DeleteObject(IntPtr obj);
 [DllImport("gdi32.dll")] public static extern bool DeleteDC(IntPtr dc);
 public static string Verify(string name) {
  var dc=CreateCompatibleDC(IntPtr.Zero);
  var font=CreateFontW(-16,0,0,0,300,0,0,0,1,0,0,0,0,name);
  var old=SelectObject(dc,font);var actual=new StringBuilder(256);
  GetTextFaceW(dc,actual.Capacity,actual);
  SelectObject(dc,old);DeleteObject(font);DeleteDC(dc);return actual.ToString();
 }
}
'@
if ([FixtureFont]::AddFontResourceW($font[0].FullName) -lt 1) { throw 'Sarasa registration failed' }
$metadata=python "$PSScriptRoot/ci-font-name.py" $font[0].FullName | ConvertFrom-Json
if ($LASTEXITCODE) { throw 'Unable to read pinned font identity' }
$family=$metadata.family
Write-Host "Pinned font: $($font[0].Name), Windows family: $family"
$actual=[FixtureFont]::Verify($family)
if ($actual -ne $family) { throw "Sarasa font substituted: $actual" }
$evidence=[ordered]@{
    Runner=$env:RUNNER_NAME; ImageVersion=$env:ImageVersion
    Font=[ordered]@{Url=$fontUrl;ArchiveSHA256=$fontHash;File=$font[0].Name;SHA256=(Get-FileHash $font[0].FullName).Hash.ToLowerInvariant();Requested=$family;Actual=$actual;Names=$metadata.names}
}
if ($Shells) {
    $busybox=Join-Path $destination 'busybox.exe'
    $record=Get-Content "$root/build/interaction-busybox/busybox.json" -Raw | ConvertFrom-Json
    if ($record.Commit -ne '5f09fb446adf81d005f0aad9dc47eca19ac3b74c') { throw 'BusyBox source identity mismatch' }
    if ($record.Configuration -ne 'mingw64u_defconfig') { throw 'Expected Unicode Windows BusyBox for Chinese paths' }
    Copy-Item "$root/build/interaction-busybox/busybox.exe" $busybox
    if ((Get-FileHash $busybox).Hash.ToLowerInvariant() -ne $record.SHA256) { throw 'BusyBox hash mismatch' }
    $destination | Out-File $env:GITHUB_PATH -Append -Encoding utf8
    $evidence.BusyBox=$record
}
$evidence | ConvertTo-Json -Depth 5 | Set-Content "$destination/environment.json" -Encoding utf8
"NEMOTERM_TEST_FONT=$family" | Out-File $env:GITHUB_ENV -Append -Encoding utf8
