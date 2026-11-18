param([Parameter(Mandatory)][int]$TargetProcess, [Parameter(Mandatory)][long]$TargetWindow,
      [Parameter(Mandatory)][ValidateSet('save','revoke')][string]$Action)
$ErrorActionPreference='Stop'
if ($env:RUNNER_ENVIRONMENT -ne 'github-hosted' -or $env:GITHUB_ACTIONS -ne 'true') {throw 'Hosted Windows fixture only'}
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class FontSettingsWindow {
 [DllImport("user32")] public static extern bool PostMessageW(IntPtr hwnd,uint msg,IntPtr wp,IntPtr lp);
 [DllImport("user32")] public static extern uint GetWindowThreadProcessId(IntPtr hwnd,out uint pid);
 [DllImport("user32")] public static extern bool IsWindow(IntPtr hwnd);
}
"@
$target=[IntPtr]$TargetWindow;[uint32]$owner=0
if (![FontSettingsWindow]::GetWindowThreadProcessId($target,[ref]$owner) -or $owner -ne $TargetProcess) {throw 'Wrong terminal owner'}
function Wait-ForValue([scriptblock]$Read) {
    $until=[DateTime]::UtcNow.AddSeconds(12)
    do {$item=& $Read;if ($item) {return $item};Start-Sleep -Milliseconds 25} while ([DateTime]::UtcNow -lt $until)
    throw 'Timed out waiting for owned font settings'
}
function Find-Named($element,[string]$label) {
    $query=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty,$label)
    return $element.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$query)
}
if (![FontSettingsWindow]::PostMessageW($target,0x111,[IntPtr]0x50,[IntPtr]::Zero)) {throw 'Unable to open settings'}
$owned=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty,$TargetProcess)
$class=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ClassNameProperty,'PuTTYConfigBox')
$dialog=Wait-ForValue {
    foreach ($entry in [System.Windows.Automation.AutomationElement]::RootElement.FindAll([System.Windows.Automation.TreeScope]::Children,$owned)) {
        $found=$entry.FindFirst([System.Windows.Automation.TreeScope]::Subtree,$class);if ($found) {return $found}
    }
}
foreach ($label in 'Window','Appearance') {
    $node=Wait-ForValue {Find-Named $dialog $label};$expand=$node.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern)
    if ($expand.Current.ExpandCollapseState -eq 'Collapsed') {$expand.Expand()}
}
$page=Wait-ForValue {Find-Named $dialog 'Font access'};$page.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Select()
foreach ($label in 'Allow programs to query the font family','Allow programs to change the font family') {
    $node=Wait-ForValue {Find-Named $dialog $label}
    if ($node.Current.IsOffscreen -or !$dialog.Current.BoundingRectangle.Contains($node.Current.BoundingRectangle)) {throw "Clipped: $label"}
    $toggle=$node.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern);if ($toggle.Current.ToggleState -ne 'On') {throw "Unexpected starting permission: $label"}
    if ($Action -eq 'revoke' -and $label -like '*change*') {$toggle.Toggle()}
}
$handle=[IntPtr]$dialog.Current.NativeWindowHandle
(Find-Named $dialog 'Save and Apply').GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
Wait-ForValue {![FontSettingsWindow]::IsWindow($handle)} | Out-Null
