"""Check the pixels emitted by Ubuntu terminfo, including actual direct-colour bytes."""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback
import uuid
import winreg

from PIL import Image
from native_test_utils import c, w, root, u, wait_for
sys.path.insert(0, str(root/'tools'))
import nemoterm_debug as api

# The palette override below gives slot 2 a known non-default colour. Slot 68
# is (1,2,4) in the standard six-level cube. The direct RGB pair differs by
# one blue level: reporting success after quantising both is not possible.
CASES = {'xterm': (8, '#25a34c', '#25a34c'),
         'xterm-256color': (256, '#5f87d7', '#5f87d7'),
         'xterm-direct': (16777216, '#12569a', '#12569b')}
DRIVER = r'''set -euo pipefail
cd -- "$(dirname -- "$0")"
exec 2>stderr.txt
trap 'echo "$?" > exit' EXIT
await() { for ((i=0;i<600;i++)); do [[ ! -f stop ]] || exit 22; [[ ! -f "$1" ]] || return 0; sleep .1; done; exit 23; }
{ printf '%s\n' "$TERM" "$COLORTERM" "$TERM_PROGRAM"; dpkg-query -W ncurses-bin ncurses-term; tput -V; sha256sum "$(command -v tput)"; } > identity.txt
[[ "$TERM" == xterm-256color && "$COLORTERM" == truecolor && "$TERM_PROGRAM" == nemoterm ]]
printf '\033[2J\033[HCOL_PRIOR_SCREEN'
for type in xterm xterm-256color xterm-direct; do
  await "go-$type"
  (
    export TERM="$type"
    infocmp -x "$TERM" > "$type.ti"
    tput colors > "$type.count"
    case "$type" in xterm) a=2; b=2;; xterm-256color) a=68; b=68;; xterm-direct) a=$((0x12569a)); b=$((0x12569b));; esac
    tput setab "$a" > "$type.bg"; tput setaf "$b" > "$type.fg"
    {
      tput smcup; tput clear; tput civis
      printf '\033]4;2;rgb:25/a3/4c\033\\'
      tput cup 2 4; cat "$type.bg"; printf '    '; tput sgr0
      tput cup 2 10; tput rev; cat "$type.fg"; printf '    '; tput sgr0
      if [[ "$COLORTERM" == truecolor ]]; then
        tput cup 2 16; printf '\033[48;2;18;86;155m    '; tput sgr0
      fi
      tput cup 6 0; printf 'COL_DRAWN:%s:' "$type"
    } | tee "$type.vt"
    await "leave-$type"
    tput sgr0; tput cnorm; tput rmcup
  )
  printf '\033[9;1HCOL_RESTORED:%s:' "$type"
done
await finish
'''

def digest(data): return hashlib.sha256(data).hexdigest()

