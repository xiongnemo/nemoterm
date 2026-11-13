"""Correlate allocation metadata with private resident pages, without payloads.

Page coverage is not ownership: a page can contain pre-observation blocks,
allocator overhead, multiple caller modules and unused space.
"""
from bisect import bisect_left


def correlate_pages(entries, addresses, ranges, page_size=4096):
    pages=sorted(addresses)
    if page_size<=0 or page_size & (page_size-1):
        raise ValueError('Page size must be a positive power of two')
    if len(set(pages))!=len(pages) or any(p<0 or p>=2**64 or p%page_size for p in pages):
        raise ValueError('Private pages must be unique aligned addresses')
    intervals=[(int(r['start'],16),int(r['end'],16)) for r in ranges]
    if any(start>=end for start,end in intervals):raise ValueError('Invalid scope')
    blocks=sorted(((int(e['address'],16),int(e['requested_bytes']),e) for e in entries),
                  key=lambda item:item[0])
    previous_end=0;seen=set();touched={};modules={}
    for start,size,entry in blocks:
        end=start+size
        if start in seen or start<previous_end or start<=0 or size<0 or end>2**64:
            raise ValueError('Invalid or overlapping live allocation metadata')
        seen.add(start);previous_end=max(previous_end,end)
        module=entry.get('module') or '<unknown>'
        group=modules.setdefault(module,dict(module=module,allocations=0,
            requested_bytes=0,requested_bytes_on_private_pages=0,pages=set()))
        group['allocations']+=1;group['requested_bytes']+=size
        if not size:continue
        first=bisect_left(pages,start//page_size*page_size)
        last=bisect_left(pages,end)
        for page in pages[first:last]:
            count=min(end,page+page_size)-max(start,page)
            if count<=0:continue
            observation=touched.setdefault(page,dict(modules=set(),requested_bytes=0))
            observation['modules'].add(module);observation['requested_bytes']+=count
            group['pages'].add(page);group['requested_bytes_on_private_pages']+=count
    covered=sum(value['requested_bytes'] for value in touched.values())
    in_scope=lambda p:any(start<=p<end for start,end in intervals)
    scope_pages=sum(in_scope(p) for p in pages)
    categories=dict(single_caller_module=0,mixed_caller_modules=0,
                    unknown_caller_module=0,unobserved=len(pages)-len(touched))
    observed=[]
    for page,value in sorted(touched.items()):
        names=sorted(value['modules'])
        category=('mixed_caller_modules' if len(names)>1 else
                  'unknown_caller_module' if names==['<unknown>'] else 'single_caller_module')
        categories[category]+=1
        observed.append(dict(address=hex(page),modules=names,
            observed_requested_bytes=value['requested_bytes'],
            uncovered_bytes=page_size-value['requested_bytes'],in_selected_scope=in_scope(page)))
    groups=[]
    for group in modules.values():
        group['private_pages_touched']=len(group.pop('pages'));groups.append(group)
    return dict(page_size=page_size,private_ws=len(pages)*page_size,
        selected_scope_private_ws=scope_pages*page_size,
        outside_scope_private_ws=(len(pages)-scope_pages)*page_size,
        observed_requested_bytes_on_private_pages=covered,
        private_bytes_not_covered_by_observed_requests=len(pages)*page_size-covered,
        page_categories=categories,observed_pages=observed,
        caller_modules=sorted(groups,key=lambda g:g['requested_bytes_on_private_pages'],reverse=True),
        limits='Caller module is not resource ownership. Mixed pages and uncovered bytes remain unassigned. Page and allocation snapshots are not atomic; no working-set acceptance is inferred.')
