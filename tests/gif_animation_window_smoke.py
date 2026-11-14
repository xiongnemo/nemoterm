"""Animated GIF codecs, disposal, timing and image lifecycle in a real terminal."""
from sixel_palette_window_smoke import main, reset, ESC, CSI
from iterm_image_window_smoke import transfer
from gif_fixture import gif,frame,PALETTE

def exercise(phase,block):
    def rect(colour,left=0,width=2,top=0,height=1):
        return block(2,colour,left=left,count=width,top=top,height=height)
    def pixels(*colours):return [rect(colour,left=i,width=1) for i,colour in enumerate(colours)]
    red,blue=frame(),frame(colour=3)
    loop=gif(2,1,[red,blue],repeats=0)
    phase('infinite-red',reset()+transfer(loop),[rect('red')])
    phase('infinite-blue','',[rect('blue')])
    phase('infinite-red-again','',[rect('red')])
    phase('infinite-blue-again','',[rect('blue')])
    phase('one-pass-final',reset()+transfer(gif(2,1,[red,blue])),[rect('blue')],stable_seconds=.6)
    # A repetition count of one means the initial pass plus one repeat.
    # Long red/blue intervals allow independent observations of both passes.
    finite=gif(2,1,[frame(delay=35),frame(colour=3,delay=35)],repeats=1)
    phase('finite-first-red',reset()+transfer(finite),[rect('red')])
    phase('finite-first-blue','',[rect('blue')])
    phase('finite-second-red','',[rect('red')])
    phase('finite-final-blue','',[rect('blue')],stable_seconds=.9)
    phase('zero-intermediate',reset()+transfer(gif(2,1,[frame(delay=0),frame(colour=3,delay=20)])),
          [rect('blue')],stable_seconds=.3)
    phase('all-zero-stops-final',reset()+transfer(gif(2,1,[frame(delay=0),frame(colour=3,delay=0)],repeats=0)),
          [rect('blue')],stable_seconds=.4)
    first=frame(1,1,1,delay=0)
    for disposal,expected in [(0,['red','green','blue']),(1,['red','green','blue']),
                               (2,['red','black','blue']),(3,['red','black','blue'])]:
        data=gif(3,1,[first,frame(1,1,2,left=1,delay=0,disposal=disposal),
                      frame(1,1,3,left=2,delay=0)])
        phase('disposal-'+str(disposal),reset()+transfer(data),pixels(*expected))
    data=gif(3,1,[frame(1,1,1,delay=0,disposal=2),
                  frame(1,1,2,left=1,delay=0,disposal=3),frame(1,1,3,left=2,delay=0)])
    phase('previous-after-clear',reset()+transfer(data),pixels('black','black','blue'))
    data=gif(3,1,[frame(3,1,1,delay=0),frame(3,1,delay=0,pixels=[0,2,0],transparent=0)])
    phase('transparent-over-previous',reset()+transfer(data),pixels('red','green','red'))
    data=gif(3,1,[frame(1,1,1,left=1,delay=0,transparent=0,disposal=2),
                  frame(1,1,3,left=2,delay=0,transparent=0)])
    phase('transparent-clear-exposes-grid',reset()+ESC+']11;#00ffff\x07'+transfer(data),
          pixels('cyan','cyan','blue'))
    data=gif(3,2,[frame(1,1,2,left=1,top=1,delay=0)],background=3)
    phase('logical-canvas-background',reset()+transfer(data),
          [rect('blue',width=3,height=2),rect('green',left=1,width=1,top=1)])
    rows=[1,2,3,1,2,3,1,2,3]
    phase('interlaced-rows',reset()+transfer(gif(1,len(rows),[frame(1,len(rows),pixels=rows,interlaced=True)])),
          [rect({1:'red',2:'green',3:'blue'}[colour],width=1,top=y) for y,colour in enumerate(rows)])
    local=PALETTE[:3]+bytes((0,0,255))+PALETTE[6:]
    phase('local-palette',reset()+transfer(gif(2,1,[frame(palette=local)])),[rect('blue')])
    phase('erase-animated-before',reset()+transfer(loop),[rect('red')])
    phase('erase-animated',CSI+'2J',[rect('black')],stable_seconds=.5)
    phase('reset-animated-before',transfer(loop),[rect('red')])
    phase('reset-animated',ESC+'c'+CSI+'?25l',[rect('black')],stable_seconds=.5)
    phase('alternate-before',transfer(loop),[rect('red')])
    phase('alternate-hides',CSI+'?1049h',[rect('black')],stable_seconds=.4)
    phase('alternate-restores',CSI+'?1049l',[rect('blue')])
    phase('alternate-restored-ticks','',[rect('red')])
    cw=(block(2,'red')['x']-1)//2
    scaled='width='+str(cw*2)+'px;height=1px;preserveAspectRatio=0'
    phase('scaled-animation',reset()+transfer(loop,scaled),[rect('red',width=cw*2)])
    phase('mask-across-frames',CSI+'2;3H'+CSI+'X',
          [rect('black',width=cw),rect('blue',left=cw,width=cw)])
    phase('mask-across-frames-red','',[rect('black',width=cw),rect('red',left=cw,width=cw)])
    phase('frame-count-limit',reset()+transfer(gif(1,1,[frame(1,1)]*257)),[rect('black',width=1)])
    phase('composed-cache-limit',reset()+transfer(gif(300,300,[frame(300,300)]*12)),[rect('black')])
    phase('logical-dimension-limit',reset()+transfer(gif(8193,1,[frame(1,1)])),[rect('black')])
    phase('recover-after-limits',transfer(loop),[rect('blue')])

if __name__=='__main__':main(exercise,suite_name='gif-animation',font='SarasaTermSC Nerd Font Light')
