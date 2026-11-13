"""Check VM diagnostic completion and scope; this never accepts working set."""
import argparse
import hashlib
import json
import os
from pathlib import Path

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--renderer',choices=('gdi','directx'),required=True)
args=parser.parse_args()
root=Path(__file__).resolve().parent.parent
prefix=f'virtual-tabs-{args.renderer}-left'
load=lambda suffix:json.loads((root/'research'/f'{prefix}-{suffix}.json').read_text(encoding='utf-8'))
observed,census,memory=load('observed'),load('census'),load('memory')
digest=hashlib.sha256(Path(os.environ['NEMOTERM_TEST_EXE']).read_bytes()).hexdigest()
assert observed['executable_sha256']==census['executable_sha256']==digest
assert observed['actual_renderer']=={'gdi':1,'directx':3}[args.renderer]
assert observed['diagnostic_completed'] and not observed['completed'] and 'error' not in observed
assert observed['memory_instrumented'] and observed['memory_acceptance'] is False
assert observed['memory_limit_passed'] is None
assert not observed['owned_job_cleanup']['terminated_remaining']
assert observed['owned_job_cleanup']['after']['active']==0
assert census['completed'] and census['observer_detached'] and not census['observer_errors']
assert census['instrumented'] and census['memory_acceptance'] is False
snapshot=census['snapshot']
assert snapshot['valid'] and not snapshot['active'] and snapshot['overflow']==0 and not snapshot['errors']
assert snapshot['pid']==census['pid']==census['scope']['pid']
assert sum(snapshot['calls'].values())>0
ranges=[(int(r['start'],16),int(r['end'],16)) for r in census['scope']['ranges']]
for sequence,event in enumerate(snapshot['events'],1):
    assert event['sequence']==sequence
    address,size=int(event['address'],16),int(event['bytes'])
    assert event['success']==(event['status']>=0)
    assert any(start<=address<end if size==0 else address<end and address+size>start for start,end in ranges)
assert len(census['reservation_changes'])==len(ranges)
for change in census['reservation_changes']:
    for key in ('before_committed_bytes','observation_start_committed_bytes','after_committed_bytes'):
        assert 0<=change[key]<=change['reserved_bytes'] and change[key]%census['page_size']==0
for name,expected in census['source_sha256'].items():
    assert hashlib.sha256((root/'tests'/name).read_bytes()).hexdigest()==expected,name
assert memory['injected'] and not memory['errors'] and memory['sample_count']>=20
assert all(sample['injected'] for sample in memory['samples'])
summary=dict(diagnostic_valid=True,memory_acceptance=False,renderer=args.renderer,
    executable_sha256=digest,events=len(snapshot['events']),
    events_without_stack=sum(not e['stack'] for e in snapshot['events']),
    reservation_changes=census['reservation_changes'])
(root/'research'/f'{prefix}-validation.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))
