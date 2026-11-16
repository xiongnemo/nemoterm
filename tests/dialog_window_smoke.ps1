param([switch]$TabHost)
# Only launched on a disposable CI desktop; all input targets this owned app.
$ErrorActionPreference='Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class ModalNative {
 [DllImport("user32.dll")] public static extern bool PostMessageW(IntPtr h,uint m,IntPtr w,IntPtr l);
 [DllImport("user32.dll")] public static extern bool IsWindowEnabled(IntPtr h);
 [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern IntPtr GetWindow(IntPtr h,uint command);
}
'@
$root=Split-Path $PSScriptRoot -Parent
$exe=if ($env:NEMOTERM_TEST_EXE) {$env:NEMOTERM_TEST_EXE} else {Join-Path $root 'dist/nemoterm.exe'}
$python=(Get-Command python.exe).Source
$name='modal-test-'+[Guid]::NewGuid().ToString('N')
$key='HKCU:\Software\Nemo\Nemoterm\Sessions\'+$name
$directory=Join-Path ([IO.Path]::GetTempPath()) $name
New-Item -ItemType Directory $directory | Out-Null
$report=Join-Path $directory 'report.json';$control=Join-Path $directory 'control.json'
$scope=[System.Windows.Automation.TreeScope]::Descendants
$app=$null;$checks=[Collections.Generic.List[string]]::new()
function Wait-Value([scriptblock]$read) {
 $until=[DateTime]::UtcNow.AddSeconds(15)
 do { $v=& $read; if ($v) {return $v}; Start-Sleep -Milliseconds 30 } while ([DateTime]::UtcNow -lt $until)
 throw 'Owned dialog fixture timed out'
}
function Find($parent,[string]$name) {
 $condition=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty,$name)
 return $parent.FindFirst($scope,$condition)
}
function Dialog([string]$title) {
 $owned=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty,$app.Id)
 $condition=New-Object System.Windows.Automation.AndCondition(
  $owned,
  (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty,$title)))
 return Wait-Value {
  foreach ($window in [System.Windows.Automation.AutomationElement]::RootElement.FindAll([System.Windows.Automation.TreeScope]::Children,$owned)) {
   $found=$window.FindFirst([System.Windows.Automation.TreeScope]::Subtree,$condition)
   if ($found) {return $found}
  }
 }
}
function Button($dialog,[string]$name) {(Wait-Value {Find $dialog $name}).GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()}
function Select-Node($dialog,[string]$name) {
 $node=Wait-Value {Find $dialog $name}
 $node.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Select()
 return $node
}
function Probe([string]$operation) {
 $v=python "$PSScriptRoot/dialog_input_probe.py" $app.Id $operation $report $control
 if ($LASTEXITCODE) {throw "Modal input probe failed: $operation"}
 return $v | ConvertFrom-Json
}
function Blocked([string]$label) {Probe 'blocked' | Out-Null;$checks.Add($label)}
function Bounds($dialog,$labels) {
 $bottom=(Find $dialog 'Save and Apply').Current.BoundingRectangle.Top
 foreach ($label in $labels) {
  $node=Wait-Value {Find $dialog $label};$rect=$node.Current.BoundingRectangle
  if ($node.Current.IsOffscreen -or !$dialog.Current.BoundingRectangle.Contains($rect) -or $rect.Bottom -gt $bottom-3) {throw "Bell control overlaps footer: $label"}
 }
}
try {
 New-Item $key -Force | Out-Null
 # Old saved zero bindings exercise migration to the requested defaults.
 foreach ($item in @{NemoTabs=[int][bool]$TabHost;WarnOnClose=0;FontHeight=12;NemoZoomInBinding=0;NemoZoomOutBinding=0}.GetEnumerator()) {
  New-ItemProperty $key -Name $item.Key -Value $item.Value -PropertyType DWord | Out-Null
 }
 $fixture=Join-Path $PSScriptRoot 'mouse_fixture.py'
 $arguments=@('--automation','--profile',$name,'--cols','80','--rows','24','--font','Consolas','-e',('"'+$python+'"'),('"'+$fixture+'"'),('"'+$report+'"'),('"'+$control+'"'),'240')
 $app=Start-Process -FilePath $exe -ArgumentList $arguments -PassThru
 Wait-Value {Test-Path $report} | Out-Null
 $instance=Probe 'prepare';$seat=@($instance.sessions | Where-Object active)[0]
 $term=[IntPtr]$seat.hwnd;$hostWindow=[IntPtr]$seat.window
 Probe 'zoom' | Out-Null;$checks.Add('Ctrl plus/minus and numeric keypad; CSI-u receives no shortcut bytes')
 [ModalNative]::PostMessageW($term,0x111,[IntPtr]0x50,[IntPtr]::Zero) | Out-Null
 $settings=Dialog ('Nemoterm - Profile: '+$name)
 if ([ModalNative]::GetWindow([IntPtr]$settings.Current.NativeWindowHandle,4) -ne $hostWindow) {throw 'Settings has the wrong top-level owner'}
 Blocked 'Settings blocks foreground activation, terminal input and new-tab commands'
 (Select-Node $settings 'Terminal').GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern).Expand()
 $bell=Select-Node $settings 'Bell'
 Bounds $settings @('None (bell disabled)','Play a custom sound file','Browse...','Raise window on bell without taking keyboard focus','Ring when the application resets the terminal')
 python "$PSScriptRoot/settings_capture.py" $app.Id $settings.Current.NativeWindowHandle bell-settings.png
 if ($LASTEXITCODE) {throw 'Bell screenshot failed'}
 Button $settings 'Browse...'
 $picker=Dialog 'Select bell sound file'
 if ([ModalNative]::IsWindowEnabled([IntPtr]$settings.Current.NativeWindowHandle)) {throw 'Nested file picker did not disable settings'}
 Blocked 'Nested file picker keeps terminal disabled'
 Button $picker 'Cancel'
 Wait-Value {[ModalNative]::IsWindowEnabled([IntPtr]$settings.Current.NativeWindowHandle)} | Out-Null
 Blocked 'Closing file picker does not unlock terminal'
 $bell.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern).Expand()
 Select-Node $settings 'Overload' | Out-Null
 Bounds $settings @('Bell is temporarily disabled when over-used','Over-use means this many bells...','... in this many seconds','Seconds of silence required')
 python "$PSScriptRoot/settings_capture.py" $app.Id $settings.Current.NativeWindowHandle bell-overload-settings.png
 if ($LASTEXITCODE) {throw 'Overload screenshot failed'}
 Button $settings 'Save and Apply'
 Wait-Value {[ModalNative]::IsWindowEnabled($hostWindow)} | Out-Null
 Probe 'ready' | Out-Null
 $stored=Get-ItemProperty $key
 if ($stored.NemoZoomInBinding -ne 0x2bb -or $stored.NemoZoomOutBinding -ne 0x2bd -or $stored.NemoZoomDefaultsVersion -ne 1) {throw 'Zoom defaults did not persist'}
 [ModalNative]::PostMessageW($term,0x111,[IntPtr]0x150,[IntPtr]::Zero) | Out-Null
 $about=Dialog 'About Nemoterm';Blocked 'About is modal'
 Button $about 'View Licence';$licence=Dialog 'Nemoterm Licence'
 Blocked 'Nested licence is modal';Button $licence 'OK'
 Wait-Value {[ModalNative]::IsWindowEnabled([IntPtr]$about.Current.NativeWindowHandle)} | Out-Null
 Blocked 'Closing licence leaves About modal';Button $about 'Close'
 Wait-Value {[ModalNative]::IsWindowEnabled($hostWindow)} | Out-Null
 [ModalNative]::PostMessageW($term,0x111,[IntPtr]0x10,[IntPtr]::Zero) | Out-Null
 $log=Dialog 'Nemoterm Event Log';Blocked 'Event Log is modal';Button $log 'Close'
 Wait-Value {[ModalNative]::IsWindowEnabled($hostWindow)} | Out-Null
 Probe 'ready' | Out-Null
 python "$PSScriptRoot/dialog_input_probe.py" $app.Id finish $term.ToInt64() | Out-Null
 if ($LASTEXITCODE) {throw 'Sibling close failed'}
 [IO.File]::WriteAllText($control,'{"stop":true}',(New-Object Text.UTF8Encoding($false)))
 if (!$app.WaitForExit(10000) -or $app.ExitCode -ne 0) {throw 'Owned dialog process did not exit cleanly'}
 $checks.Add('Closing dialogs restores terminal input; natural process exit')
 $record=@{completed=$true;tab_host=[bool]$TabHost;checks=$checks;executable_sha256=(Get-FileHash $exe -Algorithm SHA256).Hash.ToLowerInvariant()}
 $suffix=if ($TabHost) {'tabs'} else {'standalone'}
 $record | ConvertTo-Json -Depth 5 | Set-Content "$root/research/dialog-$suffix-observed.json" -Encoding UTF8
 Write-Output "Dialog and default zoom checks passed: $suffix"
} catch {Write-Output $_.ScriptStackTrace;throw} finally {
 if ($app -and !$app.HasExited) {$app.Kill();$app.WaitForExit()}
 if (Test-Path $key) {Remove-Item -LiteralPath $key}
 foreach ($file in @('report.json','report.tmp','control.json','control.json.tmp')) { $path=Join-Path $directory $file; if (Test-Path $path) {Remove-Item -LiteralPath $path} }
 Remove-Item -LiteralPath $directory
}
