"""Physical order when a different Windows process deliberately delays CF_UNICODETEXT."""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from clipboard_test_utils import SavedClipboard
from fixture_io import read_snapshot, write_snapshot
from hosted_gesture_input import DesktopInput
from native_test_utils import c, w, u, root, wait_for, terminal_host
from protocol_oracle_window import run


def trial(expire):
    assert os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted' and os.environ.get('GITHUB_ACTIONS')=='true'
    renderer={'gdi':1,'directx':3}[os.environ['RENDERER']]
    label='paste-lines-delayed-'+('expiry-' if expire else 'order-')+os.environ['RENDERER']
    os.environ.update(NEMOTERM_TEST_INPUT_CP='65001',NEMOTERM_TEST_WIDE_INPUT='1')
    record={}; data='delayed clipboard 秘密 😀'.encode(); ack=b'\x1b[0n'
    def exercise(hwnd,phase,current):
        pid=w.DWORD();assert u.GetWindowThreadProcessId(hwnd,c.byref(pid))
        u.GetPropW.argtypes,u.GetPropW.restype=[w.HWND,w.LPCWSTR],w.HANDLE
        assert int(u.GetPropW(hwnd,'NemotermRenderer') or 0)==renderer
        clip=SavedClipboard(hwnd);desk=None
        try:
            desk=DesktopInput(pid.value,terminal_host(hwnd),hwnd,record.setdefault('keyboard',{}))
            with tempfile.TemporaryDirectory() as tmp:
                state=Path(tmp)/'state.json';control=Path(tmp)/'control.json'
                helper=subprocess.Popen([sys.executable,str(root/'tests/osc52_delayed_fixture.py'),str(state),str(control),*(['--long-hold'] if expire else [])],creationflags=subprocess.CREATE_NO_WINDOW)
                try:
                    wait_for(lambda:read_snapshot(state).get('state')=='ready');phase('ordered','',b'')
                    desk.chord(0x11,0x10,ord('V'));wait_for(lambda:read_snapshot(state).get('state')=='rendering')
                    started=time.monotonic();desk.chord(0x0d);desk.chord(ord('7'))
                    if not expire:
                        desk.chord(0x11,0x10,ord('V'));desk.chord(ord('8'))
                    # Leave the owner blocked while the GUI can dispatch ordinary
                    # events. No following gesture waits for pasted bytes to arrive.
                    time.sleep(.25);response=c.c_size_t()
                    assert u.SendMessageTimeoutW(hwnd,0,0,0,2,300,c.byref(response))
                    record['before_release']=current()['hex'];record['owner_still_waiting']=read_snapshot(state).get('state')=='rendering'
                    if expire:
                        wait_for(lambda:current()['hex']==(ack+b'\r7').hex(),timeout=10)
                        record['seconds_to_release_keys']=time.monotonic()-started
                        assert 4.5<=record['seconds_to_release_keys']<10 and read_snapshot(state).get('state')=='rendering'
                    write_snapshot(control,{'release':True});wait_for(lambda:read_snapshot(state).get('state')=='rendered')
                    if expire:
                        # The timed-out response may finish after a new key. It
                        # must not insert its text into this or a later input.
                        desk.chord(ord('9'));time.sleep(.4)
                    expected=ack+b'\r79' if expire else ack+data+b'\r7'+data+b'8'
                    record['expected']=expected.hex()
                    wait_for(lambda: len(bytes.fromhex(current()['hex']))>=len(expected),timeout=12)
                    record['received']=current()['hex']
                finally:
                    write_snapshot(control,{'release':True,'stop':True})
                    try:helper.wait(timeout=6)
                    except subprocess.TimeoutExpired:helper.kill();helper.wait();raise
        finally:
            if desk:desk.restore()
            clip.restore()
    try:
        run(label,[],exercise=exercise,barrier=('\x1b[5n',ack),profile={'NemoRenderer':renderer-1,'WarnOnClose':0},font=os.environ['NEMOTERM_TEST_FONT'],source_reference='Explicit physical gesture order')
        assert record['owner_still_waiting'] and record['before_release']==ack.hex() and record['received']==record['expected'],record
    finally:(root/'research'/(label+'-keys.json')).write_text(json.dumps(record,indent=2))


if __name__=='__main__':
    trial('--expiry' in sys.argv)
