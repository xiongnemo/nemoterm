param([Parameter(Mandatory)][int]$TargetProcess,
      [Parameter(Mandatory)][long]$TargetWindow,
      [Parameter(Mandatory)][string]$Control,
      [Parameter(Mandatory)][string]$Report)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class GpuFixtureNative {
 [DllImport("user32.dll")] public static extern bool PostMessageW(IntPtr hwnd,uint message,IntPtr wp,IntPtr lp);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hwnd,out uint pid);
 [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr hwnd);
}
'@
$window=[IntPtr]$TargetWindow
[uint32]$owner=0
[GpuFixtureNative]::GetWindowThreadProcessId($window,[ref]$owner) | Out-Null
if ($owner -ne $TargetProcess) { throw 'Window is not owned by the fixture' }
$app=Get-Process -Id $TargetProcess
$scope=[System.Windows.Automation.TreeScope]::Descendants
function Wait-Value([scriptblock]$Read) {
 $deadline=[DateTime]::UtcNow.AddSeconds(12)
 do {
  if ($app.HasExited) { throw 'Fixture exited' }
  $value=& $Read
  if ($value) {return $value}
  Start-Sleep -Milliseconds 30
 } while ([DateTime]::UtcNow -lt $deadline)
 throw 'Owned GPU settings timed out'
}
function Find-Name($parent,[string]$name) {
 $condition=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty,$name)
 return $parent.FindFirst($scope,$condition)
}
function Snapshot($value) {
 # The Python peer tolerates incomplete reads. No global input or path discovery.
 [IO.File]::WriteAllText($Report,($value | ConvertTo-Json -Compress),(New-Object Text.UTF8Encoding($false)))
}
$condition=New-Object System.Windows.Automation.AndCondition(
 (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty,$TargetProcess)),
 (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ClassNameProperty,'PuTTYConfigBox')))
Snapshot @{ready=$true}
$last=0
try {
 $deadline=[DateTime]::UtcNow.AddMinutes(5)
 while ([DateTime]::UtcNow -lt $deadline) {
  $request=$null
  if (Test-Path -LiteralPath $Control) {try {$request=Get-Content -LiteralPath $Control -Raw | ConvertFrom-Json} catch {}}
  if ($request.stop) {break}
  if ($request.id -and $request.id -ne $last) {
   $last=$request.id
   $names=@('GDI (low memory)','OpenGL (GPU composition)','DirectX (GPU composition)')
   if ($request.mode -notin 0,1,2) {throw 'Invalid renderer'}
   if (![GpuFixtureNative]::PostMessageW($window,0x111,[IntPtr]0x50,[IntPtr]::Zero)) {throw 'Reconfigure failed'}
   $dialog=Wait-Value {[System.Windows.Automation.AutomationElement]::RootElement.FindFirst([System.Windows.Automation.TreeScope]::Children,$condition)}
   $node=Wait-Value {Find-Name $dialog 'Window'}
   $node.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern).Expand()
   $node=Wait-Value {Find-Name $dialog 'Rendering'}
   $node.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Select()
   $node=Wait-Value {Find-Name $dialog $names[$request.mode]}
   if ($node.Current.IsOffscreen -or !$dialog.Current.BoundingRectangle.Contains($node.Current.BoundingRectangle)) {throw 'Renderer control clipped'}
   $node.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Select()
   $handle=[IntPtr]$dialog.Current.NativeWindowHandle
   $button=Wait-Value {Find-Name $dialog 'Apply'}
   $button.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
   Wait-Value {![GpuFixtureNative]::IsWindow($handle)} | Out-Null
   Snapshot @{id=$last;applied=$request.mode}
  }
  if ($app.HasExited) {break}
  Start-Sleep -Milliseconds 20
 }
} catch {
 Snapshot @{id=$last;error=$_.Exception.Message;stack=$_.ScriptStackTrace}
 throw
}
