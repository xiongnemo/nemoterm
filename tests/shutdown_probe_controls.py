"""Check observer sensitivity using opaque markers, never dangling reads."""
import argparse
import frida
from native_test_utils import (root, Path, os, sys, subprocess, tempfile,
    hashlib, wait_for, read_snapshot, write_snapshot)
from owned_job import OwnedJob
from frida_test_utils import detach_session

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--executable',type=Path,required=True)
args=parser.parse_args()
exe=args.executable.resolve()
probe=(root/'tests/shutdown_probe.js').read_text(encoding='utf-8')
record=dict(completed=False,executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
            probe_sha256=hashlib.sha256(probe.encode()).hexdigest(),cases=[])
try:
    for mode in ('ordered','free-before-window','free-after-com'):
        item=dict(mode=mode,events=[],completed=False);record['cases'].append(item)
        with tempfile.TemporaryDirectory(prefix='nemo-shutdown-observer-') as folder,OwnedJob() as job:
            ready=Path(folder)/'ready.json'
            process=job.spawn([str(exe),mode,str(ready)],stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            session=None
            try:
                window=wait_for(lambda:read_snapshot(ready))['hwnd']
                session=frida.attach(process.pid)
                script=session.create_script(probe)
                script.on('message',lambda message,data: item['events'].append(
                    message['payload'] if message['type']=='send' else message))
                script.load();script.exports_sync.watch(hex(window))
                process.stdin.write(b'G');process.stdin.flush();process.stdin.close()
                item['exit_code']=process.wait(timeout=10)
                assert item['exit_code']==0,item
                wait_for(lambda:any(e.get('event')=='com-uninitialize-return' for e in item['events']))
                events=item['events'];freed=[e for e in events if e.get('event')=='seat-free']
                returned=[e for e in events if e.get('event')=='com-uninitialize-return']
                late=[e for e in events if e.get('event')=='callback-after-seat-free']
                assert len(returned)==1 and sorted(returned[0]['detached_observers'])==['com','heap','window'],item
                assert not returned[0]['window_alive'],item
                assert not any(e.get('type')=='error' for e in events),item
                if mode=='ordered':
                    assert len(freed)==1 and freed[0]['success'] and not freed[0]['window_alive'],item
                    assert returned[0]['seat_freed'] and not late,item
                elif mode=='free-before-window':
                    assert len(freed)==1 and freed[0]['success'] and freed[0]['window_alive'],item
                    assert returned[0]['seat_freed'] and any(e['message']==0x8000+71 for e in late),item
                else:
                    assert not freed and not returned[0]['seat_freed'],item
                item['cleanup']=job.finish(grace=5)
                assert not item['cleanup']['terminated_remaining'],item
                item['completed']=True
            finally:
                try:
                    if session:detach_session(session)
                finally:
                    item.setdefault('cleanup',job.finish(grace=0))
        print('Shutdown observer control:',mode,'passed',flush=True)
    record['completed']=True
finally:
    if sys.exc_info()[0]:record['error']=repr(sys.exc_info()[1])
    write_snapshot(root/'research/shutdown-probe-controls-observed.json',record)
