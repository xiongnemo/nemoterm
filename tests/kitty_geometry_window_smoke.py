"""Native Kitty placement geometry across font zoom and window resize."""
import argparse
import base64
import re
import traceback
import uuid
from native_test_utils import (root,c,w,u,k,hashlib,json,os,subprocess,sys,Path,
    read_snapshot,write_snapshot,wait_for,wait_snapshot)
from protocol_oracle_window import saved_profile
from owned_job import OwnedJob
from kitty_image_window_smoke import command, reset, CSI
from sixel_palette_window_smoke import bitmap

sys.path.insert(0,str(root/'tools'))
import nemoterm_debug as api

u.GetGuiResources.argtypes,u.GetGuiResources.restype=[w.HANDLE,w.DWORD],w.DWORD
u.GetWindowRect.argtypes=[w.HWND,c.POINTER(w.RECT)]
u.PostMessageW.argtypes,u.PostMessageW.restype=[w.HWND,w.UINT,w.WPARAM,w.LPARAM],w.BOOL


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--renderer',choices=('gdi','opengl','directx'),default='gdi')
    parser.add_argument('--presented-gdi',action='store_true',help='read the owned visible GDI client surface')
    parser.add_argument('--unicode-images',action='store_true',help='compare text-derived images against pinned upstream cell-size observations')
    args=parser.parse_args()
    if args.presented_gdi and args.renderer!='gdi':parser.error('--presented-gdi requires --renderer gdi')
    renderer={'gdi':0,'opengl':1,'directx':2}[args.renderer]
    exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
    font=os.environ.get('NEMOTERM_TEST_FONT','Consolas' if os.environ.get('CI')=='true' else 'SarasaTermSC Nerd Font Light')
    suite=('kitty-unicode-geometry' if args.unicode_images else 'kitty-geometry')+('-presented' if args.presented_gdi else '')
    reference=None
    if args.unicode_images:
        reference=json.loads((root/'tests/kitty_unicode_geometry_reference.json').read_text())
    folder=root/'research'/f'{suite}-{args.renderer}-{uuid.uuid4().hex}'
    folder.mkdir(parents=True)
    report,control=folder/'child-report.json',folder/'child-control.json'
    evidence=dict(completed=False,executable=str(exe),executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
        renderer=args.renderer,font=font,folder=str(folder),phases=[],inputs=[],global_input=False,clipboard_access=False,
        memory_acceptance=False,capture='public API, active GPU or native snapshot')
    profile=dict(NemoRenderer=renderer,WarnOnClose=0,CloseOnExit=1,WindowBorder=1,ScrollBar=0,
                 FontHeight=12,LockSize=0,MouseAutocopy=0)
    try:
        with saved_profile(profile) as profile_args,OwnedJob() as job:
            process=None;window=None;handle=None;presented=None
            try:
                process=job.spawn([str(exe),'--no-tabs',*profile_args,'--automation','--cols','40','--rows','12',
                    '--font',font,'-e',sys.executable,str(root/'tests/mouse_fixture.py'),str(report),str(control),'180'],
                    env=dict(os.environ,NEMOTERM_CONPTY='bundled',NEMOTERM_TEST_EXACT_OUTPUT='1'),
                    creationflags=subprocess.CREATE_NO_WINDOW)
                evidence['pid']=process.pid
                instance=wait_for(lambda:next(iter(api.discover(process.pid)),None),timeout=20)
                assert instance['pid']==process.pid and len(instance['sessions'])==1
                endpoint=instance['endpoint'];target=instance['sessions'][0]
                seat,window=target['id'],target['window']
                assert target['hwnd']==window and target['active']
                owner=w.DWORD();u.GetWindowThreadProcessId(window,c.byref(owner));assert owner.value==process.pid
                actual=target['renderer'];assert actual in (0,renderer)
                if os.environ.get('NEMOTERM_REQUIRE_'+args.renderer.upper())=='1':assert actual==renderer
                evidence.update(endpoint=endpoint,actual_renderer=actual)
                if args.presented_gdi:
                    assert actual==0
                    from presented_window_capture import PresentedWindowCapture
                    presented=PresentedWindowCapture(process.pid,window)
                    evidence['capture']='owned visible GDI client DC; no image API or WM_PRINTCLIENT'
                handle=k.OpenProcess(0x410,False,process.pid);assert handle
                def current():
                    value=read_snapshot(report)
                    assert process.poll() is None and not value.get('error'),value
                    return value
                wait_snapshot(current,lambda v:v.get('columns')==40 and v.get('rows')==12)
                serial=0
                def send(name,sequence=''):
                    nonlocal serial
                    serial+=1
                    evidence['inputs'].append(dict(name=name,sequence_hex=sequence.encode().hex(),
                        appended_geometry_query_hex=(CSI+'16t').encode().hex(),input_barrier=serial))
                    write_snapshot(control,dict(phase=f'{serial}-{name}',sequence=sequence+CSI+'16t',
                        input_barrier=serial,preserve_mouse=True))
                    value=wait_snapshot(current,lambda v:v.get('phase')==f'{serial}-{name}' and v.get('input_barrier')==serial)
                    reply=bytes.fromhex(value['hex'])
                    match=re.search(rb'\x1b\[6;(\d+);(\d+)t\x1b\[0n$',reply)
                    assert match,reply
                    ch,cw=map(int,match.groups())
                    session=next(s for s in api.request(endpoint)['sessions'] if s['id']==seat)
                    assert [session['cols'],session['rows']]==[value['columns'],value['rows']]
                    ox=(session['client_width']-session['cols']*cw)//2
                    oy=(session['client_height']-session['rows']*ch)//2
                    assert min(cw,ch)>0 and min(ox,oy)>=1
                    return dict(cw=cw,ch=ch,ox=ox,oy=oy,width=session['client_width'],height=session['client_height'],
                        cols=session['cols'],rows=session['rows'],reply_hex=reply.hex())
                base=send('reset',reset()+CSI+'H')
                offset=[base['cw']-1,base['ch']-1]
                def transfer(ident,colour,column,scaled=False):
                    return CSI+f'3;{column}H'+command(f'a=T,i={ident},f=32,s=32,v=24,C=1,X={offset[0]},Y={offset[1]}'+
                        (',c=4,r=3' if scaled else ''),bytes((*colour,255))*32*24)
                sequence=transfer(1,(255,0,0),3)+transfer(2,(0,0,255),16,True)+CSI+'H'
                if reference:
                    original=base64.b64decode(reference['input_base64']).decode()
                    # Upstream accepts oversized APCs; use legal 4096-character
                    # chunks here, preserving the exact decoded image bytes.
                    sequence,n=re.subn(r'\x1b_G([^;]*);([A-Za-z0-9+/=]+)\x1b\\',
                        lambda m:command(m[1],base64.b64decode(m[2],validate=True)),original)
                    assert n==2
                    evidence['normalized_image_apcs']=n
                    evidence['reference_sha256']=reference['source_sha256']
                geom=send('images',sequence)
                if reference:
                    assert bytes.fromhex(geom['reply_hex']).startswith(base64.b64decode(reference['reply_base64']))
                def check(name,geom,visible=True):
                    offset[0]=min(offset[0],geom['cw']-1);offset[1]=min(offset[1],geom['ch']-1)
                    record=dict(name=name,geometry=geom,offset=list(offset),matched=False)
                    evidence['phases'].append(record)
                    colours={bytes((0,0,255)):'red',bytes((255,0,0)):'blue'}
                    wanted={'red':set(),'blue':set()}
                    if visible and reference:
                        sample=reference['cases'][f'{geom["cw"]}x{geom["ch"]}']
                        record['reference_cell_size']=sample['name']
                        for layer in sample['layers']:
                            colour={1:'red',2:'blue'}[layer['image_id']]
                            left,top,right,bottom=layer['pixels']
                            src=layer['src_rect']
                            for py in range(top,bottom):
                                sy=src['top']+(py+.5-top)*(src['bottom']-src['top'])/(bottom-top)
                                # Normalise only floating-point representation
                                # noise at the exact texture border. All pixels
                                # are still tested under nearest sampling.
                                if abs(sy)<1e-6:sy=0
                                if abs(sy-1)<1e-6:sy=1
                                if not 0<=sy<1:continue
                                for px in range(left,right):
                                    sx=src['left']+(px+.5-left)*(src['right']-src['left'])/(right-left)
                                    if abs(sx)<1e-6:sx=0
                                    if abs(sx-1)<1e-6:sx=1
                                    if 0<=sx<1 and 0<=px<geom['cols']*geom['cw'] and 0<=py<geom['rows']*geom['ch']:
                                        wanted[colour].add((px+geom['ox'],py+geom['oy']))
                    elif visible:
                        for colour,col,scaled in (('red',2,False),('blue',15,True)):
                            x=geom['ox']+col*geom['cw']+offset[0];y=geom['oy']+2*geom['ch']+offset[1]
                            width=4*geom['cw']-offset[0] if scaled else 32
                            height=3*geom['ch']-offset[1] if scaled else 24
                            wanted[colour]={(px,py) for py in range(y,y+height) for px in range(x,x+width)
                                if geom['ox']<=px<geom['ox']+geom['cols']*geom['cw'] and
                                   geom['oy']<=py<geom['oy']+geom['rows']*geom['ch']}
                    last=None
                    def matches():
                        nonlocal last
                        last=presented.capture() if presented else api.request(endpoint,'image',seat)
                        width,height,pixels=bitmap(last)
                        assert (width,height)==(geom['width'],geom['height'])
                        observed={'red':set(),'blue':set()}
                        for i in range(0,len(pixels),4):
                            if colour:=colours.get(pixels[i:i+3]):observed[colour].add((i//4%width,i//4//width))
                        record['counts']={c:dict(expected=len(wanted[c]),actual=len(observed[c]),
                            missing=sorted(wanted[c]-observed[c])[:8],unexpected=sorted(observed[c]-wanted[c])[:8]) for c in wanted}
                        return observed==wanted
                    try:
                        wait_for(matches);record['matched']=True
                    finally:
                        if last:
                            filename=f'{len(evidence["phases"]):02d}-{name}.png'
                            (folder/filename).write_bytes(api.png_from_bmp(last))
                            record.update(image=filename,bmp_sha256=hashlib.sha256(last).hexdigest())
                        record.update(gdi=u.GetGuiResources(handle,0),user=u.GetGuiResources(handle,1))
                        write_snapshot(folder/'checks.json',evidence['phases'])
                check('initial',geom)
                outer=w.RECT();assert u.GetWindowRect(window,c.byref(outer))
                for name,menu in [('smaller-1',0x950),('smaller-2',0x950),('smaller-3',0x950),('reset-offsets-clamped',0x960),
                                  ('larger-1',0x940),('larger-2',0x940),('reset-larger',0x960)]:
                    previous=(geom['cw'],geom['ch'])
                    u.SendMessageW(window,0x111,menu,0)
                    geom=send(name)
                    assert (geom['cw'],geom['ch'])!=previous,(name,previous,geom)
                    check(name,geom)
                assert (geom['cw'],geom['ch'])==(base['cw'],base['ch'])
                for name,dw,dh in [('wider-taller',80,60),('original-size',0,0)]:
                    assert u.MoveWindow(window,outer.left,outer.top,outer.right-outer.left+dw,outer.bottom-outer.top+dh,True)
                    geom=send(name)
                    assert (geom['cw'],geom['ch'])==(base['cw'],base['ch'])
                    check(name,geom)
                # A font change explicitly ends synchronization and exposes the
                # already parsed image deletion, rather than rescaling a stale frame.
                geom=send('freeze-delete',CSI+'?2026h'+command('a=d,d=R,x=1,y=2' if reference else 'a=d,d=A'))
                check('frozen-image-before-zoom',geom)
                u.SendMessageW(window,0x111,0x940,0);geom=send('zoom-ends-freeze')
                check('zoom-ends-freeze',geom,False)
                if reference:
                    geom=send('history-seed',CSI+'2J'+CSI+'3J'+sequence)
                    check('history-seed',geom)
                    geom=send('scroll-images-to-history',CSI+f'{geom["rows"]};1H'+'\r\n'*geom['rows'])
                    check('scroll-images-to-history',geom,False)
                    u.SendMessageW(window,0x115,6,0)  # owned window: SB_TOP
                    geom=send('view-oldest-history')
                    check('view-oldest-history',geom)
                    u.SendMessageW(window,0x115,7,0)  # owned window: SB_BOTTOM
                    geom=send('return-to-current-screen')
                    check('return-to-current-screen',geom,False)
                    geom=send('clear-history',CSI+'3J')
                    check('clear-history',geom,False)
                    u.SendMessageW(window,0x115,6,0)
                    geom=send('cleared-history-stays-empty')
                    check('cleared-history-stays-empty',geom,False)
                    text_only=re.sub('\x1b_G.*?\x1b\\\\','',sequence,flags=re.S)
                    assert '\x1b_G' not in text_only and '\U0010eeee' in text_only
                    geom=send('template-after-history-clear',text_only)
                    check('template-after-history-clear',geom)
                if presented:evidence['presented_capture']=presented.close()
                assert u.PostMessageW(window,0x10,0,0)
                assert process.wait(timeout=15)==0
                evidence['cleanup']=job.finish();assert not evidence['cleanup']['terminated_remaining']
                evidence['completed']=True
            finally:
                if presented:evidence['presented_capture']=presented.close()
                if process and process.poll() is None and window:
                    owner=w.DWORD();u.GetWindowThreadProcessId(window,c.byref(owner))
                    if owner.value==process.pid:u.PostMessageW(window,0x10,0,0)
                if handle:k.CloseHandle(handle)
                evidence.setdefault('cleanup',job.finish(grace=5))
    except BaseException:
        evidence['error']=traceback.format_exc();raise
    finally:
        write_snapshot(root/'research'/f'{suite}-{args.renderer}-observed.json',evidence)
    print('Kitty native geometry passed:',args.renderer,len(evidence['phases']),'pixel stages')


if __name__=='__main__':main()
