"""Verify traced generations and closes against an owned Windows worker."""
import argparse
import ctypes as c
from ctypes import wintypes as w
import json
import faulthandler
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
from owned_job import OwnedJob


def worker():
    k = c.WinDLL('kernel32', use_last_error=True)
    k.CreateEventW.argtypes = [c.c_void_p, w.BOOL, w.BOOL, w.LPCWSTR]
    k.OpenEventW.argtypes = [w.DWORD, w.BOOL, w.LPCWSTR]
    k.OpenEventW.restype = w.HANDLE
    k.CreateSemaphoreW.argtypes = [c.c_void_p, w.LONG, w.LONG, w.LPCWSTR]
    k.CreateWaitableTimerW.argtypes = [c.c_void_p, w.BOOL, w.LPCWSTR]
    k.CreateIoCompletionPort.argtypes = [w.HANDLE, w.HANDLE, c.c_size_t, w.DWORD]
    for name in ('CreateEventW','CreateSemaphoreW','CreateWaitableTimerW','CreateIoCompletionPort'):
        getattr(k, name).restype = w.HANDLE
    k.CloseHandle.argtypes = [w.HANDLE]
    k.DuplicateHandle.argtypes = [w.HANDLE,w.HANDLE,w.HANDLE,c.POINTER(w.HANDLE),w.DWORD,w.BOOL,w.DWORD]
    handles = []
    event_name = 'Local\\NemotermTraceValidation.' + str(os.getpid())
    print(json.dumps(dict(stage='ready')), flush=True)
    try:
        for line in sys.stdin:
            command = line.strip()
            if command == 'create':
                assert not handles
                for value, kind in ((k.CreateEventW(None,False,False,event_name),'Event'),
                        (k.CreateEventW(None,True,False,None),'Event'),
                        (k.CreateSemaphoreW(None,0,2,None),'Semaphore'),
                        (k.CreateWaitableTimerW(None,False,None),'Timer'),
                        (k.CreateIoCompletionPort(w.HANDLE(-1),None,0,1),'IoCompletion')):
                    if not value:raise c.WinError(c.get_last_error())
                    handles.append(dict(handle=int(value),type=kind))
                duplicate=w.HANDLE()
                if not k.DuplicateHandle(w.HANDLE(-1),handles[0]['handle'],w.HANDLE(-1),c.byref(duplicate),0,False,2):
                    raise c.WinError(c.get_last_error())
                handles.append(dict(handle=duplicate.value,type='Event',operation='duplicate'))
                opened=k.OpenEventW(0x1f0003,False,event_name)
                if not opened:raise c.WinError(c.get_last_error())
                handles.append(dict(handle=opened,type='Event',api='NtOpenEvent'))
            elif command == 'close':
                for item in handles:
                    if not k.CloseHandle(item['handle']):raise c.WinError(c.get_last_error())
                handles = []
            elif command == 'exit':break
            else:raise ValueError(command)
            print(json.dumps(dict(stage=command,handles=handles)),flush=True)
    finally:
        for item in handles:k.CloseHandle(item['handle'])


def main(output):
    from handle_trace import OwnedHandleTrace
    result = dict(completed=False,checks=[],rounds=[])
    trace = None; job = None
    try:
        with OwnedJob() as job:
            child = job.spawn([sys.executable,__file__,'--worker'],stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',
                creationflags=subprocess.CREATE_NO_WINDOW)
            lines = queue.Queue()
            def reader():
                for line in child.stdout:lines.put(line)
                lines.put(None)
            thread = threading.Thread(target=reader,daemon=True);thread.start()
            def receive(stage):
                line = lines.get(timeout=8)
                if line is None:raise RuntimeError(('worker exited',child.poll()))
                value=json.loads(line);assert value['stage']==stage,value;return value
            def command(value):
                child.stdin.write(value+'\n');child.stdin.flush();return receive(value)
            receive('ready')
            trace = OwnedHandleTrace(child,job,output.with_name('trace.json'))
            for index in range(20):
                before=trace.mark('before-'+str(index));created=command('create')
                middle=trace.mark('created-'+str(index));command('close')
                after=trace.mark('closed-'+str(index))
                result['rounds'].append(dict(before=before,middle=middle,after=after,created=created))
            capture=trace.close();trace=None
            assert capture['completed'] and capture['detached'],capture
            events=capture['trace']['events'];generations=set();values=[]
            for item in result['rounds']:
                for expected in item['created']['handles']:
                    created=[e for e in events if e['operation']==expected.get('operation','create') and
                        item['before']<e['sequence']<item['middle'] and int(e['handle'],16)==expected['handle']]
                    assert len(created)==1 and created[0]['type']==expected['type'],created
                    event=created[0];assert event['frames'] and event['caller']!='0x0',event
                    if expected.get('api'):assert event['api']==expected['api'],event
                    assert event['sequence'] not in generations
                    generations.add(event['sequence']);values.append(expected['handle'])
                    closed=[e for e in events if e['operation']=='close' and
                        item['middle']<e['sequence']<item['after'] and e['generation']==event['sequence']]
                    assert len(closed)==1,closed
            assert len(generations)==140
            result['checks'].append('100 known creations, 20 local duplicates and 20 opens have exact types, caller frames and unique generation ids')
            result['checks'].append('All 140 known generations close exactly once within their controlled phase')
            result['reused_handle_values']=len(values)-len(set(values))
            assert result['reused_handle_values']>0
            result['checks'].append('Repeated native handle values retain distinct creation and close generations')
            result['checks'].append('No trace overflow, script error or duration expiry; session detached')
            child.stdin.write('exit\n');child.stdin.flush();child.wait(timeout=8)
            assert child.returncode==0,child.stderr.read()
            thread.join(2);assert not thread.is_alive()
            result['cleanup']=job.finish(grace=2);assert not result['cleanup']['terminated_remaining']
            result['completed']=True
    finally:
        if trace:
            try:trace.close()
            except BaseException as error:result['trace_cleanup_error']=repr(error)
        if job and job.cleanup is not None:result['cleanup']=job.cleanup
        error=sys.exc_info()[1]
        if error:result['error']=repr(error)
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('Owned handle trace:',len(result['checks']),'checks passed')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--worker',action='store_true')
    parser.add_argument('--output',type=Path,default=Path('research/handle-trace-native.json'))
    args=parser.parse_args()
    if args.worker:worker()
    else:
        faulthandler.dump_traceback_later(90,exit=True)
        try:main(args.output)
        finally:faulthandler.cancel_dump_traceback_later()
