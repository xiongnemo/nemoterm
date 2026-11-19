"""Explorer WSL shares: exercise an actual terminal window and real Linux objects."""
import hashlib
import json
import os
from pathlib import Path
import sys

STAGES = ('share-file-folder', 'clipboard-alias', 'extended-unc', 'distro-root', 'foreign-mixed', 'not-a-wsl-server')
END = b'~NEMO_DROP_DONE~'


def linux_peer(folder):
    import select, subprocess, tempfile, termios, time, tty, uuid
    from fixture_io import write_snapshot
    assert os.isatty(0) and os.isatty(1)
    def until(marker,clipboard=False):
        data=bytearray();deadline=time.monotonic()+25
        while marker not in data:
            if not select.select([0],[],[],max(0,deadline-time.monotonic()))[0]:raise TimeoutError((marker,data.hex()))
            piece=os.read(0,65536)
            if not piece or len(data)+len(piece)>100000:raise IOError('TTY closed or oversized')
            data.extend(piece)
            if clipboard and b'\x1b[201~' in data:
                write_snapshot(folder/'clipboard-received.json',dict(bytes=len(data)))
                clipboard=False
        assert data.endswith(marker)
        return bytes(data[:-len(marker)])
    saved=termios.tcgetattr(0)
    try:
        tty.setraw(0);os.write(1,b'\x1b[?2004h\x1b[5n');until(b'\x1b[0n')
        with tempfile.TemporaryDirectory(prefix='nemo-drop-') as d:
            from shlex import split
            a=Path(d)/"a ' 中文 $file";b=Path(d)/'folder with spaces';b.mkdir();mark=uuid.uuid4().hex
            a.write_text(mark+'F');(b/'marker').write_text(mark+'D')
            write_snapshot(folder/'ready.json',dict(file=str(a),folder=str(b),marker=mark,distro=os.environ['WSL_DISTRO_NAME']))
            for stage in STAGES:
                data=until(END,stage=='clipboard-alias');r={'wire':data.hex()};start=b'\x1b[200~';stop=b'\x1b[201~'
                if data.startswith(start) and data.endswith(stop):
                    paths=split(data[len(start):-len(stop)].decode());r['argv']=paths
                    # Inspect only known fixture locations; an unrelated UNC must never be opened.
                    if paths==[str(a),str(b)]:
                        expr=data[len(start):-len(stop)].decode()
                        # Run Bash only for the exact, trusted fixture expression.
                        quoted=" ".join("'"+n.replace("'","'\\''")+"'" for n in paths)
                        if expr==quoted:
                            cp=subprocess.run(['/bin/bash','--noprofile','--norc','-c','set -eu; set -- '+expr+'; cat -- "$1"; echo; cat -- "$2/marker"'],capture_output=True,timeout=5,check=True)
                            r['opened']=cp.stdout.decode().splitlines()
                write_snapshot(folder/(stage+'.json'),r)
            until(b'~EXIT~')
    finally:os.write(1,b'\x1b[?2004l');termios.tcsetattr(0,termios.TCSANOW,saved)


