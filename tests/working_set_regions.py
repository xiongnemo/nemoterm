"""Map resident private pages of an owned process without reading page contents."""
from native_test_utils import c,w,k,ps,mmap


class Region(c.Structure):
    _fields_=[('base',c.c_void_p),('allocation',c.c_void_p),('allocation_protect',w.DWORD),
              ('partition',w.WORD),('size',c.c_size_t),('state',w.DWORD),
              ('protect',w.DWORD),('kind',w.DWORD)]

k.VirtualQueryEx.argtypes,k.VirtualQueryEx.restype=[w.HANDLE,c.c_void_p,c.POINTER(Region),c.c_size_t],c.c_size_t
ps.GetMappedFileNameW.argtypes=[w.HANDLE,c.c_void_p,w.LPWSTR,w.DWORD]


def private_page_addresses(handle):
    """Return the resident private page addresses from one working-set query."""
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
    return sorted(int(pages[i+1])&~(mmap.PAGESIZE-1) for i in range(pages[0]) if not pages[i+1]&256)


def reservation_range(handle, allocation):
    """Walk an existing MEM_PRIVATE reservation, including uncommitted regions."""
    cursor=allocation
    for _ in range(4096):
        part=Region()
        if k.VirtualQueryEx(handle,cursor,c.byref(part),c.sizeof(part))!=c.sizeof(part):
            raise c.WinError()
        if part.state==0x10000 or part.allocation!=allocation:
            if cursor==allocation:raise RuntimeError('Selected reservation disappeared')
            return dict(start=hex(allocation),end=hex(cursor))
        if cursor==allocation and part.kind!=0x20000:
            raise RuntimeError('Selected reservation is no longer private')
        following=part.base+part.size
        if following<=cursor:raise RuntimeError('Non-advancing reservation query')
        cursor=following
    raise RuntimeError('Reservation query exceeded region limit')


def reservation_layout(handle, interval):
    """Describe a fixed selected range, including reserved/free pages.

    AllocationBase equality cannot prove identity after an address is reused.
    Keep raw region state so callers do not confuse commitment with residency.
    """
    start,end=int(interval['start'],16),int(interval['end'],16)
    if not 0<start<end:raise ValueError('Invalid selected reservation')
    cursor=start;regions=[];committed=0
    for _ in range(4096):
        part=Region()
        if k.VirtualQueryEx(handle,cursor,c.byref(part),c.sizeof(part))!=c.sizeof(part):
            raise c.WinError()
        following=min(end,part.base+part.size)
        if following<=cursor:raise RuntimeError('Non-advancing layout query')
        allocation=None if part.state==0x10000 else part.allocation
        regions.append(dict(start=hex(cursor),end=hex(following),state=part.state,
            protection=part.protect,kind=part.kind,
            allocation=hex(allocation) if allocation is not None else None))
        if part.state==0x1000 and allocation==start:committed+=following-cursor
        cursor=following
        if cursor==end:
            return dict(**interval,committed_bytes=committed,regions=regions)
    raise RuntimeError('Selected layout exceeded region limit')


def private_regions(handle):
    addresses=private_page_addresses(handle)
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
