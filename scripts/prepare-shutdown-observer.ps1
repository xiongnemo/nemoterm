param([string]$Destination = 'build/shutdown-python')
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$venv = [IO.Path]::GetFullPath($Destination, $repo)
& python -m venv $venv
if ($LASTEXITCODE) { throw 'Could not create isolated shutdown observer environment' }
$interpreter = Join-Path $venv 'Scripts/python.exe'
& $interpreter -m pip install --disable-pip-version-check -r "$repo/tests/requirements-shutdown.txt"
if ($LASTEXITCODE) { throw 'Could not install pinned shutdown observer' }
& $interpreter -c "import frida; assert frida.__version__ == '17.23.3'; print('Shutdown observer:', frida.__version__)"
if ($LASTEXITCODE) { throw 'Shutdown observer version mismatch' }
$env:NEMOTERM_SHUTDOWN_PYTHON = $interpreter
if ($env:GITHUB_ENV) {
    "NEMOTERM_SHUTDOWN_PYTHON=$interpreter" | Out-File $env:GITHUB_ENV -Append -Encoding utf8
}
