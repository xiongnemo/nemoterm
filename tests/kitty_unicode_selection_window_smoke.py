"""Owned-window selection of Unicode images with exact system-clipboard copies."""
import argparse
import traceback
import uuid
from native_test_utils import (root,c,w,u,hashlib,json,os,subprocess,sys,Path,
    read_snapshot,write_snapshot,wait_for,wait_snapshot)
from owned_job import OwnedJob
from protocol_oracle_window import saved_profile
from clipboard_test_utils import SavedClipboard,clipboard_text
from kitty_image_window_smoke import command,reset,CSI
from kitty_unicode_window_smoke import PUA,MARKS
from sixel_palette_window_smoke import bitmap

sys.path.insert(0,str(root/'tools'))
import nemoterm_debug as api


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--renderer',choices=('gdi','opengl','directx'),default='gdi')
    parser.add_argument('--presented-gdi',action='store_true')
    args=parser.parse_args()
    if args.presented_gdi and args.renderer!='gdi':parser.error('--presented-gdi requires GDI')
    requested={'gdi':0,'opengl':1,'directx':2}[args.renderer]
    exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
    font=os.environ.get('NEMOTERM_TEST_FONT','Consolas' if os.environ.get('CI')=='true' else 'SarasaTermSC Nerd Font Light')
    suite='kitty-unicode-selection'+('-presented' if args.presented_gdi else '')
    folder=root/'research'/f'{suite}-{args.renderer}-{uuid.uuid4().hex}';folder.mkdir(parents=True)
    report,control=folder/'child-report.json',folder/'child-control.json'
    evidence=dict(completed=False,executable=str(exe),executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
        requested_renderer=args.renderer,font=font,folder=str(folder),checks=[],input_operations=[],global_input=False,
        clipboard_access=True,instrumented=True,memory_acceptance=False,
        capture='public automation API; active renderer BMP',physical_input=False)
    profile=dict(NemoRenderer=requested,WarnOnClose=0,CloseOnExit=1,WindowBorder=1,ScrollBar=0,
                 FontHeight=12,MouseAutocopy=0)
    try:
        with saved_profile(profile) as profile_args,OwnedJob() as job:
            process=window=session=script=saved=presented=None
            try:
                argv=[str(exe),*profile_args,'--no-tabs','--automation','--cols','40','--rows','12','--font',font,
                      '-e',sys.executable,str(root/'tests/mouse_fixture.py'),str(report),str(control),'180']
                evidence['command']=argv
                process=job.spawn(argv,env=dict(os.environ,NEMOTERM_CONPTY='bundled',NEMOTERM_TEST_EXACT_OUTPUT='1'),
                                  creationflags=subprocess.CREATE_NO_WINDOW)
                evidence['pid']=process.pid
                instance=wait_for(lambda:next(iter(api.discover(process.pid)),None),timeout=20)
                assert instance['pid']==process.pid and len(instance['sessions'])==1
                endpoint,target=instance['endpoint'],instance['sessions'][0]
                seat,window=target['id'],target['window']
                owner=w.DWORD();u.GetWindowThreadProcessId(window,c.byref(owner));assert owner.value==process.pid
                assert target['active'] and target['hwnd']==window
                actual=target['renderer'];assert actual in (0,requested)
                if os.environ.get('NEMOTERM_REQUIRE_'+args.renderer.upper())=='1':assert actual==requested
                evidence.update(endpoint=endpoint,actual_renderer=actual)
                if args.presented_gdi:
                    from presented_window_capture import PresentedWindowCapture
                    assert actual==0;presented=PresentedWindowCapture(process.pid,window)
                    evidence['capture']='owned GDI client DC; no image API or WM_PRINTCLIENT'
                capture=lambda:presented.capture() if presented else api.request(endpoint,'image',seat)
                def current():
                    value=read_snapshot(report)
                    assert process.poll() is None and not value.get('error'),value
                    return value
                wait_snapshot(current,lambda v:v.get('columns')==40 and v.get('rows')==12)
                width,height,_=bitmap(capture());cw,ch=(width-2)//40,(height-2)//12
                assert width==40*cw+2 and height==12*ch+2
                evidence['cell_pixels']=[cw,ch]
                saved=SavedClipboard(window)
                import frida
                evidence['frida_version']=frida.__version__
                session=frida.attach(process.pid)
                script=session.create_script((root/'tests/agent_key_probe.js').read_text())
                errors=[];script.on('message',lambda m,d:errors.append(m) if m.get('type')=='error' else None)
                script.load();script.exports_sync.isolate_mouse(hex(window));serial=0
                def inject(op):
                    nonlocal serial
                    serial+=1;evidence['input_operations'].append(dict(id=serial,**op))
                    script.exports_sync.key(dict(id=serial,**op))
                    assert u.PostMessageW(window,0x8322,0,0)
                    assert wait_for(lambda:script.exports_sync.result())==dict(id=serial)
                    assert not errors,errors
                point=lambda x,y:(1+y*ch+ch//2)<<16|(1+x*cw+cw//2)
                rows=[''.join(PUA+MARKS[r]+MARKS[col] for col in range(4)) for r in range(2)]
                red=bytes((255,0,0))*4*cw*2*ch
                upload=command(f'a=T,i=42,p=7,f=24,s={4*cw},v={2*ch},c=4,r=2,U=1,C=1',red)
                graphics_reply=b'\x1b_Gi=42,p=7;OK\x1b\\'
                def save_image(name):
                    raw=capture();assert bitmap(raw)[:2]==(width,height)
                    (folder/(name+'.png')).write_bytes(api.png_from_bmp(raw))
                    return dict(file=name+'.png',bmp_sha256=hashlib.sha256(raw).hexdigest())
                def red_rectangle(row):
                    _,_,pixels=bitmap(capture())
                    return all(pixels[(y*width+x)*4:(y*width+x)*4+3]==b'\0\0\xff'
                               for y in range(1+row*ch,1+(row+2)*ch) for x in range(1+2*cw,1+6*cw))
                for flags in range(16):
                    alternate,mouse,rectangle,cluster=(bool(flags&(1<<i)) for i in range(4))
                    name=f'case-{flags:02d}'
                    # Consecutive independent selections start far apart, so
                    # fast fixture clicks cannot become word/line multi-clicks.
                    row=1+3*(flags%2)
                    assert 3*ch>u.GetSystemMetrics(37)//2  # SM_CYDOUBLECLK
                    text=(CSI+'38;5;42m'+CSI+f'{row+1};2H'+'A'+rows[0]+'B'+
                          CSI+f'{row+2};2H'+'C'+rows[1]+'D')
                    wire=reset()+command('a=d,d=R,x=1,y=4294967295')
                    if alternate:wire+=CSI+'?1049h'
                    wire+=CSI+('?2027h' if cluster else '?2027l')+upload+text+CSI+'?25l'
                    if mouse:wire+=CSI+'?1003;1006h'
                    request=dict(phase=name,sequence=wire,input_barrier=name+'-seed',preserve_mouse=True)
                    write_snapshot(control,request)
                    value=wait_snapshot(current,lambda v:v.get('phase')==name and v.get('input_barrier')==name+'-seed')
                    assert bytes.fromhex(value['hex'])==graphics_reply+b'\x1b[0n',value
                    wait_for(lambda:red_rectangle(row))
                    record=dict(name=name,alternate=alternate,application_mouse=mouse,rectangle=rectangle,
                                cluster=cluster,row=row,sequence_hex=wire.encode().hex(),matched=False,
                                before=save_image(name+'-before'))
                    evidence['checks'].append(record)
                    left,right=(3,4) if rectangle else (1,6)
                    modifiers=[16,160]+([17,162] if rectangle else [])
                    keys=1|4|(8 if rectangle else 0)
                    inject(dict(modifiers=modifiers,mouse=[dict(message=0x201,keys=keys,point=point(left,row)),
                                                         dict(message=0x200,keys=keys,point=point(right,row+1))]))
                    # Release modifiers before the button; the local drag must
                    # finish without leaking a mouse report to the child.
                    inject(dict(mouse=[dict(message=0x202,keys=0,point=point(right,row+1))]))
                    record['selected']=save_image(name+'-selected')
                    expected=('\r\n'.join(''.join(PUA+MARKS[r]+MARKS[col] for col in (1,2)) for r in range(2))
                              if rectangle else 'A'+rows[0]+'B\r\n C'+rows[1]+'D')
                    record['expected_utf8_hex']=expected.encode().hex()
                    previous=u.GetClipboardSequenceNumber()
                    inject(dict(key=67,scan=46,modifiers=[16,17,160,162]))
                    wait_for(lambda:u.GetClipboardSequenceNumber()!=previous)
                    copied=clipboard_text(window)
                    record['shortcut_utf8_hex']=copied.encode().hex()
                    assert copied==expected,(name,'shortcut',repr(copied))
                    previous=u.GetClipboardSequenceNumber()
                    inject(dict(mouse=[dict(message=0x204,keys=2,point=point(left,row)),
                                       dict(message=0x205,keys=0,point=point(left,row))]))
                    wait_for(lambda:u.GetClipboardSequenceNumber()!=previous)
                    copied=clipboard_text(window)
                    record['right_click_utf8_hex']=copied.encode().hex()
                    assert copied==expected,(name,'right click',repr(copied))
                    write_snapshot(control,dict(request,input_barrier=name+'-drain'))
                    value=wait_snapshot(current,lambda v:v.get('input_barrier')==name+'-drain')
                    assert bytes.fromhex(value['hex'])==graphics_reply+b'\x1b[0n'*2,value
                    record.update(reply_hex=value['hex'],matched=True)
                    write_snapshot(folder/'checks.json',evidence['checks'])
                evidence['completed']=True
            finally:
                if saved:saved.restore();evidence['clipboard_restore_finished']=True
                if script:script.unload()
                if session:session.detach()
                if presented:evidence['presented_capture']=presented.close()
                if process and process.poll() is None and window:
                    owner=w.DWORD();u.GetWindowThreadProcessId(window,c.byref(owner))
                    if owner.value==process.pid:u.PostMessageW(window,0x10,0,0)
                if process:assert process.wait(timeout=15)==0
                evidence['cleanup']=job.finish()
                assert not evidence['cleanup']['terminated_remaining'] and not evidence['cleanup']['remaining_processes']
        evidence['profile_removed']=True
    except BaseException:
        evidence['completed']=False;evidence['error']=traceback.format_exc();raise
    finally:
        write_snapshot(root/'research'/f'{suite}-{args.renderer}-observed.json',evidence)
    print('Native Unicode image selection passed:',args.renderer,len(evidence['checks'])*2,'exact clipboard copies')


if __name__=='__main__':main()
