"""Validate native heap-hook metadata in an owned disposable Python process.

This executes only on a dedicated Windows test runner. It does not launch
Nemoterm, sample its working set, use the clipboard or touch a desktop window.
"""
import faulthandler
import hashlib
import json
import subprocess
import sys
from pathlib import Path
import frida
from frida_test_utils import call_frida, detach_session
from owned_job import OwnedJob

root = Path(__file__).resolve().parent.parent
evidence_path = root/'allocation-census-native.json'
evidence = dict(completed=False, scope='Controlled private heap, not terminal memory attribution')
# The pinned binding's script RPC does not honor Cancellable; retain a hard
# controller bound and let the private kill-on-close job drain on expiration.
faulthandler.dump_traceback_later(90, exit=True)


def checkpoint(phase):
    evidence['phase'] = phase
    evidence_path.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    print('Allocation census adapter:', phase, flush=True)


try:
    with OwnedJob() as job:
        process = job.spawn([sys.executable, '-c', 'import time; time.sleep(120)'],
                            creationflags=subprocess.CREATE_NO_WINDOW)
        session = None
        try:
            evidence['pid'] = process.pid
            checkpoint('attach-owned-process')
            session = call_frida('census-attach', frida.attach, process.pid)
            files = ('allocation_census_probe.js', 'allocation_census_selftest.js', 'allocation_census.h')
            evidence['source_sha256'] = {name: hashlib.sha256((root/'tests'/name).read_bytes()).hexdigest()
                                         for name in files}
            source = '\n'.join((root/'tests'/name).read_text(encoding='utf-8') for name in files[:2])
            evidence['results'] = {}
            for retain_live, range_scope, name in (
                    (False, False, 'destroyed-heap'),
                    (True, False, 'live-snapshot'),
                    (True, True, 'reservation-range-snapshot')):
                script = call_frida('census-create-script', session.create_script, source)
                errors = []
                script.on('message', lambda message, data: errors.append(message)
                          if message['type'] == 'error' else None)
                checkpoint(name+'-load')
                call_frida('census-load', script.load)
                checkpoint(name+'-transitions')
                result = script.exports_sync.selftest(process.pid,
                    (root/'tests/allocation_census.h').read_text(encoding='utf-8'), retain_live, range_scope)
                evidence['results'][name] = result
                assert not errors, errors
                assert len(result['checks']) == (8 if range_scope else 6)
                assert result['final']['valid'] and not result['final']['counts']['active']
                assert result['final']['pid'] == process.pid
                entries = result['final']['entries']
                if retain_live:
                    assert len(entries) == 1, entries
                    entry = entries[0]
                    assert entry['address'] == result['expected_address']
                    assert entry['heap'] == result['expected_heap']
                    assert entry['requested_bytes'] == '128'
                    assert int(entry['generation']) > 0 and int(entry['caller'], 16) > 0
                    if range_scope:
                        scope = result['final']['scope']
                        assert 'heap' not in scope and len(scope['ranges']) == 1
                        interval = scope['ranges'][0]
                        assert int(interval['start'], 16) <= int(entry['address'], 16)
                        assert int(entry['address'], 16) + 128 <= int(interval['end'], 16)
                else:
                    assert entries == []
                checkpoint(name+'-unload')
                call_frida('census-unload', script.unload)
            checkpoint('detach-live-observer')
            detach_session(session); session = None
        finally:
            try:
                if session: detach_session(session)
            finally:
                evidence['cleanup'] = job.finish(grace=0)
                process.wait(timeout=5)
        evidence['completed'] = True
        checkpoint('complete')
finally:
    if sys.exc_info()[0]:
        evidence.update(completed=False, error=repr(sys.exc_info()[1]))
    evidence_path.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    faulthandler.cancel_dump_traceback_later()
