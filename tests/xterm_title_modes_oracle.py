"""Observe upstream title encoding flags, reset/query forms and malformed input."""
import argparse
import json
from pathlib import Path
from xterm_state_oracle import run_cases

CSI, ST = '\x1b[', '\x1b\\'
def title(text): return '\x1b]0;'+text+ST
def rqss(value='>t'): return '\x1bP$q'+value+ST
query = CSI+'20t'+CSI+'21t'
reset = CSI+'>0;1;2;3T'+CSI+'>2;3t'+title('BASE')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--xterm', required=True)
    parser.add_argument('--output', default='research/title-modes-xterm.json')
    args = parser.parse_args()
    cases = {'initial-modes':rqss(), 'baseline':reset+query+rqss()}
    for mask in range(16):
        set_bits = ';'.join(str(i) for i in range(4) if mask & (1 << i))
        mode = CSI+'>0;1;2;3T'+(CSI+'>'+set_bits+'t' if set_bits else '')
        text = 'Aé中'
        cases[f'mode-{mask}'] = reset+mode+title(text.encode().hex() if mask & 1 else text)+query+rqss()
    for command in ('>t','>T','>;t','>;T','>0;t','>;1T','>9t','>0;9;3t',
                    '>9999999999999t','>0:0t','>1:2T','>0;1:2t'):
        cases['parameters-'+command] = reset+CSI+'>0;1;2;3t'+CSI+command+rqss()
    for suffix, sequence in [('ris','\x1bc'),('soft',CSI+'!p'),
                             ('alternate',CSI+'?1049h'+CSI+'?1049l')]:
        cases['reset-'+suffix] = reset+CSI+'>0;1;2;3t'+sequence+query+rqss()
    for value in ('>t','>0t','>1t','>2t','>3t','>4t','>0;1;2;3t','>;t',
                  '>0:1t','>999999999999t','>1;1t','>0;9t'):
        cases['rqss-'+value] = reset+rqss(value)
    for value in ('','41','4','414','414g','41 42','41;42','410042','410742','410942',
                  '410A42','411842','411A42','411B42','417F42','418042','418542',
                  '419C42','41C29C42','41C28042','41C2A042','41C0AF42',
                  '41EDA08042','41F490808042','41F09F918B42'):
        cases['hex-'+value] = reset+CSI+'>0t'+title(value)+CSI+'>0T'+query
    for size in (999,1000,1001,2048,4096):
        cases[f'length-{size}'] = reset+title('x'*size)+query
    for size in (500,501):
        cases[f'hex-length-{size}'] = reset+CSI+'>0t'+title('41'*size)+CSI+'>0T'+query
    for control, name in [('\0','nul'),('\t','tab'),('\n','lf'),('\r','cr'),
                          ('\x18','can'),('\x1a','sub'),('\x7f','del'),
                          ('\u009c','utf8-st')]:
        cases['raw-'+name] = reset+title('A'+control+'B')+query
    cases['stack-with-modes'] = reset+title('é中')+CSI+'22t'+CSI+'>0t'+title('4142')+CSI+'23t'+CSI+'>1t'+query
    run_cases(args.xterm, args.output, cases, (
        '-xrm','*allowTitleOps: true','-xrm','*allowWindowOps: true',
        '-xrm','*disallowedWindowOps:','-xrm','*titleModes: 0'))
    v=json.loads(Path(args.output).read_text())
    assert v['cases']['baseline']['reply'].startswith('\x1b]LBASE'+ST+'\x1b]lBASE'+ST)
    assert v['cases']['hex-41']['reply']=='\x1b]LA'+ST+'\x1b]lA'+ST
    print('Captured',len(cases),'independent title-mode cases')

if __name__ == '__main__': main()
