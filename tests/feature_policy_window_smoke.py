"""Native policy reports through ConPTY using isolated saved profiles.

Expected replies describe Nemo's independent permission gates, not XTerm's
resource overrides. The separate component fixture replays original XTerm bytes.
No physical input, clipboard access, or focus manipulation is required.
"""
from protocol_oracle_window import run

OSC, ST = '\x1b]', '\x1b\\'
colors = 'SetColor,GetColor,GetAnsiColor'
mouse = 'X10,Locator,VT200Click,VT200Hilite,AnyButton,AnyEvent,FocusEvent,Extended,SGR,URXVT,AlternateScroll'
windows = ('RestoreWin,MinimizeWin,SetWinPosition,SetWinSizePixels,RaiseWin,LowerWin,RefreshWin,'
           'SetWinSizeChars,MaximizeWin,FullscreenWin,GetWinState,GetWinPosition,GetWinSizePixels,GetWinSizeChars,'
           'GetScreenSizeChars,GetIconTitle,GetWinTitle,PushTitle,PopTitle,SetWinLines,ColumnMode,'
           'GetChecksum,SetChecksum,GetSelection,SetSelection')
paste_denied = ('NUL,SOH,STX,ETX,EOT,ENQ,ACK,BEL,VT,FF,SO,SI,DLE,DC1,DC2,DC3,DC4,NAK,SYN,'
                'ETB,CAN,EM,SUB,ESC,FS,GS,RS,US')
all_categories = 'allowColorOps,allowFontOps,allowMouseOps,allowPasteControls,allowTcapOps,allowTitleOps,allowWindowOps'
profiles = {
    'permitted': dict(NoMouseReporting=0,NoRemoteResize=0,NoRemoteWinTitle=0,PasteControls=1,
                      NemoOSC52Write=1,NemoOSC52Read=1,NemoAllowChecksum=1,RemoteQTitleAction=2,
                      NemoAllowSetTcap=1,NemoAllowGetTcap=1),
    'restricted': dict(NoMouseReporting=1,NoRemoteResize=1,NoRemoteWinTitle=1,PasteControls=0,
                       NemoOSC52Write=0,NemoOSC52Read=0,NemoAllowChecksum=0,RemoteQTitleAction=0,
                       NemoAllowSetTcap=0,NemoAllowGetTcap=0),
    'normal': dict(NoMouseReporting=0,NoRemoteResize=0,NoRemoteWinTitle=0,PasteControls=0,
                   NemoOSC52Write=1,NemoOSC52Read=0,NemoAllowChecksum=0,RemoteQTitleAction=1,
                   NemoAllowSetTcap=0,NemoAllowGetTcap=1),
}

def query(number, payload=None, ending=ST):
    return OSC+str(number)+(';' + payload if payload is not None else '')+ending

def response(number, names='', ending=ST):
    return OSC+str(number)+(';' + names if names else '')+ending

