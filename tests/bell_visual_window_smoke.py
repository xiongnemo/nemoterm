"""Observe visual BEL pixels and restoration through an owned renderer surface."""
from native_test_utils import *
from protocol_oracle_window import saved_profile
from owned_job import OwnedJob
sys.path.insert(0,str(root/'tools'))
import nemoterm_debug as api

exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
font=os.environ.get('NEMOTERM_TEST_FONT','Consolas' if os.environ.get('CI')=='true' else 'SarasaTermSC Nerd Font Light')
record=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
            font=font,memory_acceptance=False,injected=False,physical_desktop_capture=False,modes=[])
scene='\x1b[?25l\x1b]10;#cba987\x07\x1b]11;#123456\x07\x1b[2J\x1b[HVisual bell pixel fixture'
normal=bytes.fromhex('563412');flashed=bytes.fromhex('87a9cb')
def patch(bmp):
    width,height=struct.unpack_from('<ii',bmp,18);height=-height
    assert bmp[:2]==b'BM' and struct.unpack_from('<I',bmp,10)[0]==54 and len(bmp)==54+width*height*4
    x,y=width*3//4,height*3//4
    pixels=[bmp[54+((y+dy)*width+x+dx)*4:57+((y+dy)*width+x+dx)*4] for dy in range(8) for dx in range(8)]
    assert all(p==pixels[0] for p in pixels)
    return pixels[0]

try:
    for renderer,mode in ((0,2),(1,2),(2,2),(0,0)):
        item=dict(requested_renderer=renderer,bell_mode=mode,completed=False,phases=[]);record['modes'].append(item)
        with saved_profile(dict(NemoRenderer=renderer,NemoTabs=0,Beep=mode,BellOverload=0,WarnOnClose=0,FontHeight=12)) as args, \
                tempfile.TemporaryDirectory(prefix='nemo-vbell-') as tmp,OwnedJob() as job:
            report,control=Path(tmp)/'report.json',Path(tmp)/'control.json'
            process=job.spawn([str(exe),'--automation',*args,'--cols','80','--rows','24',
                '--font',font,'-e',sys.executable,str(root/'tests/mouse_fixture.py'),str(report),str(control),'90'],
                env=dict(os.environ,NEMOTERM_CONPTY='bundled',NEMOTERM_TEST_EXACT_OUTPUT='1'),creationflags=subprocess.CREATE_NO_WINDOW)
            item['pid']=process.pid
            try:
                wait_for(lambda:read_snapshot(report))
                instance=wait_for(lambda:next(iter(api.discover(process.pid)),None));assert instance['pid']==process.pid
                target=next(s for s in instance['sessions'] if s['active']);item['actual_renderer']=target['renderer']
                if os.environ.get('NEMOTERM_REQUIRE_DIRECTX')=='1' and renderer==2:assert target['renderer']==2
                if os.environ.get('NEMOTERM_REQUIRE_OPENGL')=='1' and renderer==1:assert target['renderer']==1
                def image():return api.request(instance['endpoint'],'image',target['id'])
                def ready(phase):
                    return wait_snapshot(lambda:read_snapshot(report),lambda a:a.get('phase')==phase and bytes.fromhex(a.get('hex','')).endswith(b'\x1b[0n'))
                write_snapshot(control,dict(phase='initial',sequence=scene+'\x1b[5n'));ready('initial')
                wait_for(lambda:patch(image())==normal)
                for label,sequence in [('osc-terminator','\x1b]2;visual bell fixture\x07'),('ordinary-bel','\x07')]:
                    observation=dict(name=label,samples=[]);item['phases'].append(observation)
                    frames={};start=time.monotonic()
                    write_snapshot(control,dict(phase=label,sequence=sequence+'\x1b[5n'))
                    while time.monotonic()-start<.8:
                        bmp=image();pixel=patch(bmp);elapsed=time.monotonic()-start
                        observation['samples'].append(dict(seconds=elapsed,bgr=pixel.hex()))
                        frames.setdefault(pixel,bmp)
                        time.sleep(.005)
                    observation['wire']=ready(label)
                    observed=set(frames);expect_flash=mode==2 and label=='ordinary-bel'
                    assert observed==({normal,flashed} if expect_flash else {normal}),observation
                    assert observation['samples'][-1]['bgr']==normal.hex(),observation
                    if expect_flash:
                        for colour,bmp in frames.items():
                            name=f'visual-bell-{renderer}-'+('flash' if colour==flashed else 'normal')+'.png'
                            (root/'research'/name).write_bytes(api.png_from_bmp(bmp))
                        observation['flash_sample_count']=sum(s['bgr']==flashed.hex() for s in observation['samples'])
                write_snapshot(control,dict(stop=True));assert process.wait(timeout=10)==0
                item['cleanup']=job.finish(grace=5);assert not item['cleanup']['terminated_remaining']
                item['completed']=True
            finally:
                if sys.exc_info()[0]:item['error']=repr(sys.exc_info()[1])
                item.setdefault('cleanup',job.finish(grace=0))
finally:
    (root/'research/visual-bell-observed.json').write_text(json.dumps(record,indent=2)+'\n')
print('Visual bell pixels passed:',[(m['requested_renderer'],m['actual_renderer'],m['bell_mode']) for m in record['modes']])
