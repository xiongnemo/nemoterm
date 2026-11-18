"""Record OSC 50 on unmodified XTerm. Cell metrics are an independent effect of a set."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
from xterm_feature_policy_oracle import capture, query, E, C, ST, OSC
from xterm_locator_oracle import write

CELL = C + b'16t'


def cases(xft):
    normal, large = (b'DejaVu Sans Mono', b'DejaVu Sans') if xft else (b'6x13', b'9x15')
    def f(spec, end=ST): return query(50, spec, end)
    result = {'empty-barrier': b'', 'initial-cell': CELL, 'initial-query': f(b'?')}
    for i, payload in enumerate((b'?', b'?#', b'?0', b'?1', b'?2', b'?+1', b'?-1',
                                 b'?+', b'?-', b'?+0', b'?99', b'?#1', b'?text', b'?1 ignored')):
        for label, end in [('st', ST), ('bel', b'\x07')]: result[f'query-{i}-{label}'] = f(payload, end)
    result.update({
        'set-name': f(large), 'after-set-cell': CELL, 'after-set-query': f(b'?'),
        'restore-name': f(normal), 'restored-cell': CELL, 'restored-query': f(b'?'),
        'select-menu-1': f(b'#1'), 'menu-1-cell': CELL, 'menu-1-query': f(b'?'),
        'define-menu-2': f(b'#2 ' + large), 'menu-2-cell': CELL, 'menu-2-query': f(b'?2'),
        'relative-down': f(b'#-'), 'relative-down-query': f(b'?'), 'relative-down-cell': CELL,
        'reject-menu-99': f(b'#99'), 'after-reject': f(b'?') + CELL,
        'soft-reset': C + b'!p' + f(b'?') + CELL,
        'alternate': C + b'?1049h' + f(b'?') + CELL + C + b'?1049l',
        'c1-output': E + b' G' + f(b'?') + E + b' F',
        'raw-c1-in-utf8': b'\x9d50;?\x9c', 'utf8-c1': b'\xc2\x9d50;?\xc2\x9c',
        'cancel': OSC + b'50;?' + b'\x18' + ST + f(b'?'),
        'hard-reset': E + b'c' + f(b'?') + CELL,
    })
    return result


def main():
    assert os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted'
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--xterm',required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    base=a.output.with_suffix('');base.mkdir(); readfd,writefd=os.pipe()
    display=subprocess.Popen(['Xvfb','-displayfd',str(writefd),'-screen','0','1280x1024x24','-nolisten','tcp'],pass_fds=[writefd]);os.close(writefd)
    result=dict(completed=False,xterm_sha256=hashlib.sha256(Path(a.xterm).read_bytes()).hexdigest(),profiles={})
    try:
        name=':'+os.read(readfd,100).decode().strip();env=dict(os.environ,DISPLAY=name)
        result['font_controls']={}
        for alias in ['6x13','5x8','9x15']:
            found=subprocess.check_output(['xlsfonts','-fn',alias],text=True,env=env).splitlines();assert alias in found
            result['font_controls'][alias]=found
        for face in ['DejaVu Sans Mono','DejaVu Sans']:
            match=subprocess.check_output(['fc-match','--format','%{family}',face],text=True);assert face==match
            result['font_controls'][face]=match
        for label,policy in [('default',{}),('all',{'allowFontOps':'true'}),
                ('no-get',{'allowFontOps':'false','disallowedFontOps':'GetFont'}),
                ('no-set',{'allowFontOps':'false','disallowedFontOps':'SetFont'}),
                ('blocked',{'allowFontOps':'false','disallowedFontOps':'GetFont,SetFont'}),
                ('no-shift',{'allowFontOps':'true','shiftFonts':'false'}),('xft',{'allowFontOps':'true'})]:
            xft=label=='xft';settings={'renderFont':'true' if xft else 'false','faceName':'DejaVu Sans Mono',
                                       'font1':'5x8','font2':'9x15','allowWindowOps':'true',**policy}
            result['profiles'][label]=capture(a.xterm,name,label,settings,base,sequences=cases(xft));write(a.output,result)
        def reply(p,k):return bytes.fromhex(result['profiles'][p]['cases'][k]['reply_hex'])
        assert all(reply(p,'empty-barrier')==b'' for p in result['profiles'])
        assert reply('all','initial-cell') == C+b'6;13;6t' and reply('all','after-set-cell') == C+b'6;15;9t'
        assert reply('all','restored-cell') == reply('all','initial-cell')
        assert reply('all','initial-query') == OSC+b'50;6x13'+ST and reply('blocked','initial-query')==b''
        assert reply('no-get','initial-query')==b'' and reply('no-get','after-set-cell')==reply('all','after-set-cell')
        assert reply('no-set','initial-query')==reply('all','initial-query') and reply('no-set','after-set-cell')==reply('all','initial-cell')
        assert reply('xft','initial-query')==OSC+b'50;DejaVu Sans Mono'+ST and reply('xft','after-set-query')==OSC+b'50;DejaVu Sans'+ST
        result['completed']=True
    finally:
        write(a.output,result);os.close(readfd);display.terminate();display.wait(timeout=5)


if __name__=='__main__':main()
