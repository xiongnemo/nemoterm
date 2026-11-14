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


def exercise(sampler, first, second, output, select, resources, host, scene, inline_images=False):
    """Keep two 2000-line histories while switching/repainting/resizing."""
    result = dict(history_lines_per_tab=4096, history_limit=2000,
                  redraw_frames=24, resize_transitions=24, inline_images=inline_images, samples=[])
    if inline_images:
        from iterm_image_window_smoke import png, transfer
        inline = transfer(png(512,288,bytes((255,0,0,128))*512*288))
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
        if inline_images:
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