def windows_driver():
    import shutil, struct, subprocess, traceback
    from clipboard_test_utils import SavedClipboard
    from drop_window_smoke import block,drop_data
    from fixture_io import read_snapshot,write_snapshot
    from native_test_utils import c,w,k,u,root,wait_for
    from owned_job import OwnedJob
    from protocol_oracle_window import saved_profile
    sys.path.insert(0,str(root/'tools'));import nemoterm_debug as api
    assert os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    distro=os.environ['NEMOTERM_TEST_WSL_DISTRO'];exe=Path(os.environ['NEMOTERM_TEST_EXE']);font=os.environ['NEMOTERM_TEST_FONT']
    def mounted(p):return '/mnt/'+p.drive[0].lower()+p.as_posix()[2:]
    def q(s):return "'"+s.replace("'","'\\''")+"'"
    outcomes=[]
    for renderer,selector in [(1,['--distribution',distro]),(3,[])]:
        folder=root/'research'/f'wsl-drop-{renderer}';folder.mkdir();r=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),font=font,cases={});clip=None
        try:
            with saved_profile({'NemoRenderer':renderer-1,'NemoShell':'cmd','WarnOnClose':0,'CloseOnExit':1}) as flags,OwnedJob() as job:
                args=[str(exe),*flags,'--no-tabs','--automation','--font',font,'-e',shutil.which('wsl.exe'),*selector,'--exec','/usr/bin/python3',mounted(Path(__file__).resolve()),'--peer',mounted(folder),'--distribution','not-the-running-distro']
                proc=job.spawn(args,creationflags=subprocess.CREATE_NO_WINDOW);inst=wait_for(lambda:next(iter(api.discover(proc.pid)),None),timeout=25);seat=inst['sessions'][0];hwnd=seat['hwnd'];sid=seat['id'];ep=inst['endpoint']
                u.GetPropW.argtypes,u.GetPropW.restype=[w.HWND,w.LPCWSTR],w.HANDLE;r['renderer']=int(u.GetPropW(hwnd,'NemotermRenderer') or 0);assert r['renderer']==renderer
                ready=wait_for(lambda:read_snapshot(folder/'ready.json'),timeout=25);assert ready['distro'].casefold()==distro.casefold();names=[ready['file'],ready['folder']];clip=SavedClipboard(hwnd)
                try:
                    for stage in STAGES:
                        server={'clipboard-alias':'\\\\wsl$\\','extended-unc':'\\\\?\\UNC\\wsl.localhost\\'}.get(stage,'\\\\wsl.localhost\\');paths=[server+distro.swapcase()+n.replace('/','\\') for n in names];want=names
                        if stage=='distro-root':paths=[server+distro];want=['/']
                        if stage=='foreign-mixed':paths[1]=server+'other-distribution'+names[1].replace('/','\\');want=[]
                        if stage=='not-a-wsl-server':paths=['\\\\wsl.localhost.example\\share\\literal'];want=['//wsl.localhost.example/share/literal']
                        expected=b'\x1b[200~'+' '.join(map(q,want)).encode()+b'\x1b[201~' if want else b''
                        h=block(drop_data(paths));
                        if stage=='clipboard-alias':
                            wait_for(lambda:u.OpenClipboard(hwnd))
                            try:assert u.EmptyClipboard() and u.SetClipboardData(15,h)
                            finally:u.CloseClipboard()
                            api.request(ep,'key',sid,struct.pack('<II',86,3))
                        else:
                            try:assert u.PostMessageW(hwnd,0x233,h,0)
                            except BaseException:k.GlobalFree(h);raise
                        # A positive paste is acknowledged by the peer before adding the boundary if asynchronous; request order alone is not a clipboard ack.
                        if stage=='clipboard-alias':
                            wait_for(lambda:read_snapshot(folder/'clipboard-received.json'),timeout=12)
                        api.request(ep,'input',sid,END.decode());v=wait_for(lambda:read_snapshot(folder/(stage+'.json')),timeout=10);v.update(expected_hex=expected.hex(),paths=paths);v['passed']=v['wire']==expected.hex() and (want!=names or v.get('opened')==[ready['marker']+'F',ready['marker']+'D']);r['cases'][stage]=v
                        if stage!='clipboard-alias':k.GlobalFree(h)
                finally:
                    if clip:clip.restore();clip=None
                api.request(ep,'input',sid,'~EXIT~');assert proc.wait(timeout=15)==0;r['cleanup']=job.finish();r['completed']=True
        except Exception:r['error']=traceback.format_exc()
        finally:write_snapshot(folder/'result.json',r)
        outcomes.append(r.get('completed') and len(r['cases'])==len(STAGES) and all(x['passed'] for x in r['cases'].values()) and not r['cleanup']['terminated_remaining'])
    assert all(outcomes),'See the original dragged paths, expected bytes and real Linux object contents in result.json'


if __name__=='__main__':
    if sys.argv[1:2]==['--peer']:linux_peer(Path(sys.argv[2]))
    else:windows_driver()
