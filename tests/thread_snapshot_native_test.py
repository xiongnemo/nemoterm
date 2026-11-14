"""Validate owned thread snapshots against two explicitly created native threads."""
import argparse,ctypes as c,json,queue,subprocess,sys,threading
from ctypes import wintypes as w
from pathlib import Path
from owned_job import OwnedJob

def worker():
    k=c.WinDLL('kernel32',use_last_error=True)
    callback_type=c.WINFUNCTYPE(w.DWORD,c.c_void_p)
    k.CreateThread.argtypes=[c.c_void_p,c.c_size_t,callback_type,c.c_void_p,w.DWORD,c.POINTER(w.DWORD)]
    k.CreateThread.restype=w.HANDLE
    k.CreateEventW.argtypes=[c.c_void_p,w.BOOL,w.BOOL,w.LPCWSTR];k.CreateEventW.restype=w.HANDLE
    k.SetEvent.argtypes=k.CloseHandle.argtypes=[w.HANDLE]
    k.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD];k.WaitForSingleObject.restype=w.DWORD
    k.GetThreadTimes.argtypes=[w.HANDLE]+[c.POINTER(w.FILETIME)]*4
    k.GetCurrentProcess.restype=w.HANDLE
    k.GetProcessHandleCount.argtypes=[w.HANDLE,c.POINTER(w.DWORD)]
    @callback_type
    def run(event):return 0 if k.WaitForSingleObject(event,15000)==0 else 1
    known=[]
    def close(item):
        assert k.SetEvent(item['event'])
        assert k.WaitForSingleObject(item['handle'],2000)==0
        assert k.CloseHandle(item['handle']) and k.CloseHandle(item['event'])
    def reply(stage):
        count=w.DWORD();assert k.GetProcessHandleCount(k.GetCurrentProcess(),c.byref(count))
        print(json.dumps(dict(stage=stage,threads=known,handles=count.value)),flush=True)
    reply('ready')
    try:
        for line in sys.stdin:
            command=line.strip()
            if command=='create':
                assert not known
                for _ in range(2):
                    event=k.CreateEventW(None,True,False,None);assert event
                    tid=w.DWORD();handle=k.CreateThread(None,0,run,event,0,c.byref(tid));assert handle
                    times=[w.FILETIME() for _ in range(4)]
                    assert k.GetThreadTimes(handle,*(c.byref(t) for t in times))
                    known.append(dict(tid=tid.value,created=times[0].dwLowDateTime|(times[0].dwHighDateTime<<32),
                        start=c.cast(run,c.c_void_p).value,handle=int(handle),event=int(event)))
            elif command=='close-one':close(known.pop(0))
            elif command=='close':
                for item in known:close(item)
                known=[]
            elif command=='exit':break
            elif command!='ping':raise ValueError(command)
            reply(command)
    finally:
        for item in known:close(item)

