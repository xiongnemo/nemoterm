"""Small, explicit GIF89a fixtures, independent of the terminal's WIC decoder.

Each LZW pixel is preceded by a clear code. The code size therefore stays three
bits; no encoder library, optimization or implicit disposal policy is involved.
"""
import struct

PALETTE=bytes((0,0,0,255,0,0,0,255,0,0,0,255))

def frame(width=2,height=1,colour=1,*,left=0,top=0,delay=12,disposal=1,
          pixels=None,transparent=None,interlaced=False,palette=None):
    return dict(width=width,height=height,pixels=bytes([colour])*(width*height) if pixels is None else bytes(pixels),
        left=left,top=top,delay=delay,disposal=disposal,transparent=transparent,
        interlaced=interlaced,palette=palette)

def gif(width,height,frames,*,repeats=None,background=0):
    out=bytearray(b'GIF89a'+struct.pack('<HHBBB',width,height,0x91,background,0)+PALETTE)
    if repeats is not None:out+=b'\x21\xff\x0bNETSCAPE2.0\x03\x01'+struct.pack('<H',repeats)+b'\0'
    for f in frames:
        pixels=f['pixels'];fw,fh=f['width'],f['height']
        assert len(pixels)==fw*fh and all(p<4 for p in pixels)
        transparent=f['transparent']
        out+=b'\x21\xf9\x04'+struct.pack('<BHB',f['disposal']*4+(transparent is not None),f['delay'],transparent or 0)+b'\0'
        packed=(0x40 if f['interlaced'] else 0)|(0x81 if f['palette'] is not None else 0)
        out+=b','+struct.pack('<HHHHB',f['left'],f['top'],fw,fh,packed)
        if f['palette'] is not None:
            assert len(f['palette'])==12;out+=f['palette']
        if f['interlaced']:
            rows=[y for start,step in [(0,8),(4,8),(2,4),(1,2)] for y in range(start,fh,step)]
            pixels=b''.join(pixels[y*fw:(y+1)*fw] for y in rows)
        encoded=bytearray();bits=acc=0
        def code(value):
            nonlocal bits,acc
            acc |= value<<bits;bits+=3
            while bits>=8:
                encoded.append(acc&255);acc>>=8;bits-=8
        for pixel in pixels:code(4);code(pixel)
        code(5)
        if bits:encoded.append(acc)
        out.append(2)
        for offset in range(0,len(encoded),255):
            block=encoded[offset:offset+255];out.append(len(block));out+=block
        out.append(0)
    out.append(0x3b)
    return bytes(out)
