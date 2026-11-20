"""ReGIS and text edits in one horizontal/vertical scrolling region, at 6x13 cells."""
import re

CSI='\x1b['
# Single-cell readbacks of columns 4, 5, 9, 10, 18, 20 and 21 on two rows.
SAMPLES=[(y,x) for y in (4,5) for x in (4,5,9,10,18,20,21)]
TEXT='ABCDEFGHIJKLMNOPQRSTUVWXYZ'

def scenes():
    # The witnesses are black on black: differences between the two text fonts cannot
    # create false pixel differences. The checksums still expose their actual contents.
    seed=(CSI+'?25l'+CSI+'30;40m'+CSI+'4;1H'+TEXT+CSI+'5;1H'+TEXT.lower()+CSI+'0m'+CSI+'31#y'+
          '\x1bP1pS(E)S(M3(R0G100B0))S(M2(R100G0B0))W(I3)P[6,18]V[151,18]P[6,99]V[151,99]'+
          'W(I2)P[12,40]V[40,40]P[57,43]V[113,43]P[104,49]V[145,49]P[57,57]V[113,57]\x1b\\'+
          CSI+'?69h'+CSI+'5;20s'+CSI+'3;7r')
    query=''.join(CSI+f'{i};1;{y};{x};{y};{x}*y' for i,(y,x) in enumerate(SAMPLES,1))
    ops={'idle':(9,''),'ich':(9,CSI+'3@'),'dch':(9,CSI+'3P'),
         'sl':(9,CSI+'3 @'),'sr':(9,CSI+'3 A'),
         'decic':(9,CSI+"3'}"),'decdc':(9,CSI+"3'~"),
         'decbi':(5,'\x1b6'),'decfi':(20,'\x1b9')}
    return {'text-motion-'+k:[(seed+query).encode('ascii').hex(),
            (CSI+f'4;{x}H'+op+query).encode('ascii').hex()] for k,(x,op) in ops.items()}


def text_samples(step):
    raw=bytes.fromhex(step['reply_hex']); matches=re.findall(rb'\x1bP(\d+)!~([0-9A-Fa-f]{4})\x1b\\',raw)
    assert [int(i) for i,v in matches]==list(range(1,len(SAMPLES)+1)) and len(raw)==sum(len(i)+10 for i,v in matches),raw
    return [int(v,16) for i,v in matches]


def verify(observations):
    errors=[]
    for tag,arms in observations.items():
        for transport,arm in arms.items():
            try:
                assert arm['completed'] and not arm['forced_cleanup'] and arm['cell_pixels']==[6,13]
                first,last=arm['steps']; initial=[ord((TEXT if y==4 else TEXT.lower())[x-1]) for y,x in SAMPLES]
                assert text_samples(first)==initial
                checked=text_samples(last); unchanged=tag=='text-motion-idle'
                assert (checked==initial)==unchanged, (tag,initial,checked)
                assert first['frame']['non_black_pixels']>250 and last['repaint_barrier_hex']=='1b5b306e'
                if unchanged:assert first['frame']['rgb_sha256']==last['frame']['rgb_sha256']==last['repaint']['rgb_sha256']
            except (AssertionError,KeyError,ValueError) as e:
                errors.append(dict(scene=tag,transport=transport,error=repr(e)))
    return errors
