param([switch]$TabHost)
# Exercise the real startup settings dialog, save/load and local-session launch.
# UI Automation is scoped to a new process; no global mouse or keyboard input.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class ShellSettingsNative {
    private delegate bool EnumChildProc(IntPtr hwnd, IntPtr data);
    [DllImport("user32.dll")] private static extern bool EnumChildWindows(IntPtr hwnd, EnumChildProc callback, IntPtr data);
    public static IntPtr Content(IntPtr host) {
        IntPtr found=IntPtr.Zero;
        EnumChildWindows(host,(hwnd,data)=> {
            if (GetPropW(hwnd,"NemotermRenderer")!=IntPtr.Zero) {found=hwnd;return false;}
            return true;
        },IntPtr.Zero);
        return found;
    }
    [DllImport("user32.dll")] public static extern IntPtr SendMessageW(IntPtr hwnd, uint msg, IntPtr wp, IntPtr lp);
    [DllImport("user32.dll")] public static extern IntPtr GetParent(IntPtr hwnd);
    [DllImport("user32.dll")] public static extern int GetDlgCtrlID(IntPtr hwnd);
    [DllImport("user32.dll")] public static extern bool PostMessageW(IntPtr hwnd, uint msg, IntPtr wp, IntPtr lp);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern IntPtr GetPropW(IntPtr hwnd, string name);
    [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr hwnd);
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
function Binding-Controls($dialog, $expected, [string]$page = 'Bindings') {
    $bindingNode = Select-Node $dialog 'Bindings'
    if ($page -ne 'Bindings') {
        $bindingNode.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern).Expand()
        Select-Node $dialog $page | Out-Null
    }
    $combos = $dialog.FindAll($scope, (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::ComboBox)))
    if ($combos.Count -ne $expected.Count) { throw 'Missing binding controls' }
    for ($i=0; $i -lt $expected.Count; $i++) {
        $combo=$combos[$i]
        if ($combo.Current.IsOffscreen -or !$dialog.Current.BoundingRectangle.Contains($combo.Current.BoundingRectangle)) { throw 'Binding control clipped' }
        $selected=[ShellSettingsNative]::SendMessageW([IntPtr]$combo.Current.NativeWindowHandle,0x147,[IntPtr]::Zero,[IntPtr]::Zero).ToInt32()
        if ($selected -ne $expected[$i]) { throw "Binding $i expected $($expected[$i]), got $selected" }
    }
    return ,$combos
}
function Set-Combo($combo, [int]$index) {
    $handle=[IntPtr]$combo.Current.NativeWindowHandle
    [ShellSettingsNative]::SendMessageW($handle,0x14E,[IntPtr]$index,[IntPtr]::Zero) | Out-Null
    $id=[ShellSettingsNative]::GetDlgCtrlID($handle)
    [ShellSettingsNative]::SendMessageW([ShellSettingsNative]::GetParent($handle),0x111,[IntPtr]($id -bor (1 -shl 16)),$handle) | Out-Null
}
function Check-HyperlinkControls($dialog) {
    $terminal=Wait-Value { Find-Name $dialog 'Terminal' }
    $terminal.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern).Expand()
    Select-Node $terminal 'Hyperlinks' | Out-Null
    foreach ($label in @('Disable OSC 8 hyperlinks','Allow registered custom URI schemes')) {
        $control=Wait-Value { Find-Name $dialog $label }
        if ($control.Current.IsOffscreen -or !$dialog.Current.BoundingRectangle.Contains($control.Current.BoundingRectangle)) {
            throw 'Hyperlink option clipped or missing'
        }
        if ($control.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern).Current.ToggleState -ne [System.Windows.Automation.ToggleState]::Off) {
            throw 'Unexpected hyperlink preference'
        }
    }
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
    Check-HyperlinkControls $dialog
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
    $columns=Find-Name $dialog 'Columns' 'Edit'
    $rows=Find-Name $dialog 'Rows' 'Edit'
    if ($columns.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).Current.Value -ne '160' -or
        $rows.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).Current.Value -ne '48') { throw 'Default grid was not 160 x 48' }
    $defaultBindings=@(3,3,3,22,0,0,1)
    $customBindings=@(6,24,5,25,3,26,5)
    $combos=Binding-Controls $dialog $defaultBindings
    for ($i=0;$i -lt 7;$i++) { Set-Combo $combos[$i] $customBindings[$i] }
    Binding-Controls $dialog $customBindings | Out-Null
    # A duplicate shortcut opens a modal error. Post only the notification so
    # the test thread can inspect and dismiss that owned modal window.
    Set-Combo $combos[2] 6
    $pasteHandle=[IntPtr]$combos[3].Current.NativeWindowHandle
    [ShellSettingsNative]::SendMessageW($pasteHandle,0x14E,[IntPtr]24,[IntPtr]::Zero) | Out-Null
    $pasteId=[ShellSettingsNative]::GetDlgCtrlID($pasteHandle)
    [ShellSettingsNative]::PostMessageW([ShellSettingsNative]::GetParent($pasteHandle),0x111,[IntPtr]($pasteId -bor (1 -shl 16)),$pasteHandle) | Out-Null
    $errorCondition=New-Object System.Windows.Automation.AndCondition(
        (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty,$app.Id)),
        (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ClassNameProperty,'#32770')))
    $errorDialog=Wait-Value { $dialog.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$errorCondition) }
    Invoke-Button $errorDialog 'OK'
    Wait-Value { [ShellSettingsNative]::SendMessageW($pasteHandle,0x147,[IntPtr]::Zero,[IntPtr]::Zero).ToInt32() -eq 25 } | Out-Null
    Set-Combo $combos[2] 5
    Invoke-Button $dialog 'Reset bindings'
    $combos=Binding-Controls $dialog $defaultBindings
    for ($i=0;$i -lt 7;$i++) { Set-Combo $combos[$i] $customBindings[$i] }
    python "$PSScriptRoot/settings_capture.py" $app.Id $dialog.Current.NativeWindowHandle bindings-settings.png
    if ($LASTEXITCODE) { throw 'Bindings settings capture failed' }
    $defaultShellBindings=@(0,0,0,0,0,0,0,0)
    $customShellBindings=@(7,45,7,46,7,47,7,48)
    $shellCombos=Binding-Controls $dialog $defaultShellBindings 'Commands'
    for ($i=0;$i -lt 8;$i++) { Set-Combo $shellCombos[$i] $customShellBindings[$i] }
    Binding-Controls $dialog $customShellBindings 'Commands' | Out-Null
    python "$PSScriptRoot/settings_capture.py" $app.Id $dialog.Current.NativeWindowHandle shell-marks-settings.png
    if ($LASTEXITCODE) { throw 'Shell integration settings capture failed' }
    Select-Node $dialog 'Rendering' | Out-Null
    Select-Node $dialog 'Tabs' | Out-Null
    $tabs=Wait-Value { Find-Name $dialog 'Open sessions in tabs' }
    $tabsToggle=$tabs.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern)
    if ($tabsToggle.Current.ToggleState -ne [System.Windows.Automation.ToggleState]::Off) { throw 'Staged tab host unexpectedly enabled by default' }
    if ($TabHost) { $tabsToggle.Toggle() }
    foreach ($label in @('Open sessions in tabs','Top','Bottom','Left','Right','Preview terminal on hover')) {
        $node=Find-Name $dialog $label
        if (!$node -or $node.Current.IsOffscreen -or !$bounds.Contains($node.Current.BoundingRectangle)) { throw "Clipped tab setting: $label" }
    }
    Select-Node $dialog 'Left' | Out-Null
    $tabBindings=@(3,20,3,23,2,72,3,72)
    $tabCombos=Binding-Controls $dialog $tabBindings 'Tabs'
    foreach ($choice in @(@(4,6),@(5,14),@(6,6),@(7,16))) { Set-Combo $tabCombos[$choice[0]] $choice[1] }
    $tabBindings=@(3,20,3,23,6,14,6,16)
    Binding-Controls $dialog $tabBindings 'Tabs' | Out-Null
    python "$PSScriptRoot/settings_capture.py" $app.Id $dialog.Current.NativeWindowHandle tabs-settings.png
    if ($LASTEXITCODE) { throw 'Tab settings capture failed' }
    Select-Node $dialog 'Rendering' | Out-Null
    if (!(Find-Name $dialog 'GDI (low memory)').GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Current.IsSelected) { throw 'GDI was not the default renderer' }
    Select-Node $dialog 'DirectX (Direct2D composition)' | Out-Null
    python "$PSScriptRoot/settings_capture.py" $app.Id $dialog.Current.NativeWindowHandle rendering-settings.png
    if ($LASTEXITCODE) { throw 'Rendering settings capture failed' }
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
    $sessionNode = Find-Name $dialog 'Session'
    $sessionNode.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern).Expand()
    Select-Node $dialog 'Shell' | Out-Null
    $cwdLabel = 'Starting directory (blank inherits launcher):'
    $inheritLabel = 'Use reported directory for duplicated sessions'
    $cwdEdit = Wait-Value { Find-Name $dialog $cwdLabel 'Edit' }
    $inherit = Wait-Value { Find-Name $dialog $inheritLabel }
    foreach ($node in @($cwdEdit, $inherit)) {
        if ($node.Current.IsOffscreen -or !$bounds.Contains($node.Current.BoundingRectangle)) { throw 'Directory control clipped' }
    }
    $fixtureCwd = Join-Path $directory ('working ' + [char]0x4e2d)
    New-Item -ItemType Directory -Path $fixtureCwd | Out-Null
    $cwdEdit.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).SetValue($fixtureCwd)
    $inheritToggle = $inherit.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern)
    if ($inheritToggle.Current.ToggleState -ne [System.Windows.Automation.ToggleState]::On) { throw 'Directory inheritance was not enabled by default' }
    $inheritToggle.Toggle()
    python "$PSScriptRoot/settings_capture.py" $app.Id $dialog.Current.NativeWindowHandle cwd-settings.png
    if ($LASTEXITCODE) { throw 'Directory settings capture failed' }
    Select-Node $dialog 'Session' | Out-Null
    $saved = Wait-Value { Find-Name $dialog 'Saved Sessions' 'Edit' }
    $saved.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).SetValue($fixtureProfile)
    Invoke-Button $dialog 'Save'
    if ((Get-ItemProperty -LiteralPath $profilePath).NemoChooseShell -ne 1) { throw 'Shell startup preference was not saved' }
    if ((Get-ItemProperty -LiteralPath $profilePath).NemoShell -ne 'git-bash') { throw 'Selected default shell was not saved' }
    $values = Get-ItemProperty -LiteralPath $profilePath
    if ($values.NemoTabSide -ne 2 -or $values.NemoTabs -ne [int][bool]$TabHost -or
        $values.NemoNextTabBinding -ne 0x64e -or $values.NemoPreviousTabBinding -ne 0x650) { throw 'Tab settings did not save' }
    if ($values.NemoCopyBinding -ne 0x658 -or $values.NemoPasteBinding -ne 0x559 -or
        $values.NemoCopyPasteBinding -ne 0x35a -or $values.NemoRectangleModifiers -ne 6 -or
        $values.NemoRenderer -ne 2) { throw 'Bindings or renderer did not save' }
    if ($values.NemoPreviousPromptBinding -ne 0x778 -or $values.NemoNextPromptBinding -ne 0x779 -or
        $values.NemoSelectCommandBinding -ne 0x77a -or $values.NemoSelectOutputBinding -ne 0x77b) {
        throw 'Shell integration bindings did not save'
    }
    $expectedHex = -join ([Text.Encoding]::UTF8.GetBytes($fixtureCwd) | ForEach-Object { $_.ToString('X2') })
    if ($values.NemoStartingDirectoryUtf8Hex -ne $expectedHex -or $values.NemoInheritDirectory -ne 0) { throw 'Unicode directory settings were not saved' }
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
    $sessionNode = Find-Name $dialog 'Session'
    $sessionNode.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern).Expand()
    Select-Node $dialog 'Shell' | Out-Null
    $reloadedCwd = Wait-Value { Find-Name $dialog $cwdLabel 'Edit' }
    if ($reloadedCwd.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).Current.Value -ne $fixtureCwd) { throw 'Unicode directory did not reload' }
    $reloadedInheritance = Wait-Value { Find-Name $dialog $inheritLabel }
    if ($reloadedInheritance.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern).Current.ToggleState -ne [System.Windows.Automation.ToggleState]::Off) { throw 'Directory inheritance did not reload' }
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
    $windowNode=Find-Name $dialog 'Window'
    $windowNode.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern).Expand()
    Binding-Controls $dialog $customBindings | Out-Null
    Binding-Controls $dialog $customShellBindings 'Commands' | Out-Null
    Binding-Controls $dialog $tabBindings 'Tabs' | Out-Null
    if (!(Find-Name $dialog 'Left').GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Current.IsSelected) { throw 'Tab position did not reload' }
    Select-Node $dialog 'Rendering' | Out-Null
    if (!(Find-Name $dialog 'DirectX (Direct2D composition)').GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Current.IsSelected) { throw 'Renderer did not reload' }
    Invoke-Button $dialog 'Open'
    $observed = Wait-Value {
        if (Test-Path -LiteralPath $report) {
            $value = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
            if ($value.error) { throw $value.error }
            if ($value.hex -eq '1b5b3e343b336d1b5b3e343b3166') { $value }
        }
    }
    $termHandle=Wait-Value {
        $app.Refresh()
        if ($app.MainWindowHandle) {
            if ($TabHost) { $content=[ShellSettingsNative]::Content($app.MainWindowHandle); if ($content -ne [IntPtr]::Zero) { $content } }
            elseif ([ShellSettingsNative]::GetPropW($app.MainWindowHandle,'NemotermRenderer').ToInt32()) { $app.MainWindowHandle }
        }
    }
    $initialRenderer=[ShellSettingsNative]::GetPropW($termHandle,'NemotermRenderer').ToInt32()
    $rendererChanges=@()
    foreach ($mode in @('GDI (low memory)','OpenGL (GPU composition)','DirectX (Direct2D composition)','GDI (low memory)')) {
        [ShellSettingsNative]::PostMessageW($termHandle,0x111,[IntPtr]0x50,[IntPtr]::Zero) | Out-Null
        $dialog=Dialog $app
        Check-HyperlinkControls $dialog
        $node=Find-Name $dialog 'Window'
        $node.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern).Expand()
        Select-Node $dialog 'Rendering' | Out-Null
        Select-Node $dialog $mode | Out-Null
        $dialogHandle=[IntPtr]$dialog.Current.NativeWindowHandle
        Invoke-Button $dialog 'Apply'
        Wait-Value { ![ShellSettingsNative]::IsWindow($dialogHandle) } | Out-Null
        $allowed=if ($mode -eq 'GDI (low memory)') {@(1)} elseif ($mode -eq 'OpenGL (GPU composition)') {@(1,2)} else {@(1,3)}
        if ($mode -eq 'OpenGL (GPU composition)' -and $env:NEMOTERM_REQUIRE_OPENGL -eq '1') {$allowed=@(2)}
        if ($mode -eq 'DirectX (Direct2D composition)' -and $env:NEMOTERM_REQUIRE_DIRECTX -eq '1') {$allowed=@(3)}
        $active=Wait-Value { $value=[ShellSettingsNative]::GetPropW($termHandle,'NemotermRenderer').ToInt32(); if ($value -in $allowed) { $value } }
        if ($mode -eq 'GDI (low memory)' -and $active -ne 1) { throw 'Live GDI switch failed' }
        $rendererChanges += @{requested=$mode;active=$active}
    }
    $evidence = @{executable_sha256=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLower();
        default_grid=@(160,48);tab_host=[bool]$TabHost;saved_tab_side=2;saved_tab_bindings=$tabBindings;saved_bindings=$customBindings;duplicate_binding_rejected=$true;live_renderer_changes=$rendererChanges;
        saved_shell_bindings=$customShellBindings;saved_renderer=2;initial_renderer=$initialRenderer;
        saved_level=3;saved_format=1;copy_only_default=$true;saved_copy_and_paste=$true;
        reflow_default=$true;saved_reflow=$false;win32_default=$false;saved_win32=$true;cancel_exit=0;local_launch=$true;
        hyperlink_settings_startup=$true;hyperlink_settings_live=$true;
        saved_shell='git-bash';saved_choose_shell=$true;explicit_command_overrides_shell=$true;
        saved_unicode_directory=$fixtureCwd;saved_directory_inheritance=$false;query=$observed}
    $evidenceName=if ($TabHost) {'research/tabs-settings-window-observed.json'} else {'research/settings-window-observed.json'}
    [IO.File]::WriteAllText((Join-Path $root $evidenceName),
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
    if ($fixtureCwd -and (Test-Path -LiteralPath $fixtureCwd)) { Remove-Item -LiteralPath $fixtureCwd }
    Remove-Item -LiteralPath $directory
}
