"""OSC 1337 inline PNG pixels via public API, owned jobs and real ConPTY."""
import base64
import struct
import zlib
from sixel_palette_window_smoke import main, reset, ESC, CSI, ST, COLOURS

COLOURS.update({'half-red':bytes((0,0,128)), 'half-red-cyan':bytes((127,127,128))})
COLOURS.update({'white':bytes((255,255,255)), 'blue-over-red':bytes((128,0,127))})

# Generated from a 1x1 solid RGB image with Pillow 13.0.0; decoded here with
# standard-library base64 only. The terminal uses the real Windows codecs.
BLACK_JPEG = base64.b64decode(
    '/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/'
    '2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/'
    '8QAFQABAQAAAAAAAAAAAAAAAAAAAAj/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFAEBAAAAAAAAAAAAAAAAAAAAAP/EABQRAQAAAAAAAAAAAAAAAAAAAAD/'
    '2gAMAwEAAhEDEQA/AJ/AB//Z')
WHITE_GIF = base64.b64decode('R0lGODdhAQABAIEAAP///wAAAAAAAAAAACwAAAAAAQABAAAIBAABBAQAOw==')


def png(width, height, pixels):
    def chunk(kind, data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    raw=b''.join(b'\0'+bytes(pixels[y*width*4:(y+1)*width*4]) for y in range(height))
    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,6,0,0,0))+
            chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b''))


def transfer(data, options='', row=2, multipart=False, chunk_size=200, terminator=ST):
    encoded=base64.b64encode(data).decode()
    prefix=ESC+']1337;'
    header='inline=1'+(';' + options if options else '')
    start=CSI+f'{row};3H'
    if not multipart:return start+prefix+'File='+header+':'+encoded+terminator
    return (start+prefix+'MultipartFile='+header+terminator+
            ''.join(prefix+'FilePart='+encoded[i:i+chunk_size]+terminator
                    for i in range(0,len(encoded),chunk_size))+
            prefix+'FileEnd'+terminator)


def exercise(phase, block):
    pixels=png(2,2,[255,0,0,255,0,255,0,255,0,0,255,255,0,0,0,0])
    red=png(2,2,[255,0,0,255]*4)
    blue=png(2,2,[0,0,255,255]*4)
    translucent=png(1,1,[255,0,0,128])
    cw=(block(2,'red')['x']-1)//2
    ch=block(3,'red')['y']-block(2,'red')['y']
    def rect(row, colour, width=2, height=2, left=0, top=0):
        return block(row,colour,count=width,height=height,left=left,top=top)
    def quad(row):
        return [rect(row,'red',1,1),rect(row,'green',1,1,left=1),
                rect(row,'blue',1,1,top=1),rect(row,'black',1,1,left=1,top=1)]

    phase('inline-intrinsic-png',reset()+transfer(pixels),quad(2))
    phase('inline-BEL',reset()+transfer(pixels,terminator='\x07'),quad(2))
    bmp = (b'BM'+struct.pack('<IHHI',62,0,0,54)+
           struct.pack('<IiiHHIIiiII',40,2,1,1,24,0,8,0,0,0,0)+bytes((0,0,255,255,0,0,0,0)))
    phase('inline-bmp',reset()+transfer(bmp),[rect(2,'red',1,1),rect(2,'blue',1,1,left=1)])
    phase('inline-jpeg',reset()+ESC+']11;#00ffff\x07'+transfer(BLACK_JPEG),[rect(2,'black',1,1)])
    phase('inline-static-gif',reset()+transfer(WHITE_GIF),[rect(2,'white',1,1)])
    for size in (1,3,200):
        phase(f'multipart-{size}',reset()+transfer(pixels,multipart=True,chunk_size=size),quad(2))
    phase('pixel-dimensions',reset()+transfer(red,'width=4px;height=6px;preserveAspectRatio=0'),
          [rect(2,'red',4,6)])
    phase('aspect-preserved',reset()+transfer(blue,'width=4px;height=6px'),
          [rect(2,'blue',4,4),rect(2,'black',4,2,top=4)])
    phase('cell-dimensions',reset()+transfer(red,'width=2;height=1;preserveAspectRatio=0'),
          [rect(2,'red',2*cw,ch)])
    phase('percentage-dimensions',reset()+transfer(blue,'width=10%;height=25%;preserveAspectRatio=0'),
          [rect(2,'blue',4*cw,3*ch)])
    phase('partial-alpha-black',reset()+transfer(translucent),[rect(2,'half-red',1,1)])
    phase('partial-alpha-repaint',CSI+'?25h'+CSI+'?25l',[rect(2,'half-red',1,1)])
    phase('partial-alpha-background-change',ESC+']11;#00ffff\x07',
          [rect(2,'half-red-cyan',1,1)])
    phase('partial-alpha-over-image',reset()+transfer(red)+transfer(png(1,1,[0,0,255,128])),
          [rect(2,'blue-over-red',1,1),rect(2,'red',1,1,left=1)])
    phase('reset-clears',reset(),[rect(2,'black')])
    phase('erase-before',transfer(red),[rect(2,'red')])
    phase('erase-image',CSI+'2J',[rect(2,'black')])
    phase('alternate-before',transfer(red),[rect(2,'red')])
    phase('alternate-hides',CSI+'?1049h',[rect(2,'black')])
    phase('alternate-own-image',transfer(blue),[rect(2,'blue')])
    phase('alternate-restores',CSI+'?1049l',[rect(2,'red')])
    phase('scroll-before',reset()+transfer(red,f'width=2px;height={ch}px;preserveAspectRatio=0',row=4),
          [rect(4,'red',2,ch)])
    phase('scroll-up',CSI+'2S',[rect(2,'red',2,ch),rect(4,'black',2,ch)])
    phase('scroll-down',CSI+'1T',[rect(3,'red',2,ch),rect(2,'black',2,ch)])
    phase('malformed-recovers',reset()+ESC+']1337;File=inline=1:!!!!'+ST+transfer(blue),
          [rect(2,'blue')])
    phase('cancel-recovers',reset()+ESC+']1337;File=inline=1:YWJj\x18'+transfer(red),
          [rect(2,'red')])
    phase('codec-reject-recovers',reset()+transfer(b'not an image')+transfer(blue),[rect(2,'blue')])
    phase('dimension-limit',reset()+transfer(png(8193,1,bytes((255,0,0,255))*8193)),[rect(2,'black')])
    phase('decoded-budget-limit',reset()+transfer(png(1024,1024,bytes((255,0,0,255))*1024*1024)),
          [rect(2,'black')])


if __name__=='__main__':
    main(exercise,suite_name='iterm-images',font='SarasaTermSC Nerd Font Light')
