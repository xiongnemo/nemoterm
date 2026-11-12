# Exercise the real startup settings dialog, save/load and local-session launch.
# UI Automation is scoped to a new process; no global mouse or keyboard input.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class ShellSettingsNative {
    [DllImport("user32.dll")] public static extern IntPtr SendMessageW(IntPtr hwnd, uint msg, IntPtr wp, IntPtr lp);
    [DllImport("user32.dll")] public static extern IntPtr GetParent(IntPtr hwnd);
    [DllImport("user32.dll")] public static extern int GetDlgCtrlID(IntPtr hwnd);
}
'@
$root = Split-Path $PSScriptRoot -Parent
$exe = Join-Path $root 'dist/nemoterm.exe'
if ($env:NEMOTERM_TEST_EXE) { $exe = $env:NEMOTERM_TEST_EXE }
$python = (Get-Command python.exe -ErrorAction Stop).Source
$fixtureProfile = 'settings-test-' + [Guid]::NewGuid().ToString('N')
$profilePath = 'HKCU:\Software\Nemo\Nemoterm\Sessions\' + $fixtureProfile
$directory = Join-Path ([IO.Path]::GetTempPath()) $fixtureProfile
New-Item -ItemType Directory -Path $directory | Out-Null
$report = Join-Path $directory 'report.json'
$control = Join-Path $directory 'control.json'
$app = $null
$scope = [System.Windows.Automation.TreeScope]::Descendants

