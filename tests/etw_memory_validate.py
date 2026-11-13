"""Bind owned workload metadata to the diagnostic ETW trace artifact."""
import argparse
import hashlib
import json
import os
from pathlib import Path

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--renderer',choices=('gdi','directx'),required=True)
args=parser.parse_args()
root=Path(__file__).resolve().parent.parent
prefix=f'etw-tabs-{args.renderer}-left'
load=lambda suffix:json.loads((root/'research'/f'{prefix}-{suffix}.json').read_text(encoding='utf-8'))
observed,metadata,memory=load('observed'),load('census'),load('memory')
image=Path(os.environ['NEMOTERM_TEST_EXE'])
digest=hashlib.sha256(image.read_bytes()).hexdigest()
assert observed['executable_sha256']==metadata['executable_sha256']==digest
assert observed['actual_renderer']=={'gdi':1,'directx':3}[args.renderer]
assert observed['diagnostic_completed'] and not observed['completed'] and 'error' not in observed
assert observed['memory_limit_passed'] is None and observed['memory_acceptance'] is False
assert not observed['memory_instrumented'] and not memory['injected']
assert memory['kernel_etw_recording'] and memory['diagnostic_only']
assert all(not s['injected'] for s in memory['samples'])
assert not memory['errors'] and memory['sample_count']>=20
assert metadata['completed'] and metadata['phase']=='metadata-closed'
assert metadata['kernel_etw_recording'] and not metadata['injected']
assert not observed['owned_job_cleanup']['terminated_remaining']
assert observed['owned_job_cleanup']['after']['active']==0
assert any(s['phase']=='observe-workload' for s in metadata['stages'])
for name,expected in metadata['source_sha256'].items():
    assert hashlib.sha256((root/'tests'/name).read_bytes()).hexdigest()==expected,name
trace=root/'virtual-allocation.etl'
assert trace.stat().st_size>0
summary=dict(diagnostic_valid=True,memory_acceptance=False,pid=metadata['pid'],
    executable_sha256=digest,renderer=args.renderer,
    etl_bytes=trace.stat().st_size,etl_sha256=hashlib.sha256(trace.read_bytes()).hexdigest(),
    peak_frontend=memory['peaks']['frontend'],reservation_changes=metadata['reservation_changes'],
    event_attribution_complete=False)
(root/'research'/f'{prefix}-validation.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))
