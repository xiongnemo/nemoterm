"""Measure an OSC 50 request against glyphs from two fresh, independently configured windows."""
import argparse
import hashlib
import json
import os
import re
import traceback
import zipfile
from pathlib import Path
from native_test_utils import c, w, u, root, wait_for, write_snapshot
from automation_capture import OwnedAutomationCapture
from protocol_oracle_window import run

ST='\x1b\\'; OSC='\x1b]50;'; ALT='Consolas'
REFERENCE='03081a24ec96467ed90e6a9b9cf8d15a2acba3f2c9d19b72cf37225e762d2276'


def main():
    assert os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    parser=argparse.ArgumentParser();parser.add_argument('--renderer',choices=['gdi','directx'],required=True);args=parser.parse_args()
    base=os.environ['NEMOTERM_TEST_FONT'];assert base=='SarasaTermSC Nerd Light' and base!=ALT
    archive=root/'testdata/upstream/font-ops-xterm-412.zip';assert hashlib.sha256(archive.read_bytes()).hexdigest()==REFERENCE
    with zipfile.ZipFile(archive) as z: upstream=json.loads(z.read('font-ops-xterm.json'))
    assert upstream['completed']; xft=upstream['profiles']['xft']['cases']
    sample=bytes.fromhex(xft['initial-query']['reply_hex']); other=bytes.fromhex(xft['after-set-query']['reply_hex'])
    assert sample==b'\x1b]50;DejaVu Sans Mono\x1b\\' and other==b'\x1b]50;DejaVu Sans\x1b\\'
    renderer=args.renderer;actual={'gdi':1,'directx':3}[renderer];u.GetPropW.argtypes,u.GetPropW.restype=[w.HWND,w.LPCWSTR],w.HANDLE
    folder=root/'build/font-ops';folder.mkdir(parents=True,exist_ok=True)
    evidence=dict(source_reference=REFERENCE,renderer=renderer,font=base,cases={},errors=[],executable_sha256=hashlib.sha256(Path(os.environ['NEMOTERM_TEST_EXE']).read_bytes()).hexdigest())
    cold={}
    for label,start,aset,aget in [('cold-base',base,False,False),('cold-other',ALT,False,False),
            ('allow',base,True,True),('get-only',base,False,True),('set-only',base,True,False),('deny',base,False,False)]:
        data=evidence['cases'][label]={};name=f'font-ops-{renderer}-{label}'
        def exercise(hwnd,phase,current):
            pid=w.DWORD();u.GetWindowThreadProcessId(hwnd,c.byref(pid));cap=OwnedAutomationCapture(pid.value,hwnd)
            try:
                data['actual_renderer']=int(u.GetPropW(hwnd,'NemotermRenderer') or 0); assert data['actual_renderer']==actual
                def sample_frame(step,index,action,expect):
                    mark=bytes((25,130+index,201));srgb=';'.join(map(str,mark))
                    draw='\x1b[?25l\x1b[0m\x1b]10;#ffffff\x07\x1b]11;#000000\x07\x1b[2J\x1b[H\x1b[48;2;'+srgb+'m  \x1b[0m\x1b[2;2HMg@'
                    raw=phase(step,action+draw+'\x1b[16t',None);m=re.search(rb'\x1b\[6;(\d+);(\d+)t$',raw);assert m,raw
                    ch,cw=map(int,m.groups());r=w.RECT();assert u.GetClientRect(hwnd,c.byref(r));width=r.right
                    def painted():
                        rgb=cap.capture(return_pixels=True);assert len(rgb)% (3*width)==0
                        # Identify the first filled cell on an RGB pixel boundary.
                        for y in range(min(ch*2,len(rgb)//(3*width))):
                            for x in range(min(2*cw,width)):
                                begin=3*(y*width+x)
                                if rgb[begin:begin+3*2*cw]==mark*(2*cw):
                                    glyph=b''.join(rgb[((y+ch+j)*width+x+cw)*3:((y+ch+j)*width+x+4*cw)*3] for j in range(ch))
                                    if len(glyph)==9*cw*ch and any(glyph): return hashlib.sha256(glyph).hexdigest()
                    digest=wait_for(painted);cap.capture(f'{name}-{step}.png');frame=dict(cell=[cw,ch],glyph_sha256=digest)
                    reply=raw[:m.start()];v=data[step]=dict(reply_hex=reply.hex(),expected_reply_hex=expect.hex(),frame=frame)
                    if reply!=expect:evidence['errors'].append(f'{label}/{step}: reply')
                    return frame
                if label.startswith('cold-'):
                    cold[start]=sample_frame('cold',0,'',b'');return
                assert base in cold and ALT in cold and cold[base]!=cold[ALT],'Cold font controls must visibly differ'
                for i,(step,command,font) in enumerate([('initial','',base),('change',OSC+ALT+ST,ALT if aset else base),
                        ('invalid-menu',OSC+'#99'+ST,ALT if aset else base),
                        ('unavailable',OSC+'Nemo Missing Font 073'+ST,ALT if aset else base),
                        ('menu-assign',OSC+'#2 '+base+ST,base),('restore',OSC+base+ST,base)]):
                    expect=sample.replace(b'DejaVu Sans Mono',font.encode()) if aget else b''
                    frame=sample_frame(step,i,command+OSC+'?'+ST,expect)
                    if frame!=cold[font]:evidence['errors'].append(f'{label}/{step}: glyph or dimensions')
                # This reserved OSC 50 subcommand changes only cursor shape,
                # even when the profile denies both font operations. Read back
                # the cursor and font separately; independently compare glyphs.
                expected_font = sample.replace(b'DejaVu Sans Mono', base.encode()) if aget else b''
                frame = sample_frame('cursor-shape', 9, '\x1b[1 q'+OSC+'CursorShape=1'+ST+
                                     '\x1bP$q q'+ST+OSC+'?'+ST, b'\x1bP1$r5 q'+ST.encode()+expected_font)
                if frame != cold[base]: evidence['errors'].append(f'{label}/cursor-shape: font changed')
                # Retain and compare wire framing independently of the image comparison.
                for key,obs in xft.items():
                    if not key.startswith('query-'):continue
                    expected=bytes.fromhex(obs['reply_hex']).replace(b'DejaVu Sans Mono',base.encode()) if aget else b''
                    raw=phase(key,bytes.fromhex(obs['sequence_hex']).decode('ascii'),None)
                    data[key]=dict(reply_hex=raw.hex(),expected_reply_hex=expected.hex())
                    if raw!=expected:evidence['errors'].append(f'{label}/{key}: reply')
            finally:cap.close()
        try:
            run(name,(),exercise=exercise,font=start,automation=True,barrier=('\x1b[5n',b'\x1b[0n'),
                profile=dict(NemoRenderer={'gdi':0,'directx':2}[renderer],NemoTabs=0,WarnOnClose=0,Beep=0,
                             TrueColour=1,LockSize=0,NemoAllowGetFont=int(aget),NemoAllowSetFont=int(aset)),source_reference=REFERENCE)
        except Exception: evidence['errors'].append(label+': '+traceback.format_exc())
        write_snapshot(folder/'summary.json',evidence)
    assert not evidence['errors'],evidence['errors']


if __name__=='__main__':main()
