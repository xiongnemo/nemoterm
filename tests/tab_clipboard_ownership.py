"""Cross-tab right-click policy and input ownership on a hosted Windows desktop."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback
import uuid
import winreg
from PIL import Image, ImageChops
from clipboard_test_utils import SavedClipboard, clipboard_text
from fixture_io import read_snapshot, wait_snapshot, write_snapshot
from hosted_gesture_input import DesktopInput
from native_test_utils import c, w, u, root, wait_for
from owned_job import OwnedJob
sys.path.insert(0, str(root/'tools'))
import nemoterm_debug as api

ACK=b'\x1b[0n'
WORDS=('A中Z','BéQ')
WIDTHS=(4,3)


def profile_command(hwnd,name):
    u.GetSystemMenu.argtypes,u.GetSystemMenu.restype=[w.HWND,w.BOOL],w.HMENU
    u.GetSubMenu.argtypes,u.GetSubMenu.restype=[w.HMENU,c.c_int],w.HMENU
    u.GetMenuItemCount.argtypes=[w.HMENU]
    u.GetMenuItemID.argtypes,u.GetMenuItemID.restype=[w.HMENU,c.c_int],w.UINT
    u.GetMenuStringW.argtypes=[w.HMENU,w.UINT,w.LPWSTR,c.c_int,w.UINT]
    def search(menu):
        for i in range(u.GetMenuItemCount(menu)):
            buf=c.create_unicode_buffer(256);u.GetMenuStringW(menu,i,buf,len(buf),0x400)
            if buf.value==name:return u.GetMenuItemID(menu,i)
            child=u.GetSubMenu(menu,i)
            if child and (match:=search(child)) is not None:return match
    cmd=search(u.GetSystemMenu(hwnd,False));assert cmd is not None,name
    return cmd


def run(tmp,job,out,report,keys):
    exe=Path(os.environ['NEMOTERM_TEST_EXE']);font=os.environ['NEMOTERM_TEST_FONT'];report.update(sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),font=font,observations=[])
    profiles=[];sessions=[];pids=[];dirs=[];expected=[ACK,ACK];serial=0;desk=saved=None
    for i in range(2):
        folder=tmp/str(i);folder.mkdir();dirs.append(folder)
        name='clipboard-tab-'+uuid.uuid4().hex;profiles.append(name);key='Software\\Nemo\\Nemoterm\\Sessions\\'+name
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,key) as reg:
            keys.append(key)
            for k,v in dict(NemoTabs=1,NemoRenderer=2*i,FontHeight=12,WarnOnClose=0,CloseOnExit=1,ScrollBar=0,WindowBorder=1,TermWidth=60,TermHeight=20).items():winreg.SetValueEx(reg,k,0,winreg.REG_DWORD,v)
            if i:winreg.SetValueEx(reg,'RightClickCopyAndPaste',0,winreg.REG_DWORD,1)
            for k,v in dict(Protocol='conpty',Font=font,RemoteCommand=subprocess.list2cmdline([sys.executable,str(root/'tests/session_fixture.py'),str(folder)])).items():winreg.SetValueEx(reg,k,0,winreg.REG_SZ,v)
    proc=job.spawn([str(exe),'--automation','-load',profiles[0]],env=dict(os.environ,NEMOTERM_CONPTY='bundled',NEMOTERM_TEST_INPUT_CP='65001'),creationflags=subprocess.CREATE_NO_WINDOW)
    def file(i,kind):return dirs[i]/f'{pids[i]}.{kind}.json'
    def active():return next((s for s in api.request(endpoint)['sessions'] if s['active']),None)
    def text(i):return api.request(endpoint,'text',sessions[i]['id'])
    def shot(i,name=None):
        b=api.request(endpoint,'image',sessions[i]['id']);im=Image.open(io.BytesIO(b)).convert('RGB')
        if name:im.save(out/(name+'.png'))
        return im
    def switch(i):
        desk.chord(0x11,0x09);hwnd=sessions[i]['hwnd'];wait_for(lambda:active()['hwnd']==hwnd and desk.state().focus==hwnd)
        desk.hwnd=hwnd;desk.target();assert active()['renderer']==2*i
    def scene(i):return f'\x1b[?1049h\x1b[?25l\x1b[2J\x1b[3;1H|{WORDS[i]}|\x1b[?1002;1006;2004h\x1b[5n'
    def barrier(label,delta=(b'',b'')):
        nonlocal serial
        serial+=1;row=dict(stage=label,children=[]);report['observations'].append(row)
        for i in range(2):
            expected[i]+=delta[i]+ACK
            write_snapshot(file(i,'control'),dict(phase=1,sequence=scene(i),input_barrier=serial))
            r=wait_snapshot(lambda:read_snapshot(file(i,'report')),lambda v:v.get('input_barrier')==serial)
            row['children'].append(dict(pid=pids[i],wire=r['hex'],expected=expected[i].hex()));assert bytes.fromhex(r['hex'])==expected[i],row
    def coords(i):
        s=active();assert s['hwnd']==sessions[i]['hwnd'];cw,rem=divmod(s['client_width']-2,s['cols']);ch,rh=divmod(s['client_height']-2,s['rows']);assert not(rem or rh);return cw,ch
    def select(i):
        cw,ch=coords(i);base=shot(i,f'{i}-source')
        def check():
            diff=ImageChops.difference(base,shot(i)).convert('L');ratios=[]
            for x in range(WIDTHS[i]+2):
                box=(1+x*cw,1+2*ch,1+(x+1)*cw,1+3*ch);ratios.append(1-diff.crop(box).histogram()[0]/(cw*ch))
            report[f'{i}-selection-ratios']=ratios
            return ratios[0]<.1 and ratios[-1]<.1 and min(ratios[1:-1])>.5
        desk.drag(1+cw+cw//2,1+WIDTHS[i]*cw+cw//2,1+2*ch+ch//2,check);shot(i,f'{i}-selection')
    def right(i):
        seq=u.GetClipboardSequenceNumber();desk.event('right',True);desk.event('right',False)
        wait_for(lambda:u.GetClipboardSequenceNumber()!=seq and clipboard_text(sessions[i]['hwnd'])==WORDS[i]);report.setdefault('right_clipboard',[]).append(WORDS[i])
    def paste(i,token):
        payload=b'\x1b[200~'+token.encode()+b'\x1b[201~';wait_snapshot(lambda:read_snapshot(file(i,'report')),lambda v:bytes.fromhex(v.get('hex','')).endswith(payload));return payload
    try:
        inst=wait_for(lambda:next(iter(api.discover(proc.pid)),None));endpoint=inst['endpoint']
        for i in range(2):
            if i:
                u.SendMessageW(sessions[0]['hwnd'],0x111,profile_command(host,profiles[i]),0)
            launch=wait_for(lambda:next(iter(dirs[i].glob('*.launch.json')),None));pids.append(wait_snapshot(lambda:read_snapshot(launch),lambda v:'pid' in v)['pid'])
            s=wait_for(lambda:(v if (v:=active()) and v['id'] not in [t['id'] for t in sessions] else None));sessions.append(s);host=sessions[0]['window'];assert s['window']==host and s['renderer']==2*i
            write_snapshot(file(i,'control'),dict(phase=1,sequence=scene(i)));wait_snapshot(lambda:read_snapshot(file(i,'report')),lambda v:v.get('hex')==ACK.hex());wait_for(lambda:WORDS[i] in text(i))
        report.update(host=host,children=pids,sessions=sessions);desk=DesktopInput(proc.pid,host,sessions[1]['hwnd'],report.setdefault('desktop',{}));saved=SavedClipboard(sessions[0]['hwnd'])
        switch(0);select(0);right(0);barrier('default right copies only')
        switch(1);desk.chord(0x11,0x10,ord('V'));barrier('tab B receives tab A text once',(b'',paste(1,WORDS[0])))
        select(1);right(1);barrier('opt-in right copies and pastes only into B',(b'',paste(1,WORDS[1])))
        switch(0);desk.chord(0x11,0x10,ord('V'));barrier('tab A receives tab B text once',(paste(0,WORDS[1]),b''))
        # No new mouse selection: Win32 focus and Copy must return to A's prior selection.
        seq=u.GetClipboardSequenceNumber();desk.chord(0x11,0x10,ord('C'));wait_for(lambda:u.GetClipboardSequenceNumber()!=seq and clipboard_text(desk.hwnd)==WORDS[0]);barrier('return to A preserves its own completed selection')
        switch(1);seq=u.GetClipboardSequenceNumber();desk.chord(0x11,0x10,ord('C'));wait_for(lambda:u.GetClipboardSequenceNumber()!=seq and clipboard_text(desk.hwnd)==WORDS[1]);barrier('return to B preserves its own completed selection')
        switch(0);seq=u.GetClipboardSequenceNumber();desk.chord(0x11,0x10,ord('C'));wait_for(lambda:u.GetClipboardSequenceNumber()!=seq and clipboard_text(desk.hwnd)==WORDS[0]);saved.restore();saved=None;desk.restore();desk=None
        for i in (1,0):
            write_snapshot(file(i,'control'),{'stop':True});exit=wait_snapshot(lambda:read_snapshot(file(i,'exit')),lambda v:v.get('reason')=='control-stop');report.setdefault('exits',[]).append(exit)
        report['frontend_exit']=proc.wait(timeout=12);assert report['frontend_exit']==0;report['completed']=True
    finally:
        if saved:saved.restore()
        if desk:desk.restore()


if __name__=='__main__':
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':raise SystemExit('Requires a GitHub-hosted Windows desktop')
    out=root/'research'/'tab-clipboard';out.mkdir(exist_ok=True);report={'completed':False};keys=[]
    try:
        with tempfile.TemporaryDirectory() as tmp,OwnedJob() as job:run(Path(tmp),job,out,report,keys)
    except BaseException:
        report['error']=traceback.format_exc();raise
    finally:
        (out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        for key in keys:winreg.DeleteKey(winreg.HKEY_CURRENT_USER,key)
