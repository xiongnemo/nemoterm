"""Capture UPSS assignment, invocation and lifetime from isolated XTerm processes."""
import argparse,json
from pathlib import Path
from xterm_state_oracle import run_cases

ESC=b'\x1b';CSI=ESC+b'[';ST=ESC+b'\\'
RESET=CSI+b'?42l'+ESC+b'c'+CSI+b'65;1"p'+ESC+b'%G'
QUERY=CSI+b'&u'
ASSIGNMENTS=[(0,'%5'),(0,'A'),(0,'0'),(0,'>'),(0,'"?'),(0,'"4'),(0,'%0'),(0,'&4'),
             (1,'A'),(1,'B'),(1,'F'),(1,'H'),(1,'M'),(1,'L')]

def assign(size,name):return ESC+b'P'+str(size).encode()+b'!u'+name.encode()+ST

def cases():
    byte=ESC+b'%@';greek=assign(1,'F');latin=assign(1,'A');report=QUERY+CSI+b'1$w'
    cases={
        'default-utf8':RESET+report,
        'default-byte':RESET+byte+report,
        'utf8-ignored':RESET+greek+report,
        'nrc-accepts':RESET+CSI+b'?42h'+greek+report,
        'soft-reset-byte':RESET+byte+greek+CSI+b'!p'+report,
        'soft-reset-nrc':RESET+CSI+b'?42h'+greek+CSI+b'!p'+report,
        'hard-reset-byte':RESET+byte+greek+ESC+b'c'+report,
        'hard-reset-nrc':RESET+CSI+b'?42h'+greek+ESC+b'c'+report,
        'hard-reset-docs-cache':RESET+byte+greek+ESC+b'%G'+ESC+b'c'+byte+report,
        'cursor-save':RESET+byte+greek+ESC+b'7'+latin+ESC+b'8'+report,
        'alternate-save':RESET+byte+greek+CSI+b'?1049h'+latin+CSI+b'?1049l'+report,
        'docs-cache':RESET+byte+greek+ESC+b'%G'+QUERY+ESC+b'%@'+report,
        'docs-cursor':RESET+byte+greek+ESC+b'7'+ESC+b'%G'+ESC+b'8'+report,
        'docs-duplicate-byte':RESET+byte+greek+byte+report,
        'docs-duplicate-utf8':RESET+byte+greek+ESC+b'%G'+ESC+b'%G'+byte+report,
        'query-extra-params':RESET+byte+greek+CSI+b'7;8&u',
        'query-c1':RESET+byte+greek+ESC+b' G'+QUERY+ESC+b' F',
    }
    for level in range(1,6):
        cases[f'level-{level}']=RESET+CSI+f'{60+level};1"p'.encode()+byte+greek+report
    for suffix in ['5','?','4','B','K','<','',' F','FF','F ','%F','\x7fF','\x01F','\nF']:
        cases['suffix-'+suffix.encode().hex()]=RESET+byte+latin+assign(0,suffix)+report
    for prefix in ['', '00','01','10','2','1;0','1:0','999999999999999999999999999',' 1','1 ']:
        cases['prefix-'+prefix.encode().hex()]=RESET+byte+latin+ESC+b'P'+prefix.encode()+b'!uF'+ST+report
    for payload in [b'\x01F',b'F\x01',b'\x7fF',b'F\x7f',b'\xc6',b'\xc2\x86',b'\nF',b'F\n']:
        cases['controls-'+payload.hex()]=RESET+byte+latin+ESC+b'P1!u'+payload+ST+report
    cases['cancel']=RESET+byte+latin+ESC+b'P1!uF\x18'+report
    cases['escape-cancel']=RESET+byte+latin+ESC+b'P1!uF'+ESC+b'[6n'+report
    for size,name in ASSIGNMENTS:
        for level in (3,5):
            for right in (False,True):
                start=RESET+CSI+f'{60+level};1"p'.encode()+byte+assign(size,name)+ESC+b')<'
                start+=ESC+b'~' if right else b'\x0e'
                for i,value in enumerate(range(0x20,0x80)):
                    row,col=1+i//48,1+i%48
                    start+=CSI+f'{row};{col}H'.encode()+bytes([value|0x80 if right else value])
                # Level 3 cannot answer rectangle checksums. Preserve its
                # state report first, then change level without erasing cells.
                start+=report+CSI+b'65;1"p'+CSI+b'31#y'
                for i in range(96):
                    row,col=1+i//48,1+i%48
                    start+=CSI+f'{i+1};1;{row};{col};{row};{col}*y'.encode()
                cases[f'map-{size}-{name.encode().hex()}-l{level}-'+('gr' if right else 'gl')]=start
    return {name:value+CSI+b'?42l'+ESC+b'%G' for name,value in cases.items()}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--xterm',default='/tmp/nemoterm-xterm-reference/xterm')
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();parts=args.output.with_suffix('');parts.mkdir(exist_ok=False)
    result={}
    for name,sequence in cases().items():
        path=parts/(name+'.json')
        run_cases(args.xterm,path,{name:sequence},['-ti','vt525','-xrm','*allowWindowOps: true',
            '-xrm','*locale: false','-xrm','*wideChars: true'],raw_replies=True,utf8_command_line=False)
        part=json.loads(path.read_text())
        if not result:result={**part,'cases':{}}
        assert result['executable_sha256']==part['executable_sha256']
        result['cases'].update(part['cases'])
        args.output.write_text(json.dumps(result,indent=2)+'\n')
