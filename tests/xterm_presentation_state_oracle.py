"""Capture independent presentation reports and restoration on pinned XTerm."""
import argparse
from xterm_state_oracle import run_cases

CSI, DCS, ST = '\x1b[', '\x1bP', '\x1b\\'
CURSOR, TABS, EXTENT = CSI+'1$w', CSI+'2$w', CSI+'"v'


def cases():
    result = {}
    for args in ('', '0', '1', '2', '3', '99', '1;2', '2;1', '1:2', ';1', '0;1'):
        result['request-'+(args or 'empty')] = CSI+args+'$w'
    for level in range(61, 66):
        result[f'level-{level}'] = CSI+f'{level};1"p'+CURSOR+TABS+EXTENT
    for style in ('0','1','2','3','4','5','7','8','9','21','1;4;5;7','31;44',
                  '38:2::1:2:3;48:2::4:5:6'):
        result['rendition-'+style] = CSI+style+'m'+CURSOR
    for protection in (0,1,2):
        result[f'protect-{protection}'] = CSI+f'{protection}"q'+CURSOR
    for pos in ('1;1','12;35','24;80'):
        result['position-'+pos] = CSI+pos+'H'+CURSOR
    result['pending-wrap'] = CSI+'24;80HZ'+CURSOR+'X'+CURSOR
    result['origin-margins'] = CSI+'3;20r'+CSI+'?69h'+CSI+'11;70s'+CSI+'?6h'+CSI+'5;7H'+CURSOR+EXTENT
    result['double-size'] = CSI+'5;35H\x1b#6'+CURSOR+EXTENT
    result['alternate'] = CSI+'12;35H'+CSI+'1;4m'+CSI+'?1049h'+CURSOR+CSI+'?1049l'+CURSOR
    for control in ('\x0e','\x0f','\x1bn','\x1bo','\x1b~','\x1b}','\x1b|','\x1bN','\x1bO'):
        result['shift-'+control.encode().hex()] = control+CURSOR+'A'+CURSOR
    for bank in ('(',')','*','+'):
        for charset in ('B','0','A','U'):
            result[f'charset-{bank}{charset}'] = '\x1b'+bank+charset+CURSOR
    for name, setup in (
        ('default',''),('clear',CSI+'3g'),('column-one','\x1bH'),
        ('custom',CSI+'3g'+CSI+'1;2H\x1bH'+CSI+'1;37H\x1bH'+CSI+'1;80H\x1bH'),
        ('soft',CSI+'3g'+CSI+'1;5H\x1bH'+CSI+'!p'),
        ('alt',CSI+'3g'+CSI+'1;5H\x1bH'+CSI+'?1049h'),
        ('margins',CSI+'?69h'+CSI+'11;70s'+CSI+'?6h'),
    ):
        result['tabs-'+name] = setup+TABS+CSI+'6n'
    baseline = '7;19;1;@;@;@;0;2;@;BBBB'
    for name, payload in (
        ('plain',baseline),('bold','7;19;1;A;@;@;0;2;@;BBBB'),
        ('all-legacy','7;19;1;O;A;I;0;2;@;BBBB'),
        ('origin','7;19;1;@;@;A;0;2;@;BBBB'),
        ('wrap','7;19;1;@;@;H;0;2;@;BBBB'),
        ('wide-wrap','7;80;1;@;@;H;0;2;@;BBBB'),
        ('protect','7;19;1;@;A;@;0;2;@;BBBB'),
        ('gl1','7;19;1;@;@;@;1;2;@;B0BB'),
        ('gl2','7;19;1;@;@;@;2;2;@;BB0B'),
        ('gl3','7;19;1;@;@;@;3;2;@;BBB0'),
        ('ss2','7;19;1;@;@;B;0;2;@;BB0B'),
        ('ss3','7;19;1;@;@;D;0;2;@;BBB0'),
        ('extra','7;19;1;@;@;@;0;2;@;BBBBextra'),
    ):
        result['restore-'+name] = DCS+'1$t'+payload+ST+CURSOR+'q'+CURSOR
    for index, value in ((0,'0'),(0,'25'),(1,'0'),(1,'81'),(2,'2'),(3,'P'),
                         (4,'B'),(5,'P'),(6,'4'),(7,'4'),(8,'?')):
        parts = baseline.split(';'); parts[index] = value
        result[f'invalid-field-{index}-{value}'] = DCS+'1$t'+';'.join(parts)+ST+CURSOR
    for length in (0,1,3,5,7,10,13,16,19,22,25,28):
        result[f'truncated-{length}'] = DCS+'1$t'+baseline[:length]+ST+CURSOR
    for level in (63,64,65):
        result[f'restore-invisible-{level}'] = CSI+f'{level};1"p'+DCS+'1$t'+baseline.replace(';@;@;@;', ';P;@;@;')+ST+CURSOR+'\x1bP$qm'+ST
    for prefix in ('0','1','01','1;2','2','02','2;1','3','9'):
        result['restore-prefix-'+prefix] = DCS+prefix+'$t'+baseline+ST+CURSOR+TABS
    for name,payload in (
        ('empty',''),('custom','1/2/37/80'),('unsorted','40/2/7'),('duplicate','2/2/2/7'),
        ('out-of-view','1/80/81/160/999'),('zero','0/1/0/5'),('trailing','2/7/'),
        ('empty-fields','/2//7/'),('invalid-middle','2/7x/19'),('invalid-first','x2/7'),
        ('missing-slash','2;7'),('spaces','2 /7'),
    ):
        result['restore-tabs-'+name] = DCS+'2$t'+payload+ST+TABS+'\t'+CSI+'6n'
    result['retained-modern'] = CSI+'2;3;8;9;21;31;44m'+DCS+'1$t'+baseline+ST+CURSOR+'\x1bP$qm'+ST
    checksum = CSI+'23#y'+CSI+'7;1;1;1;1;3*y'
    for name, control in (
        ('soft', CSI+'!p'),
        ('restore-off', DCS+'1$t1;1;1;@;@;@;0;2;@;BBBB'+ST),
        ('restore-dec', DCS+'1$t1;1;1;@;A;@;0;2;@;BBBB'+ST),
    ):
        for erase in ('?2K','?2J','1;1;1;3${'):
            result[f'protection-family-{name}-{erase}'] = CSI+'1"qABC'+control+CSI+erase+CURSOR+checksum
    result['empty-selective-ed-clears-family'] = CSI+'0"qABC'+CSI+'?2J'+CURSOR
    result['restored-origin-outside-margins'] = CSI+'3;20r'+CSI+'?69h'+CSI+'11;70s'+DCS+'1$t'+baseline.replace('7;19;', '1;1;').replace(';@;@;@;', ';@;@;A;')+ST+CURSOR
    for terminator in ('\x18','\x1a','\x1b[5;6H'):
        result['cancel-'+terminator.encode().hex()] = DCS+'1$t'+baseline+terminator+CURSOR
    for level in (61,62):
        result[f'restore-low-level-{level}'] = CSI+f'{level};1"p'+DCS+'1$t'+baseline+ST+CSI+'6n'+DCS+'2$t2/7'+ST+'\t'+CSI+'6n'
    # RIS preserves the selected emulation level, so each case selects it first.
    return {name:CSI+'65;1"p\x1bc'+body for name,body in result.items()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xterm', default='/tmp/nemoterm-xterm-reference/xterm')
    parser.add_argument('--output', default='research/presentation-state-xterm.json')
    args = parser.parse_args()
    run_cases(args.xterm, args.output, cases(), ['-ti','vt520','-xrm','*allowWindowOps: true'])
