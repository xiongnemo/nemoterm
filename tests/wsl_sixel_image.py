"""Compare a WSL application's Sixel output with its independently decoded PNG."""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback
import uuid
import winreg

from PIL import Image, ImageChops
from native_test_utils import c, w, root, u, wait_for

sys.path.insert(0, str(root/'tools'))
import nemoterm_debug as api

COLS, ROWS, BORDER = 40, 12, 1
FONT = os.environ['NEMOTERM_TEST_FONT']
EXE = Path(os.environ['NEMOTERM_TEST_EXE']).resolve()
DISTRO = os.environ['NEMOTERM_TEST_WSL_DISTRO']
WSL = shutil.which('wsl.exe')
u.RedrawWindow.argtypes = [w.HWND, c.c_void_p, w.HANDLE, w.UINT]
u.RedrawWindow.restype = w.BOOL


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pattern():
    image = Image.new('P', (24, 18))
    image.putpalette([0,0,0, 255,0,0, 0,255,0, 0,0,255, 255,255,0]+[0]*(256*3-15))
    for y in range(18):
        for x in range(24):
            image.putpixel((x,y), 1+(x//7+y//4)%4 if x < 20 or y < 9 else 0)
    return image


def exercise(renderer, target):
    folder = root/'research'/('wsl-sixel-'+renderer)
    folder.mkdir(parents=True)
    profile = 'wsl-sixel-'+uuid.uuid4().hex
    reg = 'Software\\Nemo\\Nemoterm\\Sessions\\'+profile
    report = dict(completed=False, executable_sha256=digest(EXE), requested=renderer, font=FONT, fixture_sha256=digest(Path(__file__)), phases=[])
    original = pattern(); original.save(folder/'source.png')
    original.convert('RGB').save(folder/'source-rgb.png')
    script = folder/'producer.sh'
    script.write_bytes(r'''set -euo pipefail
cd -- "$(dirname -- "$0")"
exec 2>producer.stderr
trap 'echo "$?" > producer.exit' EXIT
await() { for ((i=0;i<600;i++)); do [[ ! -f stop ]] || exit 23; [[ ! -f "$1" ]] || return 0; sleep .1; done; return 22; }
{ printf 'TERM=%s\n' "$TERM"; dpkg-query -W libsixel-bin; command -v img2sixel sixel2png; sha256sum "$(command -v img2sixel)" "$(command -v sixel2png)"; } > tools.txt
printf '\033[?25l\033[?80l\033[?1070h\033[0m\033]11;rgb:0/0/0\007\033[2J\033[9;1HSIXEL_BEFORE'
await draw
printf '\033[2;3H'
img2sixel -7 -b xterm256 -d none source-rgb.png | tee encoded.six
sixel2png -i encoded.six -o decoded.png
printf '\033[9;1HSIXEL_DRAWN '
await erase
printf '\033[2J\033[9;1HSIXEL_ERASED'
await finish
'''.encode('ascii'))
    unix = '/mnt/'+script.drive[0].lower()+script.as_posix()[2:]
    proc = None
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,reg) as key:
            for k,v in dict(NemoRenderer=target, WarnOnClose=0, CloseOnExit=1, WindowBorder=BORDER,
                            ScrollBar=0, ScrollBarFullScreen=0, FontHeight=12).items():
                winreg.SetValueEx(key,k,0,winreg.REG_DWORD,v)
        command=[str(EXE),'--no-tabs','-load',profile,'--automation','--cols',str(COLS),'--rows',str(ROWS),
                 '--font',FONT,'-e',WSL,'--distribution',DISTRO,'--exec','bash',unix]
        proc=subprocess.Popen(command, env=dict(os.environ,NEMOTERM_CONPTY='bundled'),creationflags=subprocess.CREATE_NO_WINDOW)
        inst=wait_for(lambda:next(iter(api.discover(proc.pid)),None),timeout=25)
        sess,=inst['sessions'];report['session']=sess
        assert sess['renderer']==target and (sess['cols'],sess['rows'])==(COLS,ROWS),sess
        def snapshot(op): return api.request(inst['endpoint'],op,sess['id'])
        def marker(text):
            def seen():
                if (folder/'producer.exit').is_file() or proc.poll() is not None:
                    raise RuntimeError(f'producer exited before {text}')
                return text in snapshot('text')
            wait_for(seen,timeout=30)
        marker('SIXEL_BEFORE')
        w,h=sess['client_width'],sess['client_height']
        cw,rw=divmod(w-2*BORDER,COLS);ch,rh=divmod(h-2*BORDER,ROWS)
        assert cw>0 and ch>0 and (rw,rh)==(0,0),(w,h)
        x,y=BORDER+2*cw,BORDER+ch
        box=(x-1,y-1,x+25,y+19);report['guarded_crop']=box
        black=Image.new('RGB',(26,20))
        def check(name, expected):
            phase={'name':name};report['phases'].append(phase)
            last=None
            def captured():
                nonlocal last
                last=snapshot('image')
                frame=Image.open(io.BytesIO(last)).convert('RGB');assert frame.size==(w,h)
                region=frame.crop(box);diff=ImageChops.difference(region,expected)
                phase['difference_box']=diff.getbbox()
                pixels=diff.tobytes()
                phase['different_pixels']=sum(pixels[i:i+3] != b'\0\0\0' for i in range(0,len(pixels),3))
                return phase['different_pixels']==0
            try: wait_for(captured,timeout=7)
            finally:
                if last: (folder/(name+'.png')).write_bytes(api.png_from_bmp(last))
        check('before',black)
        (folder/'draw').touch();marker('SIXEL_DRAWN')
        wire=(folder/'encoded.six').read_bytes();assert wire.startswith(b'\x1bP') and b'\x1b\\' in wire
        reference=Image.open(folder/'decoded.png').convert('RGB')
        assert reference.size==original.size
        # Independently require the fixture to represent the intended colours and geometry.
        extrema=ImageChops.difference(reference,original.convert('RGB')).getextrema()
        report['source_decode_channel_ranges']=extrema
        expected=black.copy();expected.paste(reference,(1,1));expected.save(folder/'guarded-reference.png')
        check('drawn',expected)
        assert u.RedrawWindow(sess['hwnd'],None,None,0x101)  # invalidate and repaint now
        check('repainted',expected)
        (folder/'erase').touch();marker('SIXEL_ERASED');check('erased',black)
        (folder/'finish').touch();assert proc.wait(timeout=15)==0 and (folder/'producer.exit').read_text().strip()=='0'
        assert max(high for _,high in extrema)<=8,extrema
        report['completed']=True
    except Exception:
        report['error']=traceback.format_exc();raise
    finally:
        if proc and proc.poll() is None:
            (folder/'stop').touch()
            try: proc.wait(timeout=8)
            except subprocess.TimeoutExpired: proc.terminate();proc.wait(timeout=8);report['forced_cleanup']=True
        try: winreg.DeleteKey(winreg.HKEY_CURRENT_USER,reg)
        except FileNotFoundError: pass
        report['file_hashes']={p.name:digest(p) for p in sorted(folder.iterdir()) if p.is_file() and p.name!='result.json'}
        (folder/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__=='__main__':
    assert os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    failures=[]
    for name,index in [('gdi',0),('directx',2)]:
        try: exercise(name,index)
        except Exception: traceback.print_exc();failures.append(name)
    if failures: raise SystemExit('WSL Sixel failures: '+', '.join(failures))
