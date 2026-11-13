"""Map resident private pages of an owned process without reading page contents."""
from native_test_utils import c,w,k,ps,mmap


class Region(c.Structure):
    _fields_=[('base',c.c_void_p),('allocation',c.c_void_p),('allocation_protect',w.DWORD),
              ('partition',w.WORD),('size',c.c_size_t),('state',w.DWORD),
              ('protect',w.DWORD),('kind',w.DWORD)]

k.VirtualQueryEx.argtypes,k.VirtualQueryEx.restype=[w.HANDLE,c.c_void_p,c.POINTER(Region),c.c_size_t],c.c_size_t
ps.GetMappedFileNameW.argtypes=[w.HANDLE,c.c_void_p,w.LPWSTR,w.DWORD]


def private_regions(handle):
    capacity=65536
    for _ in range(8):
        pages=(c.c_size_t*(capacity+1))()
        if ps.QueryWorkingSet(handle,pages,c.sizeof(pages)):break
        error=k.GetLastError()
        if error!=24:raise c.WinError(error)
        capacity=max(capacity*2,int(pages[0])+4096)
        if capacity>4_194_304:raise RuntimeError('Working-set map exceeds observation limit')
    else:raise RuntimeError('Working set kept growing during region mapping')
    assert pages[0]<=capacity
    addresses=sorted(int(pages[i+1])&~(mmap.PAGESIZE-1) for i in range(pages[0]) if not pages[i+1]&256)
    allocations={};regions=set();current=Region()
    for address in addresses:
        if not current.base or not current.base<=address<current.base+current.size:
            if k.VirtualQueryEx(handle,address,c.byref(current),c.sizeof(current))!=c.sizeof(current):
                raise c.WinError()
        allocation=current.allocation or current.base
        if allocation not in allocations:
            path=c.create_unicode_buffer(32768)
            named=ps.GetMappedFileNameW(handle,allocation,path,len(path))
            allocations[allocation]=dict(allocation=hex(allocation),
                kind={0x20000:'private',0x40000:'mapped',0x1000000:'image'}.get(current.kind,hex(current.kind)),
                path=path.value if named else None,private_ws=0,regions=0,
                committed_regions_with_private_pages=0)
        entry=allocations[allocation];entry['private_ws']+=mmap.PAGESIZE
        if current.base not in regions:
            regions.add(current.base);entry['regions']+=1
            if current.state==0x1000:entry['committed_regions_with_private_pages']+=current.size
    result=sorted(allocations.values(),key=lambda x:x['private_ws'],reverse=True)
    by_kind={}
    for entry in result:by_kind[entry['kind']]=by_kind.get(entry['kind'],0)+entry['private_ws']
    return dict(private_ws=len(addresses)*mmap.PAGESIZE,by_kind=by_kind,allocations=result,
                scope='VirtualQueryEx metadata for resident private pages only; no process memory bytes read. Shared pages and nonresident-only regions are excluded.')
