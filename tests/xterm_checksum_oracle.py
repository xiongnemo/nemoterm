"""Rectangle checksum modes, content and boundaries from an independent XTerm."""
import argparse
from xterm_state_oracle import run_cases


def cases():
    result={}
    rect='\x1b[7;1;1;1;3;12*y'
    scenes={
        'blank':'',
        'ascii':' A B  \r\nC  D\r\n  E ',
        'attributes':'\x1b[1mA\x1b[4mB\x1b[5mC\x1b[7mD\x1b[8mE\x1b[0m'
                     '\x1b[1"qF\x1b[0"q\x1b[2;3;9;31;44mG\x1b[0m',
        'spaces':' \x1b[1m \x1b[0m\x1b[1"q \x1b[0"q\x1b[8m \x1b[0m',
        'erased':'AB\x1b[1;4;31m\x1b[2K\x1b[0m',
        'wide':'中A文\r\n界\x1b[3;12H中',
        'combining':'e\u0301x\u0301a\u0308\u0301',
        'unicode':'éñÿ\u0100\u1e00\U0001f642',
        'line-drawing':'\x1b(0_`abcdefghijklmnopqrstuvwxyzz{|}~\x1b(B',
        'uk':'\x1b(A#\x1b(B#',
    }
    for mode in range(32):
        for name,text in scenes.items():
            result[f'mode-{mode}-{name}']=text+f'\x1b[{mode}#y'+rect
    fill='ABCD\x1b[3;7HXYZ\x1b[24;80H!'
    for arg in ('','0','7','7;1','7;0','7;2','7;999','7;1;0;0;0;0',
        '7;1;1;1;1;1','7;1;1;2;1;3','7;1;3;7;3;9','7;1;24;80;24;80',
        '7;1;3;5;1;2','7;1;999;999;999;999','7;1;1;1;999;999',
        '0;1;1;1;1;4','65535;1;1;1;1;4','65536;1;1;1;1;4',
        '999999999999999999999;1;1;1;1;4',';1;1;1;1;4',
        '7;1;1;1;1;4;99','7;1;1:2;1;1;4','7;1;1;1;1;4:2'):
        result['args-'+(arg or 'empty')]=fill+'\x1b[23#y\x1b['+arg+'*y'
    for arg in ('','0','31','32','255','65535','999999999999999999999','23;0','23:0',':23'):
        result['mode-args-'+(arg or 'empty')]='A '+f'\x1b[{arg}#y'+rect
    report='\x1b[8;1;1;1;24;80*y'
    result['origin']=fill+'\x1b[3;20r\x1b[?69h\x1b[7;70s\x1b[?6h\x1b[23#y'+rect+report
    result['soft-reset']='AB\x1b[23#y\x1b[!p'+rect
    result['hard-reset']='AB\x1b[23#y\x1bcA'+rect
    result['alternate']='AB\x1b[23#y\x1b[?1049hCD'+rect+'\x1b[?1049l'+rect
    result['double-size']='ABCDEFGH\x1b#6\x1b[23#y'+rect
    result['double-hidden']='A'*80+'\x1b#6\x1b[23#y'+report
    result['wrap']='A'*80+'B\x1b[23#y'+report+'\x1b[6nC\x1b[6n'
    result['sixel']='AB\x1b[?80h\x1bP0;1q#1;2;100;0;0!30~\x1b\\\x1b[23#y'+rect
    result['cancel']='AB\x1b[23#y\x1b[7;1;1;1;3;12\x18*y'+rect
    for level in range(61,66):
        result['level-'+str(level)]=f'\x1b[{level};1"pA\x1b[23#y'+rect
    for scalar in (32,65,127,160,233,241,255,256,7680,20013,128578,65533):
        for mode in (0,1,5,23):
            result[f'scalar-{scalar}-{mode}']=chr(scalar)+f'\x1b[{mode}#y\x1b[7;1;1;1;1;1*y'
    for ch in '_`abcdefghijq~':
        result[f'graphics-{ord(ch)}']='\x1b(0'+ch+'\x1b(B\x1b[23#y\x1b[7;1;1;1;1;1*y'
    return {name:'\x1b[64;1"p\x1bc'+sequence for name,sequence in result.items()}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xterm',default='/tmp/nemoterm-xterm-reference/xterm')
    parser.add_argument('--output',default='research/checksum-xterm.json')
    parser.add_argument('--ordering-probe',action='store_true')
    args=parser.parse_args()
    selected=cases()
    if args.ordering_probe:
        selected={f'{name}-{i}':selected[name] for i in range(3) for name in (
            'mode-0-unicode','mode-1-unicode','mode-0-combining','mode-1-combining',
            'mode-23-unicode','mode-23-combining')}
    run_cases(args.xterm,args.output,selected,['-ti','vt520','-xrm','*allowWindowOps: true'])