def main(output):
    from thread_snapshot import OwnedThreadSnapshot
    from handle_snapshot import k
    k.GetCurrentProcess.restype=w.HANDLE
    result=dict(completed=False,checks=[],snapshots=[]);job=None;lease=None
    try:
        with OwnedJob() as job:
            child=job.spawn([sys.executable,__file__,'--worker'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
            lines=queue.Queue()
            def reader():
                for line in child.stdout:lines.put(line)
                lines.put(None)
            reader_thread=threading.Thread(target=reader,daemon=True);reader_thread.start()
            def receive(stage):
                line=lines.get(timeout=8)
                if line is None:raise RuntimeError(('Worker exited',child.poll()))
                value=json.loads(line);assert value['stage']==stage,value;return value
            def command(value):
                child.stdin.write(value+'\n');child.stdin.flush();return receive(value)
            receive('ready');observer=OwnedThreadSnapshot(child,job)
            with OwnedJob() as wrong:
                try:OwnedThreadSnapshot(child,wrong)
                except RuntimeError as exc:assert 'does not belong' in str(exc)
                else:raise AssertionError('Wrong owned job accepted')
            result['checks'].append('Wrong-job process rejected before thread observation')
            baseline=observer.snapshot('baseline');result['snapshots'].append(baseline)
            created=command('create');result['created']=created
            live=observer.snapshot('live');result['snapshots'].append(live)
            by_tid={t['tid']:t for t in live['threads']}
            for expected in created['threads']:
                actual=by_tid[expected['tid']]
                assert all(actual[key]==expected[key] for key in ('tid','created','start')),(actual,expected)
                assert not actual['exited']
            assert len(live['threads'])==len(baseline['threads'])+2
            assert not live['unavailable']
            result['checks'].append('Two native threads have exact independent IDs, creation times and start addresses')
            lease_before=w.DWORD();lease_after=w.DWORD()
            assert k.GetProcessHandleCount(k.GetCurrentProcess(),c.byref(lease_before))
            mismatched=[dict(t) for t in created['threads']];mismatched[1]['created']+=1
            try:observer.retain(mismatched)
            except RuntimeError as exc:assert 'creation identity changed' in str(exc)
            else:raise AssertionError('Wrong thread generation accepted')
            assert k.GetProcessHandleCount(k.GetCurrentProcess(),c.byref(lease_after))
            assert lease_before.value==lease_after.value
            lease=observer.retain(created['threads'])
            assert lease.states()==[258,258] and not lease.wait(0)
            result['checks'].append('Retained thread handles reject mismatched generations without leaking partial acquisitions')
            own_before=w.DWORD();own_after=w.DWORD()
            assert k.GetProcessHandleCount(k.GetCurrentProcess(),c.byref(own_before))
            for index in range(10):
                snapshot=observer.snapshot('repeat-'+str(index))
                assert snapshot['threads']==live['threads'] and not snapshot['unavailable']
            assert k.GetProcessHandleCount(k.GetCurrentProcess(),c.byref(own_after))
            assert own_before.value==own_after.value
            assert command('ping')['handles']==created['handles']
            result['checks'].append('Ten snapshots add no observer or target handles and preserve stable thread identities')
            one=command('close-one');after_one=observer.snapshot('one-closed');result['snapshots'].append(after_one)
            remaining={(t['tid'],t['created']) for t in after_one['threads']}
            gone,kept=created['threads']
            assert (gone['tid'],gone['created']) not in remaining
            assert (kept['tid'],kept['created']) in remaining
            assert len(after_one['threads'])==len(baseline['threads'])+1
            assert lease.states()==[0,258] and not lease.wait(0)
            result['checks'].append('Signalled-and-joined thread disappears while its sibling remains alive')
            command('close');closed=observer.snapshot('closed');result['snapshots'].append(closed)
            assert [(t['tid'],t['created']) for t in closed['threads']]==[(t['tid'],t['created']) for t in baseline['threads']]
            assert lease.wait(2000) and lease.states()==[0,0]
            lease.close();lease=None
            assert k.GetProcessHandleCount(k.GetCurrentProcess(),c.byref(lease_after))
            assert lease_before.value==lease_after.value
            result['checks'].append('Bounded wait proves both retained thread objects signalled and releases all observer handles')
            result['checks'].append('Both controlled thread lifetimes return to the exact baseline identities')
            child.stdin.write('exit\n');child.stdin.flush();assert child.wait(timeout=8)==0,child.stderr.read()
            reader_thread.join(2);assert not reader_thread.is_alive()
            try:observer.snapshot('after-exit')
            except RuntimeError as exc:assert 'no longer running' in str(exc)
            else:raise AssertionError('Exited target accepted')
            result['checks'].append('Exited retained process rejected')
            result['cleanup']=job.finish(grace=2);assert not result['cleanup']['terminated_remaining']
            result['completed']=True
    finally:
        if lease:lease.close()
        if job is not None and job.cleanup is not None:result['cleanup']=job.cleanup
        if sys.exc_info()[1]:result['error']=repr(sys.exc_info()[1])
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('Owned thread metadata:',len(result['checks']),'checks passed')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--worker',action='store_true')
    parser.add_argument('--output',type=Path,default=Path('research/thread-snapshot-native.json'))
    args=parser.parse_args()
    worker() if args.worker else main(args.output)