function Wait-Value([scriptblock]$Read) {
    $deadline = [DateTime]::UtcNow.AddSeconds(8)
    do {
        $value = & $Read
        if ($value) { return $value }
        Start-Sleep -Milliseconds 30
    } while ([DateTime]::UtcNow -lt $deadline)
    throw 'Timed out waiting for owned settings fixture'
}
function Find-Name($parent, [string]$name, [string]$class = '') {
    $condition = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, $name)
    if ($class) {
        $condition = New-Object System.Windows.Automation.AndCondition($condition,
            (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ClassNameProperty, $class)))
    }
    return $parent.FindFirst($scope, $condition)
}
function Dialog($process) {
    $condition = New-Object System.Windows.Automation.AndCondition(
        (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, $process.Id)),
        (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ClassNameProperty, 'PuTTYConfigBox')))
    return Wait-Value {
        if ($process.HasExited) { throw "Settings exited before opening: $($process.ExitCode)" }
        [System.Windows.Automation.AutomationElement]::RootElement.FindFirst([System.Windows.Automation.TreeScope]::Children, $condition)
    }
}
function Select-Node($dialog, [string]$name) {
    $node = Wait-Value { Find-Name $dialog $name }
    $node.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Select()
    Wait-Value { $node.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Current.IsSelected } | Out-Null
    return $node
}
function Invoke-Button($dialog, [string]$name) {
    $button = Wait-Value { Find-Name $dialog $name }
    $button.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
}
function Write-Control($value) {
    $temporary = $control + '.tmp'
    [IO.File]::WriteAllText($temporary, ($value | ConvertTo-Json -Compress), (New-Object Text.UTF8Encoding($false)))
    Move-Item -LiteralPath $temporary -Destination $control -Force
}
try {
    New-Item -Path $profilePath -Force | Out-Null
    New-ItemProperty -Path $profilePath -Name WarnOnClose -Value 0 -PropertyType DWord | Out-Null
    # This is the visible GUI under test, not a background helper. Hidden
    # startup also hides the modal dialog from the UI Automation tree.
    $app = Start-Process -FilePath $exe -ArgumentList @('-load', $fixtureProfile, '--settings') -PassThru
    $dialog = Dialog $app
    foreach ($name in @('Terminal', 'Keyboard')) {
        $node = Wait-Value { Find-Name $dialog $name }
        $node.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern).Expand()
    }
    Select-Node $dialog 'Extended' | Out-Null
    Select-Node $dialog 'All keys' | Out-Null
    Select-Node $dialog 'CSI-u' | Out-Null
    $win32Label = 'Preserve Windows key events (experimental)'
    $win32 = Wait-Value { Find-Name $dialog $win32Label }
    $win32Toggle = $win32.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern)
    if ($win32Toggle.Current.ToggleState -ne [System.Windows.Automation.ToggleState]::Off) { throw 'Experimental Win32 input was enabled by default' }
    $win32Toggle.Toggle()
    # All visible controls must remain within the fixed-height dialog.
    $bounds = $dialog.Current.BoundingRectangle
    if ($win32.Current.IsOffscreen -or !$bounds.Contains($win32.Current.BoundingRectangle)) { throw 'Win32 input option clipped' }
    foreach ($name in @('Off', 'Compatible', 'Modified keys', 'All keys', 'xterm (27~)', 'CSI-u')) {
        $node = Find-Name $dialog $name
        if (!$node -or $node.Current.IsOffscreen -or !$bounds.Contains($node.Current.BoundingRectangle)) {
            throw "Clipped or missing setting: $name"
        }
        $selected = $node.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Current.IsSelected
        if ($selected -ne ($name -in @('All keys', 'CSI-u'))) { throw "Incorrect radio selection: $name" }
    }
    python "$PSScriptRoot/settings_capture.py" $app.Id $dialog.Current.NativeWindowHandle
    if ($LASTEXITCODE) { throw 'Owned settings capture failed' }
    $windowNode = Find-Name $dialog 'Window'
    $windowNode.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern).Expand()
    Select-Node $dialog 'Window' | Out-Null
    $reflowLabel = 'Reflow main-screen text when columns change'
    $reflow = Wait-Value { Find-Name $dialog $reflowLabel }
    if ($reflow.Current.IsOffscreen -or !$bounds.Contains($reflow.Current.BoundingRectangle)) { throw 'Reflow option clipped' }
    $toggle = $reflow.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern)
    if ($toggle.Current.ToggleState -ne [System.Windows.Automation.ToggleState]::On) { throw 'Reflow was not enabled by default' }
    $toggle.Toggle()
    Select-Node $dialog 'Selection' | Out-Null
    $copyOnly = Find-Name $dialog 'Copy only'
    if (!$copyOnly.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Current.IsSelected) {
        throw 'Copy only was not the default'
    }
    Select-Node $dialog 'Copy and paste' | Out-Null
    Select-Node $dialog 'Session' | Out-Null
    $chooseShell = Wait-Value { Find-Name $dialog 'Choose shell on startup' }
    if ($chooseShell.Current.IsOffscreen -or !$bounds.Contains($chooseShell.Current.BoundingRectangle)) { throw 'Shell startup option clipped' }
    $chooseShell.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern).Toggle()
    $shellCombo = $dialog.FindFirst($scope, (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::ComboBox)))
    if (!$shellCombo -or $shellCombo.Current.IsOffscreen -or !$bounds.Contains($shellCombo.Current.BoundingRectangle)) { throw 'Shell selector clipped or missing' }
    $shellHandle = [IntPtr]$shellCombo.Current.NativeWindowHandle
    [ShellSettingsNative]::SendMessageW($shellHandle, 0x14E, [IntPtr]4, [IntPtr]::Zero) | Out-Null
    $fixtureShellControlId = [ShellSettingsNative]::GetDlgCtrlID($shellHandle)
    [ShellSettingsNative]::SendMessageW([ShellSettingsNative]::GetParent($shellHandle), 0x111, [IntPtr]($fixtureShellControlId -bor (1 -shl 16)), $shellHandle) | Out-Null
    python "$PSScriptRoot/settings_capture.py" $app.Id $dialog.Current.NativeWindowHandle shell-settings.png
    if ($LASTEXITCODE) { throw 'Shell settings capture failed' }
    $saved = Wait-Value { Find-Name $dialog 'Saved Sessions' 'Edit' }
    $saved.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).SetValue($fixtureProfile)
    Invoke-Button $dialog 'Save'
    if ((Get-ItemProperty -LiteralPath $profilePath).NemoChooseShell -ne 1) { throw 'Shell startup preference was not saved' }
    if ((Get-ItemProperty -LiteralPath $profilePath).NemoShell -ne 'git-bash') { throw 'Selected default shell was not saved' }
    $values = Get-ItemProperty -LiteralPath $profilePath
    if ($values.NemoModifyOtherKeys -ne 3 -or $values.NemoFormatOtherKeys -ne 1 -or $values.RightClickCopyAndPaste -ne 1 -or $values.NemoReflow -ne 0 -or $values.NemoWin32Input -ne 1) { throw 'Settings were not saved' }
    Invoke-Button $dialog 'Cancel'
    if (!$app.WaitForExit(3000) -or $app.ExitCode -ne 0) { throw 'Settings cancel failed' }

    $app = Start-Process -FilePath $exe -ArgumentList @('-load', $fixtureProfile) -PassThru
    $dialog = Dialog $app
    Invoke-Button $dialog 'Cancel'
    if (!$app.WaitForExit(3000) -or $app.ExitCode -ne 0) { throw 'Automatic startup shell chooser failed' }

    # Windows PowerShell 5 does not interpret `e; construct ESC explicitly.
    Write-Control @{phase='settings-launch';sequence=([char]27 + '[?4m' + [char]27 + '[?4g')}
    $fixture = Join-Path $PSScriptRoot 'mouse_fixture.py'
    $arguments = @('-load', $fixtureProfile, '--settings', '-e', ('"'+$python+'"'), ('"'+$fixture+'"'), ('"'+$report+'"'), ('"'+$control+'"'))
    $app = Start-Process -FilePath $exe -ArgumentList $arguments -PassThru
    $dialog = Dialog $app
    $reloadedShell = Wait-Value { Find-Name $dialog 'Choose shell on startup' }
    if ($reloadedShell.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern).Current.ToggleState -ne [System.Windows.Automation.ToggleState]::On) { throw 'Shell startup preference did not reload' }
    $shellCombo = $dialog.FindFirst($scope, (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::ComboBox)))
    if ([ShellSettingsNative]::SendMessageW([IntPtr]$shellCombo.Current.NativeWindowHandle, 0x147, [IntPtr]::Zero, [IntPtr]::Zero).ToInt32() -ne 4) { throw 'Selected default shell did not reload' }
    if (Find-Name $dialog 'Connection') { throw 'Local terminal exposed network settings' }
    foreach ($name in @('Terminal', 'Keyboard')) {
        $node = Wait-Value { Find-Name $dialog $name }
        $node.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern).Expand()
    }
    Select-Node $dialog 'Extended' | Out-Null
    $reloadedWin32 = Wait-Value { Find-Name $dialog $win32Label }
    if ($reloadedWin32.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern).Current.ToggleState -ne [System.Windows.Automation.ToggleState]::On) { throw 'Win32 preference did not reload' }
    Select-Node $dialog 'Window' | Out-Null
    $reloaded = Wait-Value { Find-Name $dialog $reflowLabel }
    if ($reloaded.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern).Current.ToggleState -ne [System.Windows.Automation.ToggleState]::Off) { throw 'Reflow preference did not reload' }
    Invoke-Button $dialog 'Open'
    $observed = Wait-Value {
        if (Test-Path -LiteralPath $report) {
            $value = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
            if ($value.error) { throw $value.error }
            if ($value.hex -eq '1b5b3e343b336d1b5b3e343b3166') { $value }
        }
    }
    $evidence = @{executable_sha256=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLower();
        saved_level=3;saved_format=1;copy_only_default=$true;saved_copy_and_paste=$true;
        reflow_default=$true;saved_reflow=$false;win32_default=$false;saved_win32=$true;cancel_exit=0;local_launch=$true;
        saved_shell='git-bash';saved_choose_shell=$true;explicit_command_overrides_shell=$true;query=$observed}
    [IO.File]::WriteAllText((Join-Path $root 'research/settings-window-observed.json'),
        ($evidence | ConvertTo-Json -Depth 5), (New-Object Text.UTF8Encoding($false)))
    Write-Control @{stop=$true}
    if (!$app.WaitForExit(5000) -or $app.ExitCode -ne 0) { throw 'Fixture shutdown failed' }
    Write-Output 'Native settings save/load, visible controls and local launch passed'
} catch {
    Write-Output $_.ScriptStackTrace
    if ($app -and $app.HasExited) { Write-Output "Owned process exit: $($app.ExitCode)" }
    if ($app -and !$app.HasExited) {
        $owner = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, $app.Id)
        $windows = [System.Windows.Automation.AutomationElement]::RootElement.FindAll([System.Windows.Automation.TreeScope]::Children, $owner)
        foreach ($window in $windows) {
            Write-Output ($window.Current | Select-Object Name, ClassName | ConvertTo-Json -Compress)
            $window.FindAll($scope, [System.Windows.Automation.Condition]::TrueCondition) | ForEach-Object { Write-Output $_.Current.Name }
        }
    }
    throw
} finally {
    if ($app -and !$app.HasExited) { $app.Kill(); $app.WaitForExit() }
    if (Test-Path -LiteralPath $profilePath) { Remove-Item -LiteralPath $profilePath }
    # Delete only these known fixture files, then the empty owned directory.
    foreach ($name in @('report.json', 'report.tmp', 'control.json', 'control.json.tmp')) {
        $path = Join-Path $directory $name
        if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path }
    }
    Remove-Item -LiteralPath $directory
}
