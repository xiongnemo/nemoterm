"""Switch one hosted window between native cooked editing and VT-aware byte / wide readers."""
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

from fixture_io import read_snapshot, write_snapshot

ROOT = Path(__file__).resolve().parents[1]
ACK = b'\x1b[0n'
RAW = [(api, mode) for api in ('ReadFile','ReadConsoleW') for mode in ('set','reset')]


def child(folder):
    state = folder/'state.json'
    k = c.WinDLL('kernel32', use_last_error=True)
    k.GetStdHandle.argtypes, k.GetStdHandle.restype = [w.DWORD], w.HANDLE
    k.GetConsoleMode.argtypes = [w.HANDLE, c.POINTER(w.DWORD)]
    k.SetConsoleMode.argtypes = [w.HANDLE, w.DWORD]
    k.ReadConsoleW.argtypes = k.ReadFile.argtypes = [w.HANDLE,c.c_void_p,w.DWORD,c.POINTER(w.DWORD),c.c_void_p]
    k.WriteFile.argtypes = [w.HANDLE,c.c_void_p,w.DWORD,c.POINTER(w.DWORD),c.c_void_p]
    stdin, stdout = k.GetStdHandle(-10), k.GetStdHandle(-11)
    def check(ok):
        if not ok: raise c.WinError(c.get_last_error())
    def mode(handle):
        value = w.DWORD(); check(k.GetConsoleMode(handle,c.byref(value))); return value.value
    oldin, oldout = mode(stdin), mode(stdout)
    observed = dict(stages={}, complete=False, oldin=oldin, oldout=oldout)
    def read(api, suffix):
        data = bytearray()
        while not data.endswith(suffix):
            size=w.DWORD();buf=c.create_string_buffer(128)
            if api=='ReadFile':
                check(k.ReadFile(stdin,buf,len(buf),c.byref(size),None)); piece=buf.raw[:size.value]
            else:
                check(k.ReadConsoleW(stdin,buf,len(buf)//2,c.byref(size),None)); piece=buf.raw[:size.value*2].decode('utf-16-le').encode('utf8')
            if not piece or len(data)+len(piece)>256: raise ValueError(('unexpected input length',api,bytes(data),piece))
            data.extend(piece)
        return bytes(data)
    def write(data):
        n=w.DWORD(); check(k.WriteFile(stdout,data,len(data),c.byref(n),None)); assert n.value==len(data)
    def ready(label, **fields):
        observed['phase']=label; row=observed['stages'][label]=dict(input_mode=mode(stdin),**fields)
        write_snapshot(state,observed);return row
    def cooked(label):
        check(k.SetConsoleMode(stdin,0x87)) # processed, line, echo, extended; VT off
        row=ready(label,api='ReadConsoleW');row['line_hex']=read('ReadConsoleW',b'\r\n').hex()
    try:
        check(k.SetConsoleMode(stdout,oldout|0x0c)); cooked('cooked-before')
        for api,mode_name in RAW:
            check(k.SetConsoleMode(stdin,0x280)) # extended + VT input; echo / line / processed off
            # The final phase resets DECBKM before handing input back to native line editing.
            cmd=b'\x1b[?67'+(b'h' if mode_name=='set' else b'l')
            write(cmd+b'\x1b[?67$p\x1b[5n'); query=read(api,ACK)
            row=ready(api+'-'+mode_name,api=api,query_hex=query.hex())
            row['key_stream_hex']=read(api,b'z').hex()
        cooked('cooked-after');observed['complete']=True
    finally:
        k.SetConsoleMode(stdin,oldin); k.SetConsoleMode(stdout,oldout)
        observed.update(restored=(mode(stdin),mode(stdout))==(oldin,oldout),phase='finished');write_snapshot(state,observed)


def main():
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':
        raise RuntimeError('This interaction belongs on a GitHub-hosted Windows runner')
    if len(sys.argv)==3 and sys.argv[1]=='--child':
        child(Path(sys.argv[2]));return
    from hosted_gesture_input import DesktopInput
    from owned_job import OwnedJob
    from native_test_utils import find_window, terminal_host, wait_for
    from protocol_oracle_window import saved_profile
    font=os.environ['NEMOTERM_TEST_FONT']; exe=Path(os.environ['NEMOTERM_TEST_EXE']).resolve()
    archive=ROOT/'testdata/upstream/backarrow-xterm-pinned.zip'
    with zipfile.ZipFile(archive) as z:
        ref=json.loads(z.read('backarrow.json')); assert ref['completed']
        keys={s['label']:bytes.fromhex(s['wire_with_barriers_hex']).split(ACK)[1] for s in ref['cases']['default-del']['steps']}
    result=dict(exe_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(), font=font,
                reference_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),completed=False,checks={})
    receipt=ROOT/'research/backarrow-native-transition.json'
    try:
        with tempfile.TemporaryDirectory() as folder, OwnedJob() as job, saved_profile(dict(NemoRenderer=0,NemoWin32Input=0,BackspaceIsDelete=1,WarnOnClose=0)) as args:
            state=Path(folder)/'state.json'; desktop=None
            proc=job.spawn([str(exe),*args,'--tabs','--cols','80','--rows','24','--font',font,'-e',sys.executable,
                            str(Path(__file__).resolve()),'--child',folder],env=dict(os.environ,NEMOTERM_CONPTY='bundled'),creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                hwnd=wait_for(lambda:find_window(proc.pid)); desktop=DesktopInput(proc.pid,terminal_host(hwnd),hwnd,result.setdefault('desktop',{}))
                for phase in ['cooked-before', *[api+'-'+mode for api,mode in RAW], 'cooked-after']:
                    wait_for(lambda:read_snapshot(state).get('phase')==phase)
                    if phase.startswith('cooked-'):
                        for vk in (ord('A'),ord('B'),ord('X'),0x08,ord('C'),0x0d):desktop.chord(vk)
                    else:
                        desktop.chord(0x08);desktop.chord(0x11,0x08);desktop.chord(0x10,0x08)
                        desktop.event(0x2e,True,extended=True);desktop.event(0x2e,False,extended=True);desktop.chord(ord('Z'))
                done=wait_for(lambda:s if (s:=read_snapshot(state)).get('phase')=='finished' else None)
                assert done['complete'] and done['restored'];result['child']=done
                for phase,row in done['stages'].items():
                    if phase.startswith('cooked-'):
                        result['checks'][phase]=(row['input_mode']==0x87 and bytes.fromhex(row['line_hex'])==b'abc\r\n')
                    else:
                        api,name=phase.split('-'); expected=b''.join(keys[s] for s in (name,name+'-control',name+'-shift','delete-control'))+b'z'
                        query=b'\x1b[?67;'+(b'1' if name=='set' else b'2')+b'$y'+ACK
                        result['checks'][phase]=(row['input_mode']==0x280 and bytes.fromhex(row['key_stream_hex'])==expected and bytes.fromhex(row['query_hex'])==query)
                result['returncode']=proc.wait(timeout=10);result['cleanup']=job.finish()
                assert result['returncode']==0 and not result['cleanup']['terminated_remaining']
            finally:
                if desktop:desktop.restore()
                result['last_state']=read_snapshot(state)
        assert len(result['checks'])==6 and all(result['checks'].values()), result['checks']
        result['completed']=True
    finally:
        receipt.write_text(json.dumps(result,indent=2),encoding='utf-8')


if __name__=='__main__':main()
