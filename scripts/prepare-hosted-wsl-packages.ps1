[CmdletBinding()]
param([Parameter(Mandatory)][ValidateSet('sixel','tmux-vim','vim','colour','pager','paste-quote')][string]$Suite)
$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_ENVIRONMENT -ne 'github-hosted' -or $env:RUNNER_OS -ne 'Windows') {
    throw 'WSL fixtures require a GitHub-hosted Windows runner.'
}
$dir = Join-Path $env:GITHUB_WORKSPACE 'build/wsl-provision'
New-Item -ItemType Directory -Force -Path $dir | Out-Null
& wsl.exe --distribution Ubuntu-24.04 --user root --cd $env:GITHUB_WORKSPACE --exec /bin/bash scripts/install-hosted-ubuntu-packages.sh $Suite 2>&1 | Tee-Object -FilePath (Join-Path $dir "$Suite.log")
if ($LASTEXITCODE -ne 0) { throw "WSL package preparation failed ($LASTEXITCODE); see build/wsl-provision/$Suite.log" }
