"""Validate NT handle metadata against named handle values in an owned worker."""
import argparse,ctypes as c,json,queue,subprocess,sys,tempfile,threading
from ctypes import wintypes as w
from pathlib import Path
from owned_job import OwnedJob

def worker(folder):
    k=c.WinDLL('kernel32',use_last_error=True)
    k.CreateEventW.argtypes=[c.c_void_p,w.BOOL,w.BOOL,w.LPCWSTR];k.CreateEventW.restype=w.HANDLE
    k.CreateSemaphoreW.argtypes=[c.c_void_p,w.LONG,w.LONG,w.LPCWSTR];k.CreateSemaphoreW.restype=w.HANDLE
    k.CreateMutexW.argtypes=[c.c_void_p,w.BOOL,w.LPCWSTR];k.CreateMutexW.restype=w.HANDLE
    k.CreateFileMappingW.argtypes=[w.HANDLE,c.c_void_p,w.DWORD,w.DWORD,w.DWORD,w.LPCWSTR];k.CreateFileMappingW.restype=w.HANDLE
    k.CreatePipe.argtypes=[c.POINTER(w.HANDLE),c.POINTER(w.HANDLE),c.c_void_p,w.DWORD]
    k.CreateFileW.argtypes=[w.LPCWSTR,w.DWORD,w.DWORD,c.c_void_p,w.DWORD,w.DWORD,w.HANDLE];k.CreateFileW.restype=w.HANDLE
    k.CloseHandle.argtypes=[w.HANDLE]
    k.GetCurrentProcess.restype=w.HANDLE
    k.GetProcessHandleCount.argtypes=[w.HANDLE,c.POINTER(w.DWORD)]
    handles=[];ledger=[]
    def count(label):
        value=w.DWORD()
        if not k.GetProcessHandleCount(k.GetCurrentProcess(),c.byref(value)):raise c.WinError(c.get_last_error())
        ledger.append(dict(label=label,count=value.value))
    def add(handle,kind):
        if not handle or handle==c.c_void_p(-1).value:raise c.WinError(c.get_last_error())
        handles.append(dict(handle=int(handle),type=kind))
        count(kind)
    print(json.dumps(dict(stage='ready')),flush=True)
    try:
        for line in sys.stdin:
            command=line.strip()
            ledger=[];count('before-'+command)
            if command=='prepare-pipe':
                # On this Windows build the first CreatePipe also initializes
                # a retained File handle. Record that setup outside the exact
                # controlled eight-handle delta; do not relax its assertions.
                read,write=w.HANDLE(),w.HANDLE()
                if not k.CreatePipe(c.byref(read),c.byref(write),None,0):raise c.WinError(c.get_last_error())
                count('pipe-created')
                for handle in (read,write):
                    if not k.CloseHandle(handle):raise c.WinError(c.get_last_error())
                count('pipe-closed')
            elif command=='create':
                assert not handles
                add(k.CreateEventW(None,True,False,None),'Event');add(k.CreateEventW(None,False,False,None),'Event')
                add(k.CreateSemaphoreW(None,0,2,None),'Semaphore');add(k.CreateMutexW(None,False,None),'Mutant')
                add(k.CreateFileMappingW(w.HANDLE(-1),None,4,0,65536,None),'Section')
                read,write=w.HANDLE(),w.HANDLE()
                if not k.CreatePipe(c.byref(read),c.byref(write),None,0):raise c.WinError(c.get_last_error())
                add(read.value,'File');add(write.value,'File')
                add(k.CreateFileW(str(folder/'owned-handle.tmp'),0xc0000000,7,None,2,0x04000100,None),'File')
            elif command=='close':
                for item in handles:
                    if not k.CloseHandle(item['handle']):raise c.WinError(c.get_last_error())
                handles=[]
            elif command=='exit':break
            elif command=='ping':pass
            else:raise ValueError(command)
            print(json.dumps(dict(stage=command,handles=handles,ledger=ledger)),flush=True)
    finally:
        for item in handles:k.CloseHandle(item['handle'])

def main(output):
    from handle_snapshot import OwnedHandleSnapshot,compare
    result=dict(completed=False,checks=[],snapshots=[]);job=None
    try:
        with tempfile.TemporaryDirectory(prefix='nemoterm-handle-test-') as tmp,OwnedJob() as job:
            child=job.spawn([sys.executable,__file__,'--worker',tmp],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
            lines=queue.Queue()
            def reader():
                for line in child.stdout:lines.put(line)
                lines.put(None)
            thread=threading.Thread(target=reader,daemon=True);thread.start()
            def receive(stage):
                line=lines.get(timeout=8)
                if line is None:raise RuntimeError(('Owned worker exited',child.poll()))
                value=json.loads(line);assert value['stage']==stage,value;return value
            def command(value):
                child.stdin.write(value+'\n');child.stdin.flush();return receive(value)
            receive('ready')
            result['handshake']=command('ping')
            result['pipe_preparation']=command('prepare-pipe')
            observer=OwnedHandleSnapshot(child,job)
            baseline=observer.snapshot('baseline');result['snapshots'].append(baseline)
            assert baseline['count']==baseline['public_count_before']==baseline['public_count_after']
            result['checks'].append('Process-local snapshot agrees with independent Win32 count')
            with OwnedJob() as wrong:
                try:OwnedHandleSnapshot(child,wrong)
                except RuntimeError as exc:assert 'does not belong' in str(exc)
                else:raise AssertionError('Wrong job accepted')
            result['checks'].append('Nonmember process rejected before catalogue or handle query')
            result['created']=command('create');created=result['created']['handles']
            live=observer.snapshot('allocated');result['snapshots'].append(live)
            by_value={e['handle']:e for e in live['entries']}
            for expected in created:assert by_value[expected['handle']]['type']==expected['type'],(expected,by_value)
            assert len(created)==8 and live['count']-baseline['count']==8
            delta=compare(baseline,live);assert delta['type_deltas']==dict(Event=2,File=3,Mutant=1,Section=1,Semaphore=1),delta
            result['checks'].append('Eight controlled event, semaphore, mutex, section, file and pipe handles have correct types and deltas')
            result['allocated_delta']=delta
            for index in range(10):
                repeat=observer.snapshot('repeat-'+str(index));assert repeat['count']==live['count']
            result['checks'].append('Ten snapshots add no target handles')
            command('close');closed=observer.snapshot('closed');result['snapshots'].append(closed)
            assert closed['count']==baseline['count']
            assert all(e['handle'] not in {x['handle'] for x in closed['entries']} for e in created)
            result['checks'].append('Closed controlled handles disappear and count returns to baseline')
            child.stdin.write('exit\n');child.stdin.flush();child.wait(timeout=8)
            assert child.returncode==0,child.stderr.read()
            thread.join(2);assert not thread.is_alive()
            try:observer.snapshot('after-exit')
            except RuntimeError as exc:assert 'no longer running' in str(exc)
            else:raise AssertionError('Exited process accepted')
            result['checks'].append('Exited retained process is rejected')
            result['cleanup']=job.finish(grace=2);assert not result['cleanup']['terminated_remaining']
            result['completed']=True
    finally:
        if job is not None and job.cleanup is not None:result['cleanup']=job.cleanup
        error=sys.exc_info()[1]
        if error:result['error']=repr(error)
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('Owned handle metadata:',len(result['checks']),'checks passed')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--worker',type=Path)
    parser.add_argument('--output',type=Path,default=Path('research/handle-snapshot-native.json'))
    args=parser.parse_args()
    if args.worker:worker(args.worker)
    else:main(args.output)