for name, settings in profiles.items():
    allowed = (all_categories if name == 'permitted' else 'allowColorOps' if name == 'restricted'
               else 'allowColorOps,allowMouseOps,allowTitleOps')
    denied_window = ('' if name == 'permitted' else
        'SetWinPosition,SetWinSizePixels,SetWinSizeChars,MaximizeWin,FullscreenWin,GetIconTitle,GetWinTitle,PushTitle,PopTitle,'
        'SetWinLines,ColumnMode,GetSelection,SetSelection,GetChecksum,SetChecksum' if name == 'restricted' else
        'GetIconTitle,GetWinTitle,GetSelection,GetChecksum,SetChecksum')
    cases = [
        ('allowed-st',query(60),response(60,allowed)),
        ('allowed-bel',query(60,'','\a'),response(60,allowed,'\a')),
        ('window-restrictions',query(61,'allowWindowOps'),response(61,denied_window)),
        ('mouse-restrictions',query(61,'allowMouseOps'),response(61,
            'X10,Locator,VT200Click,VT200Hilite,AnyButton,AnyEvent,FocusEvent' if name == 'restricted' else '')),
        ('paste-restrictions',query(61,'allowPasteControls'),response(61,'' if name == 'permitted' else paste_denied)),
        ('supported-colors',query(62,'allowColorOps'),response(62,colors)),
        ('supported-mouse',query(62,'allowMouseOps'),response(62,mouse)),
        ('supported-window',query(62,'allowWindowOps'),response(62,windows)),
        ('window-alias',query(62,'allowWinOps'),response(62,windows)),
        ('supported-font',query(62,'allowFontOps'),response(62,'SetFont,GetFont')),
        ('restricted-font',query(61,'allowFontOps'),response(61,'' if name=='permitted' else 'SetFont,GetFont')),
        ('supported-tcap',query(62,'allowTcapOps'),response(62,'SetTcap,GetTcap')),
        ('restricted-tcap',query(61,'allowTcapOps'),response(61,
            '' if name == 'permitted' else 'SetTcap,GetTcap' if name == 'restricted' else 'SetTcap')),
        ('title-table-absent',query(62,'allowTitleOps'),response(62)),
        ('names-case-insensitive',query(62,'ALLOWCOLOROPS'),response(62,colors)),
        ('unknown-name',query(62,'unknown'),response(62)),
        ('no-prefix-match',query(62,'allowColorOps;extra'),response(62)),
        ('nonempty-60-ignored',query(60,'?'),''),
        ('cannot-set-policy',query(60,'allowWindowOps:true')+query(60),response(60,allowed)),
        ('empty-category-ignored',query(61,'')+query(62,''),''),
    ]
    for phase, prefix in [('ris','\x1bc'),('soft-reset','\x1b[!p'),('level','\x1b[65;1"p'),
                          ('alternate','\x1b[?1049h'),('main','\x1b[?1049l')]:
        cases.append((phase,prefix+query(60)+query(61,'allowWindowOps'),response(60,allowed)+response(61,denied_window)))
    cases.append(('cut-buffer-permission','\x1b]52;0;YQ==\a\x1b]52;0;?\a',
                  '\x1b]52;0;YQ==\a' if name == 'permitted' else ''))
    run('feature-policy-'+name,(),extra_cases=cases,
        profile=dict(settings,WarnOnClose=0,Beep=0,NemoRenderer=0,NemoAllowSetFont=int(name=='permitted'),NemoAllowGetFont=int(name=='permitted')),
        source_reference='Nemo policy expectations; XTerm formatter reference retained separately')

# Exercise the reports and actual request gates independently. These are
# product permission contracts; they are not fabricated upstream observations.
for mask in range(4):
    allow_set, allow_get = bool(mask & 1), bool(mask & 2)
    denied = ','.join(name for name, enabled in (('SetTcap', allow_set), ('GetTcap', allow_get)) if not enabled)
    query_f1 = '\x1bP+q6b6631'+ST
    initial = '\x1bP1+r6b6631=1B4F50'+ST if allow_get else ''
    selected = ('\x1bP1+r6b6631='+('1B5B5B41' if allow_set else '1B4F50')+ST) if allow_get else ''
    cases = [
        ('restrictions', query(61,'allowTcapOps'), response(61,denied)),
        ('supported', query(62,'allowTcapOps'), response(62,'SetTcap,GetTcap')),
        ('startup', query_f1, initial),
        ('select-linux', '\x1bP+p6c696e7578'+ST+query_f1, selected),
        ('invalid-selection-retains-state', '\x1bP+pgg'+ST+query_f1, selected),
        ('reset-retains-selection', '\x1bc'+query_f1, selected),
        ('emulator-identity', '\x1bP+q544e'+ST,
            '\x1bP1+r544e=787465726D2D323536636F6C6F72'+ST if allow_get else ''),
    ]
    run('feature-policy-tcap-'+str(mask), (), extra_cases=cases,
        profile=dict(WarnOnClose=0,Beep=0,NemoRenderer=0,NemoTabs=0,LinuxFunctionKeys=9,
                     NemoTcapName='xterm-256color',NemoAllowSetTcap=int(allow_set),NemoAllowGetTcap=int(allow_get)),
        source_reference='Independent Nemoterm SetTcap/GetTcap permission contract')
