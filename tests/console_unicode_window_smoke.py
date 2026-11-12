"""Unicode VT input must retain text in native ReadConsoleInputW consumers.

Windows Terminal's SendCharEvent emits key-down text commits. Surrogate text
units must stay adjacent without invented character-bearing releases between
them; crossterm's Windows event decoder otherwise loses the scalar completely.
"""
from native_test_utils import (root,c,w,u,hashlib,json,os,subprocess,sys,tempfile,
    Path,time,wait_for,find_window,read_snapshot,write_snapshot,wait_snapshot)
import uuid
import winreg

exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
profile='console-unicode-'+uuid.uuid4().hex
keypath='Software\\Nemo\\Nemoterm\\Sessions\\'+profile
evidence=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),runs=[])
with winreg.CreateKey(winreg.HKEY_CURRENT_USER,keypath) as key:
    for name,value in dict(WarnOnClose=0,NemoWin32Input=0).items():
        winreg.SetValueEx(key,name,0,winreg.REG_DWORD,value)
try:
    for batch in (1,3,128):
        with tempfile.TemporaryDirectory(prefix='nemoterm-console-unicode-') as directory:
            report,control=(Path(directory)/name for name in ('report','control'))
            process=subprocess.Popen([str(exe),'-load',profile,'-e',sys.executable,
                str(root/'tests/win32_input_fixture.py'),str(report),str(control),'--batch',str(batch)],
                env=dict(os.environ,NEMOTERM_CONPTY='bundled'),creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                hwnd=wait_for(lambda:find_window(process.pid))
                def current():
                    value=read_snapshot(report)
                    assert not value.get('error') and process.poll() is None,value
                    return value
                for slow in (False,True):
                    phase=f'{batch}-{slow}'
                    write_snapshot(control,dict(phase=phase))
                    wait_snapshot(current,lambda v:v.get('phase')==phase)
                    text='A中é e\u0301\U0001f642\U00020000\U000f0001Z'
                    for char in text:
                        u.SendMessageW(hwnd,0x109,ord(char),0)
                        if slow:time.sleep(.025)
                    # Enter after the scalar also proves the next key is not
                    # consumed as a surrogate continuation or held indefinitely.
                    u.SendMessageW(hwnd,0x100,13,1|(28<<16))
                    u.SendMessageW(hwnd,0x101,13,1|(28<<16)|0xc0000000)
                    value=wait_snapshot(current,lambda v:any(e.get('vk')==13 and not e.get('down') for e in v.get('events',[])))
                    events=[e for e in value['events'] if e['type']=='key']
                    down=b''.join(e['character'].to_bytes(2,'little')*e['repeat']
                                  for e in events if e['down'] and e['character'])
                    assert down.decode('utf-16-le')==text+'\r',(batch,slow,events)
                    surrogate_events=[e for e in events if 0xd800<=e['character']<=0xdfff]
                    assert len(surrogate_events)==6 and all(e['down'] for e in surrogate_events),(batch,slow,surrogate_events)
                    evidence['runs'].append(dict(batch=batch,slow=slow,events=events,text=text))
            finally:
                write_snapshot(control,dict(stop=True))
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=5);raise
    (root/'research/console-unicode-observed.json').write_text(json.dumps(evidence,indent=2))
    print('Native console Unicode events passed: 3 read sizes, bulk and separated input')
finally:
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER,keypath)
