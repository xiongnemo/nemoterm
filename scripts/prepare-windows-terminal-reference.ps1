# Pinned Microsoft portable package; no AppX installation or host settings changes.
$ErrorActionPreference='Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_ENVIRONMENT -ne 'github-hosted') { throw 'Hosted Windows only' }
$dir=New-Item -ItemType Directory build/wt-reference
$tag='v1.25.3131.0'
$name='Microsoft.WindowsTerminal_1.25.3131.0_x64.zip'
$url="https://github.com/microsoft/terminal/releases/download/$tag/$name"
$zip=Join-Path $dir $name
Invoke-WebRequest -Uri $url -OutFile $zip
$sha=(Get-FileHash -LiteralPath $zip).Hash.ToLowerInvariant()
if ($sha -ne '273d6f1502eca1b5bd95c43f5d4d7ec72cc503df340102f8659717e5bead3437') { throw 'Windows Terminal release digest differs' }
Expand-Archive -LiteralPath $zip -DestinationPath "$dir/package"
$exes=@(Get-ChildItem "$dir/package" -Recurse -File -Filter WindowsTerminal.exe)
if ($exes.Count -ne 1) {throw 'Expected one Microsoft terminal frontend'}
$exe=$exes[0]
$blob='ec62a7a545b8032b95e408bee34d1120cfd65eb1'
$template=Join-Path $dir userDefaults.json
$response=Invoke-RestMethod "https://api.github.com/repos/microsoft/terminal/git/blobs/$blob"
[IO.File]::WriteAllBytes($template,[Convert]::FromBase64String($response.content))
if ((git hash-object --no-filters $template) -cne $blob) {throw 'Unexpected stock user settings'}
[IO.File]::WriteAllText((Join-Path $exe.DirectoryName '.portable'),'')
New-Item -ItemType Directory -Force (Join-Path $exe.DirectoryName 'settings') | Out-Null
$rec=[ordered]@{tag=$tag;archive=$url;archive_sha256=$sha;frontend_sha256=(Get-FileHash $exe.FullName).Hash.ToLowerInvariant();file_version=$exe.VersionInfo.FileVersion;user_defaults_blob=$blob;portable=$true}
$rec | ConvertTo-Json | Set-Content "$dir/identity.json" -Encoding utf8
"NEMOTERM_WT_REFERENCE=$($exe.FullName)" | Out-File $env:GITHUB_ENV -Append -Encoding utf8
