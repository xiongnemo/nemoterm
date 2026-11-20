"""Two profiles in the same Win32 host must not share their column-resize permission."""
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from column_mode_native_readback import AWAY, BLANK, C, HOME, QUERY, replies
from fixture_io import read_snapshot, wait_snapshot, write_snapshot
from native_test_utils import c, find_window, root, terminal_host, u, w, wait_for
from owned_job import OwnedJob
from protocol_oracle_window import saved_profile


def profile_command(menu, name):
    for idx in range(u.GetMenuItemCount(menu)):
        label = c.create_unicode_buffer(256)
        u.GetMenuStringW(menu,idx,label,len(label),0x400)
        if label.value == name: return u.GetMenuItemID(menu,idx)
        child = u.GetSubMenu(menu,idx)
        if child:
            found = profile_command(child,name)
            if found is not None: return found
    return None


def main():
    if os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted': raise RuntimeError('Hosted runner required')
    u.GetSystemMenu.argtypes,u.GetSystemMenu.restype = [w.HWND,w.BOOL],w.HMENU
    u.GetSubMenu.argtypes,u.GetSubMenu.restype = [w.HMENU,c.c_int],w.HMENU
    u.GetMenuItemCount.argtypes = [w.HMENU]
    u.GetMenuStringW.argtypes = [w.HMENU,w.UINT,w.LPWSTR,c.c_int,w.UINT]
    u.GetMenuItemID.argtypes,u.GetMenuItemID.restype = [w.HMENU,c.c_int],w.UINT
    exe=Path(os.environ['NEMOTERM_TEST_EXE']); gpu=os.environ['RENDERER']
    record=dict(product=hashlib.sha256(exe.read_bytes()).hexdigest(), renderer=gpu, samples=[],dialogs=[],completed=False)
    path=root/'research'/('column-mode-native-tabs-'+gpu+'-results.json')
    try:
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack, OwnedJob() as job:
            folder=Path(tmp); sessions=[]
            for i,tag in enumerate(('LEFT','RGHT')):
                report,control=(folder/(tag+x+'.json') for x in ('-report','-control'))
                name=stack.enter_context(saved_profile(dict(Protocol='conpty',WarnOnClose=0,CloseOnExit=1,
                    TermWidth=80,TermHeight=24,Font=os.environ['NEMOTERM_TEST_FONT'],FontHeight=8,
                    NemoTabs=1,NemoRenderer={'gdi':0,'directx':2}[gpu],NemoAllowChecksum=1,
                    NoRemoteResize=i,LockSize=0,RemoteCommand=subprocess.list2cmdline(
                        [sys.executable,str(root/'tests/mouse_fixture.py'),str(report),str(control),'180']))))
                sessions.append((tag,report,control,name))
            process=job.spawn([str(exe),*sessions[0][3]],env=dict(os.environ,NEMOTERM_CONPTY='bundled',
                NEMOTERM_TEST_EXACT_OUTPUT='1'),creationflags=subprocess.CREATE_NO_WINDOW)
            first=wait_for(lambda:find_window(process.pid)); host=terminal_host(first)
            wait_snapshot(lambda:read_snapshot(sessions[0][1]),lambda s:s.get('columns')==80 and s.get('rows')==24)
            command=profile_command(u.GetSystemMenu(host,False),sessions[1][3][1]); assert command is not None
            u.SendMessageW(first,0x111,command,0)
            wait_snapshot(lambda:read_snapshot(sessions[1][1]),lambda s:s.get('columns')==80 and s.get('rows')==24)
            second=wait_for(lambda:(h if (h:=find_window(process.pid)) and h!=first else None))
            record.update(host=host,pid=process.pid,views=[first,second]); assert host==terminal_host(second)
            def check(which, stage, allow):
                tag,report,control,_=sessions[which]; key=stage+'-'+tag
                paint=C+'2;3H'+tag+C+'7;11H'; raw=C+'?40h'+C+'?95l'+paint+C+'?3l'+QUERY+C+'5n'
                write_snapshot(control,dict(phase=key,sequence=raw,preserve_mouse=True,native_row=[2,1,4]))
                s=wait_snapshot(lambda:read_snapshot(report),lambda r:r.get('phase')==key and bytes.fromhex(r['hex']).endswith(b'\x1b[0n'))
                front=replies(bytes.fromhex(s['hex'])[:-4]); native=dict(size=[s['columns'],s['rows']],cursor=s['screen_cursor'],
                    text=''.join(chr(v[0]) for v in s['native_row']))
                expected=dict(size=[80,24],cursor=list(HOME if allow else AWAY),text=BLANK if allow else tag)
                record['samples'].append(dict(tab=tag,stage=stage,expected=expected,frontend=front,native=native,
                    cells=s['native_row'],wire=s['hex'],passed=front==native==expected))
            for stage,allow in [('initial',False),('allow',True),('deny',False)]:
                if stage!='initial':
                    change=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass',
                        '-File',str(root/'tests/owned_profile_settings.ps1'),'-TargetProcess',str(process.pid),
                        '-TargetWindow',str(second),'-Action','resize-'+stage],capture_output=True,timeout=65)
                    record['dialogs'].append(dict(action=stage,exit=change.returncode,log=(change.stdout+change.stderr).decode(errors='replace')))
                    change.check_returncode()
                check(0,stage,True); check(1,stage,allow)
            write_snapshot(sessions[1][2],dict(stop=True)); wait_for(lambda:find_window(process.pid)==first and not u.IsWindow(second))
            check(0,'after-peer-close',True); write_snapshot(sessions[0][2],dict(stop=True))
            record['exit_code']=process.wait(timeout=10); record['cleanup']=job.finish()
            assert record['exit_code']==0 and not record['cleanup']['terminated_remaining']
            assert len(record['samples'])==7 and all(row['passed'] for row in record['samples']),record['samples']
            record['completed']=True
    finally: path.write_text(json.dumps(record,indent=2),encoding='utf8')


if __name__=='__main__': main()
