"""OSC 1337 reports through the owned console host; no clipboard operations."""
from protocol_oracle_window import run

OSC, ST = '\x1b]1337;', '\x1b\\'
CAPS = OSC + 'Capabilities'
base = dict(TrueColour=1, NoMouseReporting=0, NoRemoteWinTitle=0,
            NoRemoteHyperlinks=0, DisableBracketedPaste=0, CJKAmbigWide=0,
            NemoOSC52Write=0, LineCodePage='UTF-8', WarnOnClose=0)
supported = 'T1LrMSc3UTs3BGsGoSyHSx'
direct = [
    ('bel', CAPS+'\x07', CAPS+'='+supported+ST),
    ('st', CAPS+ST, CAPS+'='+supported+ST),
    ('echo', CAPS+'='+supported+ST, ''),
    ('cancel', CAPS+'\x18\x07', ''),
    ('invalid-suffix', CAPS+'?'+ST+OSC+'ReportCellSize=1;1;1'+ST, ''),
    ('overflow', CAPS+'X'*17000+ST, ''),
    ('after-overflow', CAPS+ST, CAPS+'='+supported+ST),
    ('legacy-encoding', '\x1b%@'+CAPS+ST,
     CAPS+'=T1LrMSc3Ts3BGsGoSyHSx'+ST),
    ('restore-utf8', '\x1b%G'+CAPS+ST, CAPS+'='+supported+ST),
    ('alternate-screen', '\x1b[?1049h'+CAPS+ST+'\x1b[?1049l', CAPS+'='+supported+ST),
    ('soft-reset', '\x1b[!p'+CAPS+ST, CAPS+'='+supported+ST),
]
run('iterm-reports', (), extra_cases=direct, profile=base,
    source_reference='iTerm2 feature-reporting specification; policy assertions, not XTerm capture')

restricted = dict(base, TrueColour=0, NoMouseReporting=1, NoRemoteWinTitle=1,
                  NoRemoteHyperlinks=1, DisableBracketedPaste=1,
                  CJKAmbigWide=1, NemoOSC52Write=1)
run('iterm-reports-restricted', (), profile=restricted, extra_cases=[
    ('live-policy', CAPS+ST, CAPS+'=CwLrSc3UAwGsGoSySx'+ST),
    ('ris-policy', '\x1bc'+CAPS+ST, CAPS+'=CwLrSc3UAwGsGoSySx'+ST),
], source_reference='iTerm2 feature-reporting specification; restricted profile')
