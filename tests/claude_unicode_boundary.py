"""Compare clipboard bytes received by a native app and a pinned client on system ConPTY."""
import argparse
import ctypes as c
import hashlib
import os
import re
from pathlib import Path
import subprocess
import sys
import threading
import time
import traceback
import uuid
import winreg
from ctypes import wintypes as w

from agent_clipboard_fixture import Provider, SELECTION_PREFIX, SELECTION_TEXT, claude_command, isolated_home
from clipboard_test_utils import SavedClipboard, clipboard_text, k, u
from fixture_io import write_snapshot, read_snapshot
from hosted_gesture_input import DesktopInput
from native_test_utils import wait_for
from owned_job import OwnedJob

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'tools'))
import nemoterm_debug as api
TEXT=SELECTION_PREFIX+SELECTION_TEXT
BEGIN=b'\x1b[200~'; END=b'\x1b[201~'
WIRE=BEGIN+TEXT.encode('utf8')+END

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def child(folder):
    k.GetStdHandle.argtypes=[w.DWORD];k.GetStdHandle.restype=w.HANDLE
    k.SetConsoleMode.argtypes=[w.HANDLE,w.DWORD]
    assert k.SetConsoleCP(65001) and k.SetConsoleOutputCP(65001)
    assert k.SetConsoleMode(k.GetStdHandle(-10),0x200) and k.SetConsoleMode(k.GetStdHandle(-11),7)
    os.write(1,b'\x1b[?2004h\x1b[?1003;1006h\x1b[>5uUNICODE_PASTE_READY')
    buf=bytearray()
    while not buf.endswith(b'Q!'):
        chunk=os.read(0,4096)
        if not chunk:raise EOFError('console input closed')
        buf.extend(chunk);write_snapshot(folder/'native.json',dict(hex=buf.hex()))

def set_text(hwnd):
    data=(TEXT+'\0').encode('utf-16le');h=k.GlobalAlloc(2,len(data));assert h
    try:
        addr=k.GlobalLock(h);assert addr;c.memmove(addr,data,len(data));k.GlobalUnlock(h)
        wait_for(lambda:u.OpenClipboard(hwnd))
        try:
            assert u.EmptyClipboard() and u.SetClipboardData(13,h);h=None
        finally:u.CloseClipboard()
    finally:
        if h:k.GlobalFree(h)
    assert clipboard_text(hwnd)==TEXT

def product(exe, renderer, folder, rec):
    folder.mkdir();profile='wire-'+uuid.uuid4().hex;key='Software\\Nemo\\Nemoterm\\Sessions\\'+profile
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,key) as h:
        for n,v in [('NemoRenderer',renderer),('WarnOnClose',0),('CloseOnExit',1)]:winreg.SetValueEx(h,n,0,winreg.REG_DWORD,v)
    try:
        with OwnedJob() as job:
            proc=job.spawn([str(exe),'-load',profile,'--automation','--font','SarasaTermSC Nerd Font Light','-e',sys.executable,str(Path(__file__).resolve()),'--child',str(folder)],env=dict(os.environ,NEMOTERM_CONPTY='bundled'),creationflags=subprocess.CREATE_NO_WINDOW)
            inst=wait_for(lambda:next(iter(api.discover(proc.pid)),None),timeout=25);sess,=inst['sessions'];endpoint=inst['endpoint'];seat=sess['id']
            assert sess['renderer']==renderer and sess['window']!=sess['hwnd']; rec['session']=sess
            wait_for(lambda:'UNICODE_PASTE_READY' in api.request(endpoint,'text',seat))
            desk=DesktopInput(proc.pid,sess['window'],sess['hwnd'],rec.setdefault('system_input',{}));clip=SavedClipboard(sess['hwnd'])
            try:
                set_text(sess['hwnd']);desk.chord(0x11,0x10,ord('V'))
                data=wait_for(lambda:b if END in (b:=bytes.fromhex(read_snapshot(folder/'native.json').get('hex',''))) else None,timeout=10)
                rec['native_input_hex']=data.hex();rec['clipboard_utf16le']=clipboard_text(sess['hwnd']).encode('utf-16le').hex()
                assert data.count(BEGIN)==data.count(END)==1 and WIRE in data,rec
            finally:
                desk.restore();clip.restore()
                api.request(endpoint,'input',seat,'Q!')
            assert proc.wait(timeout=12)==0;rec['cleanup']=job.finish();assert not rec['cleanup']['terminated_remaining']
    finally:winreg.DeleteKey(winreg.HKEY_CURRENT_USER,key)

