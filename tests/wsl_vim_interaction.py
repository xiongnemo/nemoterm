"""Exercise foreground mouse ownership, Shift-copy, paste and resize in actual WSL Vim."""
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
from clipboard_test_utils import SavedClipboard, clipboard_text, set_clipboard
from hosted_gesture_input import DesktopInput
from native_test_utils import c, w, k, u, root, wait_for
sys.path.insert(0,str(root/'tools'))
import nemoterm_debug as api

GRID=(60,20)
BUFFER=['VIM_MOUSE_HEAD', 'COPY 中文 tail', 'CLICK_CURSOR_TARGET','UNCHANGED_END']
VIMRC=r'''set nocompatible encoding=utf-8 mouse=a ttymouse=sgr
set nonumber norelativenumber nowrap nofoldenable noshowmode noruler noshowcmd laststatus=0
set shortmess+=I ttimeout ttimeoutlen=100 nobackup nowritebackup noswapfile
let s:next_request = 1
function! NemoObserve(timer) abort
  if filereadable('stop') | qa! | endif
  let id = s:next_request
  if !filereadable('request-'.id) | return | endif
  let state={'request_id':id, 'grid':[&columns,&lines], 'cursor':[line('.'),col('.')], 'mode':mode(1), 'term':&term, 'mouse':&mouse, 'ttymouse':&ttymouse, 'lines':getline(1,'$')}
  call writefile([json_encode(state)],'state-'.id.'.tmp')
  if rename('state-'.id.'.tmp','state-'.id.'.json') == 0
    let s:next_request += 1
  endif
endfunction
augroup NemoEvidence
  autocmd!
  autocmd VimEnter * call timer_start(30, function('NemoObserve'), {'repeat': -1})
  autocmd InsertEnter * call writefile(['enter'], 'insert-events', 'a')
  autocmd InsertLeave * call writefile(['leave'], 'insert-events', 'a')
  autocmd VimResized * call writefile([printf('%dx%d', &columns, &lines)], 'resizes', 'a')
augroup END
'''
DRIVER=r'''set -eu
cd -- "$(dirname -- "$0")"
case "$1" in plain) export TERM=xterm;; esac
export LC_ALL=C.UTF-8
{ printf 'TERM=%s\n' "$TERM"; command -v vim; vim --version; sha256sum "$(command -v vim)"; } > vim-id.txt
await() { for ((i=0;i<1200;i++)); do [[ ! -f stop ]] || return 22; [[ ! -f "$1" ]] || return 0; sleep .1; done; return 23; }
printf '\033[2J\033[HVIM_PRIOR_SCREEN\n'
await start
if [[ "$2" = tmux ]]; then
    scratch=$(mktemp -d); sock="$scratch/tmux.sock"
    trap 'tmux -S "$sock" kill-server 2>/dev/null || :; rmdir "$scratch" 2>/dev/null || :' EXIT
    { tmux -V; sha256sum "$(command -v tmux)"; infocmp tmux-256color; } > tmux-id.txt
    printf '%s' "$sock" > tmux-socket
    tmux -S "$sock" -f "$PWD/tmux.conf" new-session -s fixture -c "$PWD" 'vim -Nu fixture.vim -i NONE -n -- buffer.txt; printf %s "$?" > vim-exit'
else
    vim -Nu fixture.vim -i NONE -n -- buffer.txt
    printf '%s' "$?" > vim-exit
fi
printf '\033[12;1HVIM_RETURNED'
await finish
'''
u.GetWindowRect.argtypes=[w.HWND,c.POINTER(w.RECT)]
u.SetWindowPos.argtypes=[w.HWND,w.HWND,c.c_int,c.c_int,c.c_int,c.c_int,w.UINT]

TMUX_CONF="""set -g status off
set -g mouse on
set -g default-terminal tmux-256color
"""

