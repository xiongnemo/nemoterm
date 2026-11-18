"""Hosted pterm/Nemoterm comparison: account for pages of the frontend alone."""
from pathlib import Path
import time
from working_set_regions import Region, c, k, mmap, resident_page_blocks
from thread_snapshot import modules


def resident_backing(handle, exe):
    # The sharing flag comes from one resident-page list; VirtualQueryEx adds
    # the backing type afterwards. A private copy of an image page is still an
    # image mapping. Neither API identifies the owner of heap allocations.
    started = time.monotonic()
    def frontend_range():
        mod, = [m for m in modules(handle) if Path(m['path']) == exe]
        return mod['base'], mod['size']
    base, size = frontend_range()
    page_size = mmap.PAGESIZE
    assert page_size == 4096 and c.sizeof(c.c_void_p) == 8
    blocks = resident_page_blocks(handle)
    categories = {key: dict(private=0, shareable=0) for key in
                  ('frontend_image', 'other_image', 'private_allocation', 'mapped_section', 'unknown')}
    region = Region()
    end = 0
    private_count = 0
    last = -1
    for block in sorted(blocks[1:1 + blocks[0]]):
        address = block & ~(page_size - 1)
        assert address > last, 'Duplicate resident page'
        last = address
        if address >= end:
            if k.VirtualQueryEx(handle, address, c.byref(region), c.sizeof(region)) != c.sizeof(region):
                raise c.WinError()
            end = (region.base or 0) + region.size
            assert (region.base or 0) <= address < end
        kind = 'unknown'
        if region.state == 0x1000:  # MEM_COMMIT at the later metadata query
            if region.kind == 0x1000000:
                kind = 'frontend_image' if region.allocation == base and base <= address < base + size else 'other_image'
            else:
                kind = {0x20000: 'private_allocation', 0x40000: 'mapped_section'}.get(region.kind, 'unknown')
        private = not block & 0x100
        private_count += private
        categories[kind]['private' if private else 'shareable'] += page_size
    assert frontend_range() == (base, size)
    total = blocks[0] * page_size
    private = private_count * page_size
    assert sum(v['private'] for v in categories.values()) == private
    assert sum(sum(v.values()) for v in categories.values()) == total
    assert sum(categories['frontend_image'].values()) > 0 and categories['private_allocation']['private'] > 0
    return dict(page_bytes=page_size, image_virtual_bytes=size, total_ws=total, private_ws=private,
                categories=categories, elapsed_seconds=time.monotonic()-started)
