"""Own-PID IMM fault injection, Unicode input and synthetic DPI transitions.

Requires the pinned Frida test dependency. Its injected VM changes memory use;
this fixture does not use instrumented working sets for the product's budget.
Real IMM API submission is recorded only when the installed IME supports it.
It is not physical key conversion, candidate UI or multi-monitor certification.
"""
from native_test_utils import (root,c,w,u,k,hashlib,json,os,subprocess,sys,tempfile,
    Path,time,read_snapshot,write_snapshot,wait_snapshot,wait_for,capture,find_window)
import frida,uuid,winreg,argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--font',default='SarasaTermSC Nerd Font Light')
args=parser.parse_args()
u.PostMessageW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM]
u.GetClientRect.argtypes=[w.HWND,c.POINTER(w.RECT)]
exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
profile='input-method-'+uuid.uuid4().hex;keypath='Software\\Nemo\\Nemoterm\\Sessions\\'+profile
with winreg.CreateKey(winreg.HKEY_CURRENT_USER,keypath) as key:
 for name,value in dict(WarnOnClose=0,NemoWin32Input=0).items():winreg.SetValueEx(key,name,0,winreg.REG_DWORD,value)
evidence=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),frida_version=frida.__version__,requested_font=args.font,input_cp=65001,checks=[],dpi=[])
try:
 with tempfile.TemporaryDirectory(prefix='nemoterm-input-method-') as temporary:
  p=Path(temporary);report,control=p/'report',p/'control'
  process=subprocess.Popen([str(exe),'-load',profile,'--cols','40','--rows','12','--font',args.font,
    '-e',sys.executable,str(root/'tests/mouse_fixture.py'),str(report),str(control)],creationflags=subprocess.CREATE_NO_WINDOW,
    env=dict(os.environ,NEMOTERM_CONPTY='bundled',NEMOTERM_TEST_UTF8_INPUT='1'))
  session=script=None;command=None;messages=[];serial=0;request={};phase_id=''
  try:
   hwnd=wait_for(lambda:find_window(process.pid));wait_for(lambda:read_snapshot(report))
   session=frida.attach(process.pid);script=session.create_script((root/'tests/input_method_probe.js').read_text(encoding='utf-8-sig'))
   def received(message,data):messages.append(message)
   script.on('message',received);script.load();wait_for(lambda:any(m.get('payload',{}).get('event')=='ready' for m in messages))
   def phase(sequence=''):
    global serial,request,phase_id
    serial+=1;phase_id=str(serial);request=dict(phase=phase_id,sequence=sequence+'\x1b[5n');write_snapshot(control,request)
    wait_snapshot(lambda:read_snapshot(report),lambda v:v.get('phase')==phase_id and bytes.fromhex(v.get('hex','')).endswith(b'\x1b[0n'))
   def check(expected,name):
    global serial
    serial+=1;token=str(serial);request['input_barrier']=token;write_snapshot(control,request)
    value=wait_snapshot(lambda:read_snapshot(report),lambda v:v.get('phase')==phase_id and v.get('input_barrier')==token)
    assert value['input_cp']==65001,value
    actual=bytes.fromhex(value['hex']);want=b'\x1b[0n'+expected+b'\x1b[0n'
    assert actual==want,(name,actual.hex(),want.hex());evidence['checks'].append(name)
   def command(kind,**fields):
    global serial
    serial+=1;ident=serial;script.exports_sync.command(dict(kind=kind,id=ident,**fields));assert u.PostMessageW(hwnd,0x8321,0,0)
    def result():
     for m in messages:
      if m.get('type')=='error':raise AssertionError(m)
      v=m.get('payload',{})
      if v.get('event')=='operation' and v.get('id')==ident:return v
    return wait_for(result)
   def inject(name,text,query=None,actual=None,mode='',expected=None):
    phase('\x1b[=0u\x1b[>4n\x1b[?9001l'+mode)
    data=list(text.encode('utf-16-le'));q=len(data) if query is None else query;a=len(data) if actual is None else actual
    script.exports_sync.configure(dict(name=name,bytes=data,query=q,actual=a))
    u.SendMessageW(hwnd,0x10f,0,0x800)
    script.exports_sync.configure(None)
    check(text.encode() if expected is None else expected,name)
   inject('short-read','nihao',actual=2,expected=b'n')
   for name,q,a in [('cancelled',10,0),('read-error',10,-1),('odd-result',10,3),('oversize-result',10,12),
                     ('odd-query',9,10),('empty-query',0,0),('failed-query',-1,10),('over-budget',65538,10)]:
    inject(name,'nihao',query=q,actual=a,expected=b'')
   inject('complete-unicode','\u4e2d\u6587\U0001f642e\u0301')
   inject('max-size-commit','a'*32768)
   inject('kitty-ime-text','\u4e2d\u6587\U0001f642',mode='\x1b[=31u',expected=b'\x1b[0;1;20013:25991:128578u')
   phase('\x1b[=0u\x1b[?9001l')
   assert u.SendMessageW(hwnd,0x109,0xffff,0)==1
   for code in (0x4e2d,0x1f642,0x301,0xd800,0x110000):u.SendMessageW(hwnd,0x109,code,0)
   check('\u4e2d\U0001f642\u0301'.encode(),'wm-unichar-scalars-and-probe')
   phase();u.SendMessageW(hwnd,0x102,0xd83d,1);u.SendMessageW(hwnd,0x10d,0,0);u.SendMessageW(hwnd,0x10e,0,0)
   u.SendMessageW(hwnd,0x102,0xde00,1);u.SendMessageW(hwnd,0x102,90,1);check(b'Z','composition-surrogate-boundary')
   phase('\x1b[=31u');u.SendMessageW(hwnd,0x109,0x1f642,0);check(b'\x1b[0;1;128578u','kitty-unichar')
   phase('\x1b[=0u');cap=command('capabilities');evidence['imm_capabilities']=cap
   if cap['context'] and cap['caps']&1:
    answer=command('ime',text='\u4e2d\u6587');evidence['real_imm_submission']=answer
    assert answer['setComposition'] and answer['complete'],answer
    check('\u4e2d\u6587'.encode(),'installed-imm-api-unicode-submission')
   else:evidence['real_imm_submission']='Unavailable: no compatible installed IME'
   # Place a fixed-size raster and a solid cursor whose pixels reveal cell size.
   phase('\x1b[2J\x1b[3J\x1b[H\x1b[2 q\x1b[?25h\x1b]12;#00ff00\x07\x1b]11;#000000\x07'
         '\x1b[3;3H\x1bP0;1q"1;1;24;12#1;2;100;0;0!24~-!24~\x1b\\\x1b[H')
   def raster():
    r=w.RECT();u.GetClientRect(hwnd,c.byref(r));pixels=capture(hwnd,return_pixels=True);green=[];red=set()
    for i in range(0,len(pixels),3):
     rgb=pixels[i:i+3];point=(i//3%r.right,i//3//r.right)
     if rgb==b'\0\xff\0':green.append(point)
     elif rgb==b'\xff\0\0':red.add(point)
    if not green:return None
    xs,ys=zip(*green);geom=(min(xs),min(ys),max(xs)-min(xs)+1,max(ys)-min(ys)+1)
    return geom,red
   def pixels_match():
    found=raster()
    if not found:return False
    (x,y,cw,ch),red=found
    return found if red=={(x+2*cw+xx,y+2*ch+yy) for xx in range(24) for yy in range(12)} else False
   initial=wait_for(pixels_match)[0];u.SendMessageW(hwnd,0x10d,0,0)
   initial_imm=command('capabilities')
   for dpi in (144,192,120,96):
    answer=command('dpi',dpi=dpi)
    def resized_pixels():
     found=pixels_match()
     if not found:return False
     geom=found[0]
     return found if abs(geom[2]/initial[2]-dpi/96)<.2 and abs(geom[3]/initial[3]-dpi/96)<.2 else False
    # The WM_DPICHANGED callback can finish before the invalidated frame paints.
    # Require the new scale as well as matching Sixel pixels in the same frame.
    geom=wait_for(resized_pixels)[0]
    answer=command('capabilities')
    if initial_imm.get('compositionFontHeight'):
     assert abs(answer['compositionFontHeight']/initial_imm['compositionFontHeight']-dpi/96)<.1,(dpi,answer)
     assert (answer['compositionWindow']['x'],answer['compositionWindow']['y'])==geom[:2],(dpi,answer,geom)
    record=dict(dpi=dpi,geometry=geom,imm=answer);evidence['dpi'].append(record)
   capture(hwnd,'input-method-dpi.png');u.SendMessageW(hwnd,0x10e,0,0)
   evidence['checks'].append('synthetic-dpi-pixels-preserve-sixel')
   evidence['imm_reads']=[m['payload'] for m in messages if m.get('payload',{}).get('event')=='read']
   assert not [m for m in messages if m.get('type')=='error'],messages
  except Exception:
   (root/'build/input-method-failure.json').write_text(json.dumps(dict(evidence=evidence,messages=messages,snapshot=read_snapshot(report)),indent=2))
   raise
  finally:
   try:
    try:
     if script:
      try:
       script.exports_sync.configure(None)
       if command:command('restore')
      finally:script.unload()
    finally:
     if session:session.detach()
   finally:
    write_snapshot(control,dict(stop=True))
    try:process.wait(timeout=10)
    except subprocess.TimeoutExpired:process.terminate();process.wait();raise
 (root/'research/input-method-observed.json').write_text(json.dumps(evidence,indent=2))
 print('Input method and synthetic DPI checks passed:',json.dumps(evidence))
finally:winreg.DeleteKey(winreg.HKEY_CURRENT_USER,keypath)