def trial(renderer,branch,mux):
    suite='wsl-tmux-vim' if mux else 'wsl-vim'
    folder=root/'research'/f'{suite}-{renderer}-{branch}';folder.mkdir(parents=True)
    exe=Path(os.environ['NEMOTERM_TEST_EXE']);font=os.environ['NEMOTERM_TEST_FONT'];term='xterm' if branch=='plain' else 'xterm-256color'
    profile='vim-test-'+uuid.uuid4().hex;reg='Software\\Nemo\\Nemoterm\\Sessions\\'+profile
    report=dict(completed=False,renderer=renderer,term=term,font=font,sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),checks=[],states=[])
    posix='/mnt/'+folder.drive[0].lower()+folder.as_posix()[2:]
    (folder/'buffer.txt').write_bytes(('\n'.join(BUFFER)+'\n').encode());(folder/'fixture.vim').write_bytes(VIMRC.encode());(folder/'driver').write_bytes(DRIVER.encode())
    if mux:(folder/'tmux.conf').write_bytes(TMUX_CONF.encode())
    wsl=[shutil.which('wsl.exe'),'--distribution',os.environ['NEMOTERM_TEST_WSL_DISTRO'],'--exec']
    proc=desk=clip=None; serial=0
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,reg) as key:
            for name,value in dict(NemoRenderer=renderer,WarnOnClose=0,CloseOnExit=1,WindowBorder=1,ScrollBar=0,FontHeight=12).items():winreg.SetValueEx(key,name,0,winreg.REG_DWORD,value)
        proc=subprocess.Popen([str(exe),'--no-tabs','-load',profile,'--automation','--cols','60','--rows','20','--font',font,'-e',*wsl,'bash',posix+'/driver',branch,'tmux' if mux else 'direct'],env=dict(os.environ,NEMOTERM_CONPTY='bundled'),creationflags=subprocess.CREATE_NO_WINDOW)
        inst=wait_for(lambda:next(iter(api.discover(proc.pid)),None),timeout=30);s,=inst['sessions'];endpoint=inst['endpoint'];seat=s['id'];hwnd=s['hwnd'];report['session']=s
        def call(op,payload=b''):return api.request(endpoint,op,seat,payload)
        def photo(name):
            bmp=call('image');(folder/(name+'.png')).write_bytes(api.png_from_bmp(bmp));return Image.open(io.BytesIO(bmp)).convert('RGB')
        def screen():return call('text')
        def visible(text):wait_for(lambda:text in screen(),timeout=20)
        def state(label):
            nonlocal serial
            # WSL may hold a request open while Windows polls Vim's state. Each
            # numbered empty marker is published only once and never replaced.
            serial+=1;(folder/f'request-{serial}').touch(exist_ok=False)
            p=folder/f'state-{serial}.json';wait_for(p.exists,timeout=5);d=json.loads(p.read_text(encoding='utf-8'));assert d['request_id']==serial,d
            report['states'].append(dict(stage=label,**d));return d
        def mux_state(label,grid):
            if not mux:return
            # Ask through a separate control connection: querying must not type into Vim
            # or switch it out of raw input mode. The socket belongs to this trial.
            sock=(folder/'tmux-socket').read_text()
            captured=subprocess.run([*wsl,'tmux','-S',sock,'list-clients','-F','#{client_termname}|#{client_width}|#{client_height}',
                ';','list-panes','-a','-F','#{pane_width}|#{pane_height}|#{pane_in_mode}',
                ';','show-options','-gv','mouse'],capture_output=True,timeout=10)
            lines=captured.stdout.decode('utf-8').splitlines()
            report.setdefault('tmux_states',[]).append(dict(stage=label,lines=lines,exit=captured.returncode,stderr=captured.stderr.decode('utf-8',errors='replace')))
            assert captured.returncode==0 and lines==[f'{term}|{grid[0]}|{grid[1]}',f'{grid[0]}|{grid[1]}|0','on'],report['tmux_states'][-1]
        assert s['renderer']==renderer and (s['cols'],s['rows'])==GRID,s
        cw,rw=divmod(s['client_width']-2,60);ch,rh=divmod(s['client_height']-2,20);assert not (rw or rh) and min(cw,ch)>0
        def xy(col,row):return (1+col*cw+cw//2,1+row*ch+ch//2)
        visible('VIM_PRIOR_SCREEN');(folder/'start').touch();visible(BUFFER[1]);before=state('initial');assert before['lines']==BUFFER and before['term']==('tmux-256color' if mux else term) and before['mouse']=='a' and before['ttymouse']=='sgr' and before['grid']==list(GRID),before
        mux_state('initial',GRID)
        rows=screen().splitlines();assert rows[1].startswith(BUFFER[1]) and rows[2].startswith(BUFFER[2]);assert 'VIM_PRIOR_SCREEN' not in screen()
        desk=DesktopInput(proc.pid,s['window'],hwnd,report.setdefault('desktop',{}));clip=SavedClipboard(hwnd);set_clipboard(hwnd,'NEMO_VIM_UNCOPIED')
        desk.point(*xy(4,2));desk.event(None,True);desk.event(None,False)
        # Cursor position comes from Vim itself; the following capture does not type into the editor.
        wait_for(lambda:state('normal-click')['cursor']==[3,5]);report['checks'].append('ordinary click reached Vim at row 3 column 5')
        base=photo('before-drag'); x0,y0=xy(6,1);x1,_=xy(7,1)
        def highlighted():
            frame=Image.open(io.BytesIO(call('image'))).convert('RGB');ratios=[]
            for col in range(4,10):
                box=(1+col*cw,1+ch,1+(col+1)*cw,1+2*ch)
                diff=ImageChops.difference(base.crop(box),frame.crop(box)).convert('L').histogram();ratios.append(1-diff[0]/(cw*ch))
            report['highlight_changed_ratios']=ratios
            return max(ratios[0],ratios[-1])<.1 and min(ratios[1:-1])>.5
        desk.drag(x0,x1,y0,highlighted);photo('selection');desk.chord(0x11,0x10,ord('C'))
        wait_for(lambda:clipboard_text(hwnd)=='中文');after=state('shift-copy');assert after['cursor']==[3,5] and after['mode']=='n' and after['lines']==BUFFER,after
        mux_state('shift-copy',GRID)
        report['checks'].append('Shift drag selected four rendered cells; exact Unicode copied; Vim cursor and buffer unchanged')
        for cols,rows in [(72,24),(52,16)]:
            current,=api.request(endpoint)['sessions'];rect=w.RECT();assert u.GetWindowRect(s['window'],c.byref(rect));assert u.SetWindowPos(s['window'],None,0,0,rect.right-rect.left+(cols-current['cols'])*cw,rect.bottom-rect.top+(rows-current['rows'])*ch,0x16)
            name=f'{cols}x{rows}';p=folder/'resizes';wait_for(lambda:p.exists() and name in p.read_text().splitlines(),timeout=12)
            seen=state(name);front,=api.request(endpoint)['sessions'];assert seen['grid']==[cols,rows] and (front['cols'],front['rows'])==(cols,rows) and seen['cursor']==[3,5] and seen['lines']==BUFFER
            mux_state(name,(cols,rows))
            photo('resize-'+name);report['checks'].append('VimResized and frontend agree: '+name)
        call('input','A');events=folder/'insert-events';wait_for(lambda:events.exists() and events.read_text().splitlines()[-1:]==['enter'])
        desk.chord(0x11,0x10,ord('V'));visible(BUFFER[2]+'中文');desk.chord(0x1b);wait_for(lambda:events.read_text().splitlines()[-1:]==['leave'])
        pre_box=state('before-rectangle');base=photo('before-rectangle')
        set_clipboard(hwnd,'NEMO_VIM_UNCOPIED_RECTANGLE')
        desk.point(*xy(6,1));desk.event(0x10,True);desk.event(0x11,True);desk.event(None,True)
        wait_for(lambda:desk.state().capture==hwnd)
        # Start on the second cell of 中, then release both modifiers before
        # the final move: the button still belongs to the original selection.
        desk.point(*xy(6,2));desk.event(0x11,False);desk.event(0x10,False);desk.point(*xy(7,2))
        def rectangle():
            frame=Image.open(io.BytesIO(call('image'))).convert('RGB');ratios={}
            for row in (1,2):
                for col in range(4,10):
                    box=(1+col*cw,1+row*ch,1+(col+1)*cw,1+(row+1)*ch)
                    diff=ImageChops.difference(base.crop(box),frame.crop(box)).convert('L').histogram()
                    ratios[row,col]=1-diff[0]/(cw*ch)
            report['rectangle_changed_ratios']=[[ratios[row,col] for col in range(4,10)] for row in (1,2)]
            return all(r>.5 if ((5<=col<=8) if row==1 else (6<=col<=7)) else r<.1 for (row,col),r in ratios.items())
        wait_for(rectangle);photo('rectangle');desk.event(None,False);wait_for(lambda:desk.state().capture!=hwnd)
        desk.chord(0x11,0x10,ord('C'));wait_for(lambda:clipboard_text(hwnd)=='中文\r\nCU')
        post_box=state('rectangle-copied');report['rectangle_copied']=clipboard_text(hwnd)
        mux_state('rectangle-copied',post_box['grid'])
        assert post_box['cursor']==pre_box['cursor'] and post_box['lines']==pre_box['lines'] and post_box['mode']=='n'
        report['checks'].append('four Chinese cells and two ASCII cells copied as a rectangle; dropping modifiers did not hand the drag to Vim')
        call('input',':wq');desk.chord(0x0d);visible('VIM_RETURNED');visible('VIM_PRIOR_SCREEN');assert BUFFER[0] not in screen();photo('restored')
        expected=BUFFER.copy();expected[2]+='中文';raw=(folder/'buffer.txt').read_bytes();assert raw==('\n'.join(expected)+'\n').encode() and (folder/'vim-exit').read_text()=='0'
        report['checks'].append('real Ctrl+Shift+V saved exact UTF-8 and restored the previous screen on exit')
        clip.restore();clip=None;desk.restore();desk=None;(folder/'finish').touch();assert proc.wait(timeout=15)==0;report['completed']=True
    except Exception:
        report['error']=traceback.format_exc()
        if proc and proc.poll() is None and 'call' in locals():
            try:(folder/'failure.txt').write_text(screen(),encoding='utf-8');photo('failure')
            except Exception:report['capture_error']=traceback.format_exc()
        raise
    finally:
        try:
            if clip:clip.restore()
            if desk:desk.restore()
        finally:
            if proc and proc.poll() is None:
                (folder/'stop').touch()
                try:proc.wait(timeout=6)
                except subprocess.TimeoutExpired:proc.terminate();proc.wait(timeout=6);report['forced_cleanup']=True
            try:winreg.DeleteKey(winreg.HKEY_CURRENT_USER,reg)
            except FileNotFoundError:pass
            (folder/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':
        raise SystemExit('Requires a GitHub-hosted Windows runner')
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--tmux',action='store_true');args=parser.parse_args()
    if args.tmux:
        registered=subprocess.check_output([shutil.which('wsl.exe'),'--list','--verbose'])
        distro=os.environ['NEMOTERM_TEST_WSL_DISTRO']
        listing=registered.decode('utf-16le' if b'\x00' in registered else 'utf-8-sig').lstrip('\ufeff')
        (root/'research'/'tmux-runner-wsl.txt').write_text(listing,encoding='utf-8')
        found=[line.split() for line in listing.replace('*',' ').splitlines() if line.split() and line.split()[0]==distro]
        if len(found)!=1 or found[0][-1]!='1':raise RuntimeError(f'Expected {distro} on hosted WSL1: {listing}')
    errors=[]
    for r in (0,2):
        for b in ('default','plain'):
            try:trial(r,b,args.tmux)
            except Exception:traceback.print_exc();errors.append((r,b))
    if errors:raise SystemExit(f'Vim interactions failed: {errors}')
