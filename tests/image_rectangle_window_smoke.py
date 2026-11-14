"""Compare public rectangle captures with full frames, including frozen tabs."""
from native_test_utils import *
from protocol_oracle_window import saved_profile
from owned_job import OwnedJob
sys.path.insert(0,str(root/'tools'))
import nemoterm_debug as api


def child():
    import runpy
    folder=Path(sys.argv[2]);pid=os.getpid()
    os.write(1,f'\x1b[2J\x1b[HRECT_CHILD_{pid}'.encode())
    sys.argv=[str(root/'tests/mouse_fixture.py'),str(folder/f'{pid}.json'),
              str(folder/f'{pid}.control'),'180']
    runpy.run_path(sys.argv[0],run_name='__main__')


def rgb(bmp):
    width,height=struct.unpack_from('<ii',bmp,18);height=-height
    assert bmp[:2]==b'BM' and len(bmp)==54+width*height*4
    data=bmp[54:];pixels=bytearray(width*height*3)
    pixels[0::3],pixels[1::3],pixels[2::3]=data[2::4],data[1::4],data[0::4]
    return width,height,bytes(pixels)


def main():
    import re
    exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
    font=os.environ.get('NEMOTERM_TEST_FONT','Consolas' if os.environ.get('CI')=='true' else 'SarasaTermSC Nerd Font Light')
    evidence=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),font=font,
                  completed=False,injected=False,memory_acceptance=False,modes=[])
    scene=('\x1b[?25l\x1b]10;#ffffff\x1b\\\x1b]11;#123456\x1b\\\x1b[2J\x1b[H'
           'RECTANGLE 中文 e\u0301 👩\u200d💻\r\n\x1b[48;2;150;30;80m'
           'Colour band across clipped glyphs\x1b[0m\r\nאבג ابت\r\nEnd')
    try:
        for renderer in (0,1,2):
            item=dict(requested_renderer=renderer,checks=[],captures=[],completed=False)
            evidence['modes'].append(item)
            with saved_profile(dict(NemoRenderer=renderer,NemoTabs=1,WarnOnClose=0,
                                    CloseOnExit=1,FontHeight=12)) as args, \
                    tempfile.TemporaryDirectory(prefix='nemo-image-rect-') as tmp,OwnedJob() as job:
                folder=Path(tmp)
                process=job.spawn([str(exe),'--automation',*args,'--cols','80','--rows','24',
                    '--font',font,'-e',sys.executable,str(Path(__file__).resolve()),'--child',tmp],
                    env=dict(os.environ,NEMOTERM_CONPTY='bundled',NEMOTERM_TEST_EXACT_OUTPUT='1'),
                    creationflags=subprocess.CREATE_NO_WINDOW)
                try:
                    instance=wait_for(lambda:next(iter(api.discover(process.pid)),None))
                    endpoint=instance['endpoint'];first=instance['sessions'][0]
                    assert 'image-rectangle' in instance['capabilities']
                    item['actual_renderer']=first['renderer']
                    if renderer==0 or os.environ.get('NEMOTERM_REQUIRE_'+('OPENGL' if renderer==1 else 'DIRECTX'))=='1':
                        assert first['renderer']==renderer
                    serial=0
                    def target(sid):return next(s for s in api.request(endpoint)['sessions'] if s['id']==sid)
                    def identify(sid):
                        marker=wait_for(lambda:re.search(r'RECT_CHILD_(\d+)',api.request(endpoint,'text',sid)))
                        pid=int(marker[1]);wait_for(lambda:read_snapshot(folder/f'{pid}.json'))
                        return pid
                    def send(sid,pid,sequence):
                        nonlocal serial
                        serial+=1
                        write_snapshot(folder/f'{pid}.control',dict(phase=serial,sequence=sequence+'\x1b[5n'))
                        wait_snapshot(lambda:read_snapshot(folder/f'{pid}.json'),lambda a:
                            a.get('phase')==serial and b'\x1b[0n' in bytes.fromhex(a.get('hex','')))
                        u.SendMessageW(target(sid)['hwnd'],0x8,0,0)
                    def image(sid,rect=None):return api.request(endpoint,'image',sid,struct.pack('<IIII',*rect) if rect else b'')
                    def compare(sid,baseline,label):
                        width,height,pixels=rgb(baseline)
                        info=target(sid)
                        assert (width,height)==(info['client_width'],info['client_height'])
                        for rect in [(0,0,1,1),(1,1,37,39),(17,31,73,67),(width-9,height-7,9,7)]:
                            x,y,cw,ch=rect;started=time.perf_counter()
                            cropped=image(sid,rect);elapsed=time.perf_counter()-started
                            actual_width,actual_height,actual=rgb(cropped)
                            expected=b''.join(pixels[((y+dy)*width+x)*3:((y+dy)*width+x+cw)*3] for dy in range(ch))
                            assert (actual_width,actual_height)==(cw,ch)
                            assert actual==expected,(renderer,label,rect,hashlib.sha256(actual).hexdigest(),hashlib.sha256(expected).hexdigest())
                            item['captures'].append(dict(phase=label,rect=rect,seconds=elapsed,
                                                         rgb_sha256=hashlib.sha256(actual).hexdigest()))
                        item['checks'].append(label)
                    first_pid=identify(first['id']);send(first['id'],first_pid,scene)
                    baseline=image(first['id']);compare(first['id'],baseline,'active exact crop')
                    width,height,_=rgb(baseline)
                    for payload in [b'x',bytes(15),bytes(17),struct.pack('<IIII',0,0,0,1),
                                    struct.pack('<IIII',0,0,1,0),struct.pack('<IIII',width,0,1,1),
                                    struct.pack('<IIII',0,height,1,1),struct.pack('<IIII',width-1,0,2,1),
                                    struct.pack('<IIII',0,0,0xffffffff,1),struct.pack('<IIII',0xffffffff,0,1,1)]:
                        try:
                            api.request(endpoint,'image',first['id'],payload)
                            raise AssertionError('Invalid rectangle accepted')
                        except api.DebugError as error:assert error.status==1
                    item['checks'].append('invalid rectangles leave subsequent captures usable')
                    compare(first['id'],baseline,'capture after invalid requests')
                    output=folder/'cli.png';rect=(17,31,8,8)
                    subprocess.run([sys.executable,str(root/'tools/nemoterm_debug.py'),'image',
                        '--endpoint',endpoint,'--session',str(first['id']),'--rect',*map(str,rect),
                        '--output',str(output)],check=True,capture_output=True,timeout=10)
                    assert output.read_bytes()==api.png_from_bmp(image(first['id'],rect))
                    item['checks'].append('CLI rectangle PNG matches direct API')
                    send(first['id'],first_pid,'\x1b[?2026h\x1b[2J\x1b[HHidden update')
                    assert rgb(image(first['id']))==rgb(baseline)
                    compare(first['id'],baseline,'active synchronized presentation')
                    # Duplicate this fixture's command. New-tab deliberately
                    # launches the user's default shell instead.
                    u.SendMessageW(first['hwnd'],0x111,0x30,0)
                    sessions=wait_for(lambda:(s if len(s:=api.request(endpoint)['sessions'])==2 else None))
                    second=next(s for s in sessions if s['id']!=first['id'])
                    second_pid=identify(second['id']);send(second['id'],second_pid,scene+' sibling')
                    assert not target(first['id'])['active']
                    compare(first['id'],baseline,'inactive synchronized presentation')
                    send(first['id'],first_pid,'\x1b[?2026l')
                    changed=image(first['id']);assert rgb(changed)!=rgb(baseline)
                    compare(first['id'],changed,'inactive committed presentation')
                    api.request(endpoint,'key',second['id'],struct.pack('<II',9,3))
                    wait_for(lambda:target(first['id'])['active'])
                    compare(first['id'],image(first['id']),'reactivated presentation')
                    for pid in (first_pid,second_pid):write_snapshot(folder/f'{pid}.control',dict(stop=True))
                    assert process.wait(timeout=10)==0
                    item['cleanup']=job.finish(grace=5);assert not item['cleanup']['terminated_remaining']
                    item['completed']=True
                finally:
                    if sys.exc_info()[0]:item['error']=repr(sys.exc_info()[1])
                    item.setdefault('cleanup',job.finish(grace=0))
        evidence['completed']=True
    finally:
        (root/'research/image-rectangle-observed.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print('Rectangle captures passed:',[(m['requested_renderer'],m['actual_renderer'],len(m['captures'])) for m in evidence['modes']])


if __name__=='__main__':
    child() if len(sys.argv)>1 and sys.argv[1]=='--child' else main()
