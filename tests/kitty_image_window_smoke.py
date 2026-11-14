"""Native Kitty APC pixels through the real frontend and its active renderer."""
import base64
import os
from pathlib import Path
from sixel_palette_window_smoke import main, reset, ESC, CSI, ST, COLOURS
from iterm_image_window_smoke import png
from fixture_io import write_snapshot
from native_test_utils import wait_for


def command(header, payload=b''):
    encoded=base64.b64encode(payload).decode()
    if not encoded:return ESC+'_G'+header+ST
    parts=[encoded[i:i+4096] for i in range(0,len(encoded),4096)]
    return ''.join(ESC+'_G'+(header+',' if i==0 else '')+
                   f'm={int(i+1<len(parts))};'+part+ST for i,part in enumerate(parts))


def image(colour, *, row=2, ident=1, z=0, columns=0, rows=0, width=8, height=6, alpha=255, extra=''):
    header=f'a=T,i={ident},f=32,s={width},v={height},C=1,z={z},c={columns},r={rows}'+extra
    rgb={'red':(255,0,0),'green':(0,255,0),'blue':(0,0,255)}[colour]
    return CSI+f'{row};3H'+command(header,bytes((*rgb,alpha))*width*height)


def observe_ready(evidence):
    if path:=os.environ.get('NEMOTERM_KITTY_OBSERVE_READY'):
        ready=Path(path)
        evidence['instrumented_observation']=True
        write_snapshot(ready,dict(pid=evidence['pid'],executable=evidence['executable'],
            executable_sha256=evidence['executable_sha256'],endpoint=evidence['endpoint']))
        wait_for(lambda:ready.with_suffix('.go').exists(),timeout=55)


def exercise(phase,block):
    cw=(block(2,'red')['x']-1)//2
    ch=block(3,'red')['y']-block(2,'red')['y']
    def rect(colour,row=2,left=0,top=0,width=8,height=6):
        return block(row,colour,left=left,top=top,count=width,height=height)
    phase('rgba-intrinsic',reset()+image('red'),[rect('red')])
    phase('rgb-intrinsic',reset()+CSI+'2;3H'+command('a=T,i=1,f=24,s=8,v=6,C=1',bytes((0,255,0))*48),[rect('green')])
    phase('png-native-codec',reset()+CSI+'2;3H'+command('a=T,i=1,f=100,C=1',png(8,6,[0,0,255,255]*48)),[rect('blue')])
    phase('scaled-cells',reset()+image('red',columns=3,rows=2),[rect('red',width=3*cw,height=2*ch)])
    quad=bytes((255,0,0,255,0,255,0,255,0,0,255,255,0,0,0,0))
    phase('crop-scale-transparent',reset()+CSI+'2;3H'+command('a=T,i=1,f=32,s=2,v=2,x=1,w=1,c=2,r=2,C=1',quad),
        [rect('green',width=2*cw,height=ch),rect('black',top=ch,width=2*cw,height=ch)])
    phase('negative-above-coloured-background',reset()+image('red',z=-1,columns=4,rows=1)+
        CSI+'2;3H'+CSI+'48;2;0;0;255m    '+CSI+'0m',[rect('red',width=4*cw,height=ch)])
    phase('below-background',reset()+image('red',z=-1073741825,columns=4,rows=1)+
        CSI+'2;3H'+CSI+'48;2;0;0;255m  '+CSI+'0m',
        [rect('blue',width=2*cw,height=ch),rect('red',left=2*cw,width=2*cw,height=ch)])
    phase('layer-boundary',reset()+image('red',z=-1073741824,columns=4,rows=1)+
        CSI+'2;3H'+CSI+'48;2;0;0;255m    '+CSI+'0m',[rect('red',width=4*cw,height=ch)])
    text=CSI+'2;3H'+CSI+'38;2;255;255;255m█e\u0301中'+CSI+'0m'
    phase('negative-under-text-and-clusters',reset()+image('red',z=-1,columns=5,rows=1)+text,
        [rect('white',left=cw//3,top=ch//3,width=2,height=2),rect('red',left=4*cw,width=cw,height=ch)])
    phase('positive-over-text',image('blue',ident=2,columns=5,rows=1),[rect('blue',width=5*cw,height=ch)])
    phase('delete-reveals-text',command('a=d,d=I,i=2'),
        [rect('white',left=cw//3,top=ch//3,width=2,height=2),rect('red',left=4*cw,width=cw,height=ch)])
    phase('same-z-creation-order',reset()+image('red',ident=9)+image('blue',ident=2),[rect('blue')])
    phase('alpha-positive-over-negative',reset()+image('red',z=-1)+image('blue',ident=2,alpha=128),[rect('blue-over-red')])
    phase('alpha-repeated-presentation',CSI+'12;1H'+CSI+'?25h',[rect('blue-over-red')],stable_seconds=2)
    phase('sync-before',reset()+image('red'),[rect('red')])
    phase('sync-frozen-image',CSI+'?2026h'+image('blue'),[rect('red')])
    phase('sync-committed-image',CSI+'?2026l',[rect('blue')])
    phase('alternate-hides',CSI+'?1049h'+CSI+'?25l',[rect('black')])
    phase('alternate-owned-image',image('green'),[rect('green')])
    phase('alternate-restores',CSI+'?1049l',[rect('blue')])
    phase('scroll-one-row',CSI+'12;1H\n',[rect('blue',row=1)])
    phase('screen-erase-removes-image',CSI+'2J',[rect('black',row=1)])
    phase('margin-source-clipping',reset()+image('green',row=2,columns=1,rows=2)+CSI+'2;5r'+CSI+'5;1H\n',
        [rect('green',width=cw,height=ch),rect('black',row=3,width=cw,height=ch)])
    phase('hard-reset-removes-image',ESC+'c'+CSI+'?25l',[rect('black')])


if __name__=='__main__':
    main(exercise,suite_name='kitty-image',before_exercise=observe_ready,
         font=os.environ.get('NEMOTERM_TEST_FONT','Consolas' if os.environ.get('CI')=='true' else 'SarasaTermSC Nerd Font Light'))
