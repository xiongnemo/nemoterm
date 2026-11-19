param([Parameter(Mandatory)][string]$Commit,[Parameter(Mandatory)][string]$Run,
      [ValidateSet('mingw','single')][string]$Product='mingw')
$ErrorActionPreference='Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_ENVIRONMENT -ne 'github-hosted' -or $Commit -cnotmatch '^[0-9a-f]{40}$' -or $Run -notmatch '^[1-9][0-9]*$') {throw 'Expected a hosted runner and a source run identity'}
$work=Join-Path $PWD 'build/profile-dump';$out=New-Item -ItemType Directory -Force "$work/report"; $null=New-Item -ItemType Directory -Force "$work/symbols"
$src=gh run view $Run --json headSha,workflowName,jobs | ConvertFrom-Json
if ($LASTEXITCODE -or $src.headSha -ne $Commit -or $src.workflowName -ne 'Test and build') {throw 'Original test run and commit must match'}
if ($Product -eq 'single') {
    $job='single / single-exe'; $observed="single-exe-evidence-$Commit"; $binary="unverified-single-exe-x64-$Commit"
    $originalResearch="$work/original/build/single-exe-check/research"; $receipt="$originalResearch/tabs-profiles-observed.json"
} else {
    $job='Windows x64 tests and portable build'; $observed="test-results-windows-$Commit"; $binary="unverified-mingw-runtime-$Commit"
    $originalResearch="$work/original/research"; $receipt="$work/original/test-results/tabs-profiles-observed.json"
}
if (@($src.jobs|Where-Object {$_.name -ceq $job -and $_.conclusion -eq 'failure'}).Count -ne 1) {throw "Expected exactly one failed $job"}
gh run download $Run --name $observed --dir "$work/original"
if ($LASTEXITCODE) {throw 'Missing original failed observation'}
gh run download $Run --name $binary --dir "$work/runtime"
if ($LASTEXITCODE) {throw 'Missing exact failed runtime'}
$r=Get-Content -Raw -LiteralPath $receipt | ConvertFrom-Json
if ($r.completed -ne $false -or $r.phase -ne 'close-host' -or !$r.close_request.posted -or $r.failure_dump.exit_code -ne 0) {throw 'No close timeout with a captured dump'}
$dump=@(Get-ChildItem -LiteralPath $originalResearch -Directory -Filter 'profiles-failure-*' | ForEach-Object {Get-ChildItem -LiteralPath $_.FullName -File -Filter 'failure.dmp'} | Where-Object {(Get-FileHash -LiteralPath $_.FullName).Hash -eq $r.failure_dump.dump.sha256})
$exe=Get-Item -LiteralPath "$work/runtime/nemoterm.exe"; $imageHash=(Get-FileHash -LiteralPath $exe.FullName).Hash.ToLowerInvariant()
if ($dump.Count -ne 1 -or $dump[0].Length -ne $r.failure_dump.dump.bytes -or $r.executable_sha256 -ne $imageHash -or $r.failure_dump.pid -ne $r.close_request.pid -or $r.process_before_cleanup.pid -ne $r.close_request.pid) {throw 'Dump and image must match the original failure receipt'}
$tid=[uint32]$r.close_request.thread
if (!$tid -or @($r.process_before_cleanup.threads.threads | Where-Object {$_.tid -eq $tid}).Count -ne 1) {throw 'No unique thread of the failing host window'}
$identity=[ordered]@{source_commit=$Commit; source_run=$Run; source_job=$job; observation_artifact=$observed; binary_artifact=$binary; analyzer_commit=$env:GITHUB_SHA; executable_sha256=$imageHash; executable_bytes=$exe.Length; dump_sha256=$r.failure_dump.dump.sha256; dump_bytes=$dump[0].Length; ui_tid=$tid; historical_pid=$r.close_request.pid; target_launched=$false; target_attached=$false}
$identity | ConvertTo-Json | Set-Content "$out/identity.json"
$cdb="${env:ProgramFiles(x86)}/Windows Kits/10/Debuggers/x64/cdb.exe"
if (!(Test-Path -LiteralPath $cdb)) {
    # Microsoft Windows SDK 10.0.26100.7705 installer, pinned by winget's manifest.
    $url='https://download.microsoft.com/download/f4b30f2a-4fc3-430e-9b03-c842b5f5f9f1/KIT_BUNDLE_WINDOWSSDK_MEDIACREATION/winsdksetup.exe'
    $installer="$work/winsdksetup.exe"; Invoke-WebRequest -Uri $url -OutFile $installer
    if ((Get-FileHash $installer).Hash -ne '6FA0FA27DB77A909F5ECB35183CB26A969A6775936780936FE239E4F9C66B458') {throw 'Unexpected SDK installer'}
    $p=Start-Process -FilePath $installer -ArgumentList '/quiet','/norestart','/features','OptionId.WindowsDesktopDebuggers' -WindowStyle Hidden -Wait -PassThru
    if ($p.ExitCode -notin @(0,3010) -or !(Test-Path -LiteralPath $cdb)) {throw "SDK debugger install failed ($($p.ExitCode))"}
}
$identity.debugger_sha256=(Get-FileHash -LiteralPath $cdb).Hash.ToLowerInvariant(); $identity.debugger_version=(Get-Item $cdb).VersionInfo.FileVersion
$identity | ConvertTo-Json | Set-Content "$out/identity.json"
$tidHex=$tid.ToString('x');$commands=".symopt+ 0x400; .reload; ~~[$tidHex]s; .echo BEGIN_WINDOW_THREAD; kn 60; .echo END_WINDOW_THREAD; ~* kn 35; lmvt; q"
& $cdb -sins -noshell -z $dump[0].FullName -i "$work/runtime" -y "srv*$work/symbols*https://msdl.microsoft.com/download/symbols" -c $commands 2>&1 | Out-File -Encoding utf8 "$out/stacks.txt"
$exitCode=$LASTEXITCODE;$log=Get-Content -Raw "$out/stacks.txt";$match=[regex]::Match($log,'(?ms)^BEGIN_WINDOW_THREAD\s*\r?\n(?<stack>.*?)^END_WINDOW_THREAD\s*$')
if ($exitCode -or !$match.Success) {throw "No debugger stack for the selected window thread (exit $exitCode)"}
$stack=$match.Groups['stack'].Value; $stack | Set-Content "$out/ui-thread.txt"
if ($stack -notmatch '(?im)^\s*[0-9a-f]+\s+.*\bnemoterm(?:!|\+)' -or $stack -notmatch '(?im)^\s*[0-9a-f]+\s+.*\bntdll(?:!|\+)') {throw 'Unwind did not reach the frontend; inspect the original transcript'}
