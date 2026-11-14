"""Kitty pixels after uninjected memory sampling, including inactive tab reads."""
from kitty_image_window_smoke import command
from iterm_image_window_smoke import png
from native_test_utils import root, sys, struct, hashlib, wait_for


def workload_image(compressed=False):
    pixels=bytearray(bytes((255,0,0,128))*512*288)
    # An opaque blue marker makes an exact, font-independent post-resize probe.
    for y in range(8):pixels[y*512*4:y*512*4+8*4]=bytes((0,0,255,255))*8
    encoded=png(512,288,pixels)
    header='a=T,i=1,f=100,C=1'
    if compressed:
        import zlib
        header+=f',o=z,S={len(encoded)}'
        encoded=zlib.compress(encoded)
    return '\x1b[2;3H'+command(header,encoded)


def verify_images(pid,children,select,observations,prefix):
    sys.path.insert(0,str(root/'tools'))
    import nemoterm_debug as api
    instance=wait_for(lambda:next(iter(api.discover(pid)),None))
    assert instance['pid']==pid
    for index,child in enumerate(children):
        for active in (False,True):
            select(children[index if active else 1-index],index if active else 1-index)
            current=api.request(instance['endpoint'],'list')
            target=next(s for s in current['sessions'] if s['hwnd']==child['hwnd'])
            assert target['active']==active
            cw=(target['client_width']-2)//target['cols']
            ch=(target['client_height']-2)//target['rows']
            patch=[1+2*cw,1+ch,8,8]
            record=dict(session=target['id'],renderer=target['renderer'],active=active,
                        after_memory_sampling=True,injected=False,patch=patch,matched=False)
            observations.append(record)
            last=None
            def matches():
                nonlocal last
                last=api.request(instance['endpoint'],'image',target['id'],struct.pack('<IIII',*patch))
                assert len(last)==54+8*8*4 and struct.unpack_from('<ii',last,18)==(8,-8)
                return all(last[i:i+3]==bytes((255,0,0)) for i in range(54,len(last),4))
            try:
                wait_for(matches)
                record['matched']=True
            finally:
                if last:
                    name=f'{prefix}-tab-{index}-'+('active' if active else 'inactive')+'.png'
                    (root/'research'/name).write_bytes(api.png_from_bmp(last))
                    record.update(image=name,bmp_sha256=hashlib.sha256(last).hexdigest())
