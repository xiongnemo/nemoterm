param(
 [Parameter(Mandatory=$true)][int]$ProcessId,
 [Parameter(Mandatory=$true)][long]$DialogHwnd,
 [Parameter(Mandatory=$true)][int]$ExpectedDpi,
 [Parameter(Mandatory=$true)][string]$Prefix
)
# Inspects only the dialog opened by dpi_window_smoke.py on the hosted runner.
$ErrorActionPreference='Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_ENVIRONMENT -ne 'github-hosted') {throw 'Hosted runner only'}
if ($Prefix -notmatch '^[a-z0-9-]+$') {throw 'Invalid evidence prefix'}
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class DpiDialogNative {
 [DllImport("user32.dll")] public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr value);
 [DllImport("user32.dll")] public static extern uint GetDpiForWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h,out uint pid);
 [DllImport("user32.dll")] public static extern bool PostMessageW(IntPtr h,uint m,IntPtr w,IntPtr l);
}
'@
# UIA bounding rectangles are physical screen coordinates. Keep the same
# client DPI context as the existing settings CI; screenshots use a separate
# PMv2-aware Python process and actual DPI comes from the target HWND.
[uint32]$owner=0
[DpiDialogNative]::GetWindowThreadProcessId([IntPtr]$DialogHwnd,[ref]$owner) | Out-Null
if ($owner -ne $ProcessId) {throw 'Dialog PID mismatch'}
$owned=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty,$ProcessId)
$byHandle=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NativeWindowHandleProperty,[int]$DialogHwnd)
$dialog=$null
foreach ($window in [System.Windows.Automation.AutomationElement]::RootElement.FindAll([System.Windows.Automation.TreeScope]::Children,$owned)) {
 $dialog=$window.FindFirst([System.Windows.Automation.TreeScope]::Subtree,$byHandle)
 if ($dialog) {break}
}
if (!$dialog) {throw 'Owned settings dialog absent from the UIA tree'}
if ($dialog.Current.ClassName -ne 'PuTTYConfigBox') {throw 'Unexpected dialog class'}
$scope=[System.Windows.Automation.TreeScope]::Descendants
function Find($parent,[string]$name) {
 $condition=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty,$name)
 $until=[DateTime]::UtcNow.AddSeconds(8)
 do {
  $v=$parent.FindFirst($scope,$condition)
  if ($v) {return $v}
  Start-Sleep -Milliseconds 20
 } while ([DateTime]::UtcNow -lt $until)
 throw "Missing control: $name"
}
function Select-Page([string[]]$path) {
 $parent=$dialog
 foreach ($name in $path) {
  $node=Find $parent $name
  $node.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Select()
  if ($name -ne $path[-1]) {$node.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern).Expand()}
  $parent=$node
 }
}
function Coordinates($r) {return @($r.Left,$r.Top,$r.Width,$r.Height)}
$root=Split-Path $PSScriptRoot -Parent
$result=@{completed=$false;expected_dpi=$ExpectedDpi;hwnd=$DialogHwnd;pages=@();ui_language='en';
 powershell=$PSVersionTable.PSVersion.ToString();client_assembly=[System.Windows.Automation.AutomationElement].Assembly.FullName}
$pages=@(
 @{id='profile';path=@('Profile');labels=@('New profile name','Add','Edit','Delete')},
 @{id='shell';path=@('Profile','Shell');labels=@('Choose shell on startup','Command (select Custom above):','Starting directory (blank inherits launcher):')},
 @{id='bell';path=@('Terminal','Bell');labels=@('Play a custom sound file','Browse...','Raise window on bell without taking keyboard focus','Ring when the application resets the terminal')},
 @{id='bell-overload';path=@('Terminal','Bell','Overload');labels=@('Bell is temporarily disabled when over-used','Seconds of silence required')},
 @{id='bindings';path=@('Window','Bindings');labels=@('Reset bindings','Rectangle modifier')},
 @{id='font';path=@('Window','Bindings','Font');labels=@('Increase key','Decrease key','Reset key')},
 @{id='tabs';path=@('Window','Tabs');labels=@('Top','Bottom','Left','Right','Preview terminal on hover')}
)
try {
 python "$PSScriptRoot/settings_capture.py" $ProcessId $DialogHwnd "$Prefix-initial.png"
 if ($LASTEXITCODE) {throw 'Initial dialog capture failed'}
 foreach ($page in $pages) {
  Select-Page $page.path
  $actual=[DpiDialogNative]::GetDpiForWindow([IntPtr]$DialogHwnd)
  if ($actual -ne $ExpectedDpi) {throw "Actual dialog DPI $actual differs from $ExpectedDpi"}
  $save=Find $dialog 'Save and Apply';$cancel=Find $dialog 'Cancel'
  $bounds=$dialog.Current.BoundingRectangle
  $observed=@{id=$page.id;actual_dpi=$actual;window=(Coordinates $bounds);controls=@();screenshot="$Prefix-$($page.id).png"}
  $result.pages+=,$observed
  foreach ($label in $page.labels+@('Save and Apply','Cancel')) {
   $node=Find $dialog $label;$r=$node.Current.BoundingRectangle
   $observed.controls+=,@{label=$label;rect=(Coordinates $r);offscreen=$node.Current.IsOffscreen}
   if ($node.Current.IsOffscreen -or !$bounds.Contains($r)) {throw "Clipped control at $ExpectedDpi DPI: $label"}
   if ($label -notin @('Save and Apply','Cancel') -and $r.Bottom -gt $save.Current.BoundingRectangle.Top-2) {throw "Footer overlap: $label"}
  }
  python "$PSScriptRoot/settings_capture.py" $ProcessId $DialogHwnd $observed.screenshot
  if ($LASTEXITCODE) {throw 'Dialog capture failed'}
 }
 $result.completed=$true
} catch {
 $result.error=$_.ToString()
 $result.visible_tree=@($dialog.FindAll($scope,[System.Windows.Automation.Condition]::TrueCondition) | ForEach-Object {
  @{name=$_.Current.Name;class=$_.Current.ClassName;control=$_.Current.ControlType.ProgrammaticName;offscreen=$_.Current.IsOffscreen;rect=(Coordinates $_.Current.BoundingRectangle)}
 })
 python "$PSScriptRoot/settings_capture.py" $ProcessId $DialogHwnd "$Prefix-failure.png"
 throw
} finally {
 $result | ConvertTo-Json -Depth 12 | Set-Content "$root/research/$Prefix-settings.json" -Encoding UTF8
 # Post Cancel even on failure, so a failed assertion cannot strand its owner.
 [DpiDialogNative]::PostMessageW([IntPtr]$DialogHwnd,0x111,[IntPtr]2,[IntPtr]0) | Out-Null
}
