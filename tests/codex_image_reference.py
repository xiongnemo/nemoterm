"""Pinned Codex on independent Windows console hosts; only generated input, local provider and disposable home."""
import argparse
import ctypes as c
from ctypes import wintypes as w
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import traceback
import zipfile

from agent_clipboard_fixture import Provider, codex_command, isolated_home, put_bitmap
from clipboard_test_utils import SavedClipboard, u, k
from fixture_io import read_snapshot, write_snapshot
from owned_job import OwnedJob

ROOT = Path(__file__).resolve().parents[1]
MARK = 'NEMOTERM_IMAGE_REFERENCE'
WARM = 'NEMOTERM_REFERENCE_WARM'
CLIENT = 'edfdd48f8b458af0906e507b4cb05217b326c3d6e515e9f024e05e3b8d650f70'
KEYS = '3ef67fbb1e30ea3e577bbccd7c93b158db11518f59f5ebea7c40b6cb4f076085'
CSI = re.compile(rb'\x1b\[[0-?]*[ -/]*[@-~]')
QUERY = re.compile(rb'\x1b(?:\[(?:\?1004h|\??6n|0?c)|\](?:10|11);\?(?:\x07|\x1b\\))')


def fixed_events():
    src = (ROOT/'research/codex-native-image-keys.zip').read_bytes()
    assert hashlib.sha256(src).hexdigest() == KEYS
    with zipfile.ZipFile(io.BytesIO(src)) as archive:
        trials = json.loads(archive.read('image-key-records/summary.json'))['cases']
    events = trials['none-api']['events']['ctrl-v']
    # Use the common four records captured at the native receiver, irrespective
    # of surrounding modifier transitions in physical desktop input.
    assert events == trials['none-api']['events']['ctrl-shift-v']
    assert len(events) == 4 and [(e['vk'], e['down']) for e in events] == [(17,1),(86,1),(86,0),(17,0)]
    return events


class Key(c.Structure):
    _fields_ = [('down',w.BOOL),('repeat',w.WORD),('vk',w.WORD),('scan',w.WORD),('character',w.WORD),('control',w.DWORD)]


class Payload(c.Union):
    _fields_ = [('key',Key),('padding',c.c_byte*16)]


class Record(c.Structure):
    _fields_ = [('type',w.WORD),('event',Payload)]


def console_peer(folder, cmd):
    # This wrapper starts the unmodified client as its own console child. It
    # only writes fixed test records to its own console, never to another PID.
    assert os.environ.get('NEMOTERM_HOSTED_REFERENCE') == '1' and c.sizeof(Record) == 20
    k.GetStdHandle.argtypes=[w.DWORD]; k.GetStdHandle.restype=w.HANDLE
    k.GetConsoleMode.argtypes=[w.HANDLE,c.POINTER(w.DWORD)]
    k.WriteConsoleInputW.argtypes=[w.HANDLE,c.POINTER(Record),w.DWORD,c.POINTER(w.DWORD)]
    u.MapVirtualKeyW.argtypes=[w.UINT,w.UINT]; u.MapVirtualKeyW.restype=w.UINT
    stdin=k.GetStdHandle(-10); mode=w.DWORD(); assert k.GetConsoleMode(stdin,c.byref(mode))
    captured=fixed_events(); seq=0; child=subprocess.Popen(cmd)
    while child.poll() is None:
        request=read_snapshot(folder/'command.json')
        if request.get('id') != seq+1:
            time.sleep(.003);continue
        action=request['action']; rows=[]
        def stroke(vk,char,mods):
            scan=u.MapVirtualKeyW(vk,0)
            for down in (1,0):rows.append(dict(down=down,repeat=1,vk=vk,scan=scan,character=char,control=mods))
        if action=='image': rows=captured
        elif action in ('marker','warm'):
            for char in (MARK if action=='marker' else WARM):stroke(0xbd if char=='_' else ord(char),ord(char),16)
        elif action=='enter':stroke(13,13,0)
        elif action=='quit':stroke(67,3,8)
        else:raise ValueError(action)
        buf=(Record*len(rows))()
        for item,row in zip(buf,rows):item.type=1;item.event.key=Key(*(row[n] for n,_ in Key._fields_))
        assert k.GetConsoleMode(stdin,c.byref(mode)); count=w.DWORD()
        assert k.WriteConsoleInputW(stdin,buf,len(buf),c.byref(count)) and count.value==len(buf)
        seq+=1;write_snapshot(folder/f'command-{seq:02}.json',dict(action=action,input_mode=mode.value,written=count.value,records=rows))
    return child.returncode


def window():
    u.CreateWindowExW.argtypes=[w.DWORD,w.LPCWSTR,w.LPCWSTR,w.DWORD,c.c_int,c.c_int,c.c_int,c.c_int,w.HWND,w.HMENU,w.HINSTANCE,c.c_void_p]
    u.CreateWindowExW.restype=w.HWND;u.DestroyWindow.argtypes=[w.HWND]
    hwnd=u.CreateWindowExW(0,'STATIC','Nemoterm hosted reference clipboard',0,0,0,0,0,None,None,None,None)
    if not hwnd:raise c.WinError()
    return hwnd