def exercise(renderer, index):
    folder = root/'research'/('wsl-terminfo-colour-'+renderer); folder.mkdir(parents=True)
    exe = Path(os.environ['NEMOTERM_TEST_EXE']); font = os.environ['NEMOTERM_TEST_FONT']
    script = folder/'driver.sh'; script.write_bytes(DRIVER.encode('ascii'))
    profile = 'terminfo-colour-'+uuid.uuid4().hex; reg = 'Software\\Nemo\\Nemoterm\\Sessions\\'+profile
    report = dict(completed=False, renderer=renderer, font=font, exe_sha256=digest(exe.read_bytes()), cases={})
    proc = None
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,reg) as key:
            for n,v in dict(NemoRenderer=index,WarnOnClose=0,CloseOnExit=1,ScrollBar=0,WindowBorder=1,FontHeight=12).items():
                winreg.SetValueEx(key,n,0,winreg.REG_DWORD,v)
        unix = '/mnt/'+script.drive[0].lower()+script.as_posix()[2:]
        proc = subprocess.Popen([str(exe),'--no-tabs','-load',profile,'--automation','--cols','40','--rows','12','--font',font,'-e',shutil.which('wsl.exe'),'--distribution',os.environ['NEMOTERM_TEST_WSL_DISTRO'],'--exec','bash',unix],env=dict(os.environ,NEMOTERM_CONPTY='bundled'),creationflags=subprocess.CREATE_NO_WINDOW)
        inst = wait_for(lambda:next(iter(api.discover(proc.pid)),None),timeout=30); sess,=inst['sessions']; report['session']=sess
        assert sess['renderer']==index and (sess['cols'],sess['rows'])==(40,12),sess
        cw,rw=divmod(sess['client_width']-2,40); ch,rh=divmod(sess['client_height']-2,12); assert min(cw,ch)>1 and rw==rh==0
        def request(op): return api.request(inst['endpoint'],op,sess['id'])
        def marker(word):
            def seen():
                assert not (folder/'exit').exists() and proc.poll() is None,word
                return word in request('text')
            wait_for(seen,timeout=15)
        # The grid text can be ahead of a presented DirectX frame. Wait only for
        # independently positioned marker text, never for the swatches under test.
        def capture(name, visible_row, cleared_row=None):
            start=time.monotonic(); observations=[]; bmp=None; image=None
            def ink(row):
                data=image.crop((1,1+row*ch,1+8*cw,1+(row+1)*ch)).convert('L')
                return sum(data.histogram()[16:])
            def presented():
                nonlocal bmp,image
                bmp=request('image'); image=Image.open(io.BytesIO(bmp)).convert('RGB')
                current=ink(visible_row); cleared=ink(cleared_row) if cleared_row is not None else 0
                observations.append([round(time.monotonic()-start,4),current,cleared])
                if len(observations)==1: (folder/(name+'-first.png')).write_bytes(api.png_from_bmp(bmp))
                return current>=12 and cleared==0
            try: wait_for(presented,timeout=5)
            finally:
                report.setdefault('frame_markers',{})[name]=observations
                if bmp: (folder/(name+'.png')).write_bytes(api.png_from_bmp(bmp))
            return image
        marker('COL_PRIOR_SCREEN'); initial=capture('before',0)
        boxes=[(1+col*cw,1+2*ch,1+(col+4)*cw,1+3*ch) for col in (4,10,16)]
        # Include a blank cell on either side of every four-cell swatch.
        guards=[(1+col*cw,1+2*ch,1+(col+1)*cw,1+3*ch) for col in (3,8,9,14,15,20)]
        def pixels(im,box): return im.crop(box).tobytes()
        for term,(count,bg,fg) in CASES.items():
            r=report['cases'][term]={}; (folder/('go-'+term)).touch(); marker('COL_DRAWN:'+term+':')
            r['count']=int((folder/(term+'.count')).read_text()); assert r['count']==count
            r['sequences']={n:(folder/(term+'.'+n)).read_bytes().hex() for n in ('bg','fg')}; assert all(r['sequences'].values())
            assert 'COL_PRIOR_SCREEN' not in request('text')
            r['pixel_phases']={}
            for phase in ('drawn','repainted'):
                if phase=='repainted': assert u.RedrawWindow(sess['hwnd'],None,None,0x101)
                image=capture(term+'-'+phase,6,0); actual=[]
                for box,wanted in zip(boxes,[bg,fg,'#12569b']):
                    wanted_rgb=bytes.fromhex(wanted[1:]); data=pixels(image,box)
                    actual.append(dict(expected=wanted,first=data[:3].hex(),wrong=sum(data[i:i+3]!=wanted_rgb for i in range(0,len(data),3))))
                r['pixel_phases'][phase]=actual
                assert all(x['wrong']==0 for x in actual), (term,phase,actual)
                assert all(pixels(image,g)==pixels(initial,g) for g in guards),(term,phase,'neighbours')
            (folder/('leave-'+term)).touch(); marker('COL_RESTORED:'+term+':'); assert 'COL_PRIOR_SCREEN' in request('text') and 'COL_DRAWN:' not in request('text')
            image=capture(term+'-restored',0,6); assert all(pixels(image,g)==pixels(initial,g) for g in boxes+guards)
            r['restored']=True
        (folder/'finish').touch(); assert proc.wait(timeout=15)==0 and (folder/'exit').read_text().strip()=='0'; report['completed']=True
    except Exception:
        report['error']=traceback.format_exc(); raise
    finally:
        if proc and proc.poll() is None:
            (folder/'stop').touch()
            try:proc.wait(timeout=7)
            except subprocess.TimeoutExpired:proc.terminate();proc.wait(timeout=7);report['forced_cleanup']=True
        try: winreg.DeleteKey(winreg.HKEY_CURRENT_USER,reg)
        except FileNotFoundError: pass
        report['hashes']={p.name:digest(p.read_bytes()) for p in sorted(folder.iterdir()) if p.is_file() and p.name!='result.json'}
        (folder/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')

if __name__=='__main__':
    assert os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
    u.RedrawWindow.argtypes=[w.HWND,c.c_void_p,w.HANDLE,w.UINT]; u.RedrawWindow.restype=w.BOOL
    failures=[]
    for name,idx in [('gdi',0),('directx',2)]:
        try: exercise(name,idx)
        except Exception: traceback.print_exc();failures.append(name)
    if failures: raise SystemExit('WSL terminfo colour failed: '+', '.join(failures))
