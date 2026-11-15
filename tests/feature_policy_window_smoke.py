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
           'SetWinSizeChars,MaximizeWin,GetWinState,GetWinPosition,GetWinSizePixels,GetWinSizeChars,'
           'GetScreenSizeChars,GetIconTitle,GetWinTitle,PushTitle,PopTitle,SetWinLines,ColumnMode,'
           'GetChecksum,SetChecksum,GetSelection,SetSelection')
paste_denied = ('NUL,SOH,STX,ETX,EOT,ENQ,ACK,BEL,VT,FF,SO,SI,DLE,DC1,DC2,DC3,DC4,NAK,SYN,'
                'ETB,CAN,EM,SUB,ESC,FS,GS,RS,US')
all_categories = 'allowColorOps,allowMouseOps,allowPasteControls,allowTcapOps,allowTitleOps,allowWindowOps'
profiles = {
    'permitted': dict(NoMouseReporting=0,NoRemoteResize=0,NoRemoteWinTitle=0,PasteControls=1,
                      NemoOSC52Write=1,NemoOSC52Read=1,NemoAllowChecksum=1,RemoteQTitleAction=2),
    'restricted': dict(NoMouseReporting=1,NoRemoteResize=1,NoRemoteWinTitle=1,PasteControls=0,
                       NemoOSC52Write=0,NemoOSC52Read=0,NemoAllowChecksum=0,RemoteQTitleAction=0),
    'normal': dict(NoMouseReporting=0,NoRemoteResize=0,NoRemoteWinTitle=0,PasteControls=0,
                   NemoOSC52Write=1,NemoOSC52Read=0,NemoAllowChecksum=0,RemoteQTitleAction=1),
}

def query(number, payload=None, ending=ST):
    return OSC+str(number)+(';' + payload if payload is not None else '')+ending

def response(number, names='', ending=ST):
    return OSC+str(number)+(';' + names if names else '')+ending

for name, settings in profiles.items():
    allowed = (all_categories if name == 'permitted' else 'allowColorOps,allowTcapOps' if name == 'restricted'
               else 'allowColorOps,allowMouseOps,allowTcapOps,allowTitleOps')
    denied_window = ('' if name == 'permitted' else
        'SetWinPosition,SetWinSizePixels,SetWinSizeChars,GetIconTitle,GetWinTitle,PushTitle,PopTitle,'
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
        ('font-unsupported',query(62,'allowFontOps'),response(62)),
        ('get-tcap-only',query(62,'allowTcapOps'),response(62,'GetTcap')),
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
        profile=dict(settings,WarnOnClose=0,Beep=0,NemoRenderer=0),
        source_reference='Nemo policy expectations; XTerm formatter reference retained separately')
