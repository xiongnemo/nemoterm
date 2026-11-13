"""Capture reverse-wrap cursor, mode and cell behavior from an owned XTerm."""
import argparse
import json
import re
from pathlib import Path
from xterm_state_oracle import run_cases

CSI = '\x1b['
CPR = CSI+'6n'
MODES = CSI+'?45$p'+CSI+'?1045$p'
CELLS = [(r,c) for r in (1,2,3,4,5,6,23,24) for c in (1,2,4,5,6,9,10,11,39,40,41,78,79,80)]
POLICIES = [('off',''), ('normal',CSI+'?45h'), ('extended',CSI+'?1045h'), ('both',CSI+'?45;1045h')]


def cases():
    result = {'initial': '\x1bc'+MODES}
    movements = [('bs','\b'),('bs3','\b'*3),('cub-default',CSI+'D'),('cub-zero',CSI+'0D'),
                 ('cub2',CSI+'2D'),('cub80',CSI+'80D'),('cub81',CSI+'81D'),
                 ('cub160',CSI+'160D'),('cub1921',CSI+'1921D'),
                 ('cub65535',CSI+'65535D'),('cub-max',CSI+'4294967295D'),('bi','\x1b6')]
    for policy, mode in POLICIES:
        for row,col in ((1,1),(1,5),(3,1),(3,5),(24,1),(24,80)):
            for name, move in movements:
                result[f'{policy}-plain-{row}-{col}-{name}'] = '\x1bc'+mode+f'{CSI}{row};{col}H'+move+CPR
        for scenario, setup in [
            ('wrapped', CSI+'2;1H'+'A'*80+'BC'),
            ('pending', CSI+'3;80HX'),
            ('hard-break', CSI+'2;1HAAAA\r\nBC'),
            ('wide-tail', CSI+'2;79H中BC'),
            ('wide-gap', CSI+'2;79HA中'),
            ('combining-tail', CSI+'2;80Hx\u0301BC'),
            ('three-wrapped', CSI+'2;1H'+'A'*80+'B'*80+'CD'),
            ('double-row', CSI+'2;1H\x1b#6'+'A'*40+'BC'),
            ('double-pending', CSI+'2;1H\x1b#6'+'A'*40),
            ('nowrap', CSI+'?7l'+CSI+'3;1H'),
        ]:
            for name,move in [('bs3','\b'*3),('cub3',CSI+'3D'),('cub81',CSI+'81D')]:
                result[f'{policy}-{scenario}-{name}'] = '\x1bc'+mode+setup+move+CPR
        for row,col in ((1,1),(2,5),(3,5),(3,10),(4,1),(4,5),(4,12),(6,5),(7,5)):
            for name,move in [('bs','\b'),('cub7',CSI+'7D'),('cub25',CSI+'25D')]:
                region = CSI+'?69h'+CSI+'5;10s'+CSI+'3;6r'
                result[f'{policy}-margin-{row}-{col}-{name}'] = '\x1bc'+mode+region+f'{CSI}{row};{col}H'+move+CPR
        result[policy+'-margin-wrapped'] = '\x1bc'+mode+CSI+'?69h'+CSI+'5;10s'+CSI+'3;6r'+CSI+'3;5HABCDEFGHIJKLM'+CSI+'9D'+CPR
        for name, op in [('lf',''),('su',CSI+'S'),('sd',CSI+'T'),('il',CSI+'3;5H'+CSI+'L'),('dl',CSI+'3;5H'+CSI+'M')]:
            result[policy+'-margin-scroll-'+name] = '\x1bc'+mode+CSI+'?69h'+CSI+'5;10s'+CSI+'3;6r'+CSI+'3;5H'+'ABCDEFGHIJKLMNOPQRSTUVWX'*3+op+CSI+'6;6H'+CSI+'9D'+CPR
        result[policy+'-origin'] = '\x1bc'+mode+CSI+'?69h'+CSI+'5;10s'+CSI+'3;6r'+CSI+'?6h'+CSI+'2;1H'+CSI+'7D'+CPR
        for action, sequence in [
            ('soft-reset',CSI+'!p'),('hard-reset','\x1bc'),
            ('save-restore',CSI+'?45;1045s'+CSI+'?45;1045l'+CSI+'?45;1045r'),
            ('save-ris-restore',CSI+'?45;1045s'+'\x1bc'+CSI+'?45;1045r'),
            ('save-soft-restore',CSI+'?45;1045s'+CSI+'!p'+CSI+'?45;1045r'),
            ('cursor-save','\x1b7'+CSI+'?45;1045l'+'\x1b8'),
            ('alternate',CSI+'?1049h'+MODES+CSI+'?45;1045l'+CSI+'?1049l'),
            ('alternate-set',CSI+'?1049h'+CSI+'?45;1045h'+CSI+'?1049l'),
        ]:
            result[policy+'-'+action] = '\x1bc'+mode+sequence+MODES+CSI+'3;1H\b'+CPR
    for n,s in list(result.items()):
        # Give the reference a blank saved line for its previous-row lookup at
        # the top edge. A cold top edge is checked separately in our fixtures.
        result[n] = '\x1bc'+'\r\n'*25+s+MODES+CSI+'1$w'+'Z'+CPR
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xterm', default='/tmp/nemoterm-xterm-reference/xterm')
    parser.add_argument('--output', default='research/reverse-wrap-xterm.json')
    args = parser.parse_args()
    originals = cases()
    suffix = CSI+'?6l'+CSI+'?69l'+CSI+'31#y'+''.join(
        f'{CSI}{i};1;{r};{c};{r};{c}*y' for i,(r,c) in enumerate(CELLS,1))
    run_cases(args.xterm,args.output,{n:s+suffix for n,s in originals.items()},
              ['-ti','vt520','-xrm','*allowWindowOps: true'])
    path = Path(args.output)
    data = json.loads(path.read_text(encoding='utf-8'))
    for name,case in data['cases'].items():
        checks = re.findall(r'\x1bP(\d+)!~([0-9A-Fa-f]+)\x1b\\',case['reply'])
        assert len(checks) == len(CELLS), (name,len(checks))
        case['input'] = originals[name]
        case['state_reply'] = case['reply'].split('\x1bP1!~',1)[0]
        case['cells'] = [int(v,16) for _,v in checks]
    data['cell_positions'] = CELLS
    path.write_text(json.dumps(data,indent=2),encoding='utf-8')
