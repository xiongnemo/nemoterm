"""Verify source-built OpenConsole UTF-8 stream reads and surrogate boundaries."""
from native_test_utils import root,Path,os,sys,subprocess,tempfile,time,json,hashlib,read_snapshot,write_snapshot,wait_snapshot
import uuid,winreg
exe=Path(os.environ.get('NEMOTERM_TEST_EXE',root/'dist/nemoterm.exe')).resolve()
evidence=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),runs=[])
profile='unicode-input-'+uuid.uuid4().hex;keypath='Software\\Nemo\\Nemoterm\\Sessions\\'+profile
with winreg.CreateKey(winreg.HKEY_CURRENT_USER,keypath) as key:winreg.SetValueEx(key,'WarnOnClose',0,winreg.REG_DWORD,0)
try:
 for chunk in (1,2,3,4,7,1024):
  for mode in (0x80,0x280,0x82,0x83):
   with tempfile.TemporaryDirectory(prefix='nemoterm-unicode-input-') as temporary:
    folder=Path(temporary);report,control=folder/'report',folder/'control';serial=0
    process=subprocess.Popen([str(exe),'-load',profile,'-e',sys.executable,str(root/'tests/unicode_input_fixture.py'),
      str(report),str(control),str(chunk),str(mode)],creationflags=subprocess.CREATE_NO_WINDOW,env=dict(os.environ,NEMOTERM_CONPTY='bundled'))
    record=dict(chunk=chunk,input_mode=mode,checks=[])
    try:
     wait_snapshot(lambda:read_snapshot(report))
     def put(units=(),reset=True,flush=False):
      global serial
      serial+=1;write_snapshot(control,dict(id=serial,units=list(units),reset=reset,flush=flush))
      return wait_snapshot(lambda:read_snapshot(report),lambda v:v.get('id')==serial)
     def check(expected,name):
      value=wait_snapshot(lambda:read_snapshot(report),lambda v:v.get('id')==serial and bytes.fromhex(v.get('hex',''))==expected)
      assert not value['reader_done'] and not value['read_error'],value
      assert all(0<n<=chunk for n in value['read_sizes']),value
      record['checks'].append(name)
     text='A\u4e2d\U0001f642B\U0001f9eae\u0301'
     raw=text.encode('utf-16-le');units=[int.from_bytes(raw[i:i+2],'little') for i in range(0,len(raw),2)]
     if mode&2:
      put(units+[13]);check((text+('\r\n' if mode&1 else '\r')).encode(),'cooked-mixed-scalars-small-reads')
      evidence['runs'].append(record);continue
     put(units);check(text.encode(),'mixed-scalars-small-reads')
     put([0xd83d]);time.sleep(.12)
     value=wait_snapshot(lambda:read_snapshot(report),lambda v:v.get('id')==serial and v.get('events_pending')==0)
     assert not value['reader_done'] and not value['hex'],value
     put([0xde42],reset=False);check('\U0001f642'.encode(),'pair-across-wait')
     put([0xd83d]);time.sleep(.12);put([ord('Z')],reset=False)
     # The key-to-VT translator drops orphan leaders in VT mode. Raw ReadFile
     # conversion uses the Unicode replacement scalar, preserving the next key.
     check(('\ufffdZ' if mode==0x80 else 'Z').encode(),'orphan-then-ascii')
     put([0xd83d]);time.sleep(.12);put([0xd83e,0xddea],reset=False)
     check(('\ufffd\U0001f9ea' if mode==0x80 else '\U0001f9ea').encode(),'orphan-then-pair')
     put([0xd83d]);time.sleep(.12);put([ord('F')],reset=False,flush=True);check(b'F','flush-pending-leader')
     evidence['runs'].append(record)
    except Exception:
     (root/'build/unicode-input-failure.json').write_text(json.dumps(dict(evidence=evidence,run=record,snapshot=read_snapshot(report)),indent=2))
     raise
    finally:
     write_snapshot(control,dict(stop=True))
     try:process.wait(timeout=10)
     except subprocess.TimeoutExpired:process.terminate();process.wait();raise
 (root/'research/unicode-input-observed.json').write_text(json.dumps(evidence,indent=2))
 print('Unicode console byte reads passed:',json.dumps(evidence))
finally:winreg.DeleteKey(winreg.HKEY_CURRENT_USER,keypath)
