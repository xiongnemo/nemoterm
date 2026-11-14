"""Preserve exact 8-bit reply bytes through the native console host."""
from c1_controls_oracle_cases import CASES
from protocol_oracle_window import run
from native_test_utils import u,wait_snapshot,time
import argparse,os

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--input-cp',type=int,choices=(28591,65001),default=28591)
args=parser.parse_args()
os.environ['NEMOTERM_TEST_INPUT_CP']=str(args.input_cp)
# Windows console byte reads encode Unicode using the application's input CP.
# ISO-8859-1 preserves the original octets; UTF-8 uses U+0080..U+009F scalars.
def input_cp(name):
    # The source-built Windows host implements DOCS by changing both console
    # code pages: ESC % G selects UTF-8; ESC % @ selects ISO-8859-1.
    # All other cases explicitly start with the fixture's requested input CP.
    return 65001 if name=='lifetime-utf8-on' else 28591 if name=='lifetime-utf8-off' else args.input_cp
cases=[(name,sequence,reply if input_cp(name)==28591 else
    b''.join(chr(b).encode('utf-8') if 0x80<=b<=0x9f else bytes([b]) for b in reply))
    for name,sequence,reply in CASES]

def exercise(hwnd,phase,current):
    prefix=b'\xc2' if args.input_cp==65001 else b''
    csi,ss3=prefix+b'\x9b',prefix+b'\x8f'
    marker=csi+b'0n';evidence={}
    def setup(name,sequence):
        phase(name,'\x1b[65;1"p\x1b G'+sequence,b'',phase_barrier=('\x1b[5n',marker))
    def key(vk,scan):
        lp=1 | ((scan&255)<<16) | ((scan&256)<<16)
        u.SendMessageW(hwnd,0x100,vk,lp);u.SendMessageW(hwnd,0x101,vk,lp|0xc0000000)
    def check(name,expected):
        value=wait_snapshot(current,lambda v:bytes.fromhex(v.get('hex',''))==marker+expected)
        time.sleep(.03)
        value=current();assert bytes.fromhex(value['hex'])==marker+expected,value
        assert value['input_cp']==args.input_cp,value
        evidence[name]=value
    setup('legacy-csi-key','\x1b[?1l');key(38,0x148);check('legacy-csi',csi+b'A')
    setup('legacy-ss3-key','\x1b[?1h');key(38,0x148);check('legacy-ss3',ss3+b'A')
    setup('mok-key','\x1b[>4;3m\x1b[>4;1f')
    u.SendMessageW(hwnd,0x102,0x4e2d,1);check('mok',csi+b'20013;1u')
    setup('kitty-key','\x1b[=31u')
    u.SendMessageW(hwnd,0x102,0x4e2d,1);check('kitty',csi+b'0;1;20013u')
    setup('literal-text','\x1b[=0u\x1b[>4;0m')
    u.SendMessageW(hwnd,0x102,ord('x'),1)
    expected=b'x'
    if args.input_cp==65001:
        u.SendMessageW(hwnd,0x102,0x4e2d,1);expected+='中'.encode('utf-8')
    check('literal',expected)
    phase('restore-default','\x1b F',b'')
    return evidence

run('c1-controls-'+str(args.input_cp),cases,barrier=('\x1b[5n',b'\x1b[0n'),
    exercise=exercise,
    font='Consolas' if os.environ.get('CI')=='true' else 'SarasaTermSC Nerd Font Light')
