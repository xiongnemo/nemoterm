"""Independent XTerm palette stacks and title-stack position reports."""
import argparse
from xterm_state_oracle import run_cases

CSI='\x1b['
OSC='\x1b]'
ST='\x1b\\'
REPORT=CSI+'#R'
QUERY=REPORT+OSC+'4;1;?;2;?;17;?;255;?'+ST+OSC+'10;?;?;?'+ST


def colours(seed):
    rgb=lambda n:f'#{(seed+n)%256:02x}{(seed+2*n)%256:02x}{(seed+3*n)%256:02x}'
    return OSC+'4;'+(';'.join(f'{index};{rgb(i+1)}' for i,index in enumerate((1,2,17,255))))+ST+\
        OSC+'10;'+(';'.join(rgb(i+9) for i in range(3)))+ST


def cases():
    result={'initial':REPORT,'initial-missing-pop':CSI+'9#Q'+REPORT,
            'cold-indexed':CSI+'4#P'+REPORT,
            'cold-missing-gap':CSI+'4#P'+CSI+'3#Q'+REPORT}
    # RIS does not empty XTerm's palette slots or reset its high-water mark.
    # Define every slot and both indices before each independent warm case.
    prefix='\x1bc'+colours(16)+CSI+'1#P'+CSI+'#Q'+(CSI+'#P')*10+(CSI+'#Q')*10
    warm={}
    for action in ('P','Q'):
        for arg in ('','0','1','2','9','10','11','99','65535','999999999999999',
                    ';','0;0','1;2','2;1',';1','1;','10;0','1;11;2','1:2',':1'):
            warm[f'{action}-args-{arg or "empty"}']=CSI+'#P'+colours(80)+CSI+arg+'#'+action+QUERY
    for count in (0,1,2,9,10,11,12,20,32):
        warm[f'depth-{count}']=''.join(colours(i+32)+CSI+'#P'+REPORT for i in range(count))+\
            colours(160)+''.join(CSI+'#Q'+QUERY for _ in range(count+2))
    for index in (0,1,5,10,11):
        warm[f'repeated-index-{index}']=colours(30)+CSI+f'{index}#P'+colours(60)+\
            CSI+f'{index}#Q'+QUERY+colours(90)+CSI+f'{index}#Q'+QUERY
    for name,control in dict(ris='\x1bc',soft=CSI+'!p',alternate=CSI+'?1049h',
                             cursor='\x1b7\x1b8',sgr=CSI+'0m',palette_reset=OSC+'104'+ST).items():
        warm['retention-'+name]=colours(30)+CSI+'#P'+colours(60)+control+REPORT+CSI+'#Q'+QUERY+CSI+'?1049l'
    warm['alternate-shared']=colours(30)+CSI+'#P'+CSI+'?1049h'+colours(60)+CSI+'#P'+\
        colours(90)+CSI+'#Q'+QUERY+CSI+'?1049l'+CSI+'#Q'+QUERY
    for arg in ('','0','1','999','1;2','1:2'):
        warm['report-args-'+(arg or 'empty')]=CSI+'#P'+CSI+arg+'#R'+QUERY
    for cancel in ('\x18','\x1a'):
        warm['cancel-'+str(ord(cancel))]=CSI+'#'+cancel+'P'+REPORT+QUERY
    for level in range(61,66):
        warm[f'level-{level}']=CSI+f'{level};1"p'+colours(30)+CSI+'#P'+colours(60)+CSI+'#Q'+QUERY
    result.update({name:prefix+sequence for name,sequence in warm.items()})

    title_prefix=(CSI+'23t')*64+''.join(CSI+f'22;3;{i}t' for i in range(1,11))+\
        CSI+'>0;1T'+CSI+'>2;3t'+OSC+'0;BASE'+ST
    title_report=CSI+'#S'
    titles={}
    for count in (0,1,9,10,11,12,20,32):
        titles[f'depth-{count}']=''.join(OSC+f'0;S{i}'+ST+CSI+'22t'+title_report for i in range(count))+\
            ''.join(CSI+'23t'+title_report for _ in range(count+2))
    for args in ('1','9','10','11','999'):
        titles['indexed-'+args]=CSI+f'22;0;{args}t'+title_report+CSI+f'23;0;{args}t'+title_report
    for args in ('','0','1','99','1;2','1:2'):
        titles['report-'+(args or 'empty')]=CSI+'22t'+CSI+args+'#S'
    for name,control in dict(ris='\x1bc',soft=CSI+'!p',alternate=CSI+'?1049h').items():
        titles['retention-'+name]=CSI+'22t'+control+title_report+CSI+'23t'+title_report+CSI+'?1049l'
    titles['overflow-index-interleave']=(CSI+'22t')*12+(CSI+'23t')*10+\
        OSC+'0;DIRECT'+ST+CSI+'22;0;2t'+title_report+CSI+'23t'+title_report+CSI+'21t'+CSI+'23t'+title_report
    result.update({'title-'+name:title_prefix+sequence for name,sequence in titles.items()})
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xterm',default='/tmp/nemoterm-xterm-reference/xterm')
    parser.add_argument('--output',default='research/palette-stack-evidence/xterm.json')
    args=parser.parse_args()
    run_cases(args.xterm,args.output,cases(),['-ti','vt520','-xrm','*allowWindowOps: true'])