def run(args, folder, rec):
    client=args.codex.resolve(strict=True);rec['client_sha256']=hashlib.sha256(client.read_bytes()).hexdigest();assert rec['client_sha256']==CLIENT
    rec['native_key_archive_sha256']=KEYS;fixed_events()
    home,work,env=isolated_home(folder);env.pop('NEMOTERM_CONPTY',None);env.update(NEMOTERM_HOSTED_REFERENCE='1',HOME=str(home),GIT_ALLOW_PROTOCOL='file',GIT_TERMINAL_PROMPT='0')
    server=Provider();server.selection=False;thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    hwnd=window();clip=SavedClipboard(hwnd)
    try:
        cmd=codex_command(str(client),home,work,env,f'http://127.0.0.1:{server.server_port}/v1')
        helper=ROOT/'tests/claude_unicode_boundary.py'
        target=[sys.executable,str(helper),'--upstream-pty',str(folder),{'conpty':'0','winpty':'1'}[args.host],sys.executable,str(Path(__file__).resolve()),'--peer',str(folder),*cmd]
        with OwnedJob() as job,(folder/'helper-stderr.txt').open('wb') as err:
            proc=job.spawn(target,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,bufsize=0,cwd=work,env=env,creationflags=subprocess.CREATE_NO_WINDOW)
            raw=bytearray();seq=0;cursor=0;rec['queries']=[]
            def drain():
                with (folder/'system-output.vt').open('wb') as stream:
                    while data:=proc.stdout.read(8192):raw.extend(data);stream.write(data);stream.flush()
            pump=threading.Thread(target=drain,daemon=True);pump.start()
            def poll():
                nonlocal cursor
                data=bytes(raw)
                for m in QUERY.finditer(data,cursor):
                    q=m.group();cursor=m.end()
                    if q.startswith(b'\x1b]'):
                        selector=q[2:4];rgb=b'c0c0/c0c0/c0c0' if selector==b'10' else b'0000/0000/0000';reply=b'\x1b]'+selector+b';rgb:'+rgb+b'\x1b\\'
                    else:reply={b'\x1b[?1004h':b'\x1b[I',b'\x1b[6n':b'\x1b[1;1R',b'\x1b[?6n':b'\x1b[?1;1R'}.get(q,b'\x1b[?1;2c')
                    proc.stdin.write(reply);proc.stdin.flush();rec['queries'].append([q.hex(),reply.hex()])
                return CSI.sub(b'',data)
            def until(label,test,timeout):
                deadline=time.monotonic()+timeout
                while time.monotonic()<deadline:
                    if proc.poll() is not None:raise RuntimeError(f'{label}: client driver exited {proc.returncode}')
                    if test(poll()):return
                    time.sleep(.004)
                raise TimeoutError(label)
            def send(action):
                nonlocal seq
                seq+=1;write_snapshot(folder/'command.json',dict(id=seq,action=action))
                return seq
            try:
                # Prepare the generated DIB before startup so that observing
                # the first marker need not wait for clipboard IPC.
                put_bitmap(hwnd);until('first Codex prompt',lambda plain:b'Ask Codex' in plain,90)
                if args.phase=='after-turn':
                    send('warm');until('warm text painted',lambda p:WARM.encode() in p,15);send('enter')
                    until('first provider reply rendered',lambda p:b'NEMOTERM_TEXT_ACCEPTED' in p and any(WARM in r['text'] for r in server.requests),30)
                send('marker');until('fixture marker painted',lambda p:MARK.encode() in p,20)
                before=bytes(raw);(folder/'at-paste.vt').write_bytes(before);rec['idle_visible_before']=b'\x1b]7501;state=idle:app=codex' in before
                n=send('image');until('four native records written',lambda _:read_snapshot(folder/f'command-{n:02}.json').get('written')==4,8)
                try:until('image marker painted',lambda p:b'[Image' in p,10);rec['attachment_visible']=True
                except TimeoutError:rec['attachment_visible']=False
                send('enter');until('provider received image-test marker',lambda _:any(MARK in r['text'] for r in server.requests),30)
                until('provider reply rendered',lambda p:b'NEMOTERM_IMAGE_ACCEPTED' in p[len(CSI.sub(b'',before)):] or b'NEMOTERM_TEXT_ACCEPTED' in p[len(CSI.sub(b'',before)):],25)
                rec['exact_images']=sum(im['generated_pixels_match'] for r in server.requests if MARK in r['text'] for im in r['images'])
            finally:
                rec['requests']=server.requests;rec['provider_errors']=server.errors
                if proc.poll() is None:
                    send('quit');time.sleep(.35)
                    if proc.poll() is None:send('quit')
                    try:rec['exit_code']=proc.wait(timeout=12)
                    except subprocess.TimeoutExpired:rec['exit_code']=None
                else:rec['exit_code']=proc.returncode
                proc.stdin.close();rec['cleanup']=job.finish();pump.join(5);rec['output_drained']=not pump.is_alive()
            assert not server.errors and rec['exit_code']==0 and rec['output_drained'] and not rec['cleanup']['terminated_remaining'],rec
            assert rec['attachment_visible'] and rec['exact_images']==1,'No single exact image submission'
    finally:
        clip.restore();u.DestroyWindow(hwnd);server.shutdown();server.server_close();thread.join(3)


def main():
    if sys.argv[1:2]==['--peer']:return console_peer(Path(sys.argv[2]),sys.argv[3:])
    assert os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    parser=argparse.ArgumentParser();parser.add_argument('--host',choices=['conpty','winpty'],required=True);parser.add_argument('--phase',choices=['first','after-turn'],required=True);parser.add_argument('--codex',type=Path,required=True);args=parser.parse_args()
    folder=ROOT/'build/codex-image-reference';folder.mkdir(parents=True,exist_ok=False)
    rec=dict(host=args.host,phase=args.phase,fixture_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),passed=False)
    try:run(args,folder,rec);rec['passed']=True
    except Exception:rec['error']=traceback.format_exc()
    write_snapshot(folder/'summary.json',rec);print(json.dumps(rec,indent=2));return int(not rec['passed'])


if __name__=='__main__':sys.exit(main())
