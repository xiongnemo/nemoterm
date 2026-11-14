"""Compressed Kitty pictures through ConPTY, the PNG codec and active renderer."""
import base64
import os
import zlib
from kitty_image_window_smoke import command, image
from iterm_image_window_smoke import png
from sixel_palette_window_smoke import main, reset, ESC, CSI, ST


def compressed(data, *, level=6, strategy=zlib.Z_DEFAULT_STRATEGY):
    encoder=zlib.compressobj(level,zlib.DEFLATED,15,8,strategy)
    return encoder.compress(data)+encoder.flush()


def part(header,data):
    return ESC+'_G'+header+';'+base64.b64encode(data).decode()+ST


def exercise(phase,block):
    def rect(colour,width=8,height=6):
        return block(2,colour,count=width,height=height)
    cursor=CSI+'2;3H'
    header='a=T,i=1,f=32,s=8,v=6,C=1,o=z'
    red=bytes((255,0,0,255))*48
    blue=bytes((0,0,255,255))*48
    blue_z=compressed(blue,strategy=zlib.Z_FIXED)
    phase('rgba-fixed',reset()+cursor+command(header,blue_z),[rect('blue')])
    phase('rgb-stored',reset()+cursor+command('a=T,i=1,f=24,s=8,v=6,C=1,o=z',
          compressed(bytes((0,255,0))*48,level=0)),[rect('green')])
    dynamic=compressed(bytes((255,0,0,255))*64*48,strategy=zlib.Z_HUFFMAN_ONLY)
    assert (dynamic[2]>>1)&3==2
    phase('rgba-dynamic',reset()+cursor+command('a=T,i=1,f=32,s=64,v=48,C=1,o=z',dynamic),
          [rect('red',64,48)])
    encoded=png(8,6,blue)
    png_header=f'a=T,i=1,f=100,C=1,o=z,S={len(encoded)}'
    phase('png-native-codec',reset()+cursor+command(png_header,compressed(encoded)),[rect('blue')])
    phase('chunk-first-padded',reset()+cursor+part(header+',m=1',blue_z[:1]),[rect('black')])
    phase('chunk-middle-padded',part('m=1',blue_z[1:3]),[rect('black')])
    phase('chunk-final',part('m=0',blue_z[3:]),[rect('blue')])
    phase('empty-final-before',reset()+cursor+part(header+',m=1',blue_z),[rect('black')])
    phase('empty-final-after',part('m=0',b''),[rect('blue')])
    phase('query-has-no-picture',reset()+cursor+command(header.replace('a=T','a=q'),blue_z),[rect('black')])
    for name,bad in [('checksum',blue_z[:-1]+bytes([blue_z[-1]^1])),
                     ('truncated',blue_z[:-1]),('raw-deflate',blue_z[2:-4])]:
        phase(name+'-rejected',reset()+cursor+command(header,bad),[rect('black')])
        phase(name+'-recovery',cursor+command(header,blue_z),[rect('blue')])
    for name,size in [('short',len(encoded)-1),('long',len(encoded)+1),('missing',None)]:
        h='a=T,i=1,f=100,C=1,o=z'+(f',S={size}' if size is not None else '')
        phase('png-size-'+name,reset()+cursor+command(h,compressed(encoded)),[rect('black')])
        phase('png-size-'+name+'-recovery',cursor+command(png_header,compressed(encoded)),[rect('blue')])
    phase('trailing-bytes',reset()+cursor+command(header,blue_z+b'TRAILING'),[rect('blue')])
    phase('concatenated-first-stream',reset()+cursor+command(header,blue_z+compressed(red)),[rect('blue')])
    phase('compressed-alpha',reset()+image('red',z=-1)+cursor+command(header.replace('i=1','i=2'),
          compressed(bytes((0,0,255,128))*48)),[rect('blue-over-red')],stable_seconds=1)
    phase('delete-compressed-reveals-underlay',command('a=d,d=I,i=2'),[rect('red')])
    phase('cancel-incomplete-before',reset()+cursor+part(header+',m=1',blue_z[:1]),[rect('black')])
    phase('cancel-incomplete-recovery',command('a=d,d=A')+cursor+command(header,blue_z),[rect('blue')])
    phase('reset-releases-compressed-image',ESC+'c'+CSI+'?25l',[rect('black')])


if __name__=='__main__':
    main(exercise,suite_name='kitty-compression',
         font=os.environ.get('NEMOTERM_TEST_FONT','Consolas' if os.environ.get('CI')=='true' else 'SarasaTermSC Nerd Font Light'))
