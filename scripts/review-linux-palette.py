"""Audit hosted Linux-console colour archives offline. Input PNGs/records are never regenerated."""
import argparse
from hashlib import sha256
from io import BytesIO
from itertools import product
import json
from pathlib import Path
from zipfile import ZipFile

from PIL import Image

OSC=b'\x1b]'; ST=b'\x1b\\'; CSI=b'\x1b['; ACK=CSI+b'0n'

def review(path):
    with ZipFile(path) as z:
        def doc(name): return json.loads(z.read(name))
        result_path,=[n for n in z.namelist() if n.startswith('research/') and n.endswith('/result.json')]
        folder=result_path.rsplit('/',1)[0]; result=doc(result_path); trace=doc(folder+'-observed.json');source=doc('build/colour-product/SOURCE-HOST.json')
        ref=doc('build/linux-palette-reference/linux-palette.json');env=doc('build/interaction-dependencies/environment.json')
        assert ref['terminal']=='linux' and ref['passed'] and bytes.fromhex(ref['reset'])==OSC+b'R'
        palette=[]
        for i,entry in enumerate(ref['entries']):
            wire=bytes.fromhex(entry['hex']);assert wire.startswith(OSC+b'P') and len(wire)==10 and int(wire[3:4],16)==i==entry['index']
            rgb=bytes.fromhex(wire[4:].decode());assert list(rgb)==entry['rgb'];palette.append(tuple(rgb))
        assert len(palette)==len(set(palette))==16
        assert trace['completed'] and not trace['cleanup']['terminated_remaining'] and not trace['cleanup']['remaining_processes']
        assert trace['requested_font']=='SarasaTermSC Nerd Light' and env['Font']['File']=='SarasaTermSCNerd-Light.ttf'
        assert trace['executable_sha256']==source['Executable']['SHA256'].lower()
        cw,ch=result['cell'];initial=[tuple(map(int,trace['profile_values'][f'Colour{6+2*(i%8)+i//8}'].split(','))) for i in range(16)]
        native_initial=result['native_base'];assert len(native_initial)==16; native_set=[None]*16
        for i,(r,g,b) in enumerate(palette): native_set[(i&10)|((i&1)<<2)|((i&4)>>2)] = r+256*g+65536*b
        stages=[('legacy-set',16,True),('legacy-reset',1,False),('modern-set',16,True),('modern-reset',1,False),('modern-set-for-reset',16,True),('cross-reset',1,False)]
        if 'uppercase-set' in result['stages']:stages += [('uppercase-set',16,True),('reset-after-uppercase',1,False),('literal-and-invalid',3,False)]
        assert [s[0] for s in stages]==list(result['stages'])
        def frame(label):
            im=Image.open(BytesIO(z.read(f'{folder}/{label}.png'))).convert('RGB');assert im.size==(80*cw+2,24*ch+2);return im
        def swatches(im):return [im.getpixel((2+cw*x,2)) for x in range(16)]
        def highlight(im):return [x for x in range(10) if im.getpixel((2+cw*x,2+2*ch))==(34,51,85)]
        assert swatches(frame('before'))==initial and highlight(frame('before'))==[] and highlight(frame('selected'))==[3,4,5,6]
        failures={}; checks=0
        for i,(label,count,changed) in enumerate(stages,1):
            s=result['stages'][label];im=frame(label);assert im.getpixel((2+30*cw,2))==(220,80+i,124)
            colours=palette if changed else initial; wire=CSI+f'4;{1+count}R'.encode()+b''.join(OSC+f'4;{j};rgb:'.encode()+b'/'.join((f'{v:02x}'*2).encode() for v in col)+ST for j,col in enumerate(colours))
            ink=[x for x in range(17) if any(min(im.getpixel((1+x*cw+dx,1+3*ch+dy)))>128 for dx,dy in product(range(cw),range(ch)))]
            child=bytes.fromhex(s['child']);actual=bytes.fromhex(trace['cases'][label]);assert actual==bytes.fromhex(s['actual'])+ACK
            text=s['native_text']
            if 'native_row' in s:assert ''.join(chr(unit) for unit,attr in s['native_row'])==text
            flags=dict(replies=actual==wire+ACK,swatches=swatches(im)==colours,following_text=ink==list(range(count)),highlight=highlight(im)==[3,4,5,6],copy=s['clipboard_changed'] and s['clipboard']=='中文',input=child==actual+b'8',native_text=text=='@'*count+' '*(17-count),native_colours=s['native_colours']==(native_set if changed else native_initial))
            if label=='literal-and-invalid':flags['literal_title']=s['win32_title']=='R P1123456 is literal title text'
            assert flags==s['checks'],(label,flags,s['checks']);checks+=len(flags)
            if not all(flags.values()):failures[label]=[k for k,v in flags.items() if not v]
            writes=trace['console_writes'][label];assert writes['style']==result['style'] and writes['bytes']>0 and writes['calls']==(1 if result['style']=='whole' else writes['bytes'])
        assert result['passed']==(not failures)
        return dict(artifact_sha256=sha256(path.read_bytes()).hexdigest(),exe_sha256=trace['executable_sha256'],product=source['SourceCommit'],renderer=result['renderer'],style=result['style'],stages=len(stages),checks=checks,passed_stages=len(stages)-len(failures),failures=failures)

if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('archives',type=Path,nargs='+');args=cli.parse_args()
    rows=[review(path) for path in args.archives];print(json.dumps(rows,indent=2));raise SystemExit(any(row['failures'] for row in rows))
