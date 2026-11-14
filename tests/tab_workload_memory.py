"""External process-tree sampling and bounded tab workloads, without injection.

No clipboard, cursor movement, working-set trimming, or capture helper is used.
Summed working sets count shared pages in each process; they are not physical
machine RAM. The Python workload clients are reported separately from the app.
"""
from native_test_utils import time, threading, os, Path, w, c, u
from console_process_utils import owned_processes, workload_process_role


class TabMemorySampler:
    def __init__(self, pid, executable, interval=.1, injected=False, kernel_etw_recording=False):
        self.pid = pid
        self.executable = os.path.normcase(str(Path(executable).resolve()))
        self.interval = interval
        # A diagnostic caller conservatively labels the entire run, including
        # its startup samples, when it will inject into the observed frontend.
        self.injected = injected
        self.kernel_etw_recording = kernel_etw_recording
        self.phase = 'startup'
        self.started = time.monotonic()
        self.samples = []
        self.errors = []
        self.exited_during_sample = []
        self.done = threading.Event()
        self.worker = threading.Thread(target=self._run, daemon=True)
        self.worker.start()

    def _run(self):
        while not self.done.is_set():
            started = time.monotonic()
            try:
                phase = self.phase
                exited=[]
                processes = owned_processes(self.pid,exited=exited)
                self.exited_during_sample.extend(dict(seconds=round(started-self.started,4),phase=phase,**p)
                                                for p in exited)
                assert any(p['pid'] == self.pid for p in processes), 'Owned root missing'
                groups = {name: dict(count=0, private_ws=0, total_ws=0, private_commit=0)
                          for name in ('frontend','hosts','clients','all')}
                for process in processes:
                    role = workload_process_role(process, self.pid, self.executable)
                    process['role'] = role
                    for group in (groups[role],groups['all']):
                        group['count'] += 1
                        for key,value in process['memory'].items():
                            group[key] += value
                self.samples.append(dict(seconds=round(started-self.started,4), phase=phase,
                                         injected=self.injected, groups=groups, processes=processes))
            except Exception as error:
                self.errors.append(dict(seconds=round(started-self.started,4), error=repr(error)))
                return
            self.done.wait(max(0,self.interval-(time.monotonic()-started)))

    def stop(self):
        self.done.set()
        self.worker.join(timeout=10)
        assert not self.worker.is_alive(), 'Memory sampler did not stop'
        peaks = {role: {key:max((s['groups'][role][key] for s in self.samples),default=0)
                        for key in ('count','private_ws','total_ws','private_commit')}
                 for role in ('frontend','hosts','clients','all')}
        return dict(interval_seconds=self.interval, sample_count=len(self.samples),
                    seconds=round(time.monotonic()-self.started,3), errors=self.errors,
                    exited_during_sample=self.exited_during_sample,
                    injected=self.injected, kernel_etw_recording=self.kernel_etw_recording,
                    diagnostic_only=self.injected or self.kernel_etw_recording,
                    peaks=peaks, samples=self.samples,
                    scope='Synthetic dense text, bounded scrollback, links, images, tab lifetime and resize; not a real agent or physical hover acceptance.',
                    totals_note='Summed process working sets include shared pages more than once; host and client totals are separate from the frontend threshold.')


