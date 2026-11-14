"""Capture exact 7/8-bit control replies from a private pinned XTerm."""
import argparse
from xterm_state_oracle import run_cases


def cases():
    result={}
    rqss=lambda q:'\x1bP$q'+q+'\x1b\\'
    report='\x1b[5n\x1b[6n'+rqss('"p')+rqss('m')
    for switch in ('','\x1b F','\x1b G','\x1b G\x1b F','\x1b F\x1b G'):
        result['switch-'+switch.encode().hex()]=switch+report
    for level in (61,62,63,64,65,60,66,999999999):
        for control in ('','0','1','2','3','999999999'):
            for initial in ('F','G'):
                result[f'level-{level}-{control}-{initial}']='\x1b '+initial+f'\x1b[{level};{control}"p'+report
    for name,operation in [('ris','\x1bc'),('soft','\x1b[!p'),('save','\x1b7'),
                           ('restore','\x1b7\x1b G\x1b8'),('alt','\x1b[?1049h\x1b[?1049l'),
                           ('utf8-on','\x1b%G'),('utf8-off','\x1b%@')]:
        result['lifetime-'+name]='\x1b G'+operation+report
    for control in ('61','62','63','64','65',';','62:1;1','62;1:1','62;0;1','62;1;0'):
        result['arguments-'+control]='\x1b G\x1b['+control+'"p'+report
    for name,query in [('sgr',rqss('m')),('rqss-unknown',rqss('xyz')),('da3','\x1b[=c'),
                       ('private-cpr','\x1b[?6n'),('mode','\x1b[?25$p'),
                       ('geometry','\x1b["v'),('tabs','\x1b[2$w'),
                       ('palette-bel','\x1b]4;1;?\x07'),('palette-st','\x1b]4;1;?\x1b\\'),
                       ('title','\x1b[21t'),('termcap','\x1bP+q436f\x1b\\')]:
        result['reply-'+name]='\x1b G'+query
    for level in (61,62,63,64,65):
        for switch in ('F','G'):
            result[f'switch-after-level-{level}-{switch}']=f'\x1b[{level};1"p\x1b '+switch+report
        result[f'reset-effects-{level}']='\x1b[3;20r\x1b[?6h\x1b[7;9H\x1b[1;31m'+f'\x1b[{level};1"p'+report+rqss('r')
    # S7C1T itself is ignored at level 1. Re-enter level 5 with 7-bit controls
    # only after all observed replies, so the existing barrier is unambiguous.
    return {name:'\x1b[65;1"p\x1bc'+sequence+'\x1b[65;1"p\x1b F' for name,sequence in result.items()}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xterm',default='/tmp/nemoterm-xterm-reference/xterm')
    parser.add_argument('--output',default='research/c1-controls-xterm.json')
    args=parser.parse_args()
    run_cases(args.xterm,args.output,cases(),['-ti','vt525'],raw_replies=True)