def upstream_pty(folder,backend,cmd):
    # The independent upstream bridge owns the console. This subprocess is
    # inside the runner's private job, with only the disposable client env.
    import codecs
    from importlib.metadata import version
    from winpty import PtyProcess
    proc=PtyProcess.spawn(cmd,cwd=os.getcwd(),env=dict(os.environ),dimensions=(30,100),backend=backend)
    write_snapshot(folder/'reference-backend.json',dict(pywinpty=version('pywinpty'),backend=backend,pid=proc.pid))
    def send():
        decoder=codecs.getincrementaldecoder('utf-8')()
        with (folder/'reference-stdin.vt').open('wb') as record:
            while data:=os.read(0,16384):
                record.write(data);record.flush();value=decoder.decode(data)
                if value:proc.write(value)
    threading.Thread(target=send,daemon=True).start()
    try:
        while True:
            value=proc.read(32768)
            if value:sys.stdout.buffer.write(value.encode('utf8'));sys.stdout.buffer.flush()
    except EOFError:pass
    return proc.wait()

def reference(backend,client,folder,rec):
    folder.mkdir();home,work,env=isolated_home(folder);env.pop('NEMOTERM_CONPTY',None);env['NEMOTERM_HOSTED_REFERENCE']='1'
    server=Provider();server.selection=True
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        cmd=claude_command(str(client),folder,home,work,env,'http://127.0.0.1:%d/v1'%server.server_port)
        if backend=='1':
            # WinPTY sends incremental damage. Keep a simultaneous read-only
            # view of the client's own backing cells for the final display ack.
            cmd=[sys.executable,str(ROOT/'tests/console_frame_observer.py'),str(folder),*cmd]
        with OwnedJob() as job,(folder/'helper-stderr.txt').open('wb') as err:
            target=[sys.executable,str(Path(__file__).resolve()),'--upstream-pty',str(folder),backend,*cmd]
            proc=job.spawn(target,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,cwd=work,env=env,bufsize=0,creationflags=subprocess.CREATE_NO_WINDOW)
            raw=bytearray();token=b'NEMOTERM_TEXT_ACCEPTED';started=time.monotonic_ns()
            events=rec['timeline']=[]
            def mark(action,**extra):
                events.append(dict(action=action,ms=round((time.monotonic_ns()-started)/1e6,1),**extra))
            mark('bridge-started')
            def drain():
                with (folder/'system-output.vt').open('wb') as f:
                    first=True
                    while block:=proc.stdout.read(8192):
                        previous=len(raw);f.write(block);f.flush();raw.extend(block)
                        if first and (pos:=raw.find(token,max(0,previous-len(token)+1)))>=0:
                            mark('first-reply-in-output',byte_offset=pos);first=False
            pump=threading.Thread(target=drain,daemon=True);pump.start()
            def wrote(payload):proc.stdin.write(payload);proc.stdin.flush()
            def seen(pred):
                if proc.poll() is not None:raise RuntimeError('system reference exited: '+str(proc.returncode))
                return pred()
            try:
                # Windows' console host requests focus and cursor information
                # from its terminal peer; answer only observed requests. System
                # ConPTY may split words with cursor-position/SGR sequences.
                offset=0;rec['terminal_queries']=[]
                pattern=re.compile(rb'\x1b\[(?:\?1004h|6n|\?6n|0?c)')
                def ready():
                    nonlocal offset
                    data=bytes(raw)
                    for m in pattern.finditer(data,offset):
                        q=m.group();offset=m.end();reply={b'\x1b[?1004h':b'\x1b[I',b'\x1b[6n':b'\x1b[1;1R',
                            b'\x1b[?6n':b'\x1b[?1;1R'}.get(q,b'\x1b[?1;2c')
                        wrote(reply);rec['terminal_queries'].append([q.hex(),reply.hex()])
                    plain=re.sub(rb'\x1b\[[0-?]*[ -/]*[@-~]',b'',data).lower()
                    return b'shift+tab' in plain
                # First native startup spent 43 s inside client setup before
                # drawing. This is distinct from any input/receipt deadline.
                wait_for(lambda:seen(ready),timeout=120)
                mark('composer-ready');rec['sent_hex']=WIRE.hex();wrote(WIRE)
                wait_for(lambda:b'NEMOTERM_SUBMIT' in bytes(raw),timeout=15);time.sleep(.2);mark('submit');wrote(b'\r')
                wait_for(lambda:seen(lambda:server.requests),timeout=35)
                mark('provider-receipt');rec['requests']=list(server.requests);row,=rec['requests'];assert row['path']=='/v1/messages' and row['advertised_tools']==0 and not server.errors
                assert row['selection_received'] != row['selection_nfc_present'],row
                rec['form']='exact' if row['selection_received'] else 'NFC'
                def accepted():
                    token='NEMOTERM_TEXT_ACCEPTED';data=bytes(raw)
                    screen=read_snapshot(folder/'peer-screen.json').get('text','') if backend=='1' else ''
                    if token.encode() not in data and token not in screen:return False
                    rec['rendered_ack']=dict(output_bytes=token.encode() in data,console_cells=token in screen)
                    if token in screen:write_snapshot(folder/'accepted-screen.json',dict(text=screen))
                    return True
                try:
                    wait_for(accepted,timeout=15)
                except AssertionError:
                    # The normal-view deadline remains failed. Distinguish a
                    # missing reply from damage/repaint loss and exit normally.
                    rec['normal_view_timed_out']=True
                    rec['display_controls']=[]
                    for label,key in [('redraw',b'\x0c'),('transcript',b'\x0f')]:
                        pos=len(raw);mark(label,output_bytes=pos);wrote(key)
                        def caught():
                            pane=read_snapshot(folder/'peer-screen.json').get('text','')
                            return 'NEMOTERM_TEXT_ACCEPTED' in pane or b'NEMOTERM_TEXT_ACCEPTED' in bytes(raw[pos:])
                        try:wait_for(caught,timeout=4);visible=True
                        except AssertionError:visible=False
                        rec['display_controls'].append(dict(action=label,visible=visible,new_output=len(raw)-pos))
                        if visible:break
                    if rec['display_controls'][-1]['action']=='transcript':mark('escape-transcript');wrote(b'\x1b');time.sleep(.15)
                mark('first-ctrl-c');wrote(b'\x03');time.sleep(.3)
                if proc.poll() is None:mark('second-ctrl-c');wrote(b'\x03')
                assert proc.wait(timeout=18)==0
            finally:
                rec['provider_errors']=list(server.errors);rec['requests']=list(server.requests)
                proc.stdin.close();rec['cleanup']=job.finish();pump.join(5);mark('cleanup')
                active=read_snapshot(folder/'peer-active-first-reply.json')
                if active:rec['active_buffer_first_reply_ms']=round((active['monotonic_ns']-started)/1e6,1)
            assert not rec['cleanup']['terminated_remaining'] and not pump.is_alive()
            assert not rec.get('normal_view_timed_out'),'Normal-view reply missed its original deadline: '+str(rec.get('display_controls'))
    finally:server.shutdown();server.server_close();thread.join(3)

