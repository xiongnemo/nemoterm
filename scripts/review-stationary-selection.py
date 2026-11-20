"""Review the right-tab replay's original images, clipboard and child input."""
import hashlib
import json
from pathlib import Path
import sys

from PIL import Image


def review(folder):
    def record(name):
        return json.loads((folder/name).read_text(encoding='utf-8-sig'))

    identity=record('identity.json'); observed=record('tabs-selection-observed.json')
    assert (identity['execution_directory_files']==['nemoterm.exe'] and
            observed['executable_sha256']==identity['executable_sha256'] and
            observed['completed'] and observed['tab_side']=='right' and observed['tab_host'] and
            observed['active_renderer']==1 and observed['requested_renderer']==0)
    cw,ch=observed['cell_pixels']; assert cw>0 and ch>0
    results={}; ack='1b5b306e'*2
    for label,y,block in [('stream',8,False),('block',13,True)]:
        case='repeat-cell-'+label; prefix='message-column-'+case
        row,=[r for r in observed['horizontal_press'] if r['case']==case]
        assert row['pressed']==[10,y] and row['released']==[14,y] and row['block']==block
        assert row['down_and_motion_lparam']==((1+y*ch+ch//2)<<16 | (1+10*cw+cw//2))
        assert row['wire_before_real_drag']==row['gesture_wire']==row['right_wire']==ack
        assert row['right_copy']==row['shortcut_copy']=='KLM'
        images=[]; digests={}
        for suffix in ('-source','-edited',''):
            p=folder/(prefix+suffix+'.png'); digests[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
            with Image.open(p) as image: images.append(image.convert('RGB'))
        src,edited,selected=images
        assert src.size==edited.size==selected.size and src.width>=1+80*cw and src.height>=1+24*ch
        def tile(frame,x,r):
            return frame.crop((1+x*cw,1+r*ch,1+(x+1)*cw,1+(r+1)*ch)).tobytes()
        glyphs=[tile(src,x,y) for x in range(10,13)]
        assert len(set(glyphs))==3 and all(len(set(glyph[::3]))>1 for glyph in glyphs)
        assert glyphs==[tile(edited,x,y) for x in range(12,15)] and tile(src,10,y)!=tile(edited,10,y)
        marked=[(x,r) for r in (y-1,y,y+1) for x in range(80) if tile(edited,x,r)!=tile(selected,x,r)]
        assert marked==[(12,y),(13,y),(14,y)],(case,marked)
        results[case]=dict(verified_cells=marked,copied=row['right_copy'],png_sha256=digests)
    return dict(identity=identity,cases=results)


if __name__=='__main__':
    directory=Path(sys.argv[1]); result=review(directory)
    (directory/'stationary-pixel-review.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print('Both original frame sequences match: KLM moved by two cells, only those three cells were selected, and both copies matched.')