def exercise(sampler, first, second, output, select, resources, host, scene, inline_images=False, animated_images=False):
    """Keep two 2000-line histories while switching/repainting/resizing."""
    result = dict(history_lines_per_tab=4096, history_limit=2000,
                  redraw_frames=24, resize_transitions=24, inline_images=inline_images,
                  animated_images=animated_images, samples=[])
    assert not (inline_images and animated_images)
    if inline_images:
        from iterm_image_window_smoke import png, transfer
        inline = transfer(png(512,288,bytes((255,0,0,128))*512*288))
    if animated_images:
        from gif_fixture import gif, frame
        from iterm_image_window_smoke import transfer
        import hashlib
        encoded=gif(256,144,[frame(256,144,colour=colour,delay=10) for colour in (1,2,3,0)],repeats=0)
        inline=transfer(encoded,'width=512px;height=288px;preserveAspectRatio=0')
        result['animation']=dict(frames=4,canvas=[256,144],display=[512,288],
            frame_delay_ms=100,plays='infinite',frame_pixel_bytes=4*256*144*4,
            encoded_bytes=len(encoded),encoded_sha256=hashlib.sha256(encoded).hexdigest())
    for tab_index,child in enumerate((first,second)):
        select(child,tab_index)
        sampler.phase = f'history-{tab_index}'
        output(child,'\x1b[?1049l\x1b[?2027h\x1b[2J\x1b[H')
        for batch in range(32):
            rows = []
            for item in range(128):
                serial = batch*128+item
                rows.append(f'\x1b[38;2;{serial%256};120;180m{serial:05d} '
                            f'\x1b]8;;https://example.invalid/{tab_index}/{serial}\x1b\\'
                            'source 文件 e\u0301 אבג ابت \x1b]8;;\x1b\\'
                            ' | streaming output with distinct line numbers and links\x1b[0m\r\n')
            output(child,''.join(rows))
        result['samples'].append(dict(phase=sampler.phase, **resources()))

    original = w.RECT()
    assert u.GetWindowRect(host,c.byref(original))
    width,height = original.right-original.left,original.bottom-original.top
    for frame in range(24):
        sampler.phase = f'frame-{frame}'
        child = (first,second)[frame%2]
        select(child,frame%2)
        # Full-frame changes retain history and exercise dense font caches.
        output(child,scene(f'WORKLOAD {frame}','20;40;70'))
        # One sizeable Sixel per retained terminal, rebuilt through normal VT.
        output(child,'\x1b[2;4H\x1bP0;1q"1;1;512;288#1;2;20;40;70#1'+
                     ('!512~-')*48+'\x1b\\')
        if inline_images or animated_images:
            output(child,inline)
        target = (max(400,width-160),max(300,height-100)) if frame%2 == 0 else (width,height)
        assert u.MoveWindow(host,original.left,original.top,*target,True)
        for other in (first,second):
            output(other,'\x1b[18t')
        result['samples'].append(dict(phase=sampler.phase, **resources()))
        time.sleep(.12)
    sampler.phase = 'settled'
    time.sleep(.5)
    result['samples'].append(dict(phase='settled', **resources()))
    return result


def verify_animation(pid, children, select, observations, prefix):
    """Pixel evidence after sampling; never load capture buffers into the gate."""
    from native_test_utils import root, sys, struct, hashlib, wait_for
    sys.path.insert(0,str(root/'tools'))
    import nemoterm_debug as api
    instance=wait_for(lambda:next(iter(api.discover(pid)),None))
    assert instance['pid']==pid
    for index,child in enumerate(children):
        select(child,index)
        current=api.request(instance['endpoint'],'list')
        target=next(s for s in current['sessions'] if s['hwnd']==child['hwnd'])
        assert target['active']
        record=dict(session=target['id'],hwnd=child['hwnd'],renderer=target['renderer'],
                    injected=False,after_memory_sampling=True,captures=0,frames=[])
        observations.append(record)
        colours={bytes((0,0,255)):'red',bytes((0,255,0)):'green',bytes((255,0,0)):'blue'}
        seen=set();started=time.monotonic();deadline=started+3
        while seen!=set(colours.values()) and time.monotonic()<deadline:
            bmp=api.request(instance['endpoint'],'image',target['id'])
            width,height=struct.unpack_from('<ii',bmp,18);height=-height
            offset=struct.unpack_from('<I',bmp,10)[0]
            assert bmp[:2]==b'BM' and offset==54 and len(bmp)==54+width*height*4
            # The fixture places a 512x288 image at cell (3,2). This interior
            # patch stays inside it across the workload's 100px height changes.
            cw,ch=(width-2)//target['cols'],(height-2)//target['rows']
            x,y=1+2*cw+256,1+ch+144
            assert x+8<=width and y+8<=height
            pixels=[bmp[offset+((y+dy)*width+x+dx)*4:offset+((y+dy)*width+x+dx)*4+3]
                    for dy in range(8) for dx in range(8)]
            record['captures']+=1
            colour=colours.get(pixels[0])
            if colour and colour not in seen and all(p==pixels[0] for p in pixels):
                seen.add(colour);name=f'{prefix}-tab-{index}-{colour}.png'
                (root/'research'/name).write_bytes(api.png_from_bmp(bmp))
                record['frames'].append(dict(colour=colour,seconds=time.monotonic()-started,
                    image=name,bmp_sha256=hashlib.sha256(bmp).hexdigest(),patch=[x,y,8,8]))
            time.sleep(.025)
        record['seconds']=time.monotonic()-started
        assert seen==set(colours.values()),record