def main():
    # The child inherits only the isolated client environment (no runner tokens).
    if sys.argv[1:2]==['--upstream-pty']:
        if os.environ.get('NEMOTERM_HOSTED_REFERENCE')!='1':raise RuntimeError('Reference must be spawned on the hosted runner')
        return upstream_pty(Path(sys.argv[2]),sys.argv[3],sys.argv[4:])
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':raise RuntimeError('GitHub hosted runner required')
    if sys.argv[1:2]==['--child']:return child(Path(sys.argv[2]))
    parser=argparse.ArgumentParser();parser.add_argument('--claude',type=Path,required=True);args=parser.parse_args()
    exe=Path(os.environ['NEMOTERM_TEST_EXE']).resolve(strict=True);client=args.claude.resolve(strict=True)
    out=ROOT/'build/unicode-boundary';out.mkdir(parents=True,exist_ok=False)
    report=dict(executable_sha256=digest(exe),client_sha256=digest(client),fixture_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),cases={});failed=False
    for name,run in [('gdi',lambda d,r:product(exe,0,d,r)),('directx',lambda d,r:product(exe,2,d,r)),('system-claude',lambda d,r:reference('0',client,d,r)),('winpty-claude',lambda d,r:reference('1',client,d,r))]:
        rec=report['cases'][name]=dict(passed=False)
        try:run(out/name,rec);rec['passed']=True
        except Exception:rec['error']=traceback.format_exc();failed=True
        finally:write_snapshot(out/'summary.json',report)
    return int(failed)

if __name__=='__main__':sys.exit(main())
