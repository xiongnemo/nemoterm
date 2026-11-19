param([Parameter(Mandatory)][int]$TargetProcess, [Parameter(Mandatory)][long]$TargetWindow,
      [Parameter(Mandatory)][ValidateSet('save','revoke','shell-cmd','wsl-pty-on','wsl-pty-off')][string]$Action)
$ErrorActionPreference='Stop'
if ($env:RUNNER_ENVIRONMENT -ne 'github-hosted' -or $env:GITHUB_ACTIONS -ne 'true') {throw 'Hosted Windows fixture only'}
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class OwnedSettingsWindow {
 [DllImport("user32")] public static extern bool PostMessageW(IntPtr hwnd,uint msg,IntPtr wp,IntPtr lp);
 [DllImport("user32")] public static extern uint GetWindowThreadProcessId(IntPtr hwnd,out uint pid);
 [DllImport("user32")] public static extern IntPtr SendMessageW(IntPtr hwnd,uint msg,IntPtr wp,IntPtr lp);
 [DllImport("user32")] public static extern int GetDlgCtrlID(IntPtr hwnd);
 [DllImport("user32")] public static extern IntPtr GetParent(IntPtr hwnd);
 [DllImport("user32")] public static extern bool IsWindow(IntPtr hwnd);
}
"@
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
$stage='opening dialog'
$target=[IntPtr]$TargetWindow;[uint32]$owner=0
if (![OwnedSettingsWindow]::GetWindowThreadProcessId($target,[ref]$owner) -or $owner -ne $TargetProcess) {throw 'Wrong terminal owner'}
function Wait-ForValue([scriptblock]$Read) {
    $until=[DateTime]::UtcNow.AddSeconds(12)
    do {$item=& $Read;if ($item) {return $item};Start-Sleep -Milliseconds 25} while ([DateTime]::UtcNow -lt $until)
    if ($dialog) {
        $all=$dialog.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
        Write-Host ('Owned controls: '+(($all | ForEach-Object {$_.Current.Name} | Where-Object {$_}) -join ' | '))
    }
    throw "Timed out while $stage"
}
function Find-Named($element,[string]$label) {
    $query=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty,$label)
    return $element.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$query)
}
if (![OwnedSettingsWindow]::PostMessageW($target,0x111,[IntPtr]0x50,[IntPtr]::Zero)) {throw 'Unable to open settings'}
$owned=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty,$TargetProcess)
$class=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ClassNameProperty,'PuTTYConfigBox')
$dialog=Wait-ForValue {
    foreach ($entry in [System.Windows.Automation.AutomationElement]::RootElement.FindAll([System.Windows.Automation.TreeScope]::Children,$owned)) {
        $found=$entry.FindFirst([System.Windows.Automation.TreeScope]::Subtree,$class);if ($found) {return $found}
    }
}
if ($Action -eq 'shell-cmd' -or $Action -like 'wsl-pty-*') {
    $stage='selecting startup shell'
    $profile=Wait-ForValue {Find-Named $dialog 'Profile'}
    $expand=$profile.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern)
    if ($expand.Current.ExpandCollapseState -eq 'Collapsed') {$expand.Expand()}
    $node=Wait-ForValue {Find-Named $profile 'Shell'}
    $node.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Select()
    if ($Action -like 'wsl-pty-*') {
        $stage='changing WSL transport'
        $option=Wait-ForValue {Find-Named $dialog 'Use Linux PTY for x64 WSL sessions'}
        if ($option.Current.IsOffscreen -or !$dialog.Current.BoundingRectangle.Contains($option.Current.BoundingRectangle)) {throw 'WSL PTY control is clipped'}
        $toggle=$option.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern)
        $expected=if ($Action -eq 'wsl-pty-on') {'On'} else {'Off'}
        if ($toggle.Current.ToggleState.ToString() -eq $expected) {throw 'Unexpected initial WSL transport'}
        $toggle.Toggle(); Wait-ForValue {$toggle.Current.ToggleState.ToString() -eq $expected} | Out-Null
    } else {
        $kind=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::ComboBox)
        $combo=Wait-ForValue {$dialog.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$kind)}
        $h=[IntPtr]$combo.Current.NativeWindowHandle
        if ([OwnedSettingsWindow]::SendMessageW($h,0x147,[IntPtr]::Zero,[IntPtr]::Zero).ToInt32() -ne 2) {throw 'Initial shell is not Windows PowerShell'}
        if ([OwnedSettingsWindow]::SendMessageW($h,0x14e,[IntPtr]6,[IntPtr]::Zero).ToInt32() -ne 6) {throw 'Could not select Command Prompt'}
        $id=[OwnedSettingsWindow]::GetDlgCtrlID($h)
        [OwnedSettingsWindow]::SendMessageW([OwnedSettingsWindow]::GetParent($h),0x111,[IntPtr]($id -bor 0x10000),$h) | Out-Null
    }
} else {
    foreach ($label in 'Window','Appearance') {
        $stage="expanding $label"; Write-Host $stage
        $node=Wait-ForValue {Find-Named $dialog $label};$expand=$node.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern)
        if ($expand.Current.ExpandCollapseState -eq 'Collapsed') {$expand.Expand()}
    }
    $stage='selecting Font access';Write-Host $stage
    $page=Wait-ForValue {Find-Named $dialog 'Font access'};$page.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Select()
    foreach ($label in 'Allow programs to query the font family','Allow programs to change the font family') {
        $stage="reading $label"; Write-Host $stage
        $node=Wait-ForValue {Find-Named $dialog $label}
        if ($node.Current.IsOffscreen -or !$dialog.Current.BoundingRectangle.Contains($node.Current.BoundingRectangle)) {throw "Clipped: $label"}
        $toggle=$node.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern);if ($toggle.Current.ToggleState -ne 'On') {throw "Unexpected starting permission: $label"}
        if ($Action -eq 'revoke' -and $label -like '*change*') {$toggle.Toggle()}
    }
}
$stage='saving settings';Write-Host $stage
$handle=[IntPtr]$dialog.Current.NativeWindowHandle
(Find-Named $dialog 'Save and Apply').GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
Wait-ForValue {![OwnedSettingsWindow]::IsWindow($handle)} | Out-Null
