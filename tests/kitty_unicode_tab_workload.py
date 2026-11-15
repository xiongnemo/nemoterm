"""Dense Unicode-image cells for the existing uninjected two-tab memory gate."""
import hashlib
import struct
from kitty_image_window_smoke import command
from iterm_image_window_smoke import png
from native_test_utils import root,sys,wait_for


def workload_image(columns,rows):
    assert 4<=columns<=512 and 4<=rows<=256
    assert (columns-2)*(rows-2)<=8192, 'Workload exceeds the declared cell-image run limit'
    # One shared raster, repeated in separate one-cell virtual placements.
    # Explicit repeated (0,0) coordinates prevent adjacent cells from becoming
    # a single contiguous image run. Leave a border to avoid autowrap.
    encoded=png(512,288,bytes((0,0,255,255))*512*288)
    upload=command('a=T,i=1,p=1,f=100,C=1,U=1,c=1,r=1',encoded)
    cell='\U0010eeee\u0305\u0305'
    text='\x1b[38;5;1m'+''.join(f'\x1b[{row+1};2H'+cell*(columns-2) for row in range(1,rows-1))
    return upload+text+'\x1b[0m\x1b[?25l'


def verify_images(pid,children,select,observations,prefix,grids):
    """Check every repeated cell after sampling, including inactive tab reads."""
    sys.path.insert(0,str(root/'tools'))
    import nemoterm_debug as api
    instance=wait_for(lambda:next(iter(api.discover(pid)),None))
    assert instance['pid']==pid
    for index,child in enumerate(children):
        for active in (False,True):
            selected=index if active else 1-index
            select(children[selected],selected)
            current=api.request(instance['endpoint'],'list')
            target=next(s for s in current['sessions'] if s['hwnd']==child['hwnd'])
            cols,rows=grids[index]
            assert target['active']==active and [target['cols'],target['rows']]==[cols,rows]
            cw=(target['client_width']-2)//cols;ch=(target['client_height']-2)//rows
            assert cw>=4 and ch>=6
            record=dict(session=target['id'],renderer=target['renderer'],active=active,
                grid=[cols,rows],after_memory_sampling=True,injected=False,rows=[],matched=False)
            observations.append(record)
            for row in range(1,rows-1):
                # A one-pixel-high strip bounds capture buffers at any DPI.
                # Each cell's center lies inside its aspect-fitted solid image.
                patch=[1+cw,1+row*ch+ch//2,(cols-2)*cw,1]
                last=None
                def matches():
                    nonlocal last
                    last=api.request(instance['endpoint'],'image',target['id'],struct.pack('<IIII',*patch))
                    assert len(last)==54+patch[2]*4 and struct.unpack_from('<ii',last,18)==(patch[2],-1)
                    return all(last[54+(col*cw+cw//2)*4:57+(col*cw+cw//2)*4]==b'\xff\0\0'
                               for col in range(cols-2))
                row_record=dict(row=row,patch=patch,matched=False)
                record['rows'].append(row_record)
                try:
                    wait_for(matches);row_record['matched']=True
                finally:
                    if last:
                        row_record['bmp_sha256']=hashlib.sha256(last).hexdigest()
                        if row in (1,rows//2,rows-2) or not row_record['matched']:
                            name=f'{prefix}-tab-{index}-{active}-row-{row}.png'
                            (root/'research'/name).write_bytes(api.png_from_bmp(last))
                            row_record['image']=name
            record.update(matched=True,cells_verified=(cols-2)*(rows-2))
