"""Validate a completed diagnostic capture, without accepting memory usage."""
import argparse
import hashlib
import json
import os
from pathlib import Path

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--renderer',choices=('gdi','directx'),required=True)
args=parser.parse_args()
root=Path(__file__).resolve().parent.parent
prefix=f'allocation-tabs-{args.renderer}-left'
load=lambda suffix:json.loads((root/'research'/f'{prefix}-{suffix}.json').read_text(encoding='utf-8'))
observed,census,memory=load('observed'),load('census'),load('memory')
digest=hashlib.sha256(Path(os.environ['NEMOTERM_TEST_EXE']).read_bytes()).hexdigest()
assert observed['executable_sha256']==census['executable_sha256']==digest
assert observed['actual_renderer']=={'gdi':1,'directx':3}[args.renderer]
assert observed['diagnostic_completed'] and not observed['completed']
assert observed['memory_instrumented'] and observed['memory_acceptance'] is False
assert observed['memory_limit_passed'] is None and 'error' not in observed
assert not observed['owned_job_cleanup']['terminated_remaining']
assert observed['owned_job_cleanup']['after']['active']==0
assert census['completed'] and census['observer_detached'] and not census['observer_errors']
assert census['instrumented'] and census['memory_acceptance'] is False
snapshot=census['snapshot'];counts=snapshot['counts'];entries=snapshot['entries']
assert snapshot['valid'] and counts['errors']==0 and counts['active']==0
assert snapshot['pid']==census['pid']==census['scope']['pid']
assert counts['live_count']==len(entries)>0
assert int(counts['live_requested_bytes'])==sum(int(e['requested_bytes']) for e in entries)
for name,expected in census['source_sha256'].items():
    assert hashlib.sha256((root/'tests'/name).read_bytes()).hexdigest()==expected,name
assert memory['injected'] and not memory['errors'] and memory['sample_count']>=20
assert all(sample['injected'] for sample in memory['samples'])
correlation=census['correlation']
assert correlation['private_ws']==len(census['private_page_addresses'])*correlation['page_size']
assert sum(correlation['page_categories'].values())==len(census['private_page_addresses'])
assert correlation['observed_requested_bytes_on_private_pages']>0
summary=dict(diagnostic_valid=True,memory_acceptance=False,renderer=args.renderer,
    executable_sha256=digest,live_count=counts['live_count'],
    live_requested_bytes=counts['live_requested_bytes'],
    observed_requested_bytes_on_private_pages=correlation['observed_requested_bytes_on_private_pages'],
    page_categories=correlation['page_categories'])
(root/'research'/f'{prefix}-validation.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))
