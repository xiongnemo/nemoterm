"""Observe an attached tmux client writing the clipboard while Vim owns the mouse."""
import base64
import hashlib
import io
import re
import subprocess
from PIL import Image, ImageChops
from clipboard_test_utils import clipboard_text, set_clipboard
from native_test_utils import u, wait_for
from presented_window_capture import PresentedWindowCapture

PAYLOAD = 'tmux → 剪贴板 🍵'
FENCE = 'NEMO_CLIPBOARD_FENCE'


def frame(pid, hwnd, renderer, folder, name):
    camera = PresentedWindowCapture(pid, hwnd, directx=renderer == 2)
    try:
        camera.wait_for_initial_geometry()
        im = Image.open(io.BytesIO(camera.capture())).convert('RGB')
        im.save(folder / ('clipboard-' + name + '.png'))
        return im
    finally:
        camera.close()


def exercise(report, policy, wsl, folder, posix, hwnd, desk, xy, photo, visible, state):
    rec = report['tmux_clipboard'] = {'policy':policy, 'payload':PAYLOAD}
    sock = (folder / 'tmux-socket').read_text()
    def tmux(*args):
        return subprocess.run([*wsl, 'tmux', '-S', sock, *args], capture_output=True,
                              timeout=12, check=True).stdout
    clients = tmux('list-clients','-F','#{client_name}').decode().splitlines()
    assert len(clients) == 1, clients
    rec['client'] = clients[0]
    (folder/'clip-payload.txt').write_bytes(PAYLOAD.encode())
    initial = photo('selected'); cw, ch = ((initial.width-2)//60,(initial.height-2)//20)
    box=(1+4*cw,1+ch,1+10*cw,1+2*ch)
    with Image.open(folder/'clipboard-base.png') as base:
        diff=ImageChops.difference(base.convert('RGB'),initial)
        ratios=[]
        for col in range(4,10):
            hist=diff.crop((1+col*cw,1+ch,1+(col+1)*cw,1+2*ch)).convert('L').histogram()
            ratios.append(1-hist[0]/(cw*ch))
        rec['selected_cell_ratios']=ratios
        assert max(ratios[0],ratios[-1])<.1 and min(ratios[1:-1])>.5,ratios
    set_clipboard(hwnd,'local clipboard sentinel'); first=u.GetClipboardSequenceNumber()
    tmux('load-buffer','-w','-b','nemo-clip','-t',clients[0],posix+'/clip-payload.txt')
    assert tmux('save-buffer','-b','nemo-clip','-') == PAYLOAD.encode()
    # The marker is published only after load-buffer has returned, and Vim writes
    # its echo through the same attached client as the clipboard request.
    (folder/'clip-fence').touch(exist_ok=False); visible(FENCE)
    wanted=PAYLOAD if policy=='default' else 'local clipboard sentinel'
    if policy=='default': wait_for(lambda:clipboard_text(hwnd)==wanted)
    rec['remote_text']=clipboard_text(hwnd); rec['remote_changed']=u.GetClipboardSequenceNumber()!=first
    assert rec['remote_text']==wanted and rec['remote_changed']==(policy=='default'),rec
    after=photo('remote');rec['same_selected_pixels']=initial.crop(box).tobytes()==after.crop(box).tobytes();assert rec['same_selected_pixels']
    for label,keys in [('right',('right',)),('shortcut',(0x11,0x10,ord('C')))]:
        set_clipboard(hwnd,label+' sentinel'); seq=u.GetClipboardSequenceNumber();desk.point(*xy(6,1));desk.chord(*keys)
        wait_for(lambda:u.GetClipboardSequenceNumber()!=seq and clipboard_text(hwnd)=='中文');rec[label]=clipboard_text(hwnd)
    rec['tmux_buffer_after_local_copy']=tmux('save-buffer','-b','nemo-clip','-').decode();assert rec['tmux_buffer_after_local_copy']==PAYLOAD
    end=state('after-tmux-clipboard');assert end['cursor']==[3,5] and end['mode']=='n' and end['lines']==['VIM_MOUSE_HEAD','COPY 中文 tail','CLICK_CURSOR_TARGET','UNCHANGED_END']


def verify_wire(folder,report):
    raw=(folder/'clipboard-client.vt').read_bytes();payload=base64.b64encode(PAYLOAD.encode())
    packets=list(re.finditer(rb'\x1b\]52;([cpsq0-7]*);'+re.escape(payload)+rb'(?:\x07|\x1b\\)',raw))
    assert len(packets)==1, (len(packets),len(raw));packet=packets[0]; marker=raw.find(FENCE.encode(),packet.end());assert marker>=packet.end()
    report['tmux_clipboard']['wire']={'sha256':hashlib.sha256(raw).hexdigest(),'length':len(raw),'packet_hex':packet.group().hex(),'offset':packet.start(),'fence_offset':marker}
