"""Independent XTerm rendition stack and rectangular attribute reports."""
import argparse
from xterm_state_oracle import run_cases

CSI = '\x1b['
SAMPLE = CSI+'HA'+CSI+'1;1;1;1#|'


def cases():
    result = {}
    rich = '1;2;3;4;5;7;8;9;31;44'
    selectors = ('', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
                 '10', '11', '21', '22', '30', '31', '32', '99',
                 '99999999999999999', '1;3;30', '0;1', ';1', '1:2', ':1')
    for alias in ('{', 'p'):
        for selector in selectors:
            result[f'push-{alias}-{selector or "empty"}'] = (
                CSI+rich+'m'+CSI+selector+'#'+alias+CSI+'0;32;45m'+CSI+'#}'+SAMPLE)
    for args in ('', '0', '1', '99', '1;2', '1:2'):
        for alias in ('}', 'q'):
            result[f'pop-{alias}-{args or "empty"}'] = (
                CSI+'1;31m'+CSI+'#{'+CSI+'0;32m'+CSI+args+'#'+alias+SAMPLE)
    for style in ('4','21','4;21','21;4','0','4:2','4:3'):
        for selector in ('', '4', '21', '4;21'):
            result[f'underline-{style}-{selector or "all"}'] = (
                CSI+style+'m'+CSI+selector+'#{'+CSI+'0;21m'+CSI+'#}'+SAMPLE)
    for old, new in (('31;44','32;45'), ('91;104','92;105'),
                     ('38;5;123;48;5;234','38;5;122;48;5;233'),
                     ('38:2::1:2:3;48:2::4:5:6','38:2::9:8:7;48:2::6:5:4'),
                     ('0','31;44'), ('31;44','0')):
        for selector in ('', '30', '31', '10', '11', '30;31'):
            result[f'colors-{old}-{selector or "all"}'] = (
                CSI+old+'m'+CSI+selector+'#{'+CSI+new+'m'+CSI+'#}'+SAMPLE)
    for depth in (0,1,9,10,11,20,32):
        sequence = ''.join(CSI+f'0;38;5;{i+1}m'+CSI+'#{' for i in range(depth))
        sequence += CSI+'0;37m'
        sequence += ''.join(CSI+'#}'+SAMPLE for _ in range(depth+2))
        result[f'depth-{depth}'] = sequence
    for name, control in dict(ris='\x1bc', soft=CSI+'!p', sgr=CSI+'0m',
                              alternate=CSI+'?1049h', cursor='\x1b7\x1b8').items():
        result['retention-'+name] = CSI+'1;31m'+CSI+'#{'+CSI+'0;32m'+control+CSI+'#}'+SAMPLE
    result['alternate-shared'] = CSI+'31m'+CSI+'#{'+CSI+'?1049h'+CSI+'32m'+CSI+'#{'+CSI+'33m'+CSI+'#}'+SAMPLE+CSI+'?1049l'+CSI+'#}'+SAMPLE
    result['protection-separate'] = CSI+'1"q'+CSI+'31m'+CSI+'#{'+CSI+'0"q'+CSI+'0m'+CSI+'#}'+SAMPLE+'\x1bP$q"q\x1b\\'
    result['empty-pop'] = CSI+'1;32m'+CSI+'#}'+SAMPLE
    result['cancel-push'] = CSI+'1;31m'+CSI+'1#\x18{'+CSI+'0;32m'+CSI+'#}'+SAMPLE

    styles = ('0','1','2','3','4','5','7','8','9','21',rich,'31;44',
              '91;104','38;5;123;48;5;234','38:2::1:2:3;48:2::4:5:6')
    for style in styles:
        result['report-one-'+style] = CSI+style+'mAB'+CSI+'1;1;1;1#|'
        result['report-mixed-'+style] = CSI+style+'mA'+CSI+'0mB'+CSI+'1;1;1;2#|'
    for a,b in (('1;31;44','1;32;44'),('1;31','3;31'),('31','91'),
                ('38:2::1:2:3','38:2::1:2:4'),('4','21'),('1;2','1;3')):
        result[f'intersection-{a}-{b}'] = CSI+a+'mA'+CSI+b+'mB'+CSI+'1;1;1;2#|'
    fill = CSI+'31mAB'+CSI+'0m'+CSI+'3;7H'+CSI+'1;44mCD'+CSI+'0m'
    for arg in ('','0;0;0;0','1;1;1;2','3;7;3;8','3;7;1;2',
                '999;999;999;999','1;1;999;999','1;1;1;2;99','1:2;1;1;2'):
        result['report-args-'+(arg or 'empty')] = fill+CSI+arg+'#|'
    result['report-origin'] = fill+CSI+'3;20r'+CSI+'?69h'+CSI+'7;70s'+CSI+'?6h'+CSI+'1;1;1;2#|'+CSI+'999;999;999;999#|'
    result['report-erased'] = CSI+'1;31;44m'+CSI+'2K'+CSI+'1;1;1;5#|'
    result['report-selective-erased'] = CSI+'31;44;1;4mABC'+CSI+'32;45m'+CSI+'?2K'+CSI+'1;1;1;5#|'
    result['report-erased-rgb'] = CSI+'38:2::1:2:3;48:2::4:5:6m'+CSI+'2K'+CSI+'1;1;1;5#|'
    result['report-erased-rgb-inverse'] = CSI+'38:2::1:2:3;48:2::4:5:6m'+CSI+'2K'+CSI+'1;1;1;5;7$r'+CSI+'1;1;1;5#|'
    result['report-wide'] = CSI+'1;31m中e\u0301'+CSI+'1;1;1;3#|'+CSI+'1;2;1;2#|'
    result['report-double-size'] = CSI+'1;31m'+'A'*80+'\x1b#6'+CSI+'1;41;1;80#|'
    result['report-unchanged'] = CSI+'1;31m'+CSI+'1;80HZ'+CSI+'1;80;1;80#|'+CSI+'6nX'+CSI+'6n'
    for level in range(61,66):
        result[f'level-{level}'] = CSI+f'{level};1"p'+CSI+'31m'+CSI+'#{'+CSI+'32m'+CSI+'#}'+SAMPLE
        result[f'checksum-selection-level-{level}'] = 'A'+CSI+f'{level};1"p'+CSI+'23#y'+CSI+'64;1"p'+CSI+'7;1;1;1;1;1*y'
    prefix = CSI+'64;1"p'+(CSI+'#}')*64+'\x1bc'
    return {name:prefix+sequence for name,sequence in result.items()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xterm', default='/tmp/nemoterm-xterm-reference/xterm')
    parser.add_argument('--output', default='research/sgr-stack-xterm.json')
    args = parser.parse_args()
    run_cases(args.xterm, args.output, cases(), ['-ti','vt520','-xrm','*allowWindowOps: true'])
